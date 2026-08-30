/* ==========================================================================
   政策会議ウォッチ (PM-HUB) - Main Application Core Logic
   ========================================================================== */


if (typeof document !== 'undefined') {
document.addEventListener('DOMContentLoaded', async () => {
  let dataLastModified = '';
  try {
    const res = await fetch(`data.json?t=${new Date().getTime()}`);
    if (!res.ok) throw new Error('Failed to load data.json');
    dataLastModified = (res.headers && typeof res.headers.get === 'function') ? (res.headers.get('Last-Modified') || '') : '';
    const data = await res.json();
    window.COUNCILS = (data.councils || []).filter(c => c.status !== 'pending');
    window.MEETINGS = data.meetings || [];
    window.MINISTRIES = data.ministries || {};
    window.CATEGORIES = data.categories || {};
    window.DOC_TYPES = data.docTypes || {};
    window.INITIAL_ALERT_KEYWORDS = data.initialAlertKeywords || [];
    window.LAST_CRAWL_TIME = data.lastCrawlTime || '';
    window.DATA_LAST_MODIFIED = dataLastModified;
  } catch(e) {
    console.error('Data loading error:', e);
    window.COUNCILS = [];
    window.MEETINGS = [];
    window.MINISTRIES = {};
    window.CATEGORIES = {};
    window.DOC_TYPES = {};
    window.INITIAL_ALERT_KEYWORDS = [];
    window.LAST_CRAWL_TIME = '';
    window.DATA_LAST_MODIFIED = '';
  }

  const COUNCILS = window.COUNCILS || [];
  const MEETINGS = window.MEETINGS || [];
  const MINISTRIES = window.MINISTRIES || {};
  const CATEGORIES = window.CATEGORIES || {};
  const DOC_TYPES = window.DOC_TYPES || {};
  const INITIAL_ALERT_KEYWORDS = window.INITIAL_ALERT_KEYWORDS || [];
  const LAST_CRAWL_TIME = window.LAST_CRAWL_TIME || '';
  const DATA_LAST_MODIFIED = window.DATA_LAST_MODIFIED || dataLastModified;

  // --- STATE MANAGEMENT ---
  const state = {
    currentTab: 'main',
    viewMode: 'BY_COUNCIL',
    expandedCouncilIds: new Set(),
    searchQuery: '',
    ministryFilter: 'ALL',
    categoryFilter: 'ALL',
    docTypeFilter: 'ALL',
    dateRangeFilter: 'PAST_YEAR',
    watchlistOnly: false,
    sortBy: 'NEWEST',
    watchedCouncilIds: new Set(JSON.parse(localStorage.getItem('pmhub_watched')) || ['cao-ai-strategy', 'digital-suishin', 'cao-kisei-kaikaku', 'meti-sangyo-kozo', 'mhlw-shakai-hosho', 'mof-zaisei-seido']),
    alertKeywords: JSON.parse(localStorage.getItem('pmhub_keywords')) || (typeof INITIAL_ALERT_KEYWORDS !== 'undefined' ? [...INITIAL_ALERT_KEYWORDS] : ['AI', 'デジタル', '規制改革', '社会保障', 'GX', '経済安全保障']),
    theme: localStorage.getItem('pmhub_theme') || 'light',
    enableAiSummary: localStorage.getItem('pmhub_enable_ai_summary') === 'true', // Default: false (Token cost control)
    activeModalMeeting: null,
    chartsInitialized: false
  };

  // Pre-group meetings by council ID for O(1) lookups
  const meetingsByCouncilMap = new Map();
  MEETINGS.forEach(m => {
    if (!meetingsByCouncilMap.has(m.councilId)) {
      meetingsByCouncilMap.set(m.councilId, []);
    }
    meetingsByCouncilMap.get(m.councilId).push(m);
  });

  const councilsByIdMap = new Map(COUNCILS.map(c => [c.id, c.name]));
  function getCouncilName(meeting) {
    if (!meeting) return '';
    return meeting.councilName || councilsByIdMap.get(meeting.councilId) || meeting.title || '';
  }

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
    watchlistFilterBtn: document.getElementById('watchlistFilterBtn'),
    watchlistFilterBadge: document.getElementById('watchlistFilterBadge'),
    resetFiltersBtn: document.getElementById('resetFiltersBtn'),
    sortBySelect: document.getElementById('sortBySelect'),
    keywordChips: document.querySelectorAll('.keyword-chip'),
    activeFiltersBar: document.getElementById('activeFiltersBar'),
    activeTagsContainer: document.getElementById('activeTagsContainer'),
    resultsCount: document.getElementById('resultsCount'),

    // Mode toggle
    modeByCouncilBtn: document.getElementById('modeByCouncilBtn'),
    modeByDateBtn: document.getElementById('modeByDateBtn'),
    byCouncilView: document.getElementById('byCouncilView'),
    byDateView: document.getElementById('byDateView'),

    // Timeline (BY_DATE mode)
    timelineFeed: document.getElementById('timelineFeed'),
    noResultsState: document.getElementById('noResultsState'),
    noResultsResetBtn: document.getElementById('noResultsResetBtn'),

    // Councils (BY_COUNCIL mode)
    councilsAccordionList: document.getElementById('councilsAccordionList'),

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
    modalSummary: document.getElementById('modalSummary'),
    modalAgenda: document.getElementById('modalAgenda'),
    modalDocsList: document.getElementById('modalDocsList'),
    copyCitationBtn: document.getElementById('copyCitationBtn'),
    modalOfficialLinkBtn: document.getElementById('modalOfficialLinkBtn'),

    // Toast
    toastContainer: document.getElementById('toastContainer')
  };

  // --- DYNAMICALLY POPULATE MINISTRY SELECT ---
  function populateMinistrySelect() {
    if (!el.ministrySelect || !window.MINISTRIES) return;
    el.ministrySelect.innerHTML = '<option value="ALL">すべての省庁・行政機関</option>';
    
    const groups = {
      '府・省': [],
      '庁': [],
      '委員会': [],
      'その他': []
    };
    
    Object.values(window.MINISTRIES).forEach(min => {
      if (min.name.endsWith('府') || min.name.endsWith('省')) {
        groups['府・省'].push(min);
      } else if (min.name.endsWith('庁')) {
        groups['庁'].push(min);
      } else if (min.name.endsWith('委員会')) {
        groups['委員会'].push(min);
      } else {
        groups['その他'].push(min);
      }
    });
    
    ['府・省', '庁', '委員会', 'その他'].forEach(groupName => {
      if (groups[groupName].length === 0) return;
      const optgroup = document.createElement('optgroup');
      optgroup.label = groupName;
      groups[groupName].forEach(min => {
        const opt = document.createElement('option');
        opt.value = min.code;
        opt.textContent = `${min.name} (${min.code})`;
        optgroup.appendChild(opt);
      });
      el.ministrySelect.appendChild(optgroup);
    });
  }
  populateMinistrySelect();


  // --- PRE-COMPUTE MEETING COUNTS ---
  const meetingCounts = {};
  for (let i = 0; i < MEETINGS.length; i++) {
    const cId = MEETINGS[i].councilId;
    meetingCounts[cId] = (meetingCounts[cId] || 0) + 1;
  }

  // --- INITIALIZATION ---
  initTheme();
  updateHeroStats();
  setupEventListeners();
  renderMainView();
  renderWatchlist();

  // --- THEME HANDLER ---
  function initTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    el.body.setAttribute('data-theme', state.theme);
  }

  function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', state.theme);
    el.body.setAttribute('data-theme', state.theme);
    localStorage.setItem('pmhub_theme', state.theme);
    showToast(`テーマを${state.theme === 'dark' ? 'ダーク' : 'ライト'}モードに切り替えました`);
  }

  // --- AI SUMMARY FEATURE FLAG TOGGLE ---
  function toggleAiSummaryFeature() {
    state.enableAiSummary = !state.enableAiSummary;
    localStorage.setItem('pmhub_enable_ai_summary', state.enableAiSummary);
    updateAiSummaryButtonUI();
    renderMainView();
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
      if (typeof LAST_CRAWL_TIME !== 'undefined' && LAST_CRAWL_TIME) {
        el.statLastUpdate.textContent = formatDate(LAST_CRAWL_TIME);
      } else if (typeof DATA_LAST_MODIFIED !== 'undefined' && DATA_LAST_MODIFIED) {
        el.statLastUpdate.textContent = formatDate(DATA_LAST_MODIFIED);
      } else {
        el.statLastUpdate.textContent = '—';
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
      switchTab('main');
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
      renderMainView();
    });

    el.clearSearchBtn.addEventListener('click', () => {
      el.searchInput.value = '';
      state.searchQuery = '';
      el.clearSearchBtn.classList.add('hidden');
      renderMainView();
    });

    el.ministrySelect.addEventListener('change', (e) => {
      state.ministryFilter = e.target.value;
      renderMainView();
    });

    el.categorySelect.addEventListener('change', (e) => {
      state.categoryFilter = e.target.value;
      renderMainView();
    });

    el.docTypeSelect.addEventListener('change', (e) => {
      state.docTypeFilter = e.target.value;
      renderMainView();
    });

    el.dateRangeSelect.addEventListener('change', (e) => {
      state.dateRangeFilter = e.target.value;
      renderMainView();
    });

    el.resetFiltersBtn.addEventListener('click', resetFilters);
    if (el.noResultsResetBtn) el.noResultsResetBtn.addEventListener('click', resetFilters);

    if (el.watchlistFilterBtn) {
      el.watchlistFilterBtn.addEventListener('click', () => {
        state.watchlistOnly = !state.watchlistOnly;
        if (state.watchlistOnly) {
          el.watchlistFilterBtn.classList.add('active');
          if (state.watchedCouncilIds.size === 0) {
            showToast('現在ウォッチ中の会議体がありません。「ウォッチ」ボタンで会議体を登録してください');
          } else {
            showToast(`ウォッチ対象 (${state.watchedCouncilIds.size}件) に絞り込みました ⭐`);
          }
        } else {
          el.watchlistFilterBtn.classList.remove('active');
          showToast('全件表示に戻しました');
        }
        renderMainView();
      });
    }

    el.sortBySelect.addEventListener('change', (e) => {
      state.sortBy = e.target.value;
      renderMainView();
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
        renderMainView();
      });
    });

    // Mode Toggle Buttons
    if (el.modeByCouncilBtn) {
      el.modeByCouncilBtn.addEventListener('click', () => switchViewMode('BY_COUNCIL'));
    }
    if (el.modeByDateBtn) {
      el.modeByDateBtn.addEventListener('click', () => switchViewMode('BY_DATE'));
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

    if (tabName === 'analytics') {
      renderCharts();
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // --- VIEW MODE SWITCHING ---
  function switchViewMode(mode) {
    if (state.viewMode === mode) return;
    state.viewMode = mode;

    // Toggle mode buttons
    if (el.modeByCouncilBtn) el.modeByCouncilBtn.classList.toggle('active', mode === 'BY_COUNCIL');
    if (el.modeByDateBtn) el.modeByDateBtn.classList.toggle('active', mode === 'BY_DATE');

    // Toggle view containers
    if (el.byCouncilView) el.byCouncilView.classList.toggle('hidden', mode !== 'BY_COUNCIL');
    if (el.byDateView) el.byDateView.classList.toggle('hidden', mode !== 'BY_DATE');

    renderMainView();
  }

  // --- MAIN VIEW DISPATCHER ---
  function renderMainView() {
    if (state.viewMode === 'BY_COUNCIL') {
      renderByCouncilView();
    } else {
      renderByDateView();
    }
  }


  // --- FILTER & TIMELINE ENGINE ---
  function resetFilters() {
    state.searchQuery = '';
    state.ministryFilter = 'ALL';
    state.categoryFilter = 'ALL';
    state.docTypeFilter = 'ALL';
    state.dateRangeFilter = 'ALL';
    state.watchlistOnly = false;
    state.sortBy = 'NEWEST';

    el.searchInput.value = '';
    el.clearSearchBtn.classList.add('hidden');
    el.ministrySelect.value = 'ALL';
    el.categorySelect.value = 'ALL';
    el.docTypeSelect.value = 'ALL';
    el.dateRangeSelect.value = 'ALL';
    el.sortBySelect.value = 'NEWEST';

    if (el.watchlistFilterBtn) {
      el.watchlistFilterBtn.classList.remove('active');
    }

    el.keywordChips.forEach(c => c.classList.remove('active'));

    renderMainView();
    showToast('検索・絞り込み条件をクリアしました');
  }

  // --- DATE REFERENCE & PAST YEAR HELPERS ---
  function getReferenceDate() {
    // データの最終クロール日時または現在時刻を基準日とする
    if (typeof LAST_CRAWL_TIME !== 'undefined' && LAST_CRAWL_TIME) {
      const d = new Date(LAST_CRAWL_TIME.replace(/-/g, '/'));
      if (!isNaN(d.getTime())) return d;
    }
    return new Date();
  }

  function getCouncilPastYearCount(council) {
    const councilMeetings = meetingsByCouncilMap.get(council.id) || [];
    const meetingsWithDates = councilMeetings.filter(m => m.date && m.date !== '-');
    if (meetingsWithDates.length > 0) {
      const refDate = getReferenceDate();
      const oneYearAgo = new Date(refDate);
      oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
      let count = 0;
      meetingsWithDates.forEach(m => {
        const d = new Date(m.date.replace(/-/g, '/'));
        if (!isNaN(d.getTime()) && d >= oneYearAgo && d <= refDate) {
          count++;
        }
      });
      return count;
    }
    if (typeof council.pastYearCount === 'number') {
      return council.pastYearCount;
    }
    if (typeof council.pastYearCount === 'string') {
      const parsed = parseInt(council.pastYearCount.replace(/[^0-9]/g, ''), 10);
      return !isNaN(parsed) ? parsed : 0;
    }
    return 0;
  }

  function filterMeetings() {
    return MEETINGS.filter(meeting => {
      // Watchlist filter
      if (state.watchlistOnly && !state.watchedCouncilIds.has(meeting.councilId)) {
        return false;
      }

      // Free word search
      if (state.searchQuery) {
        const queries = state.searchQuery.toLowerCase().split(/[\s　]+/).filter(k => k);
        const c = COUNCILS.find(c => c.id === meeting.councilId);
        const cName = c ? c.name : '';
        
        const match = queries.every(q => {
          const titleMatch = meeting.title.toLowerCase().includes(q);
          const councilMatch = cName.toLowerCase().includes(q);
          const summaryMatch = meeting.summary ? meeting.summary.toLowerCase().includes(q) : false;
          const tagMatch = meeting.tags ? meeting.tags.some(t => t.toLowerCase().includes(q)) : false;
          const agendaMatch = meeting.agenda ? meeting.agenda.some(a => a.toLowerCase().includes(q)) : false;
          const matMatch = meeting.materials ? meeting.materials.some(m => (m.name || '').toLowerCase().includes(q)) : false;
          return titleMatch || councilMatch || summaryMatch || tagMatch || agendaMatch || matMatch;
        });

        if (!match) return false;
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
        if (!meeting.date || meeting.date === '-') return false;
        const meetingDate = new Date(meeting.date.replace(/-/g, '/'));
        if (isNaN(meetingDate.getTime())) return false;
        const refDate = getReferenceDate();
        const diffDays = (refDate - meetingDate) / (1000 * 60 * 60 * 24);

        if (state.dateRangeFilter === '7D' && (diffDays < 0 || diffDays > 7)) return false;
        if (state.dateRangeFilter === '30D' && (diffDays < 0 || diffDays > 30)) return false;
        if (state.dateRangeFilter === '90D' && (diffDays < 0 || diffDays > 90)) return false;
        if (state.dateRangeFilter === 'PAST_YEAR' && (diffDays < 0 || diffDays > 365)) return false;
        if (state.dateRangeFilter === 'YEAR' && getFiscalYear(meetingDate) !== getFiscalYear(refDate)) return false;
        if (state.dateRangeFilter === 'PREV_YEAR' && getFiscalYear(meetingDate) !== (getFiscalYear(refDate) - 1)) return false;
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
      } else if (state.sortBy === 'DOCS_ASC') {
        return (a.item.materials ? a.item.materials.length : 0) - (b.item.materials ? b.item.materials.length : 0);
      } else if (state.sortBy === 'MEETINGS_DESC') {
        return (meetingCounts[b.item.councilId] || 0) - (meetingCounts[a.item.councilId] || 0);
      } else if (state.sortBy === 'MEETINGS_ASC') {
        return (meetingCounts[a.item.councilId] || 0) - (meetingCounts[b.item.councilId] || 0);
      }
      return 0;
    });

    for (let i = 0; i < list.length; i++) {
      list[i] = mapped[i].item;
    }
    return list;
  }

  function renderByDateView() {
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
    if (state.watchlistOnly) activeTags.push({ label: '⭐ ウォッチ対象のみ', key: 'watchlistOnly' });
    if (state.ministryFilter !== 'ALL') activeTags.push({ label: `省庁: ${MINISTRIES[state.ministryFilter]?.name || state.ministryFilter}`, key: 'ministry' });
    if (state.categoryFilter !== 'ALL') activeTags.push({ label: `会議種別: ${CATEGORIES[state.categoryFilter]}`, key: 'category' });
    if (state.docTypeFilter !== 'ALL') activeTags.push({ label: `資料: ${state.docTypeFilter}`, key: 'docType' });
    if (state.dateRangeFilter !== 'ALL') {
      const dateLabels = {
        'PAST_YEAR': '直近1年間',
        'YEAR': '今年度',
        'PREV_YEAR': '昨年度',
        '7D': '直近7日間',
        '30D': '直近30日間',
        '90D': '直近90日間'
      };
      activeTags.push({ label: `期間: ${dateLabels[state.dateRangeFilter] || state.dateRangeFilter}`, key: 'dateRange' });
    }

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

  window.toggleMaterialsAccordion = function(btnOrMeetingId, optionalMeetingId) {
    let accordionEl = null;
    let meetingId = optionalMeetingId;

    if (btnOrMeetingId && typeof btnOrMeetingId === 'object' && btnOrMeetingId.closest) {
      accordionEl = btnOrMeetingId.closest('.materials-accordion');
    } else if (typeof btnOrMeetingId === 'string') {
      meetingId = btnOrMeetingId;
      const content = document.getElementById(`materials-content-${meetingId}`);
      if (content) {
        accordionEl = content.closest('.materials-accordion');
      }
    }

    if (!accordionEl) return;

    const contentEl = accordionEl.querySelector('.materials-collapse-content');
    const arrowEl = accordionEl.querySelector('.toggle-arrow');
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

  function renderMaterialsAccordionHTML(materials, meetingId, officialUrl, label = '資料リストを開く', emptyText = '配付資料はありません') {
    // 一次ソースと同じ場所へのリンクを除外
    const filteredMaterials = (materials || []).filter(mat => {
      if (officialUrl && mat.url === officialUrl) return false;
      if (mat.name && (mat.name.includes('一次ソース') || mat.name.includes('公式ポータル') || mat.name.includes('公式ページ'))) return false;
      return true;
    });

    const hasMaterials = filteredMaterials.length > 0;

    const listItems = hasMaterials ? filteredMaterials.map(mat => {
      const isPrivate = Boolean(mat.isPrivate || mat.type === '非公開' || mat.url === '#');
      const docType = mat.type || (mat.url && mat.url.toLowerCase().endsWith('.pdf') ? 'PDF' : (mat.url ? 'HTML' : 'PDF'));
      const icon = isPrivate ? '🔒' : (docType === 'PDF' ? '📄' : '🌐');
      
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
            ` : (mat.size && mat.size !== 'PDF' && mat.size !== '-' && mat.size !== 'HTML' ? `
              <span class="badge-file-size">${escapeHtml(mat.size)}</span>
            ` : '')}
          </div>
        </li>
      `;
    }).join('') : `
      <li class="material-item-empty">
        <span class="text-muted">${emptyText}</span>
      </li>
    `;

    return `
      <div class="materials-accordion">
        <button class="materials-toggle-btn" onclick="toggleMaterialsAccordion(this, '${meetingId}')" type="button">
          <div class="materials-toggle-left">
            <span>📂 ${escapeHtml(label)}</span>
            <span class="materials-badge-count ${hasMaterials ? '' : 'no-materials'}">${hasMaterials ? `${filteredMaterials.length}件` : '資料なし'}</span>
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
    } else if (key === 'watchlistOnly') {
      state.watchlistOnly = false;
      if (el.watchlistFilterBtn) el.watchlistFilterBtn.classList.remove('active');
    }
    renderMainView();
  };

  function createTimelineCardHTML(meeting) {
    const minInfo = MINISTRIES[meeting.ministry] || { name: meeting.ministry, color: '#3b82f6' };
    const categoryName = CATEGORIES[meeting.category] || meeting.category;

    const docPillsHTML = (meeting.materials || []).map(doc => `
      <a href="${escapeHtml(sanitizeUrl(doc.url))}" target="_blank" rel="noopener noreferrer" class="doc-pill" title="${escapeHtml(doc.name)} (${escapeHtml(doc.size)})">
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
          <span class="card-council-name">
            ${escapeHtml(getCouncilName(meeting))}
            <a href="${escapeHtml(sanitizeUrl(meeting.officialUrl))}" target="_blank" rel="noopener noreferrer" class="inline-link-icon" title="公式トップページを開く" onclick="event.stopPropagation();">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>
          </span>
          <h3 class="card-title">
            ${escapeHtml(meeting.title)}
            <a href="${escapeHtml(sanitizeUrl(meeting.officialUrl))}" target="_blank" rel="noopener noreferrer" class="inline-link-icon" title="一次ソースを開く">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>
          </h3>
        </div>

        ${(state.enableAiSummary && meeting.summary) ? `<div class="card-summary">${escapeHtml(meeting.summary)}</div>` : ''}

        ${renderMaterialsAccordionHTML(meeting.materials, meeting.id, meeting.officialUrl)}

        <div class="card-bottom-row">
          <div class="card-tags">${tagsHTML}</div>
        </div>
      </article>
    `;
  }

  // --- COUNCILS BY-COUNCIL VIEW ENGINE ---
  function getCouncilLatestDate(c) {
    const councilMeetings = (meetingsByCouncilMap.get(c.id) || []).filter(m => m.date && m.date !== '-');
    let dates = councilMeetings.map(m => m.date.replace(/-/g, '/'));
    if (c.latestDate && c.latestDate !== '-') {
      dates.push(c.latestDate.replace(/-/g, '/'));
    }
    if (dates.length === 0) return '-';
    dates.sort((a, b) => b.localeCompare(a));
    return dates[0];
  }

  function formatPastYearCountDisplay(c) {
    if (c.pastYearCount === '-' || c.pastYearCount === null || c.hasTopPageDates === false) {
      return '-';
    }
    const count = getCouncilPastYearCount(c);
    return `${count} 回`;
  }

  function filterCouncils() {
    return COUNCILS.filter(council => {
      if (state.watchlistOnly && !state.watchedCouncilIds.has(council.id)) return false;
      if (state.ministryFilter !== 'ALL' && council.ministry !== state.ministryFilter) return false;
      if (state.categoryFilter !== 'ALL' && council.category !== state.categoryFilter) return false;

      // 開催期間フィルタ（過去1年間に1回以上開催等）
      if (state.dateRangeFilter !== 'ALL') {
        if (state.dateRangeFilter === 'PAST_YEAR') {
          const pastYearCount = getCouncilPastYearCount(council);
          if (pastYearCount <= 0) return false;
        } else {
          const councilMeetings = meetingsByCouncilMap.get(council.id) || [];
          const refDate = getReferenceDate();
          const hasMatchingMeeting = councilMeetings.some(m => {
            if (!m.date || m.date === '-') return false;
            const md = new Date(m.date.replace(/-/g, '/'));
            if (isNaN(md.getTime())) return false;
            const diffDays = (refDate - md) / (1000 * 60 * 60 * 24);
            if (state.dateRangeFilter === '7D') return diffDays >= 0 && diffDays <= 7;
            if (state.dateRangeFilter === '30D') return diffDays >= 0 && diffDays <= 30;
            if (state.dateRangeFilter === '90D') return diffDays >= 0 && diffDays <= 90;
            if (state.dateRangeFilter === 'YEAR') return getFiscalYear(md) === getFiscalYear(refDate);
            if (state.dateRangeFilter === 'PREV_YEAR') return getFiscalYear(md) === (getFiscalYear(refDate) - 1);
            return true;
          });
          if (!hasMatchingMeeting) return false;
        }
      }

      if (state.searchQuery) {
        const queries = state.searchQuery.toLowerCase().split(/[\s　]+/).filter(k => k);
        const minName = MINISTRIES[council.ministry]?.name || '';
        const councilMeetings = meetingsByCouncilMap.get(council.id) || [];
        
        const match = queries.every(q => {
          const matchName = council.name.toLowerCase().includes(q);
          const matchMin = minName.toLowerCase().includes(q);
          const matchDesc = (council.description || '').toLowerCase().includes(q);
          const matchMeetings = councilMeetings.some(m => {
            return m.title.toLowerCase().includes(q) ||
              (m.summary && m.summary.toLowerCase().includes(q)) ||
              (m.tags && m.tags.some(t => t.toLowerCase().includes(q))) ||
              (m.materials && m.materials.some(mat => (mat.name || '').toLowerCase().includes(q)));
          });
          return matchName || matchMin || matchDesc || matchMeetings;
        });

        if (!match) return false;
      }
      // If doc type filter is set, only show councils that have matching meetings
      if (state.docTypeFilter !== 'ALL') {
        const councilMeetings = meetingsByCouncilMap.get(council.id) || [];
        const hasMatch = councilMeetings.some(m => {
          if (state.docTypeFilter === 'MINUTES' && m.hasMinutes) return true;
          if (state.docTypeFilter === 'MATERIALS' && m.materials && m.materials.length > 0) return true;
          if (state.docTypeFilter === 'REPORT' && m.tags && (m.tags.includes('答申') || m.tags.includes('報告書'))) return true;
          return false;
        });
        if (!hasMatch) return false;
      }
      return true;
    });
  }

  function renderByCouncilView() {
    const list = filterCouncils();

    // Sort councils
    const ministryOrderKeys = Object.keys(MINISTRIES);
    list.sort((a, b) => {
      if (state.sortBy === 'NEWEST' || state.sortBy === 'OLDEST') {
        const dateA = getCouncilLatestDate(a);
        const dateB = getCouncilLatestDate(b);
        if (dateA !== '-' && dateB !== '-') {
          const cmp = state.sortBy === 'NEWEST' ? dateB.localeCompare(dateA) : dateA.localeCompare(dateB);
          if (cmp !== 0) return cmp;
        } else if (dateA !== '-') {
          return state.sortBy === 'NEWEST' ? -1 : 1;
        } else if (dateB !== '-') {
          return state.sortBy === 'NEWEST' ? 1 : -1;
        }
        return a.name.localeCompare(b.name, 'ja');
      } else if (state.sortBy === 'DOCS_DESC') {
        const docsA = (meetingsByCouncilMap.get(a.id) || []).reduce((sum, m) => sum + (m.materials ? m.materials.length : 0), 0);
        const docsB = (meetingsByCouncilMap.get(b.id) || []).reduce((sum, m) => sum + (m.materials ? m.materials.length : 0), 0);
        return docsB - docsA;
      } else if (state.sortBy === 'DOCS_ASC') {
        const docsA = (meetingsByCouncilMap.get(a.id) || []).reduce((sum, m) => sum + (m.materials ? m.materials.length : 0), 0);
        const docsB = (meetingsByCouncilMap.get(b.id) || []).reduce((sum, m) => sum + (m.materials ? m.materials.length : 0), 0);
        return docsA - docsB;
      } else if (state.sortBy === 'MEETINGS_DESC') {
        return (meetingCounts[b.id] || 0) - (meetingCounts[a.id] || 0);
      } else if (state.sortBy === 'MEETINGS_ASC') {
        return (meetingCounts[a.id] || 0) - (meetingCounts[b.id] || 0);
      }
      return 0;
    });

    // Render active filter tags
    renderActiveFilterTags(list.length);

    if (!el.councilsAccordionList) return;

    if (list.length === 0) {
      el.councilsAccordionList.innerHTML = `
        <div class="councils-no-results card-glass">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin: 0 auto;">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <h3>該当する会議体が見つかりませんでした</h3>
          <p>開催期間や省庁・会議種別などの絞り込み条件を緩和してお試しください。</p>
        </div>
      `;
      return;
    }

    el.councilsAccordionList.innerHTML = list.map(c => {
      const minInfo = MINISTRIES[c.ministry] || { name: c.ministry };
      const isWatching = state.watchedCouncilIds.has(c.id);
      const pastYearDisplay = formatPastYearCountDisplay(c);
      const latestDateDisplay = getCouncilLatestDate(c);
      const isExpanded = state.expandedCouncilIds.has(c.id);
      let councilMeetings = (meetingsByCouncilMap.get(c.id) || []).slice().sort((a, b) => {
        const da = a.date ? a.date.replace(/-/g, '/') : '';
        const db = b.date ? b.date.replace(/-/g, '/') : '';
        return db.localeCompare(da);
      });

      if (state.searchQuery) {
        const queries = state.searchQuery.toLowerCase().split(/[\s　]+/).filter(k => k);
        const matchCouncil = queries.every(q => 
          c.name.toLowerCase().includes(q) || 
          minInfo.name.toLowerCase().includes(q) || 
          (c.description || '').toLowerCase().includes(q)
        );
        // If the council itself doesn't match all keywords, filter its meetings so we only show the matching ones
        if (!matchCouncil) {
          councilMeetings = councilMeetings.filter(m => {
            return queries.every(q => {
              return m.title.toLowerCase().includes(q) ||
                (m.summary && m.summary.toLowerCase().includes(q)) ||
                (m.tags && m.tags.some(t => t.toLowerCase().includes(q))) ||
                (m.materials && m.materials.some(mat => (mat.name || '').toLowerCase().includes(q)));
            });
          });
        }
      }

      // 会議体カードを展開した際は、その会議体のすべての回の資料を表示（ただし検索キーワードに合致するもののみに絞り込み）
      const meetingsHTML = councilMeetings.length > 0 ? councilMeetings.map(m => `
        <div class="meeting-row">
          <div class="meeting-row-header">
            <span class="meeting-row-title">
              ${escapeHtml(m.title)}
              <a href="${escapeHtml(sanitizeUrl(m.officialUrl))}" target="_blank" rel="noopener noreferrer" class="inline-link-icon" title="一次ソースを開く" onclick="event.stopPropagation();">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </span>
            <span class="meeting-row-date">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              ${formatDate(m.date)}
            </span>
          </div>
          ${(state.enableAiSummary && m.summary) ? `<div class="meeting-row-summary">${escapeHtml(m.summary)}</div>` : ''}
          ${renderMaterialsAccordionHTML(m.materials, m.id, m.officialUrl)}
        </div>
      `).join('') : `<div class="meeting-row-no-data">開催記録はありません</div>`;

      return `
        <div class="council-accordion-card ${isExpanded ? 'expanded' : ''}" id="council-card-${c.id}">
          <div class="council-accordion-header" onclick="toggleCouncilAccordion('${c.id}')">
            <div class="council-header-left">
              <div class="council-header-top-row">
                <span class="badge-ministry ${c.ministry}">${minInfo.name}</span>
                <span class="badge-category">${CATEGORIES[c.category] || c.category}</span>
                <button class="btn-watchlist-toggle ${isWatching ? 'watching' : ''}" style="margin-left: auto;" onclick="event.stopPropagation(); toggleWatchlist('${c.id}')">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="${isWatching ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                  ${isWatching ? 'ウォッチ中' : 'ウォッチ'}
                </button>
              </div>
              <span class="council-header-title">
                ${escapeHtml(c.name)}
                <a href="${escapeHtml(sanitizeUrl(c.officialUrl))}" target="_blank" rel="noopener noreferrer" class="inline-link-icon" title="公式トップページを開く" onclick="event.stopPropagation();">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                </a>
              </span>
              <span class="council-header-desc">${escapeHtml(c.description)}</span>
            </div>
            <div class="council-header-right">
              <div class="council-header-meta">
                <span>最新開催: <strong>${latestDateDisplay}</strong></span>
                <span>全期間: <strong>${meetingCounts[c.id] || 0}回</strong></span>
                <span>過去1年: <strong style="color: var(--accent-secondary);">${pastYearDisplay}</strong></span>
              </div>
              <span class="council-expand-arrow">▼</span>
            </div>
          </div>
          <div class="council-meetings-body">
            ${(Array.isArray(c.materials) && c.materials.length > 0) ? `
              <div class="council-common-materials-wrapper" style="padding: 0.6rem 0.8rem 0.2rem; border-bottom: 1px dashed var(--border-subtle, rgba(255,255,255,0.08));">
                ${renderMaterialsAccordionHTML(c.materials, 'council-' + c.id, c.officialUrl, '会議体の資料リストを開く（構成員名簿・設置根拠等）')}
              </div>
            ` : ''}
            <div class="council-meetings-list">
              ${meetingsHTML}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  window.toggleCouncilAccordion = function(councilId) {
    const cardEl = document.getElementById(`council-card-${councilId}`);
    if (!cardEl) return;
    if (state.expandedCouncilIds.has(councilId)) {
      state.expandedCouncilIds.delete(councilId);
      cardEl.classList.remove('expanded');
    } else {
      state.expandedCouncilIds.add(councilId);
      cardEl.classList.add('expanded');
    }
  };

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
    renderMainView();
    renderWatchlist();
  };


  // --- WATCHLIST & ALERTS VIEW ---
  function renderWatchlist() {
    const watchedList = COUNCILS.filter(c => state.watchedCouncilIds.has(c.id));
    
    if (watchedList.length === 0) {
      el.watchlistItems.innerHTML = `<p class="text-sm">現在登録中の会議体はありません。「会議一覧」の会議体別ビューからお気に入りの会議体を追加してください。</p>`;
      if (el.rssUrlInput) {
        el.rssUrlInput.value = 'https://pm-hub.gov.example/rss/feed.xml';
      }
    } else {
      el.watchlistItems.innerHTML = watchedList.map(c => {
        const minInfo = MINISTRIES[c.ministry] || { name: c.ministry };
        const pastYearDisplay = formatPastYearCountDisplay(c);
        return `
          <div class="watchlist-item-card">
            <div>
              <span class="badge-ministry ${c.ministry}" style="font-size:0.65rem;">${minInfo.name}</span>
              <h4 style="font-weight:700; margin-top:0.3rem;">${escapeHtml(c.name)}</h4>
              <span class="text-sm">過去1年間の開催数: <strong>${pastYearDisplay}</strong></span>
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
  let ministryChartInstance = null;
  let timelineChartInstance = null;

  function renderCharts() {
    if (typeof Chart === 'undefined') return;
    renderMinistryChart();
    initTimelineFiscalYearSelect();
    renderTimelineChart();
    state.chartsInitialized = true;
  }

  window.setMinistryChartMetric = function(metric) {
    state.analyticsMetric = metric;
    // Update button active state
    const btnGroup = document.getElementById('ministryMetricBtnGroup');
    if (btnGroup) {
      btnGroup.querySelectorAll('.btn-chart-metric').forEach(btn => {
        if (btn.getAttribute('data-metric') === metric) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });
    }
    renderMinistryChart();
  };

  window.setAnalyticsFiscalYear = function(fy) {
    state.analyticsFiscalYear = parseInt(fy, 10);
    renderTimelineChart();
  };

  function renderMinistryChart() {
    const canvas = document.getElementById('ministryChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const ctx = canvas.getContext('2d');

    const metric = state.analyticsMetric || 'MEETINGS';
    const minKeys = Object.keys(MINISTRIES);

    let dataValues = [];
    let metricLabel = '';
    let titleText = '';
    let descText = '';

    if (metric === 'COUNCILS') {
      const counts = {};
      minKeys.forEach(k => counts[k] = 0);
      COUNCILS.forEach(c => {
        if (counts[c.ministry] !== undefined) counts[c.ministry]++;
      });
      dataValues = minKeys.map(k => counts[k]);
      metricLabel = '所管会議体数 (件)';
      titleText = '省庁別 所管会議体数';
      descText = '各省庁が所管する会議体マスター数 breakdown';
    } else if (metric === 'MATERIALS') {
      const counts = {};
      minKeys.forEach(k => counts[k] = 0);
      MEETINGS.forEach(m => {
        if (counts[m.ministry] !== undefined) counts[m.ministry] += (m.materials ? m.materials.length : 0);
      });
      COUNCILS.forEach(c => {
        if (counts[c.ministry] !== undefined) counts[c.ministry] += (c.materials ? c.materials.length : 0);
      });
      dataValues = minKeys.map(k => counts[k]);
      metricLabel = '公開資料点数 (点)';
      titleText = '省庁別 公開資料数';
      descText = '各省庁の会議で公開された配付資料・議事録の総点数 breakdown';
    } else {
      // MEETINGS (default)
      const counts = {};
      minKeys.forEach(k => counts[k] = 0);
      MEETINGS.forEach(m => {
        if (counts[m.ministry] !== undefined) counts[m.ministry]++;
      });
      dataValues = minKeys.map(k => counts[k]);
      metricLabel = '会議開催数 (回)';
      titleText = '省庁別 会議の数';
      descText = '各省庁の開催会議数 breakdown';
    }

    const titleEl = document.getElementById('ministryChartTitle');
    const descEl = document.getElementById('ministryChartDesc');
    if (titleEl) titleEl.textContent = titleText;
    if (descEl) descEl.textContent = descText;

    if (ministryChartInstance) {
      try { ministryChartInstance.destroy(); } catch(e) {}
    }

    const palette = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#f43f5e', '#a855f7', '#ec4899', '#84cc16', '#6366f1', '#14b8a6'];

    ministryChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: minKeys.map(k => MINISTRIES[k].name),
        datasets: [{
          label: metricLabel,
          data: dataValues,
          backgroundColor: minKeys.map((_, i) => palette[i % palette.length]),
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                return `${context.dataset.label}: ${context.raw.toLocaleString()}`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#94a3b8' }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#94a3b8', maxRotation: 45, minRotation: 0 }
          }
        }
      }
    });
  }

  function getAvailableFiscalYears() {
    const fySet = new Set();
    MEETINGS.forEach(m => {
      if (m.date && m.date.length >= 7) {
        const parts = m.date.replace(/-/g, '/').split('/');
        const y = parseInt(parts[0], 10);
        const mon = parseInt(parts[1], 10);
        if (!isNaN(y) && !isNaN(mon) && y >= 1990) {
          const fy = mon >= 4 ? y : y - 1;
          fySet.add(fy);
        }
      }
    });
    return Array.from(fySet).sort((a, b) => b - a);
  }

  function initTimelineFiscalYearSelect() {
    const selectEl = document.getElementById('analyticsFiscalYearSelect');
    if (!selectEl) return;

    const fys = getAvailableFiscalYears();
    if (fys.length === 0) {
      fys.push(new Date().getFullYear());
    }

    if (!state.analyticsFiscalYear || !fys.includes(state.analyticsFiscalYear)) {
      state.analyticsFiscalYear = fys[0]; // 最も新しい年度
    }

    selectEl.innerHTML = fys.map(fy => `
      <option value="${fy}" ${fy === state.analyticsFiscalYear ? 'selected' : ''}>
        ${fy}年度 (${fy}年4月〜${fy + 1}年3月)
      </option>
    `).join('');
  }

  function renderTimelineChart() {
    const canvas = document.getElementById('timelineChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const ctx = canvas.getContext('2d');

    const targetFY = state.analyticsFiscalYear || new Date().getFullYear();

    // 4月〜翌年3月 (12ヶ月)
    const monthLabels = ['4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月', '1月', '2月', '3月'];
    const meetingCounts = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const materialCounts = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

    MEETINGS.forEach(m => {
      if (m.date && m.date.length >= 7) {
        const parts = m.date.replace(/-/g, '/').split('/');
        const y = parseInt(parts[0], 10);
        const mon = parseInt(parts[1], 10);
        if (!isNaN(y) && !isNaN(mon)) {
          const fy = mon >= 4 ? y : y - 1;
          if (fy === targetFY) {
            const idx = (mon - 4 + 12) % 12;
            meetingCounts[idx]++;
            materialCounts[idx] += (m.materials ? m.materials.length : 0);
          }
        }
      }
    });

    if (timelineChartInstance) {
      try { timelineChartInstance.destroy(); } catch(e) {}
    }

    timelineChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: monthLabels,
        datasets: [
          {
            label: '公開配布資料数 (点)',
            data: materialCounts,
            borderColor: '#06b6d4',
            backgroundColor: 'rgba(6, 182, 212, 0.12)',
            fill: true,
            tension: 0.35,
            pointBackgroundColor: '#06b6d4',
            pointRadius: 4
          },
          {
            label: '会議開催数 (回)',
            data: meetingCounts,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.12)',
            fill: true,
            tension: 0.35,
            pointBackgroundColor: '#3b82f6',
            pointRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#94a3b8', font: { weight: '600' } }
          },
          tooltip: {
            callbacks: {
              title: function(items) {
                return `${targetFY}年度 ${items[0].label}`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#94a3b8' }
          },
          x: {
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#94a3b8' }
          }
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
    el.modalMinistry.textContent = `所管省庁: ${minInfo.name} (${getCouncilName(meeting)})`;
    el.modalDate.textContent = `📅 開催年月日: ${formatDate(meeting.date)}`;
    
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
        const isPrivate = Boolean(doc.isPrivate || doc.type === '非公開' || doc.url === '#');
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
        const docType = doc.type || (doc.url && doc.url.toLowerCase().endsWith('.pdf') ? 'PDF' : (doc.url ? 'HTML' : 'PDF'));
        const sizeInfo = (doc.size && doc.size !== 'PDF' && doc.size !== '-' && doc.size !== 'HTML') ? `<span class="text-sm" style="display:block; margin-top:0.2rem;">ファイルサイズ: ${escapeHtml(doc.size)}</span>` : '';
        return `
          <a href="${escapeHtml(sanitizeUrl(doc.url))}" target="_blank" rel="noopener noreferrer" class="doc-download-item">
            <div>
              <strong>[${escapeHtml(docType)}] ${escapeHtml(doc.name)}</strong>
              ${sizeInfo}
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
      `"${sanitizeCsvField(getCouncilName(m).replace(/"/g, '""'))}"`,
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

});
}

// Helper function
function getFiscalYear(dateInput) {
  if (!dateInput) return null;
  let date;
  if (dateInput instanceof Date) {
    date = dateInput;
  } else if (typeof dateInput === 'string') {
    date = new Date(dateInput.replace(/-/g, '/'));
  } else {
    return null;
  }
  if (isNaN(date.getTime())) return null;
  const y = date.getFullYear();
  const m = date.getMonth() + 1;
  return m >= 4 ? y : y - 1;
}

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

function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    getFiscalYear,
    formatDate,
    escapeHtml,
    sanitizeUrl,
    capitalize
  };
}
