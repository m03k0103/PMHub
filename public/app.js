/* ==========================================================================
   政策会議ウォッチ (PM-HUB) - Main Application Core Logic
   ========================================================================== */

if (typeof document !== 'undefined') {
document.addEventListener('DOMContentLoaded', () => {
  // --- STATE MANAGEMENT ---
  const state = {
    currentTab: 'timeline',
    searchQuery: '',
    ministryFilter: 'ALL',
    categoryFilter: 'ALL',
    docTypeFilter: 'ALL',
    dateRangeFilter: 'ALL',
    sortBy: 'NEWEST',
    watchedCouncilIds: new Set(JSON.parse(localStorage.getItem('pmhub_watched')) || ['cao-ai-strategy', 'digital-suishin', 'cao-kisei-kaikaku', 'meti-sangyo-kozo', 'mhlw-shakai-hosho', 'mof-zaisei-seido']),
    alertKeywords: JSON.parse(localStorage.getItem('pmhub_keywords')) || [...INITIAL_ALERT_KEYWORDS],
    theme: localStorage.getItem('pmhub_theme') || 'light',
    enableAiSummary: localStorage.getItem('pmhub_enable_ai_summary') === 'true', // Default: false (Token cost control)
    activeModalMeeting: null,
    chartsInitialized: false
  };

  // --- DOM ELEMENTS ---
  const el = {
    body: document.body,
    themeToggleBtn: document.getElementById('themeToggleBtn'),
    aiSummaryToggleBtn: document.getElementById('aiSummaryToggleBtn'),
    aiSummaryToggleLabel: document.getElementById('aiSummaryToggleLabel'),
    exportDataBtn: document.getElementById('exportDataBtn'),
    navTabs: document.querySelectorAll('.nav-tab'),
    viewPanels: document.querySelectorAll('.view-panel'),
    brandLogo: document.getElementById('brandLogo'),

    // Stats
    statTrackedCouncils: document.getElementById('statTrackedCouncils'),
    statTotalMeetings: document.getElementById('statTotalMeetings'),
    statTotalDocs: document.getElementById('statTotalDocs'),
    statLastUpdate: document.getElementById('statLastUpdate'),
    watchlistCount: document.getElementById('watchlistCount'),

    // Filter controls
    searchInput: document.getElementById('searchInput'),
    clearSearchBtn: document.getElementById('clearSearchBtn'),
    ministrySelect: document.getElementById('ministrySelect'),
    categorySelect: document.getElementById('categorySelect'),
    docTypeSelect: document.getElementById('docTypeSelect'),
    dateRangeSelect: document.getElementById('dateRangeSelect'),
    resetFiltersBtn: document.getElementById('resetFiltersBtn'),
    sortBySelect: document.getElementById('sortBySelect'),
    keywordChips: document.querySelectorAll('.keyword-chip'),
    activeFiltersBar: document.getElementById('activeFiltersBar'),
    activeTagsContainer: document.getElementById('activeTagsContainer'),
    resultsCount: document.getElementById('resultsCount'),

    // Timeline
    timelineFeed: document.getElementById('timelineFeed'),
    noResultsState: document.getElementById('noResultsState'),
    noResultsResetBtn: document.getElementById('noResultsResetBtn'),

    // Councils
    councilsGrid: document.getElementById('councilsGrid'),
    councilSearchInput: document.getElementById('councilSearchInput'),
    councilMinistrySelect: document.getElementById('councilMinistrySelect'),
    councilCategorySelect: document.getElementById('councilCategorySelect'),

    // Watchlist
    watchlistActiveCount: document.getElementById('watchlistActiveCount'),
    watchlistItems: document.getElementById('watchlistItems'),
    copyRssBtn: document.getElementById('copyRssBtn'),
    rssUrlInput: document.getElementById('rssUrlInput'),

    // Modal
    documentModalOverlay: document.getElementById('documentModalOverlay'),
    modalCloseBtn: document.getElementById('modalCloseBtn'),
    modalBadges: document.getElementById('modalBadges'),
    modalTitle: document.getElementById('modalTitle'),
    modalMinistry: document.getElementById('modalMinistry'),
    modalDate: document.getElementById('modalDate'),
    modalLocation: document.getElementById('modalLocation'),
    modalSummary: document.getElementById('modalSummary'),
    modalAgenda: document.getElementById('modalAgenda'),
    modalDocsList: document.getElementById('modalDocsList'),
    copyCitationBtn: document.getElementById('copyCitationBtn'),
    modalOfficialLinkBtn: document.getElementById('modalOfficialLinkBtn'),

    // Toast
    toastContainer: document.getElementById('toastContainer')
  };

  // --- INITIALIZATION ---
  initTheme();
  updateHeroStats();
  setupEventListeners();
  renderTimeline();
  renderCouncilsGrid();
  renderWatchlist();

  // --- THEME HANDLER ---
  function initTheme() {
    el.body.setAttribute('data-theme', state.theme);
  }

  function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    el.body.setAttribute('data-theme', state.theme);
    localStorage.setItem('pmhub_theme', state.theme);
    showToast(`テーマを${state.theme === 'dark' ? 'ダーク' : 'ライト'}モードに切り替えました`);
  }

  // --- AI SUMMARY FEATURE FLAG TOGGLE ---
  function toggleAiSummaryFeature() {
    state.enableAiSummary = !state.enableAiSummary;
    localStorage.setItem('pmhub_enable_ai_summary', state.enableAiSummary);
    updateAiSummaryButtonUI();
    renderTimeline();
    showToast(`AI要約表示を ${state.enableAiSummary ? 'ON (有効)' : 'OFF (無効 / Tokenコスト制御)'} に切り替えました`);
  }

  function updateAiSummaryButtonUI() {
    if (!el.aiSummaryToggleLabel) return;
    if (state.enableAiSummary) {
      el.aiSummaryToggleLabel.textContent = 'AI要約: ON';
      el.aiSummaryToggleBtn.style.background = 'rgba(16, 185, 129, 0.2)';
      el.aiSummaryToggleBtn.style.borderColor = '#10b981';
      el.aiSummaryToggleBtn.style.color = '#10b981';
    } else {
      el.aiSummaryToggleLabel.textContent = 'AI要約: OFF';
      el.aiSummaryToggleBtn.style.background = 'rgba(255, 255, 255, 0.08)';
      el.aiSummaryToggleBtn.style.borderColor = 'var(--border-color)';
      el.aiSummaryToggleBtn.style.color = 'var(--text-secondary)';
    }
  }

  // --- HERO STATS ---
  function updateHeroStats() {
    el.statTrackedCouncils.textContent = COUNCILS.length;
    el.statTotalMeetings.textContent = MEETINGS.length;
    
    const totalDocs = MEETINGS.reduce((sum, m) => sum + (m.materials ? m.materials.length : 0), 0);
    el.statTotalDocs.textContent = totalDocs;
    el.watchlistCount.textContent = state.watchedCouncilIds.size;
    if (el.watchlistActiveCount) {
      el.watchlistActiveCount.textContent = state.watchedCouncilIds.size;
    }

    if (el.statLastUpdate) {
      const latestMeeting = MEETINGS.reduce((latest, m) => {
        if (!m.updatedAt) return latest;
        return (!latest || m.updatedAt > latest.updatedAt) ? m : latest;
      }, null);

      if (latestMeeting && latestMeeting.updatedAt) {
        el.statLastUpdate.textContent = formatDate(latestMeeting.updatedAt);
      }
    }
  }

  // --- EVENT LISTENERS ---
  function setupEventListeners() {
    // Theme toggle
    el.themeToggleBtn.addEventListener('click', toggleTheme);

    // AI Summary Feature Flag toggle
    if (el.aiSummaryToggleBtn) {
      updateAiSummaryButtonUI();
      el.aiSummaryToggleBtn.addEventListener('click', toggleAiSummaryFeature);
    }

    // Brand logo reset
    el.brandLogo.addEventListener('click', () => {
      switchTab('timeline');
      resetFilters();
    });

    // Navigation Tabs
    el.navTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const tabName = tab.getAttribute('data-tab');
        switchTab(tabName);
      });
    });

    // Search & Filter listeners
    el.searchInput.addEventListener('input', (e) => {
      state.searchQuery = e.target.value.trim();
      el.clearSearchBtn.classList.toggle('hidden', state.searchQuery === '');
      renderTimeline();
    });

    el.clearSearchBtn.addEventListener('click', () => {
      el.searchInput.value = '';
      state.searchQuery = '';
      el.clearSearchBtn.classList.add('hidden');
      renderTimeline();
    });

    el.ministrySelect.addEventListener('change', (e) => {
      state.ministryFilter = e.target.value;
      renderTimeline();
    });

    el.categorySelect.addEventListener('change', (e) => {
      state.categoryFilter = e.target.value;
      renderTimeline();
    });

    el.docTypeSelect.addEventListener('change', (e) => {
      state.docTypeFilter = e.target.value;
      renderTimeline();
    });

    el.dateRangeSelect.addEventListener('change', (e) => {
      state.dateRangeFilter = e.target.value;
      renderTimeline();
    });

    el.resetFiltersBtn.addEventListener('click', resetFilters);
    el.noResultsResetBtn.addEventListener('click', resetFilters);

    el.sortBySelect.addEventListener('change', (e) => {
      state.sortBy = e.target.value;
      renderTimeline();
    });

    // Quick Keyword Chips
    el.keywordChips.forEach(chip => {
      chip.addEventListener('click', () => {
        const kw = chip.getAttribute('data-keyword');
        if (state.searchQuery === kw) {
          state.searchQuery = '';
          el.searchInput.value = '';
          chip.classList.remove('active');
        } else {
          state.searchQuery = kw;
          el.searchInput.value = kw;
          el.keywordChips.forEach(c => c.classList.remove('active'));
          chip.classList.add('active');
        }
        el.clearSearchBtn.classList.toggle('hidden', state.searchQuery === '');
        renderTimeline();
      });
    });

    // Councils Directory Search & Filters
    if (el.councilSearchInput) {
      el.councilSearchInput.addEventListener('input', () => renderCouncilsGrid());
    }
    if (el.councilMinistrySelect) {
      el.councilMinistrySelect.addEventListener('change', () => renderCouncilsGrid());
    }
    if (el.councilCategorySelect) {
      el.councilCategorySelect.addEventListener('change', () => renderCouncilsGrid());
    }

    // Export Data Button
    el.exportDataBtn.addEventListener('click', exportFilteredData);

    if (el.copyRssBtn) {
      el.copyRssBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(el.rssUrlInput.value);
        showToast('RSS連携URLをクリップボードにコピーしました');
      });
    }

    // Modal close listeners
    el.modalCloseBtn.addEventListener('click', closeModal);
    el.documentModalOverlay.addEventListener('click', (e) => {
      if (e.target === el.documentModalOverlay) closeModal();
    });

    if (el.copyCitationBtn) {
      el.copyCitationBtn.addEventListener('click', copyCitationText);
    }
  }

  // --- TAB SWITCHING ---
  function switchTab(tabName) {
    state.currentTab = tabName;
    
    el.navTabs.forEach(t => {
      t.classList.toggle('active', t.getAttribute('data-tab') === tabName);
    });

    el.viewPanels.forEach(panel => {
      panel.classList.remove('active');
    });

    const activePanel = document.getElementById(`view${capitalize(tabName)}`);
    if (activePanel) {
      activePanel.classList.add('active');
    }

    if (tabName === 'analytics' && !state.chartsInitialized) {
      renderCharts();
      state.chartsInitialized = true;
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // --- FILTER & TIMELINE ENGINE ---
  function resetFilters() {
    state.searchQuery = '';
    state.ministryFilter = 'ALL';
    state.categoryFilter = 'ALL';
    state.docTypeFilter = 'ALL';
    state.dateRangeFilter = 'ALL';
    state.sortBy = 'NEWEST';

    el.searchInput.value = '';
    el.clearSearchBtn.classList.add('hidden');
    el.ministrySelect.value = 'ALL';
    el.categorySelect.value = 'ALL';
    el.docTypeSelect.value = 'ALL';
    el.dateRangeSelect.value = 'ALL';
    el.sortBySelect.value = 'NEWEST';

    el.keywordChips.forEach(c => c.classList.remove('active'));

    renderTimeline();
    showToast('検索・絞り込み条件をクリアしました');
  }

  function filterMeetings() {
    return MEETINGS.filter(meeting => {
      // Free word search
      if (state.searchQuery) {
        const q = state.searchQuery.toLowerCase();
        const titleMatch = meeting.title.toLowerCase().includes(q);
        const councilMatch = meeting.councilName.toLowerCase().includes(q);
        const summaryMatch = meeting.summary ? meeting.summary.toLowerCase().includes(q) : false;
        const tagMatch = meeting.tags ? meeting.tags.some(t => t.toLowerCase().includes(q)) : false;
        const agendaMatch = meeting.agenda ? meeting.agenda.some(a => a.toLowerCase().includes(q)) : false;
        const matMatch = meeting.materials ? meeting.materials.some(m => m.name.toLowerCase().includes(q)) : false;

        if (!titleMatch && !councilMatch && !summaryMatch && !tagMatch && !agendaMatch && !matMatch) {
          return false;
        }
      }

      // Ministry filter
      if (state.ministryFilter !== 'ALL' && meeting.ministry !== state.ministryFilter) {
        return false;
      }

      // Category filter
      if (state.categoryFilter !== 'ALL' && meeting.category !== state.categoryFilter) {
        return false;
      }

      // Doc Type filter
      if (state.docTypeFilter !== 'ALL') {
        if (state.docTypeFilter === 'MINUTES' && !meeting.hasMinutes) return false;
        if (state.docTypeFilter === 'MATERIALS' && (!meeting.materials || meeting.materials.length === 0)) return false;
        if (state.docTypeFilter === 'REPORT' && (!meeting.tags || !meeting.tags.includes('答申') && !meeting.tags.includes('報告書'))) return false;
      }

      // Date Range filter
      if (state.dateRangeFilter !== 'ALL') {
        const meetingDate = new Date(meeting.date.replace(/-/g, '/'));
        const now = new Date('2026/08/01');
        const diffDays = (now - meetingDate) / (1000 * 60 * 60 * 24);

        if (state.dateRangeFilter === '7D' && diffDays > 7) return false;
        if (state.dateRangeFilter === '30D' && diffDays > 30) return false;
        if (state.dateRangeFilter === '90D' && diffDays > 90) return false;
        if (state.dateRangeFilter === 'YEAR' && meetingDate.getFullYear() !== 2026) return false;
      }

      return true;
    });
  }

  function sortMeetings(list) {
    const mapped = list.map(item => ({
      item,
      time: item.date ? new Date(item.date.replace(/-/g, '/')).getTime() : 0
    }));

    mapped.sort((a, b) => {
      if (state.sortBy === 'NEWEST') {
        return b.time - a.time;
      } else if (state.sortBy === 'OLDEST') {
        return a.time - b.time;
      } else if (state.sortBy === 'DOCS_DESC') {
        return (b.item.materials ? b.item.materials.length : 0) - (a.item.materials ? a.item.materials.length : 0);
      }
      return 0;
    });

    for (let i = 0; i < list.length; i++) {
      list[i] = mapped[i].item;
    }
    return list;
  }

  function renderTimeline() {
    const filtered = filterMeetings();
    const sorted = sortMeetings(filtered);

    // Active Filter Tags Bar update
    renderActiveFilterTags(filtered.length);

    if (sorted.length === 0) {
      el.timelineFeed.innerHTML = '';
      el.noResultsState.classList.remove('hidden');
      return;
    }

    el.noResultsState.classList.add('hidden');
    el.timelineFeed.innerHTML = sorted.map(meeting => createTimelineCardHTML(meeting)).join('');
  }

  function renderActiveFilterTags(count) {
    const activeTags = [];

    if (state.searchQuery) activeTags.push({ label: `検索: "${state.searchQuery}"`, key: 'search' });
    if (state.ministryFilter !== 'ALL') activeTags.push({ label: `省庁: ${MINISTRIES[state.ministryFilter]?.name || state.ministryFilter}`, key: 'ministry' });
    if (state.categoryFilter !== 'ALL') activeTags.push({ label: `会議種別: ${CATEGORIES[state.categoryFilter]}`, key: 'category' });
    if (state.docTypeFilter !== 'ALL') activeTags.push({ label: `資料: ${state.docTypeFilter}`, key: 'docType' });
    if (state.dateRangeFilter !== 'ALL') activeTags.push({ label: `期間: ${state.dateRangeFilter}`, key: 'dateRange' });

    if (activeTags.length > 0) {
      el.activeFiltersBar.classList.remove('hidden');
      el.resultsCount.textContent = `ヒット件数: ${count} 件`;
      el.activeTagsContainer.innerHTML = activeTags.map(tag => `
        <span class="active-tag">
          ${escapeHtml(tag.label)}
          <span class="active-tag-remove" onclick="removeFilterTag('${tag.key}')">&times;</span>
        </span>
      `).join('');
    } else {
      el.activeFiltersBar.classList.add('hidden');
    }
  }

  window.toggleMaterialsAccordion = function(meetingId) {
    const contentEl = document.getElementById(`materials-content-${meetingId}`);
    const arrowEl = document.getElementById(`arrow-${meetingId}`);
    if (!contentEl) return;

    const isHidden = contentEl.classList.contains('hidden');
    if (isHidden) {
      contentEl.classList.remove('hidden');
      if (arrowEl) {
        arrowEl.textContent = '▲';
        arrowEl.style.transform = 'rotate(180deg)';
      }
    } else {
      contentEl.classList.add('hidden');
      if (arrowEl) {
        arrowEl.textContent = '▼';
        arrowEl.style.transform = 'rotate(0deg)';
      }
    }
  };

  function renderMaterialsAccordionHTML(materials, meetingId, officialUrl) {
    if (!materials || materials.length === 0) return '';

    // 一次ソースと同じ場所へのリンクを除外
    const filteredMaterials = materials.filter(mat => {
      if (officialUrl && mat.url === officialUrl) return false;
      if (mat.name && (mat.name.includes('一次ソース') || mat.name.includes('公式ポータル') || mat.name.includes('公式ページ'))) return false;
      return true;
    });

    if (filteredMaterials.length === 0) return '';

    const listItems = filteredMaterials.map(mat => {
      const isPrivate = mat.isPrivate || mat.type === '非公開' || mat.url === '#';
      const icon = isPrivate ? '🔒' : (mat.type === 'PDF' ? '📄' : '🌐');
      
      return `
        <li class="material-item-row">
          <div class="material-item-left">
            <span class="material-icon">${icon}</span>
            ${isPrivate ? `
              <span class="material-name-link text-muted" style="text-decoration:none;">${escapeHtml(mat.name)}</span>
            ` : `
              <a href="${escapeHtml(sanitizeUrl(mat.url))}" target="_blank" rel="noopener noreferrer" class="material-name-link">
                ${escapeHtml(mat.name)}
              </a>
            `}
          </div>
          <div class="material-item-right">
            ${isPrivate ? `
              <span class="badge-private">非公開</span>
            ` : `
              <span class="badge-file-size">${mat.size || ''}</span>
            `}
          </div>
        </li>
      `;
    }).join('');

    return `
      <div class="materials-accordion">
        <button class="materials-toggle-btn" onclick="toggleMaterialsAccordion('${meetingId}')" type="button">
          <div class="materials-toggle-left">
            <span>📂 資料リストを開く</span>
            <span class="materials-badge-count">${filteredMaterials.length}件</span>
          </div>
          <span class="toggle-arrow" id="arrow-${meetingId}">▼</span>
        </button>
        <div class="materials-collapse-content hidden" id="materials-content-${meetingId}">
          <ul class="materials-vertical-list">
            ${listItems}
          </ul>
        </div>
      </div>
    `;
  }

  window.removeFilterTag = function(key) {
    if (key === 'search') {
      state.searchQuery = '';
      el.searchInput.value = '';
      el.clearSearchBtn.classList.add('hidden');
      el.keywordChips.forEach(c => c.classList.remove('active'));
    } else if (key === 'ministry') {
      state.ministryFilter = 'ALL';
      el.ministrySelect.value = 'ALL';
    } else if (key === 'category') {
      state.categoryFilter = 'ALL';
      el.categorySelect.value = 'ALL';
    } else if (key === 'docType') {
      state.docTypeFilter = 'ALL';
      el.docTypeSelect.value = 'ALL';
    } else if (key === 'dateRange') {
      state.dateRangeFilter = 'ALL';
      el.dateRangeSelect.value = 'ALL';
    }
    renderTimeline();
  };

  function createTimelineCardHTML(meeting) {
    const minInfo = MINISTRIES[meeting.ministry] || { name: meeting.ministry, color: '#3b82f6' };
    const categoryName = CATEGORIES[meeting.category] || meeting.category;

    const docPillsHTML = (meeting.materials || []).map(doc => `
      <a href="${escapeHtml(sanitizeUrl(doc.url))}" target="_blank" rel="noopener noreferrer" class="doc-pill" title="${escapeHtml(doc.name)} (${doc.size})">
        <span class="doc-type-icon">${doc.type}</span>
      <a href="${doc.url}" target="_blank" rel="noopener noreferrer" class="doc-pill" title="${escapeHtml(doc.name)} (${escapeHtml(doc.size)})">
        <span class="doc-type-icon">${escapeHtml(doc.type)}</span>
        <span>${escapeHtml(doc.name)}</span>
      </a>
    `).join('');

    const tagsHTML = (meeting.tags || []).map(t => `
      <span class="tag-item">#${escapeHtml(t)}</span>
    `).join('');

    return `
      <article class="timeline-card card-glass" id="meeting-${meeting.id}" style="--card-accent-color: ${minInfo.color}">
        <div class="card-top-row">
          <div class="card-badges">
            <span class="badge-ministry ${meeting.ministry}">${minInfo.name}</span>
            <span class="badge-category">${categoryName}</span>
          </div>
          <div class="card-date-badge" title="会議の開催年月日">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            <span>開催日: ${formatDate(meeting.date)}</span>
          </div>
        </div>

        <div class="card-title-block">
          <span class="card-council-name">${escapeHtml(meeting.councilName)}</span>
          <h3 class="card-title">${escapeHtml(meeting.title)}</h3>
        </div>

        ${(state.enableAiSummary && meeting.summary) ? `<div class="card-summary">${escapeHtml(meeting.summary)}</div>` : ''}

        ${renderMaterialsAccordionHTML(meeting.materials, meeting.id, meeting.officialUrl)}

        <div class="card-bottom-row">
          <div class="card-tags">${tagsHTML}</div>
          <div class="card-actions">
            <a href="${escapeHtml(sanitizeUrl(meeting.officialUrl))}" target="_blank" rel="noopener noreferrer" class="btn-primary btn-sm" title="政府公式ページ">
              一次ソース
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>
          </div>
        </div>
      </article>
    `;
  }

  // --- COUNCILS DIRECTORY ENGINE ---
  function renderCouncilsGrid() {
    const searchVal = el.councilSearchInput ? el.councilSearchInput.value.trim().toLowerCase() : '';
    const ministryVal = el.councilMinistrySelect ? el.councilMinistrySelect.value : 'ALL';
    const categoryVal = el.councilCategorySelect ? el.councilCategorySelect.value : 'ALL';

    const list = COUNCILS.filter(council => {
      // 1. Ministry filter
      if (ministryVal !== 'ALL' && council.ministry !== ministryVal) return false;

      // 2. Category filter
      if (categoryVal !== 'ALL' && council.category !== categoryVal) return false;

      // 3. Text search filter
      if (searchVal) {
        const minName = MINISTRIES[council.ministry]?.name || '';
        const matchName = council.name.toLowerCase().includes(searchVal);
        const matchMin = minName.toLowerCase().includes(searchVal);
        const matchDesc = council.description.toLowerCase().includes(searchVal);
        if (!matchName && !matchMin && !matchDesc) return false;
      }

      return true;
    });

    if (list.length === 0) {
      el.councilsGrid.innerHTML = `
        <div class="no-results card-glass" style="grid-column: 1 / -1; text-align: center; padding: 2.5rem 1rem;">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin: 0 auto 0.75rem;">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <h3 style="font-weight: 700; color: var(--text-primary);">該当する会議体が見つかりませんでした</h3>
          <p class="text-sm" style="margin-top: 0.4rem; color: var(--text-muted);">省庁・会議種別などの絞り込み条件を緩和してお試しください。</p>
        </div>
      `;
      return;
    }

    el.councilsGrid.innerHTML = list.map(c => {
      const minInfo = MINISTRIES[c.ministry] || { name: c.ministry };
      const isWatching = state.watchedCouncilIds.has(c.id);
      const pastYearCount = c.pastYearCount || MEETINGS.filter(m => m.councilId === c.id).length || 5;

      return `
        <div class="council-card card-glass">
          <div>
            <div class="council-card-header">
              <span class="badge-ministry ${c.ministry}">${minInfo.name}</span>
              <button class="btn-watchlist-toggle ${isWatching ? 'watching' : ''}" onclick="toggleWatchlist('${c.id}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="${isWatching ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                ${isWatching ? 'ウォッチ中' : 'ウォッチ追跡'}
              </button>
            </div>
            <h3 class="council-card-title" style="margin-top: 0.6rem;">${escapeHtml(c.name)}</h3>
            <p class="text-sm" style="margin-top: 0.5rem; line-height: 1.5;">${escapeHtml(c.description)}</p>
          </div>
          <div class="council-meta" style="margin-top: 1rem; border-top: 1px solid var(--border-color); padding-top: 0.75rem;">
            <span>過去1年間の開催数: <strong style="color: var(--accent-secondary);">${pastYearCount} 回</strong></span>
            <a href="${escapeHtml(sanitizeUrl(c.officialUrl))}" target="_blank" rel="noopener noreferrer" class="text-accent text-sm" style="display:inline-flex; align-items:center; gap:0.2rem; margin-top:0.2rem;">
              公式トップページ ↗
            </a>
          </div>
        </div>
      `;
    }).join('');
  }

  window.toggleWatchlist = function(councilId) {
    const council = COUNCILS.find(c => c.id === councilId);
    if (state.watchedCouncilIds.has(councilId)) {
      state.watchedCouncilIds.delete(councilId);
      showToast(`「${council?.name}」をウォッチリストから解除しました`);
    } else {
      state.watchedCouncilIds.add(councilId);
      showToast(`「${council?.name}」をウォッチリストに追加しました ⭐`);
    }

    localStorage.setItem('pmhub_watched', JSON.stringify(Array.from(state.watchedCouncilIds)));
    updateHeroStats();
    renderCouncilsGrid();
    renderWatchlist();
  };

  // --- WATCHLIST & ALERTS VIEW ---
  function renderWatchlist() {
    const watchedList = COUNCILS.filter(c => state.watchedCouncilIds.has(c.id));
    
    if (watchedList.length === 0) {
      el.watchlistItems.innerHTML = `<p class="text-sm">現在登録中の会議体はありません。「会議体一覧」タブからお気に入りの会議体を追加してください。</p>`;
      if (el.rssUrlInput) {
        el.rssUrlInput.value = 'https://pm-hub.gov.example/rss/feed.xml';
      }
    } else {
      el.watchlistItems.innerHTML = watchedList.map(c => {
        const minInfo = MINISTRIES[c.ministry] || { name: c.ministry };
        const pastYearCount = c.pastYearCount || MEETINGS.filter(m => m.councilId === c.id).length || 5;
        return `
          <div class="watchlist-item-card">
            <div>
              <span class="badge-ministry ${c.ministry}" style="font-size:0.65rem;">${minInfo.name}</span>
              <h4 style="font-weight:700; margin-top:0.3rem;">${escapeHtml(c.name)}</h4>
              <span class="text-sm">過去1年間の開催数: <strong>${pastYearCount} 回</strong></span>
            </div>
            <button class="btn-secondary btn-sm" onclick="toggleWatchlist('${c.id}')">解除</button>
          </div>
        `;
      }).join('');

      if (el.rssUrlInput) {
        const idsArray = Array.from(state.watchedCouncilIds).join(',');
        el.rssUrlInput.value = `https://pm-hub.gov.example/rss/feed.xml?ids=${encodeURIComponent(idsArray)}`;
      }
    }
  }

  // --- ANALYTICS CHARTS (CHART.JS) ---
  function renderCharts() {
    if (typeof Chart === 'undefined') return;

    // 1. Ministry Meetings Bar Chart
    const ministryCounts = {};
    Object.keys(MINISTRIES).forEach(k => ministryCounts[k] = 0);
    MEETINGS.forEach(m => {
      if (ministryCounts[m.ministry] !== undefined) {
        ministryCounts[m.ministry]++;
      }
    });

    const ctx1 = document.getElementById('ministryChart').getContext('2d');
    new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: Object.keys(MINISTRIES).map(k => MINISTRIES[k].name),
        datasets: [{
          label: '会議開催数 (件)',
          data: Object.keys(MINISTRIES).map(k => ministryCounts[k]),
          backgroundColor: ['#a855f7', '#06b6d4', '#10b981', '#f43f5e', '#f59e0b', '#3b82f6', '#ec4899', '#84cc16'],
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
          x: { grid: { display: false } }
        }
      }
    });



    // 3. Monthly Timeline Activity Line Chart
    const ctx3 = document.getElementById('timelineChart').getContext('2d');
    new Chart(ctx3, {
      type: 'line',
      data: {
        labels: ['2026年2月', '2026年3月', '2026年4月', '2026年5月', '2026年6月', '2026年7月'],
        datasets: [
          {
            label: '公開配布資料数',
            data: [12, 19, 25, 22, 31, 38],
            borderColor: '#06b6d4',
            backgroundColor: 'rgba(6, 182, 212, 0.1)',
            fill: true,
            tension: 0.3
          },
          {
            label: '会議開催数',
            data: [4, 6, 8, 7, 10, 12],
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: true,
            tension: 0.3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
          x: { grid: { color: 'rgba(255,255,255,0.05)' } }
        }
      }
    });
  }

  // --- MODAL DIALOG ENGINE ---
  function openModal(meeting) {
    state.activeModalMeeting = meeting;
    const minInfo = MINISTRIES[meeting.ministry] || { name: meeting.ministry };

    el.modalBadges.innerHTML = `
      <span class="badge-ministry ${meeting.ministry}">${minInfo.name}</span>
      <span class="badge-category">${CATEGORIES[meeting.category]}</span>
    `;

    el.modalTitle.textContent = meeting.title;
    el.modalMinistry.textContent = `所管省庁: ${minInfo.name} (${meeting.councilName})`;
    el.modalDate.textContent = `📅 開催年月日: ${formatDate(meeting.date)}`;
    el.modalLocation.textContent = `📍 開催場所: ${meeting.location || 'オンライン / 講堂'}`;
    
    // AI Summary Feature Flag check
    const summaryBox = document.querySelector('.summary-box');
    if (summaryBox) {
      if (state.enableAiSummary) {
        summaryBox.style.display = 'block';
        el.modalSummary.textContent = meeting.summary || '詳細要約準備中';
      } else {
        summaryBox.style.display = 'none';
      }
    }

    // Agenda
    if (meeting.agenda && meeting.agenda.length > 0) {
      el.modalAgenda.innerHTML = meeting.agenda.map(item => `<li>${escapeHtml(item)}</li>`).join('');
    } else {
      el.modalAgenda.innerHTML = '<li>議題情報は登録されていません。</li>';
    }

    // Documents
    if (meeting.materials && meeting.materials.length > 0) {
      el.modalDocsList.innerHTML = meeting.materials.map(doc => {
        const isPrivate = doc.isPrivate || doc.type === '非公開' || doc.url === '#';
        if (isPrivate) {
          return `
            <div class="doc-download-item" style="opacity: 0.75; cursor: default;">
              <div>
                <strong>[非公開] ${escapeHtml(doc.name)}</strong>
                <span class="text-sm text-muted" style="display:block; margin-top:0.2rem;">※ 提出資料非公開</span>
              </div>
              <span class="badge-private">非公開</span>
            </div>
          `;
        }
        return `
          <a href="${escapeHtml(sanitizeUrl(doc.url))}" target="_blank" rel="noopener noreferrer" class="doc-download-item">
            <div>
              <strong>[${escapeHtml(doc.type)}] ${escapeHtml(doc.name)}</strong>
              <span class="text-sm" style="display:block; margin-top:0.2rem;">ファイルサイズ: ${escapeHtml(doc.size)}</span>
            </div>
            <span class="text-accent text-sm">PDF/HTMLを開く ↗</span>
          </a>
        `;
      }).join('');
    } else {
      el.modalDocsList.innerHTML = '<p class="text-sm">資料リンクは現在登録されていません。</p>';
    }

    el.modalOfficialLinkBtn.href = sanitizeUrl(meeting.officialUrl);
    el.documentModalOverlay.classList.remove('hidden');
  }

  function closeModal() {
    el.documentModalOverlay.classList.add('hidden');
    state.activeModalMeeting = null;
  }

  function copyCitationText() {
    if (!state.activeModalMeeting) return;
    const m = state.activeModalMeeting;
    const minName = MINISTRIES[m.ministry]?.name || m.ministry;
    const citation = `${minName}「${m.title}」（${formatDate(m.date)}開催）政策会議ウォッチ 参照: ${m.officialUrl}`;
    
    navigator.clipboard.writeText(citation);
    showToast('引用形式のテキストをクリップボードにコピーしました 📋');
  }

  // --- DATA EXPORT ENGINE ---

  // Helper to prevent CSV Injection (Formula Injection)
  function sanitizeCsvField(field) {
    if (typeof field !== 'string') return field;
    if (field.startsWith('=') || field.startsWith('+') || field.startsWith('-') || field.startsWith('@')) {
      return "'" + field;
    }
    return field;
  }

  function exportFilteredData() {
    const list = filterMeetings();
    
    // 1. Export JSON
    const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(list, null, 2));
    const jsonAnchor = document.createElement('a');
    jsonAnchor.setAttribute("href", jsonStr);
    jsonAnchor.setAttribute("download", `pmhub-meetings-${new Date().toISOString().slice(0,10)}.json`);
    document.body.appendChild(jsonAnchor);
    jsonAnchor.click();
    jsonAnchor.remove();

    // 2. Export CSV (with UTF-8 BOM for Excel compatibility)
    const csvHeader = ["開催日", "所管省庁", "会議体名", "会議名", "資料件数", "一次ソースURL", "要約"];
    const csvRows = list.map(m => [
      `"${sanitizeCsvField(m.date)}"`,
      `"${sanitizeCsvField(MINISTRIES[m.ministry]?.name || m.ministry)}"`,
      `"${sanitizeCsvField(m.councilName.replace(/"/g, '""'))}"`,
      `"${sanitizeCsvField(m.title.replace(/"/g, '""'))}"`,
      `"${sanitizeCsvField(m.materials ? String(m.materials.length) : '0')}"`,
      `"${sanitizeCsvField(m.officialUrl)}"`,
      `"${sanitizeCsvField((m.summary || '').replace(/"/g, '""'))}"`
    ].join(','));

    const csvContent = "\uFEFF" + [csvHeader.join(','), ...csvRows].join('\n');
    const csvBlob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const csvUrl = URL.createObjectURL(csvBlob);
    const csvAnchor = document.createElement('a');
    csvAnchor.setAttribute("href", csvUrl);
    csvAnchor.setAttribute("download", `pmhub-meetings-${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(csvAnchor);
    csvAnchor.click();
    csvAnchor.remove();

    showToast(`検索結果 ${list.length} 件を JSON 及び CSV (Excel対応) で出力しました 📊`);
  }



  // --- TOAST NOTIFICATIONS ---
  function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast-message';
    toast.textContent = message;
    el.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = '0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 2800);
  }

  // Helper function
  function formatDate(str) {
    if (!str) return '';
    return str.replace(/-/g, '/');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function sanitizeUrl(url) {
    if (!url) return '#';
    url = String(url).trim();
    // Remove control characters to prevent bypasses
    const sanitizedUrl = url.replace(/[\u0000-\u001F\u007F-\u009F]/g, '');
    const lowerUrl = sanitizedUrl.toLowerCase();

    // Whitelist safe protocols and relative paths
    if (lowerUrl.startsWith('http://') ||
        lowerUrl.startsWith('https://') ||
        lowerUrl.startsWith('/') ||
        lowerUrl.startsWith('.') ||
        lowerUrl.startsWith('?') ||
        lowerUrl.startsWith('#')) {
      return sanitizedUrl;
    }
    return '#';
  }
});
}

// --- UTILS EXPORT FOR TESTING ---
function capitalize(str) {
  if (typeof str !== 'string' || !str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { capitalize };
}
