  // ─── Utility & Sanitization Helpers (XSS Protection) ───
  function sanitizeUrl(url) {
    if (!url) return '#';
    url = String(url).trim();
    const sanitizedUrl = url.replace(/[\u0000-\u001F\u007F-\u009F]/g, '');
    const lowerUrl = sanitizedUrl.toLowerCase();
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
  window.sanitizeUrl = sanitizeUrl;

  function escHtml(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
  window.escHtml = escHtml;

  function escAttr(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
  window.escAttr = escAttr;

  // ─── Global Navigation Engine ───
  window.switchTab = function(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    const content = document.getElementById(tabId);
    if (content) content.classList.add('active');

    let targetBtn = btn;
    if (!targetBtn) {
      document.querySelectorAll('.tab-btn').forEach(b => {
        const attr = b.getAttribute('onclick') || '';
        if (attr.includes(tabId)) {
          targetBtn = b;
        }
      });
    }
    if (targetBtn) targetBtn.classList.add('active');
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, null, `#${tabId.replace('tab-', '')}`);
    }

    // タブ表示切替時に各画面のデータ描画処理を実行
    try {
      if (tabId === 'tab-councils') {
        if (typeof window.renderCards === 'function') window.renderCards();
      } else if (tabId === 'tab-meetings') {
        if (typeof window.renderMeetingsList === 'function') window.renderMeetingsList();
      } else if (tabId === 'tab-rejected') {
        if (typeof window.renderRejectedList === 'function') window.renderRejectedList();
      } else if (tabId === 'tab-ministries') {
        if (typeof window.renderMinistryList === 'function') window.renderMinistryList();
      }
    } catch(e) {
      console.warn('Tab render notice:', e);
    }
  };
  const switchTab = window.switchTab;

  // ─── 0. Backup & Rollback Manager (Global scope definition) ───
  window.loadBackupStatus = async function() {
    const countBadge = document.getElementById('adminBackupCountBadge');
    const timeBadge = document.getElementById('adminLatestBackupTime');
    const rollbackBtn = document.getElementById('adminRollbackBtn');
    try {
      const res = await fetch('/api/backups');
      if (!res.ok) return;
      const data = await res.json();
      const backups = data.backups || [];
      if (countBadge) countBadge.textContent = `${backups.length} 世代保持中`;
      if (backups.length > 0) {
        if (timeBadge) timeBadge.textContent = `${backups[0].createdAt} (${backups[0].filename})`;
        if (rollbackBtn) {
          rollbackBtn.disabled = false;
          rollbackBtn.title = `直前のバックアップ (${backups[0].filename}) にロールバックします`;
        }
      } else {
        if (timeBadge) timeBadge.textContent = 'なし (初期状態)';
        if (rollbackBtn) rollbackBtn.disabled = true;
      }
    } catch (e) {
      console.warn('Failed to load backup status:', e);
      if (countBadge) countBadge.textContent = '取得エラー';
    }
  };

  window.rollbackDataJson = async function() {
    const rollbackBtn = document.getElementById('adminRollbackBtn');
    if (!confirm('【確認】直前世代（1世代前）のバックアップファイルから docs/data.json をロールバック（復元）しますか？\n\n※ 誤操作防止のため、現在の状態も自動で退避バックアップされます。')) {
      return;
    }

    if (rollbackBtn) {
      rollbackBtn.disabled = true;
      rollbackBtn.textContent = '⏳ ロールバック復元中…';
    }

    try {
      const res = await fetch('/api/rollback-data', { method: 'POST' });
      const data = await res.json();
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || `HTTP ${res.status}`);
      }

      alert(`✅ ロールバック成功！\n\n${data.message}\n・会議体数: ${data.councilsCount} 件\n・会議データ数: ${data.meetingsCount} 件\n・最終クロール日時: ${data.lastCrawlTime}`);
      
      if (window.loadBackupStatus) window.loadBackupStatus();
      if (typeof updateDataJsonInspector === 'function') updateDataJsonInspector();
      if (typeof loadAndRenderAllData === 'function') {
        await loadAndRenderAllData();
      } else {
        location.reload();
      }
    } catch (e) {
      alert(`❌ ロールバック失敗: ${e.message || e}`);
    } finally {
      if (rollbackBtn) {
        rollbackBtn.disabled = false;
        rollbackBtn.textContent = '⏮ 1世代前のバックアップにロールバック';
      }
    }
  };

  // ─── 1. Council Discovery Engine (Global scope definition) ───
  let isRunningDiscovery = false;
    window.startDiscovery = async function() {
      if (isRunningDiscovery) return;
      isRunningDiscovery = true;
      alert('【審議会ディスカバリー開始】全省庁の審議会等ページURLへの検出巡回を開始します。\n（実際のページへHTTPアクセスしてリダイレクト後の最終正規URLを検証します）');

      const btn = document.getElementById('btnStartDiscovery');
      const fillEl = document.getElementById('discoveryProgressFill');
      const logsEl = document.getElementById('discoveryTerminalLogs');
      const summaryEl = document.getElementById('discoverySummaryBar');
      const resultCountEl = document.getElementById('discoveryResultCount');

      if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ 検出巡回中 (アクセス検証中)…';
      }

      if (fillEl) fillEl.style.width = '0%';
      if (logsEl) logsEl.innerHTML = '';
      if (summaryEl) summaryEl.style.display = 'none';

      const logLine = (msg, time = new Date().toTimeString().slice(0,8)) => {
        if (!logsEl) return;
        const line = document.createElement('div');
        line.className = 'crawler-log-line';
        line.innerHTML = `<span class="crawler-log-time" style="color:#60a5fa;">[${time}]</span> <span>${msg}</span>`;
        logsEl.appendChild(line);
        logsEl.scrollTop = logsEl.scrollHeight;
      };

      logLine('全省庁の審議会等一覧ページ (councilsUrls) の巡回を開始します...');

      try {
        if (fillEl) fillEl.style.width = '5%';
        logLine('サーバー側ディスカバリーエンジン (discover_councils.py) を開始中...');

        const startRes = await fetch('/api/run-discovery', { method: 'POST' });
        if (!startRes.ok) {
          throw new Error('ディスカバリー開始リクエストに失敗しました');
        }

        let lastLogId = 0;
        let isDone = false;

        while (!isDone) {
          await new Promise(r => setTimeout(r, 600));
          try {
            const statusRes = await fetch(`/api/discovery-status?since_id=${lastLogId}`);
            if (statusRes.ok) {
              const statusData = await statusRes.json();

              // プログレスバー更新
              if (fillEl && statusData.progress !== undefined) {
                fillEl.style.width = `${Math.max(5, statusData.progress)}%`;
              }

              // 新着ログを出力
              if (statusData.logs && statusData.logs.length > 0) {
                statusData.logs.forEach(item => {
                  const lineText = (typeof item === 'object' && item.text) ? item.text : item;
                  logLine(lineText);
                  if (typeof item === 'object' && item.id) {
                    lastLogId = Math.max(lastLogId, item.id);
                  }
                });
                if (statusData.latest_log_id) {
                  lastLogId = Math.max(lastLogId, statusData.latest_log_id);
                }
              }

              // ボタンテキストに進捗を表示
              if (btn && statusData.current_idx && statusData.total_ministries) {
                btn.textContent = `⏳ 検出巡回中 [${statusData.current_idx}/${statusData.total_ministries} 省庁] (検出: ${statusData.discovered_count}件)…`;
              }

              // 完了判定
              if (!statusData.running) {
                isDone = true;
                if (statusData.error) {
                  logLine(`[ERROR] ディスカバリーエラー: ${statusData.error}`);
                } else {
                  if (fillEl) fillEl.style.width = '100%';
                  const discovered = statusData.result || [];
                  logLine(`✅ ディスカバリー完了: 合計 ${discovered.length} 件の新規会議体（正規URL）を検出・保存しました`);

                  const addedCount = (window.integrateDiscoveredCouncils || integrateDiscoveredCouncils)(discovered);
                  if (summaryEl) summaryEl.style.display = 'flex';
                  if (resultCountEl) resultCountEl.textContent = `✨ 新規会議体 ${discovered.length} 件を検出しました！（未レビューとして追加: ${addedCount} 件）`;
                }
                return;
              }
            }
          } catch (pollErr) {
            console.warn('Status poll error:', pollErr);
          }
        }
      } catch(e) {
        logLine(`[WARN] ローカルサーバーAPI接続エラー: ${e}`);
      } finally {
        isRunningDiscovery = false;
        if (btn) {
          btn.disabled = false;
          btn.textContent = '⚡ 実行';
        }
      }

      // 2. Client-side simulation fallback if server is not running
      logLine('[WARN] ブラウザ直接巡回シミュレーションを実行します...');
      const targetMinistries = Object.keys(ministries).filter(k => ministries[k].hasCouncils !== false && ministries[k].councilsUrls && ministries[k].councilsUrls.length);
      let idx = 0;
      const interval = setInterval(() => {
        if (idx < targetMinistries.length) {
          const code = targetMinistries[idx];
          const m = ministries[code];
          idx++;
          const pct = Math.round((idx / targetMinistries.length) * 100);
          if (fillEl) fillEl.style.width = pct + '%';
          logLine(`[${pct}%] 省庁ページ巡回完了: ${m.name} (${code}) - 審議会URL ${m.councilsUrls.length} 件`);
        } else {
          clearInterval(interval);
          if (fillEl) fillEl.style.width = '100%';
          logLine('全省庁の審議会一覧巡回が完了しました。');
          if (btn) {
            btn.disabled = false;
            btn.textContent = '⚡ 実行';
          }
        }
      }, 80);
    };

  // ─── 2. Meeting Crawler Engine (Global scope definition) ───
  let isRunningMeetingCrawl = false;

  window.stopMeetingCrawl = async function() {
    const stopBtn = document.getElementById('adminStopCrawlBtn');
    if (stopBtn) {
      stopBtn.disabled = true;
      stopBtn.textContent = '🛑 停止処理中…';
    }
    try {
      const res = await fetch('/api/stop-crawler', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      console.log('Stop response:', data);
    } catch (e) {
      alert(`停止リクエスト失敗: ${e.message || e}`);
      if (stopBtn) stopBtn.disabled = false;
    }
  };

  window.startMeetingCrawl = async function() {
    if (isRunningMeetingCrawl) return;
    isRunningMeetingCrawl = true;

    const btn = document.getElementById('adminStartCrawlBtn');
    const stopBtn = document.getElementById('adminStopCrawlBtn');
    const logInfo = document.getElementById('adminCrawlerLogFileInfo');
    const logPath = document.getElementById('adminCrawlerLogFilePath');
    const progressFill = document.getElementById('adminProgressFill');
    const logs = document.getElementById('adminTerminalLogs');

    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ クロール中…';
    }
    if (stopBtn) {
      stopBtn.style.display = 'inline-block';
      stopBtn.disabled = false;
      stopBtn.textContent = '🛑 クロール停止';
    }
    if (progressFill) progressFill.style.width = '0%';
    if (logs) logs.innerHTML = '';
    if (logInfo) logInfo.style.display = 'none';

    const logLine = (msg, time = new Date().toTimeString().slice(0,8)) => {
      if (!logs) return;
      const line = document.createElement('div');
      line.className = 'crawler-log-line';
      line.innerHTML = `<span class="crawler-log-time" style="color: #60a5fa;">[${time}]</span> <span>${msg}</span>`;
      logs.appendChild(line);
      logs.scrollTop = logs.scrollHeight;
    };

    logLine('バックエンドの Python クローラー (admin/crawler.py) を起動しています...');

    try {
      // 1. サーバーAPIにクロール開始を要求
      const res = await fetch('/api/run-crawler', { method: 'POST' });
      if (!res.ok) {
        throw new Error(`サーバーエラー (HTTP ${res.status}): ローカルサーバーが起動しているか確認してください。`);
      }
      const initData = await res.json();
      logLine(`サーバー応答: ${initData.message || 'クロール開始'}`);

      // 2. ポーリングループで進捗・ログをリアルタイム受信
      let lastLogId = 0;
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/crawler-status?since_id=${lastLogId}`);
          if (!statusRes.ok) return;
          const data = await statusRes.json();

          if (data.log_file && logInfo && logPath) {
            logInfo.style.display = 'block';
            logPath.textContent = data.log_file;
          }

          if (data.stopping && stopBtn) {
            stopBtn.disabled = true;
            stopBtn.textContent = '🛑 停止処理中…';
          }

          if (data.logs && data.logs.length > 0) {
            data.logs.forEach(item => {
              const lineText = (typeof item === 'object' && item.text) ? item.text : item;
              logLine(lineText);
              if (typeof item === 'object' && item.id) {
                lastLogId = Math.max(lastLogId, item.id);
              }
            });
            if (data.latest_log_id) {
              lastLogId = Math.max(lastLogId, data.latest_log_id);
            }
          }

          if (progressFill && data.progress !== undefined) {
            progressFill.style.width = Math.min(100, Math.max(0, data.progress)) + '%';
          }

          if (btn && data.current_council) {
            btn.textContent = `⏳ クロール中 (${data.current_idx || 0}/${data.total_councils || 0})…`;
          }

          // クロール完了または停止
          if (!data.running) {
            clearInterval(pollInterval);
            isRunningMeetingCrawl = false;
            if (progressFill) progressFill.style.width = '100%';
            if (btn) {
              btn.disabled = false;
              btn.textContent = '⚡ 実行';
            }
            if (stopBtn) {
              stopBtn.style.display = 'none';
              stopBtn.disabled = false;
              stopBtn.textContent = '🛑 クロール停止';
            }

            if (data.error) {
              logLine(`[ERROR] クローラー実行エラー: ${data.error}`);
              alert(`クローラー実行中にエラーが発生しました: ${data.error}`);
            } else {
              // 新着会議リストの取得・描画
              loadAndRenderNewMeetings();

              // 画面のデータインスペクターとキャッシュを自動更新
              if (typeof updateDataJsonInspector === 'function') updateDataJsonInspector();
            }
          }
        } catch (pollErr) {
          console.warn('Crawler status polling error:', pollErr);
        }
      }, 600);

    } catch (e) {
      logLine(`[ERROR] クロール起動に失敗しました: ${e.message || e}`);
      alert(`クロール起動エラー: ${e.message || e}`);
      if (btn) {
        btn.disabled = false;
        btn.textContent = '⚡ 実行';
      }
      if (stopBtn) {
        stopBtn.style.display = 'none';
      }
      isRunningMeetingCrawl = false;
    }
  };

  window.loadAndRenderNewMeetings = async function() {
    try {
      const res = await fetch('/api/new-meetings');
      if (!res.ok) return;
      const data = await res.json();
      const section = document.getElementById('newlyDiscoveredSection');
      const countEl = document.getElementById('newlyDiscoveredCount');
      const container = document.getElementById('newlyDiscoveredListContainer');
      if (!section || !container) return;

      const meets = data.meetings || [];
      if (meets.length === 0) {
        section.style.display = 'none';
        return;
      }

      section.style.display = 'block';
      if (countEl) countEl.textContent = meets.length;
      container.innerHTML = meets.map(m => {
        const matCount = (m.materials || []).length;
        const matPdfCount = (m.materials || []).filter(x => (x.url || '').toLowerCase().endsWith('.pdf')).length;
        return `
          <div style="background: rgba(0,0,0,0.3); border: 1px solid rgba(16,185,129,0.3); border-radius: var(--radius-md); padding: 0.85rem 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem;">
              <div>
                <span class="badge" style="background: rgba(16,185,129,0.2); color:#10b981; margin-right: 0.4rem; font-size: 0.75rem;">NEW</span>
                <span style="font-weight: 600; color: var(--text-primary); font-size: 0.95rem;">${m.name || m.id}</span>
                <span style="color: var(--text-muted); font-size: 0.82rem; margin-left: 0.5rem;">(${m.councilName || ((typeof allCouncils !== 'undefined' ? allCouncils : []).find(c => c.id === m.councilId)?.name) || m.councilId})</span>
              </div>
              <span style="font-size: 0.8rem; color: #38bdf8; font-weight: 500; white-space: nowrap;">📅 ${m.date || '日付未定'}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-muted);">
              <div>
                <span>配布資料: <strong style="color: var(--text-primary);">${matCount}</strong> 件 (PDF: <strong style="color:#10b981;">${matPdfCount}</strong> 件)</span>
                ${m.discoveredAt ? `<span style="margin-left: 0.8rem; color: #94a3b8;">検知: ${m.discoveredAt}</span>` : ''}
              </div>
              ${m.officialUrl ? `<a href="${escAttr(sanitizeUrl(m.officialUrl))}" target="_blank" rel="noopener" style="color: #60a5fa; text-decoration: underline;">公式ページ ↗</a>` : ''}
            </div>
          </div>
        `;
      }).join('');
    } catch(e) {
      console.warn('Failed to load new meetings:', e);
    }
  };

  document.addEventListener('DOMContentLoaded', async () => {
    let rejectedCouncils = [];
    window.rejectedCouncils = rejectedCouncils;

    let data = { councils: [], meetings: [], ministries: {}, categories: {}, docTypes: {}, initialAlertKeywords: [], lastCrawlTime: '' };
    try {
      let dataRes = await fetch(`../docs/data.json?t=${new Date().getTime()}`).catch(() => null);
      if (!dataRes || !dataRes.ok) {
        dataRes = await fetch(`/docs/data.json?t=${new Date().getTime()}`).catch(() => null);
      }
      if (dataRes && dataRes.ok) {
        data = await dataRes.json();
      } else {
        console.error('Failed to load data.json');
      }

      const rejRes = await fetch(`/api/rejected-councils?t=${new Date().getTime()}`).catch(() => null);
      if (rejRes && rejRes.ok) {
        const rejJson = await rejRes.json();
        rejectedCouncils = Array.isArray(rejJson) ? rejJson : [];
        window.rejectedCouncils = rejectedCouncils;
      }
    } catch(e) {
      console.error('Data loading error:', e);
    }

    window.COUNCILS = data.councils || [];
    window.MEETINGS = data.meetings || [];
    window.MINISTRIES = data.ministries || {};
    window.CATEGORIES = data.categories || {};
    window.DOC_TYPES = data.docTypes || {};
    window.INITIAL_ALERT_KEYWORDS = data.initialAlertKeywords || [];
    window.LAST_CRAWL_TIME = data.lastCrawlTime || '';

    const STORAGE_KEY_VERDICTS = 'pmhub_council_verdicts';
    const STORAGE_KEY_DISCOVERED = 'pmhub_discovered_councils';

    function getSavedVerdicts() {
      try { return JSON.parse(localStorage.getItem(STORAGE_KEY_VERDICTS) || '{}'); } catch(e) { return {}; }
    }
    function saveSavedVerdicts(vMap) {
      try {
        localStorage.setItem(STORAGE_KEY_VERDICTS, JSON.stringify(vMap));
      } catch(e) {
        console.warn('localStorage save failed (Verdicts). Quota exceeded?', e);
      }
    }

    window.clearCacheAndSyncWithDataJson = function() {
      if (confirm('ブラウザの古いlocalStorageキャッシュをクリアし、docs/data.json の最新データで強制同期しますか？')) {
        localStorage.removeItem(STORAGE_KEY_DISCOVERED);
        localStorage.removeItem(STORAGE_KEY_VERDICTS);
        window.location.reload();
      }
    };

    function isSessionName(name) {
      if (!name) return false;
      return /第\s*[\d０-９一二三四五六七八九十百千]+\s*回|第\s*[\d０-９一二三四五六七八九十百千]+\s*期|配布資料|配付資料|議事次第|議事録|議事要旨|中間とりまとめ|中間報告|報告書|開催案内|の開催について/.test(name);
    }

    function getSavedDiscovered() {
      try {
        const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY_DISCOVERED) || '[]');
        const list = Array.isArray(parsed) ? parsed : (parsed && Array.isArray(parsed.councils) ? parsed.councils : []);
        // セッション名・個別開催回を含む古いキャッシュエントリを自動排除
        return list.filter(item => item && item.id && !isSessionName(item.name));
      } catch(e) { return []; }
    }
    function saveSavedDiscovered(list) {
      try {
        const cleanList = (list || []).filter(item => item && item.id && !isSessionName(item.name));
        localStorage.setItem(STORAGE_KEY_DISCOVERED, JSON.stringify(cleanList));
      } catch(e) {
        console.warn('localStorage save failed (Discovered). Quota exceeded?', e);
      }
    }

    const KNOWN_NEW_IDS = [];
    const knownIdSet = new Set(KNOWN_NEW_IDS);

    const baseCouncils  = (window.COUNCILS && Array.isArray(window.COUNCILS)) ? window.COUNCILS : [];
    const meetings  = (window.MEETINGS && Array.isArray(window.MEETINGS)) ? window.MEETINGS : [];
    const ministries = window.MINISTRIES || {};
    const categories = window.CATEGORIES || {};

    function isGenericPortalUrl(url) {
      if (!url) return true;
      const u = url.replace(/\/+$/, '').toLowerCase();
      return u.endsWith('/index.html') || u.endsWith('/index.htm') || u.endsWith('/shingikailist.html') ||
             u.endsWith('/indexshingi.html') || u.endsWith('/councils') || u.endsWith('/kenkyu.htm') ||
             u.endsWith('/minutes') || u.endsWith('/meeting.html');
    }

    function isRejectedCouncil(c) {
      if (!c) return false;
      const rList = window.rejectedCouncils || [];
      if (c.id && rList.some(rc => rc.id === c.id)) return true;
      const cName = (c.name || '').trim();
      if (cName && rList.some(rc => (rc.name || '').trim() === cName)) return true;
      const cUrl = (c.officialUrl || '').replace(/\/+$/, '').toLowerCase();
      if (cUrl && !isGenericPortalUrl(cUrl) && rList.some(rc => (rc.officialUrl || '').replace(/\/+$/, '').toLowerCase() === cUrl)) return true;
      return false;
    }

    // councils をそのまま allCouncils として使用（ID/完全名称一致の却下済みのみ除外）
    let allCouncils = [...baseCouncils].filter(c => c && c.id && !isRejectedCouncil(c));
    allCouncils.forEach(c => {
      if (c.status === 'pending') c.isNew = true;
    });

    window.integrateDiscoveredCouncils = function(newCouncilsList) {
      if (!newCouncilsList || !newCouncilsList.length) return 0;
      const currentIds = new Set(allCouncils.map(c => c.id));
      let addedCount = 0;
      newCouncilsList.forEach(dc => {
        if (dc && dc.id && !isSessionName(dc.name) && !isRejectedCouncil(dc)) {
          const aiVerdict = (dc.status === 'approved' || dc.status === 'rejected') ? dc.status : null;

          if (!currentIds.has(dc.id)) {
            dc.isNew = true;
            allCouncils.push(dc); window.allCouncils = allCouncils;
            currentIds.add(dc.id);
            verdicts[dc.id] = { verdict: aiVerdict, notes: '', correctedUrl: '' };
            addedCount++;
          } else if (aiVerdict && (!verdicts[dc.id] || verdicts[dc.id].verdict === null || verdicts[dc.id].verdict === 'pending')) {
            verdicts[dc.id] = { verdict: aiVerdict, notes: '', correctedUrl: verdicts[dc.id]?.correctedUrl || '' };
          }
        }
      });
      saveSavedDiscovered(allCouncils.filter(c => c.isNew && !baseCouncils.some(bc => bc.id === c.id)));
      saveSavedVerdicts(verdicts);
      if (typeof populateFilterDropdowns === 'function') populateFilterDropdowns();
      if (typeof renderCards === 'function') renderCards();
      return addedCount;
    };
    const integrateDiscoveredCouncils = window.integrateDiscoveredCouncils;

    function normalizeVerdict(item, defaultV) {
      if (!item) return { verdict: defaultV, notes: '', correctedUrl: '' };
      if (typeof item === 'string') return { verdict: item, notes: '', correctedUrl: '' };
      return {
        verdict: item.verdict !== undefined ? item.verdict : defaultV,
        notes: item.notes || '',
        correctedUrl: item.correctedUrl || ''
      };
    }

    const meetingMap = {};
    meetings.forEach(m => { if (!meetingMap[m.councilId]) meetingMap[m.councilId] = []; meetingMap[m.councilId].push(m); });

    const savedVerdicts = getSavedVerdicts();
    const verdicts = {};
    const urlStatus = {};
    const matStatus = {};
    const meetingUrlCorrections = {};

    allCouncils.forEach(c => {
      const isBase = baseCouncils.some(bc => bc.id === c.id);
      let defaultV = isBase ? 'approved' : ((c.isNew === true || knownIdSet.has(c.id)) ? null : 'approved');
      if (c.status === 'approved' || c.status === 'rejected') defaultV = c.status;
      const norm = normalizeVerdict(savedVerdicts[c.id], defaultV);
      // 本番公開データ (baseCouncils) は原則承認済みとして同期
      if (isBase && norm.verdict !== 'approved') {
        norm.verdict = 'approved';
      }
      verdicts[c.id] = norm;
    });

    const loadRejectedCouncils = async () => {
      try {
        const res = await fetch('/api/rejected-councils');
        if (res.ok) {
          const list = await res.json();
          rejectedCouncils = Array.isArray(list) ? list : [];
          window.rejectedCouncils = rejectedCouncils;
          if (typeof renderRejectedList === 'function') renderRejectedList();
        }
      } catch (e) {
        console.warn('Rejected councils load error:', e);
      }
    };
    loadRejectedCouncils();
    if (typeof loadAndRenderNewMeetings === 'function') loadAndRenderNewMeetings();

    function populateFilterDropdowns() {
      const ministrySet = new Set(allCouncils.map(c => c.ministry));
      const categorySet = new Set(allCouncils.map(c => c.category));
      const filterMinistry = document.getElementById('filterMinistry');
      const filterCategory = document.getElementById('filterCategory');
      const filterMeetingsMinistry = document.getElementById('filterMeetingsMinistry');
      const filterMeetingsCategory = document.getElementById('filterMeetingsCategory');
      const kwMinistrySelect = document.getElementById('kwMinistrySelect');

      const filterRejectedMinistry = document.getElementById('filterRejectedMinistry');
      const filterRejectedCategory = document.getElementById('filterRejectedCategory');

      if (filterMinistry) filterMinistry.innerHTML = '<option value="">全省庁</option>';
      if (filterMeetingsMinistry) filterMeetingsMinistry.innerHTML = '<option value="">全省庁</option>';
      if (filterRejectedMinistry) filterRejectedMinistry.innerHTML = '<option value="">全省庁</option>';
      if (kwMinistrySelect) kwMinistrySelect.innerHTML = '<option value="">省庁を選択...</option>';
      ministrySet.forEach(code => {
        const name = ministries[code] ? ministries[code].name : code;
        if (filterMinistry) filterMinistry.innerHTML += `<option value="${code}">${name} (${code})</option>`;
        if (filterMeetingsMinistry) filterMeetingsMinistry.innerHTML += `<option value="${code}">${name} (${code})</option>`;
        if (filterRejectedMinistry) filterRejectedMinistry.innerHTML += `<option value="${code}">${name} (${code})</option>`;
        if (kwMinistrySelect) kwMinistrySelect.innerHTML += `<option value="${code}">${name} (${code})</option>`;
      });

      if (filterCategory) filterCategory.innerHTML = '<option value="">全カテゴリ</option>';
      if (filterMeetingsCategory) filterMeetingsCategory.innerHTML = '<option value="">全カテゴリ</option>';
      if (filterRejectedCategory) filterRejectedCategory.innerHTML = '<option value="">全カテゴリ</option>';
      categorySet.forEach(cat => {
        const label = categories[cat] || cat;
        if (filterCategory) filterCategory.innerHTML += `<option value="${cat}">${label}</option>`;
        if (filterMeetingsCategory) filterMeetingsCategory.innerHTML += `<option value="${cat}">${label}</option>`;
        if (filterRejectedCategory) filterRejectedCategory.innerHTML += `<option value="${cat}">${label}</option>`;
      });
    }
    populateFilterDropdowns();

    const listEl = document.getElementById('councilList');
    const meetingsListEl = document.getElementById('meetingsList');
    let meetingsRenderLimit = 100;
    let meetingsObserver = null;

    window.loadMoreMeetings = function() {
      meetingsRenderLimit += 100;
      renderMeetingsList();
    };

    function getMinistryColor(code) {
      const colorMap = {
        CAO:'#a855f7', CAS:'#4f46e5', DIGITAL:'#06b6d4', CFA:'#ec4899',
        MIC:'#f43f5e', MOJ:'#64748b', MOFA:'#0284c7', MOF:'#3b82f6', MEXT:'#d946ef',
        MHLW:'#f59e0b', MAFF:'#16a34a', METI:'#10b981', MLIT:'#0d9488', MOE:'#84cc16',
        MOD:'#475569', NPA:'#1e3a8a', FSA:'#2563eb', FSC:'#f97316', NPSC:'#64748b',
        CAA:'#f97316', PPC:'#0891b2', NRA:'#dc2626'
      };
      return colorMap[code] || '#3b82f6';
    }

    // ─── Render Meetings Management (TAB 2) ───
    function renderMeetingsList() {
      window.renderMeetingsList = renderMeetingsList;
      if (!meetingsListEl) return;
      const searchTerm = (document.getElementById('filterMeetingsSearch') ? document.getElementById('filterMeetingsSearch').value : '').toLowerCase();
      const fMinistry  = document.getElementById('filterMeetingsMinistry') ? document.getElementById('filterMeetingsMinistry').value : '';
      const fCategory  = document.getElementById('filterMeetingsCategory') ? document.getElementById('filterMeetingsCategory').value : '';
      const fDocType   = document.getElementById('filterMeetingsDocType') ? document.getElementById('filterMeetingsDocType').value : '';
      const fUrlStatus = document.getElementById('filterMeetingsUrlStatus') ? document.getElementById('filterMeetingsUrlStatus').value : '';

      const councilsList = typeof allCouncils !== 'undefined' ? allCouncils : (typeof baseCouncils !== 'undefined' ? baseCouncils : []);
      const councilsMap = new Map(councilsList.map(c => [c.id, c]));
      let filtered = meetings.filter(m => {
        const cObj = councilsMap.get(m.councilId) || {};
        const mMinistry = m.ministry || cObj.ministry || '';
        const mCategory = m.category || cObj.category || 'COUNCIL';
        const mCouncilName = m.councilName || cObj.name || m.name || '';
        const minName = ministries[mMinistry] ? ministries[mMinistry].name : mMinistry;
        const matNames = (m.materials || []).map(mat => mat.name).join(' ');
        const text = `${m.name} ${mCouncilName} ${m.id} ${m.date} ${minName} ${mMinistry} ${matNames}`.toLowerCase();
        if (searchTerm && !text.includes(searchTerm)) return false;
        if (fMinistry && mMinistry !== fMinistry) return false;
        if (fCategory && mCategory !== fCategory) return false;
        if (fDocType === 'has_docs' && (!m.materials || m.materials.length === 0)) return false;
        if (fDocType === 'no_docs' && m.materials && m.materials.length > 0) return false;
        if (fUrlStatus) {
          const mMats = m.materials || [];
          const hasTargetStatus = mMats.some(mat => {
            const matKey = m.councilId + '::' + mat.url;
            return matStatus[matKey] === fUrlStatus;
          });
          if (!hasTargetStatus) return false;
        }
        return true;
      });

      const totalDocs = filtered.reduce((sum, m) => sum + (m.materials ? m.materials.length : 0), 0);
      const totalAllDocs = meetings.reduce((sum, m) => sum + (m.materials ? m.materials.length : 0), 0);
      const correctedCount = Object.values(meetingUrlCorrections).filter(url => url && url.trim() !== '').length;

      const statMeetingsTotal = document.getElementById('statMeetingsTotal');
      const statMeetingsDocsTotal = document.getElementById('statMeetingsDocsTotal');
      const statMeetingsFiltered = document.getElementById('statMeetingsFiltered');
      const statMeetingsCorrected = document.getElementById('statMeetingsCorrected');
      
      if (statMeetingsTotal) statMeetingsTotal.textContent = meetings.length;
      if (statMeetingsDocsTotal) statMeetingsDocsTotal.textContent = `${totalAllDocs} 点`;
      if (statMeetingsFiltered) statMeetingsFiltered.textContent = `${filtered.length} 件 / ${totalDocs} 点`;
      if (statMeetingsCorrected) statMeetingsCorrected.textContent = correctedCount;

      const toRender = filtered.slice(0, meetingsRenderLimit);

      const badge = document.getElementById('filterMeetingsResultBadge');
      if (badge) {
        badge.textContent = `表示中: 会議 ${toRender.length} / ${filtered.length} 件 (資料 ${totalDocs} 点)`;
      }

      if (filtered.length === 0) {
        if (meetingsObserver) {
          meetingsObserver.disconnect();
          meetingsObserver = null;
        }
        meetingsListEl.innerHTML = `<div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <p>該当する会議データがありません</p>
        </div>`;
        return;
      }

      const cardsHtml = toRender.map((m, i) => {
        const cObj = councilsMap.get(m.councilId) || {};
        const mMinistry = m.ministry || cObj.ministry || '';
        const mCategory = m.category || cObj.category || 'COUNCIL';
        const mCouncilName = m.councilName || cObj.name || m.name || '';
        const minName = ministries[mMinistry] ? ministries[mMinistry].name : mMinistry;
        const catLabel = categories[mCategory] || mCategory;
        const accentColor = getMinistryColor(mMinistry);
        const mMats = m.materials || [];

        const mCorrected = meetingUrlCorrections[m.id] || '';
        const mHasCorr = mCorrected.trim() !== '';
        let mDiff = '';
        if (mHasCorr) {
          mDiff = `<div class="mu-diff">
            <div class="old-url">− ${escHtml(m.officialUrl)}</div>
            <div class="new-url">+ ${escHtml(mCorrected)}</div>
          </div>`;
        }

        let matRowsHtml = '';
        if (mMats.length > 0) {
          const matRows = mMats.map((mat, mi) => {
            const matKey = m.councilId + '::' + mat.url;
            const ms = matStatus[matKey];
            let msBadge = '<span class="url-status" style="color:var(--text-muted);font-size:0.65rem;">未検証</span>';
            if (ms === 'checking') msBadge = '<span class="url-status checking">⏳</span>';
            else if (ms === 'ok') msBadge = '<span class="url-status ok">✓ OK</span>';
            else if (ms === 'error') msBadge = '<span class="url-status error">✗ NG (エラー)</span>';
            const matType = mat.type || (mat.url && mat.url.toLowerCase().endsWith('.pdf') ? 'PDF' : (mat.url ? 'HTML' : 'PDF'));
            const typeClass = matType === 'PDF' ? 'mat-type-pdf' : matType === 'HTML' ? 'mat-type-html' : 'mat-type-other';

            return `<tr>
              <td style="width: 5%;">${mi + 1}</td>
              <td style="width: 45%;">${escHtml(mat.name)}</td>
              <td style="width: 12%;"><span class="mat-type-badge ${typeClass}">${matType}</span></td>
              <td style="width: 28%;"><a href="${escAttr(sanitizeUrl(mat.url))}" target="_blank" rel="noopener">${truncateUrl(mat.url, 45)}</a></td>
              <td style="width: 10%;">${msBadge}</td>
            </tr>`;
          }).join('');

          matRowsHtml = `<table class="mat-table" style="margin-top: 0.35rem;">
            <thead><tr><th>#</th><th>資料名</th><th>形式</th><th>URL</th><th>疎通</th></tr></thead>
            <tbody>${matRows}</tbody>
          </table>`;
        } else {
          matRowsHtml = `<div style="font-size:0.75rem; color:var(--text-muted); padding:0.3rem 0;">※ この開催回の資料データなし</div>`;
        }

        const isDateUnconfirmed = m.date === '2099/01/01' || m.isDateUnconfirmed;
        const dateDisplay = isDateUnconfirmed
          ? `<span class="meta-chip" style="color:#eab308;border-color:rgba(234,179,8,0.4);background:rgba(234,179,8,0.12);font-weight:bold;">⚠️ 開催日不明（要確認）</span>`
          : `開催日: 📅 ${m.date}`;

        return `<div class="council-card" style="--card-accent: ${accentColor}; margin-bottom: 1rem; animation-delay: ${Math.min(i * 0.02, 0.5)}s;">
          <div class="card-top">
            <div class="card-title-area">
              <div class="card-idx">#${i + 1} / ${filtered.length} ｜ ${dateDisplay}</div>
              <div class="card-name" style="font-size: 1.05rem;">${escHtml(m.name)} ${isDateUnconfirmed ? '<span class="meta-chip" style="color:#f59e0b;border-color:rgba(245,158,11,0.4);background:rgba(245,158,11,0.1);font-size:0.75rem;">要確認</span>' : ''}</div>
              <div class="card-id">ID: ${escHtml(m.id)} ｜ 会議体: ${escHtml(mCouncilName || m.councilId)}</div>
            </div>
            <div class="card-actions">
              ${mMats.length ? `<button class="btn-check-mats" onclick="checkMeetingMaterials('${escAttr(m.councilId)}', '${escAttr(m.id)}')">🔗 資料疎通チェック</button>` : ''}
            </div>
          </div>

          <div class="card-meta" style="margin-top: 0.65rem;">
            <span class="meta-chip"><span class="chip-icon">🏛</span> ${escHtml(minName)} (${escHtml(mMinistry)})</span>
            <span class="category-badge cat-${escAttr(mCategory)}">${escHtml(catLabel)}</span>
            <span class="meta-chip"><span class="chip-icon">📎</span> 配布資料: ${mMats.length} 件</span>
          </div>

          <div class="url-correction" style="margin-top: 0.75rem;">
            <div class="uc-label">✏️ 個別会議ページURL</div>
            <div class="uc-row">
              <input type="url" value="${escAttr(mCorrected)}" placeholder="${escAttr(m.officialUrl)}（変更不要ならそのまま）"
                class="${mHasCorr ? 'has-value' : ''}"
                oninput="setCorrectedMeetingUrl('${escAttr(m.id)}', this.value)" />
              <button class="btn-open-url" onclick="openMeetingUrl('${escAttr(m.id)}')">開く ↗</button>
            </div>
            ${mDiff}
          </div>

          <div class="materials-panel" style="margin-top: 0.75rem;">
            <div class="mat-header">
              <div class="mat-label">📎 配布資料一覧（${mMats.length}件）</div>
            </div>
            ${matRowsHtml}
          </div>
        </div>`;
      }).join('');

      let footerHtml = '';
      if (filtered.length > toRender.length) {
        const remaining = filtered.length - toRender.length;
        const nextChunk = Math.min(100, remaining);
        footerHtml = `<div id="meetingsLoadMoreContainer" style="text-align: center; padding: 2rem 1rem; margin: 1.5rem 0 3rem 0; background: rgba(30, 41, 59, 0.5); border-radius: 8px; border: 1px dashed var(--border-color, #334155);">
          <div style="font-size: 0.9rem; color: var(--text-muted, #94a3b8); margin-bottom: 0.75rem;">
            全 ${filtered.length.toLocaleString()} 件中 <strong>${toRender.length.toLocaleString()}</strong> 件を表示中（残り ${remaining.toLocaleString()} 件）
          </div>
          <button type="button" class="btn-primary" id="btnLoadMoreMeetings" onclick="loadMoreMeetings()" style="padding: 0.65rem 1.8rem; font-size: 0.9rem; font-weight: 600; cursor: pointer;">
            さらに表示（次の ${nextChunk} 件） ⬇
          </button>
          <div id="meetingsScrollTrigger" style="height: 1px; width: 100%;"></div>
        </div>`;
      } else if (filtered.length > 100) {
        footerHtml = `<div style="text-align: center; padding: 1.5rem 0; color: var(--text-muted, #94a3b8); font-size: 0.85rem;">
          全 ${filtered.length.toLocaleString()} 件をすべて表示しました
        </div>`;
      }

      meetingsListEl.innerHTML = cardsHtml + footerHtml;

      // 自動スクロール追記（IntersectionObserver）
      if (meetingsObserver) {
        meetingsObserver.disconnect();
        meetingsObserver = null;
      }
      if (filtered.length > toRender.length && typeof IntersectionObserver !== 'undefined') {
        const triggerEl = document.getElementById('meetingsScrollTrigger');
        if (triggerEl) {
          meetingsObserver = new IntersectionObserver((entries) => {
            if (entries[0] && entries[0].isIntersecting) {
              loadMoreMeetings();
            }
          }, { rootMargin: '300px' });
          meetingsObserver.observe(triggerEl);
        }
      }
    }

    // ─── Render Councils Management (TAB 3) ───
    function renderCards() {
      window.allCouncils = allCouncils;
      window.renderCards = renderCards;
      const listEl = document.getElementById('councilList');
      if (!listEl) return;
      const sEl = document.getElementById('filterSearch');
      const mEl = document.getElementById('filterMinistry');
      const cEl = document.getElementById('filterCategory');
      const vEl = document.getElementById('filterVerdict');
      const uEl = document.getElementById('filterUrlStatus');
      
      const searchTerm = sEl ? sEl.value.toLowerCase() : '';
      const fMinistry  = mEl ? mEl.value : '';
      const fCategory  = cEl ? cEl.value : '';
      const fVerdict   = vEl ? vEl.value : '';
      const fUrlStatus = uEl ? uEl.value : '';

      const rejectedIdSet = new Set((rejectedCouncils || []).map(rc => rc.id));

      let filtered = allCouncils.filter(c => {
        // 却下済み会議体は会議体データ管理に表示しない
        if (rejectedIdSet.has(c.id)) return false;

        const minName = ministries[c.ministry] ? ministries[c.ministry].name : c.ministry;
        const text = `${c.name} ${c.id} ${minName} ${c.ministry}`.toLowerCase();
        if (searchTerm && !text.includes(searchTerm)) return false;
        if (fMinistry && c.ministry !== fMinistry) return false;
        if (fCategory && c.category !== fCategory) return false;
        if (fVerdict) {
          const vObj = verdicts[c.id];
          const v = vObj ? vObj.verdict : null;
          if (fVerdict === 'pending' && v !== null && v !== 'pending') return false;
          if (fVerdict === 'approved' && v !== 'approved') return false;
        }
        if (fUrlStatus) {
          const st = urlStatus[c.id] || 'unverified';
          if (fUrlStatus === 'unverified') {
            if (st && st !== 'unverified') return false;
          } else {
            if (st !== fUrlStatus) return false;
          }
        }
        return true;
      });

      const filterResultBadge = document.getElementById('filterResultBadge');
      if (filterResultBadge) {
        filterResultBadge.textContent = `表示中: 会議体 ${filtered.length} 件`;
      }
      const statFilteredCounts = document.getElementById('statFilteredCounts');
      if (statFilteredCounts) {
        statFilteredCounts.textContent = `${filtered.length} 件`;
      }

      if (filtered.length === 0) {
        let emptyMsg = '<p>該当する会議体がありません</p>';
        if (fVerdict === 'pending') {
          emptyMsg = `
            <p style="font-weight:600; color:var(--text-main); margin-bottom:0.4rem;">未レビューの新規会議体はありません</p>
            <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:1rem;">現在すべての会議体がレビュー・登録済みです。「全ステータス」に切り替えると登録済み会議体一覧を確認できます。</p>
            <button class="btn-bulk export-json" onclick="document.getElementById('filterVerdict').value=''; renderCards();" style="padding:0.4rem 0.9rem; font-size:0.85rem;">
              📋 全ステータスの会議体を表示する
            </button>
          `;
        }
        listEl.innerHTML = `<div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          ${emptyMsg}
        </div>`;
        updateStats();
        return;
      }

      listEl.innerHTML = filtered.map((c, i) => {
        const v = verdicts[c.id] || { verdict: null, notes: '', correctedUrl: '' };
        const verdictClass = v.verdict ? `verdict-${v.verdict}` : '';
        const minName = ministries[c.ministry] ? ministries[c.ministry].name : c.ministry;
        const catLabel = categories[c.category] || c.category;
        const cMeetings = meetingMap[c.id] || [];
        const uStatus = urlStatus[c.id];
        const accentColor = getMinistryColor(c.ministry);

        let urlBadge = '';
        if (uStatus === 'checking') urlBadge = '<span class="url-status checking">⏳ 確認中…</span>';
        else if (uStatus === 'ok')   urlBadge = '<span class="url-status ok">✓ 疎通OK</span>';
        else if (uStatus === 'error') urlBadge = '<span class="url-status error">✗ エラー</span>';

        const correctedVal = v.correctedUrl || '';
        const hasCorrection = correctedVal.trim() !== '';
        let diffHtml = '';
        if (hasCorrection) {
          diffHtml = `<div class="uc-diff">
            <div class="old-url">− ${escHtml(c.officialUrl)}</div>
            <div class="new-url">+ ${escHtml(correctedVal)}</div>
          </div>`;
        }
        const urlCorrectionHtml = `<div class="url-correction">
          <div class="uc-label">🔗 会議体URL</div>
          <div class="uc-row">
            <input type="url" value="${escAttr(correctedVal)}" placeholder="${escAttr(c.officialUrl)}（変更不要ならそのまま）"
              class="${hasCorrection ? 'has-value' : ''}" id="url-input-${c.id}"
              oninput="setCorrectedUrl('${c.id}', this.value)" />
            <button class="btn-open-url" onclick="openCorrectedUrl('${c.id}')">開く ↗</button>
          </div>
          ${diffHtml}
        </div>`;

        const correctedNameVal = v.correctedName || '';
        const displayName = (correctedNameVal.trim() !== '') ? correctedNameVal.trim() : c.name;
        const hasNameCorrection = correctedNameVal.trim() !== '' && correctedNameVal.trim() !== c.name;
        let nameDiffHtml = '';
        if (hasNameCorrection) {
          nameDiffHtml = `<div class="uc-diff">
            <div class="old-url">− ${escHtml(c.name)}</div>
            <div class="new-url">+ ${escHtml(correctedNameVal)}</div>
          </div>`;
        }
        const nameCorrectionHtml = `<div class="url-correction" style="margin-bottom:0.6rem;">
          <div class="uc-label">✏️ 会議体名称の修正</div>
          <div class="uc-row">
            <input type="text" value="${escAttr(correctedNameVal)}" placeholder="${escAttr(c.name)}（名称変更が必要な場合に入力）"
              class="${hasNameCorrection ? 'has-value' : ''}" id="name-input-${c.id}"
              oninput="setCorrectedName('${c.id}', this.value)" />
          </div>
          ${nameDiffHtml}
        </div>`;

        let actionButtons = '';
        if (v.verdict === null || v.verdict === 'pending') {
          actionButtons = `
            <button class="btn-approve" onclick="setVerdict('${c.id}','approved')">✓ 承認</button>
            <button class="btn-reject" onclick="setVerdict('${c.id}','rejected')">✗ 却下</button>`;
        } else {
          actionButtons = `<button class="btn-revert" onclick="setVerdict('${c.id}', null)">↩ 取消</button>`;
        }

        const isManualLocked = c.manualLock === true;
        const lockBtn = isManualLocked
          ? `<button class="btn-unlock" onclick="toggleManualLock('${c.id}', false)" title="クロール保護を解除する">🔓 保護解除</button>`
          : `<button class="btn-lock" onclick="toggleManualLock('${c.id}', true)" title="クロール上書きを禁止する">🔒 手動保護</button>`;
        actionButtons += lockBtn;

        const globalIdx = i + 1;
        const totalCount = allCouncils.length;
        const statusBadge = v.verdict === 'approved'
          ? '<span class="meta-chip" style="color:#10b981;border-color:rgba(16,185,129,0.3);background:rgba(16,185,129,0.08);">✓ 承認済</span>'
          : v.verdict === 'rejected'
          ? '<span class="meta-chip" style="color:#ef4444;border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.08);">✗ 却下</span>'
          : '<span class="meta-chip" style="color:#f59e0b;border-color:rgba(245,158,11,0.3);background:rgba(245,158,11,0.08);">⏳ 未レビュー</span>';

        const isNewChip = c.isNew ? '<span class="meta-chip" style="color:#ec4899;border-color:rgba(236,72,153,0.3);background:rgba(236,72,153,0.08);">✨ 新規検出</span>' : '';
        const lockBadge = isManualLocked ? '<span class="meta-chip" style="color:#fbbf24;border-color:rgba(251,191,36,0.3);background:rgba(251,191,36,0.08);">🔒 手動保護中</span>' : '';
        const lockedClass = isManualLocked ? 'manual-locked' : '';

        const cMaterials = c.materials || [];
        let cMatRowsHtml = '';
        if (cMaterials.length > 0) {
          cMatRowsHtml = cMaterials.map((mat, mi) => `
            <div class="c-mat-row" style="display:flex; align-items:center; gap:0.4rem; margin-top:0.3rem;">
              <span style="font-size:0.8rem;">${mat.type === 'PDF' || (mat.url && mat.url.endsWith('.pdf')) ? '📄' : '🌐'}</span>
              <input type="text" value="${escAttr(mat.name)}" placeholder="資料名（例: 構成員名簿）" style="flex:2; font-size:0.78rem; padding:0.25rem 0.4rem; background:rgba(0,0,0,0.2); border:1px solid rgba(255,255,255,0.1); border-radius:4px; color:#fff;" onchange="updateCouncilMaterial('${c.id}', ${mi}, 'name', this.value)" />
              <input type="url" value="${escAttr(mat.url)}" placeholder="URL" style="flex:3; font-size:0.78rem; padding:0.25rem 0.4rem; background:rgba(0,0,0,0.2); border:1px solid rgba(255,255,255,0.1); border-radius:4px; color:#fff;" onchange="updateCouncilMaterial('${c.id}', ${mi}, 'url', this.value)" />
              <button class="btn-open-url" style="padding:0.2rem 0.4rem; font-size:0.75rem;" onclick="openSafeUrl('${escAttr(mat.url)}')">開く ↗</button>
              <button class="btn-remove-url" style="padding:0.2rem 0.4rem; font-size:0.75rem; background:rgba(239,68,68,0.2); color:#ef4444; border:1px solid rgba(239,68,68,0.3); border-radius:4px; cursor:pointer;" onclick="removeCouncilMaterial('${c.id}', ${mi})" title="削除">✕</button>
            </div>
          `).join('');
        }
        const cMaterialsHtml = `
          <div class="council-materials-box" style="margin-top:0.5rem; padding:0.5rem 0.7rem; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-size:0.8rem; font-weight:600; color:var(--accent-primary);">📂 会議体共通資料 (構成員名簿・設置根拠等: ${cMaterials.length}件)</span>
              <button style="padding:0.2rem 0.5rem; font-size:0.75rem; background:rgba(6,182,212,0.15); color:var(--accent-primary); border:1px solid rgba(6,182,212,0.3); border-radius:4px; cursor:pointer;" onclick="addCouncilMaterial('${c.id}')">＋ 資料を追加</button>
            </div>
            ${cMatRowsHtml}
          </div>
        `;

        return `<div class="council-card ${verdictClass} ${lockedClass}" style="--card-accent: ${accentColor}; animation-delay: ${i * 0.02}s;" id="card-${c.id}">
          <div class="card-top">
            <div class="card-title-area">
              <div class="card-idx">#${globalIdx} / ${totalCount}</div>
              <div class="card-name">${escHtml(displayName)} ${statusBadge} ${isNewChip} ${lockBadge} ${hasNameCorrection ? '<span class="meta-chip" style="color:#38bdf8;border-color:rgba(56,189,248,0.3);background:rgba(56,189,248,0.08);">✏️ 名称修正あり</span>' : ''}</div>
              <div class="card-id">ID: ${c.id}</div>
            </div>
            <div class="card-actions">${actionButtons}</div>
          </div>
          <div class="card-meta">
            <span class="meta-chip"><span class="chip-icon">🏛</span> ${minName} (${c.ministry})</span>
            <span class="category-badge cat-${c.category}">${catLabel}</span>
            <span class="meta-chip"><span class="chip-icon">🔗</span> <a href="${escAttr(sanitizeUrl(c.officialUrl))}" target="_blank" rel="noopener">${truncateUrl(c.officialUrl, 55)}</a> ${urlBadge}</span>
            <span class="meta-chip" style="cursor:pointer;" onclick="jumpToMeetingList('${c.id}')"><span class="chip-icon">📋</span> 会議数: ${cMeetings.length} 件 ↗</span>
          </div>
          ${nameCorrectionHtml}
          ${urlCorrectionHtml}
          ${cMaterialsHtml}
          <textarea class="notes-area" placeholder="検証メモ（任意）…" onchange="setNotes('${c.id}', this.value)">${v.notes || ''}</textarea>
        </div>`;
      }).join('');

      updateStats();
    }


    window.toggleManualLock = async function(councilId, lockValue) {
      try {
        const res = await fetch('/api/toggle-manual-lock', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: councilId, type: 'council', manualLock: lockValue })
        });
        if (res.ok) {
          // Update in-memory council data
          const c = allCouncils.find(x => x.id === councilId);
          if (c) c.manualLock = lockValue;
          renderCards();
          console.log(`[manualLock] ${councilId} -> ${lockValue}`);
        } else {
          const err = await res.json().catch(() => ({}));
          alert(`manualLock 変更失敗: ${err.message || 'Unknown error'}`);
        }
      } catch(e) {
        // サーバーが起動していない場合はローカルのみ更新
        const c = allCouncils.find(x => x.id === councilId);
        if (c) c.manualLock = lockValue;
        renderCards();
        console.warn('[toggleManualLock] Server unavailable, local-only update. Changes will not persist to data.json until server is running.', e);
      }
    };

    window.updateCouncilMaterial = function(councilId, idx, field, value) {
      const c = allCouncils.find(x => x.id === councilId);
      if (!c) return;
      if (!c.materials) c.materials = [];
      if (c.materials[idx]) {
        c.materials[idx][field] = value.trim();
        if (field === 'url' && value.toLowerCase().endsWith('.pdf')) {
          c.materials[idx].type = 'PDF';
        }
      }
    };

    window.addCouncilMaterial = function(councilId) {
      const c = allCouncils.find(x => x.id === councilId);
      if (!c) return;
      if (!c.materials) c.materials = [];
      c.materials.push({ name: '', url: '', type: 'PDF' });
      renderCards();
    };

    window.removeCouncilMaterial = function(councilId, idx) {
      const c = allCouncils.find(x => x.id === councilId);
      if (!c || !c.materials) return;
      c.materials.splice(idx, 1);
      renderCards();
    };

    window.jumpToMeetingList = function(councilId) {

      switchTab('tab-meetings');
      const searchInput = document.getElementById('filterMeetingsSearch');
      if (searchInput) {
        searchInput.value = councilId;
        renderMeetingsList();
      }
    };

    let isSavingMeetingUrlsDirect = false;
    window.saveMeetingUrlsDirectToDataJson = async function() {
      if (isSavingMeetingUrlsDirect) return;
      isSavingMeetingUrlsDirect = true;
      try {
      const corrections = [];
      Object.keys(meetingUrlCorrections).forEach(mId => {
        const corrUrl = meetingUrlCorrections[mId];
        const m = meetings.find(item => item.id === mId);
        if (corrUrl && corrUrl.trim() !== '' && m) {
          corrections.push({
            action: 'update_field',
            target: 'MEETINGS',
            targetId: mId,
            field: 'officialUrl',
            oldValue: m.officialUrl,
            newValue: corrUrl.trim(),
            reason: `Admin corrected meeting page URL for ${mId}`
          });
        }
      });

      if (corrections.length === 0) {
        alert('修正された個別会議URLがありません。');
        return;
      }

      const report = {
        _format: 'pmhub-verification-report-v2',
        _description: '個別会議URL更新',
        exportedAt: new Date().toISOString(),
        targetFile: 'docs/data.json',
        corrections: corrections
      };

      try {
        const res = await fetch('/api/save-verification-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(report)
        });
        if (res.ok) {
          corrections.forEach(corr => {
            const targetMeeting = meetings.find(m => m.id === corr.targetId);
            if (targetMeeting) targetMeeting.officialUrl = corr.newValue;
            delete meetingUrlCorrections[corr.targetId];
          });
          renderMeetingsList();
          alert('【サーバー経由】docs/data.json への会議URL保存が完了しました！');
          return;
        } else {
          const errData = await res.json().catch(() => ({}));
          console.warn('Server error on save-verification-report:', errData);
        }
      } catch(e) {
        console.warn('Network error on save-verification-report:', e);
      }

      if ('showOpenFilePicker' in window && window.location.protocol !== 'file:') {
        try {
          const [fileHandle] = await window.showOpenFilePicker({
            types: [{ description: 'JavaScript File', accept: { 'text/javascript': ['.js'] } }]
          });
          if (!fileHandle.name.endsWith('data.json')) {
            if (!confirm(`選択されたファイル (${fileHandle.name}) は data.json ではありませんが、続行しますか？`)) return;
          }
          const file = await fileHandle.getFile();
          let text = await file.text();

          corrections.forEach(corr => {
            if (corr.action === 'update_field') {
              const pattern = new RegExp(`(id:\\s*'${corr.targetId}'[\\s\\S]*?officialUrl:\\s*')[^']+(')`);
              text = text.replace(pattern, `$1${corr.newValue}$2`);
            }
          });

          const writable = await fileHandle.createWritable();
          await writable.write(text);
          await writable.close();

          corrections.forEach(corr => {
            const targetMeeting = meetings.find(m => m.id === corr.targetId);
            if (targetMeeting) targetMeeting.officialUrl = corr.newValue;
            delete meetingUrlCorrections[corr.targetId];
          });
          renderMeetingsList();
          alert('docs/data.json に直接反映・更新しました！');
          return;
        } catch (err) {
          if (err.name === 'AbortError' || err.name === 'NotAllowedError' || err.name === 'SecurityError') return;
        }
      }

      const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      await saveJsonFile(report, `meeting_urls_updates_${new Date().toISOString().slice(0,10)}.json`);
      if (isLocalhost) {
        alert('【サーバー保存エラー】localhost:8000 への保存処理が完了できませんでした。\nローカルサーバー (py admin/server.py) が正常に起動しているかご確認ください。\n\nバックアップとしてJSONを出力しました。');
      } else {
        alert('file:// 直開きのブラウザ制限によりファイル直接上書きが制限されているため、JSONを出力しました。\n\nターミナルで以下を実行すると docs/data.json に反映できます：\npy admin/apply_report.py admin/meeting_urls_updates_*.json');
      }
      } finally {
        isSavingMeetingUrlsDirect = false;
      }
    };
    window.saveMeetingUrlsDirectToDataJs = window.saveMeetingUrlsDirectToDataJson;

    document.getElementById('btnExportMeetingsJson').addEventListener('click', async () => {
      const corrections = [];
      Object.keys(meetingUrlCorrections).forEach(mId => {
        const corrUrl = meetingUrlCorrections[mId];
        const m = meetings.find(item => item.id === mId);
        if (corrUrl && corrUrl.trim() !== '' && m) {
          corrections.push({
            action: 'update_field',
            target: 'MEETINGS',
            targetId: mId,
            field: 'officialUrl',
            oldValue: m.officialUrl,
            newValue: corrUrl.trim(),
            reason: `Admin corrected meeting page URL for ${mId}`
          });
        }
      });
      if (corrections.length === 0) {
        alert('変更された個別会議URLがありません。');
        return;
      }
      const report = {
        _format: 'pmhub-verification-report-v2',
        _description: '個別会議URL更新',
        exportedAt: new Date().toISOString(),
        targetFile: 'docs/data.json',
        corrections: corrections
      };
      await saveJsonFile(report, `meeting_urls_updates_${new Date().toISOString().slice(0,10)}.json`);
    });

    document.getElementById('btnCheckAllMeetingMats').addEventListener('click', async () => {
      const btn = document.getElementById('btnCheckAllMeetingMats');
      btn.disabled = true;
      const allUrls = [];
      meetings.forEach(m => {
        if (m.materials) {
          m.materials.forEach(mat => allUrls.push({ councilId: m.councilId, url: mat.url }));
        }
      });
      const total = allUrls.length;
      let completed = 0;
      btn.textContent = `🔗 資料チェック中 (0 / ${total} 件)…`;

      try {
        const batchSize = 12;
        for (let i = 0; i < total; i += batchSize) {
          const batch = allUrls.slice(i, i + batchSize);
          await Promise.all(batch.map(item => checkSingleMat(item.councilId, item.url, true)));
          completed += batch.length;
          btn.textContent = `🔗 資料チェック中 (${Math.min(completed, total)} / ${total} 件)…`;
          renderMeetingsList();
        }
      } catch (err) {
        console.error('Meetings Materials Check Error:', err);
      } finally {
        btn.disabled = false;
        btn.textContent = '🔗 全会議の資料を一括疎通チェック';
        renderMeetingsList();
      }
    });

    const resetMeetingsLimitAndRender = () => {
      meetingsRenderLimit = 100;
      renderMeetingsList();
    };
    if (document.getElementById('filterMeetingsSearch')) document.getElementById('filterMeetingsSearch').addEventListener('input', resetMeetingsLimitAndRender);
    if (document.getElementById('filterMeetingsMinistry')) document.getElementById('filterMeetingsMinistry').addEventListener('change', resetMeetingsLimitAndRender);
    if (document.getElementById('filterMeetingsCategory')) document.getElementById('filterMeetingsCategory').addEventListener('change', resetMeetingsLimitAndRender);
    if (document.getElementById('filterMeetingsDocType')) document.getElementById('filterMeetingsDocType').addEventListener('change', resetMeetingsLimitAndRender);
    if (document.getElementById('filterMeetingsUrlStatus')) document.getElementById('filterMeetingsUrlStatus').addEventListener('change', resetMeetingsLimitAndRender);

    if (document.getElementById('filterSearch')) document.getElementById('filterSearch').addEventListener('input', renderCards);
    if (document.getElementById('filterMinistry')) document.getElementById('filterMinistry').addEventListener('change', renderCards);
    if (document.getElementById('filterCategory')) document.getElementById('filterCategory').addEventListener('change', renderCards);
    if (document.getElementById('filterVerdict')) document.getElementById('filterVerdict').addEventListener('change', renderCards);
    if (document.getElementById('filterUrlStatus')) document.getElementById('filterUrlStatus').addEventListener('change', renderCards);

    function truncateUrl(url, max) {
      if (!url) return '';
      if (url.length <= max) return url;
      return url.substring(0, max) + '…';
    }
    function escHtml(str) {
      return (str || '')
        .replace(/&/g,'&amp;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;')
        .replace(/'/g,'&#39;');
    }
    function escAttr(str) {
      return (str || '')
        .replace(/&/g,'&amp;')
        .replace(/"/g,'&quot;')
        .replace(/'/g,'&#39;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;');
    }

    window.setVerdict = async function(id, verdict) {
      if (!verdicts[id]) verdicts[id] = { verdict: null, notes: '', correctedUrl: '' };
      verdicts[id].verdict = verdict;
      saveSavedVerdicts(verdicts);

      const council = allCouncils.find(c => c.id === id);
      if (verdict === 'rejected' && council) {
        const rejItem = {
          id: council.id,
          name: council.name,
          ministry: council.ministry,
          category: council.category || 'COUNCIL',
          officialUrl: council.officialUrl || '',
          rejectedAt: new Date().toISOString().slice(0, 10),
          reason: verdicts[id].notes || 'Admin rejected council'
        };
        if (!rejectedCouncils.some(rc => rc.id === id)) {
          rejectedCouncils.push(rejItem);
          window.rejectedCouncils = rejectedCouncils;
        }

        // サーバーAPI呼び出し: docs/data.json から削除 & rejected_councils.json に保存
        try {
          await fetch('/api/reject-council', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              id: council.id,
              reason: rejItem.reason,
              rejectedAt: rejItem.rejectedAt,
              council: rejItem
            })
          });
        } catch (err) {
          console.warn('Failed to call /api/reject-council, falling back to saveRejectedCouncilsDirect:', err);
          saveRejectedCouncilsDirect(true);
        }

        // baseCouncils からも除外
        const bIdx = baseCouncils.findIndex(bc => bc.id === id);
        if (bIdx !== -1) baseCouncils.splice(bIdx, 1);
      } else if (verdict !== 'rejected') {
        const rejIdx = rejectedCouncils.findIndex(rc => rc.id === id);
        if (rejIdx !== -1) {
          rejectedCouncils.splice(rejIdx, 1);
          window.rejectedCouncils = rejectedCouncils;
          saveRejectedCouncilsDirect(true);
        }
      }
      
      try {
        renderCards();
        if (typeof renderRejectedList === 'function') renderRejectedList();
      } catch(e) {
        console.error('renderCards error in setVerdict:', e);
      }
    };
    window.setNotes = function(id, text) {
      if (!verdicts[id]) verdicts[id] = { verdict: null, notes: '', correctedUrl: '' };
      verdicts[id].notes = text;
      saveSavedVerdicts(verdicts);
    };
    window.setCorrectedUrl = function(id, url) {
      if (!verdicts[id]) verdicts[id] = { verdict: null, notes: '', correctedUrl: '', correctedName: '' };
      verdicts[id].correctedUrl = url.trim();
      saveSavedVerdicts(verdicts);
      const card = document.getElementById(`card-${id}`);
      if (card) {
        const input = card.querySelector('.url-correction input[type=url]');
        if (input) input.classList.toggle('has-value', url.trim() !== '');
      }
    };
    window.setCorrectedName = function(id, name) {
      if (!verdicts[id]) verdicts[id] = { verdict: null, notes: '', correctedUrl: '', correctedName: '' };
      verdicts[id].correctedName = name.trim();
      saveSavedVerdicts(verdicts);
      const card = document.getElementById(`card-${id}`);
      if (card) {
        const input = card.querySelector('#name-input-' + id);
        const council = allCouncils.find(c => c.id === id);
        const originalName = council ? council.name : '';
        if (input) input.classList.toggle('has-value', name.trim() !== '' && name.trim() !== originalName);
      }
    };
    window.openCorrectedUrl = function(id) {
      const corrected = verdicts[id] ? verdicts[id].correctedUrl : '';
      const council = allCouncils.find(c => c.id === id);
      const url = corrected || (council ? council.officialUrl : '');
      if (url) window.open(url, '_blank');
    };
    window.setCorrectedMeetingUrl = function(meetingId, url) {
      meetingUrlCorrections[meetingId] = url.trim();
    };
    window.openSafeUrl = function(url) {
      const s = sanitizeUrl(url);
      if (s && s !== '#') window.open(s, '_blank', 'noopener,noreferrer');
    };
    window.openMeetingUrl = function(meetingId) {
      const corrected = meetingUrlCorrections[meetingId];
      const meeting = meetings.find(m => m.id === meetingId);
      const rawUrl = corrected || (meeting ? meeting.officialUrl : '');
      const url = sanitizeUrl(rawUrl);
      if (url && url !== '#') window.open(url, '_blank', 'noopener,noreferrer');
    };

    async function checkSingleMat(councilId, matUrl, skipRender = false) {
      const key = councilId + '::' + matUrl;
      matStatus[key] = 'checking';
      if (!skipRender) { renderCards(); renderMeetingsList(); }
      try {
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 3500);
        await fetch(matUrl, { mode: 'no-cors', signal: ctrl.signal });
        clearTimeout(tid);
        matStatus[key] = 'ok';
      } catch (e) {
        matStatus[key] = 'error';
      }
      if (!skipRender) { renderCards(); renderMeetingsList(); }
    }
    window.checkMaterials = async function(councilId) {
      const cMeetings = meetingMap[councilId] || [];
      const allUrls = [];
      cMeetings.forEach(m => {
        if (m.materials) m.materials.forEach(mat => allUrls.push(mat.url));
      });
      for (let i = 0; i < allUrls.length; i += 3) {
        const batch = allUrls.slice(i, i + 3);
        await Promise.all(batch.map(u => checkSingleMat(councilId, u)));
        renderCards();
      }
    };

    window.checkMeetingMaterials = async function(councilId, meetingId) {
      const targetMeeting = meetings.find(m => m.id === meetingId);
      if (!targetMeeting || !targetMeeting.materials || !targetMeeting.materials.length) return;
      const allUrls = targetMeeting.materials.map(mat => mat.url);
      for (let i = 0; i < allUrls.length; i += 3) {
        const batch = allUrls.slice(i, i + 3);
        await Promise.all(batch.map(u => checkSingleMat(councilId, u)));
        renderCards();
      }
    };

    function updateStats() {
      const rejIdSet = new Set((rejectedCouncils || []).map(rc => rc.id));
      const activeCouncils = allCouncils.filter(c => !rejIdSet.has(c.id));
      const total = activeCouncils.length;
      const approved = activeCouncils.filter(c => verdicts[c.id] && verdicts[c.id].verdict === 'approved').length;
      const rejected = (rejectedCouncils || []).length;
      const pending  = total - approved;
      const urlOk    = activeCouncils.filter(c => urlStatus[c.id] === 'ok').length;
      const corrected = activeCouncils.filter(c => {
        const v = verdicts[c.id];
        return v && v.correctedUrl && typeof v.correctedUrl === 'string' && v.correctedUrl.trim() !== '';
      }).length;

      document.getElementById('statTotal').textContent = total;
      document.getElementById('statApproved').textContent = approved;
      document.getElementById('statRejected').textContent = rejected;
      document.getElementById('statPending').textContent = pending;
      document.getElementById('statUrlOk').textContent = `${urlOk} / ${total}`;
      const statCorrectedEl = document.getElementById('statCorrected');
      if (statCorrectedEl) statCorrectedEl.textContent = corrected;
      window.updateStats = updateStats;

      // デバッグ・自動検出: 本番 baseCouncils のうち非承認状態 (rejected または null/pending) のものを特定
      const unapprovedBaseCouncils = baseCouncils.filter(bc => {
        const v = verdicts[bc.id];
        return !v || v.verdict !== 'approved';
      });

      const bannerEl = document.getElementById('discrepancyAlertBanner');
      if (bannerEl) {
        let debugStr = `【デバッグ情報】baseCouncils件数: ${baseCouncils.length}件, allCouncils件数: ${allCouncils.length}件, statApproved: ${approved}件。`;
        
        if (unapprovedBaseCouncils.length > 0) {
          const itemsList = unapprovedBaseCouncils.map(c => {
            const st = (verdicts[c.id] && verdicts[c.id].verdict === 'rejected') ? '【却下】' : '【未レビュー】';
            return `<b>${st} ${escHtml(c.name)}</b> (ID: <code>${c.id}</code>)`;
          }).join(', ');
          
          bannerEl.style.display = 'block';
          bannerEl.style.background = 'rgba(245,158,11,0.12)';
          bannerEl.style.borderColor = 'rgba(245,158,11,0.4)';
          bannerEl.style.color = '#f59e0b';
          bannerEl.innerHTML = `⚠️ <b>公開データとの不一致検出:</b> 本番データ中 ${unapprovedBaseCouncils.length} 件が非承認状態です。<br/>該当会議体: ${itemsList}<br/>${debugStr}`;
        } else {
          bannerEl.style.display = 'block';
          bannerEl.style.background = 'rgba(16,185,129,0.12)';
          bannerEl.style.borderColor = 'rgba(16,185,129,0.4)';
          bannerEl.style.color = '#10b981';
          bannerEl.innerHTML = `✅ <b>不一致なし:</b> すべての baseCouncils が承認済です。<br/>${debugStr}`;
        }
      }
    }

    // ─── Ministry Management ───
    const ministryUpdates = {};
    function getMinistryCouncilsUrls(code) {
      const min = ministries[code];
      const update = ministryUpdates[code] || {};
      if (update.councilsUrls !== undefined) return update.councilsUrls;
      if (min && min.councilsUrls) return min.councilsUrls;
      if (min && min.councilsUrl) return [min.councilsUrl];
      return [];
    }

    function renderMinistryList() {
      window.renderMinistryList = renderMinistryList;
      const container = document.getElementById('ministryListContainer');
      if (!container) return;
      const codes = Object.keys(ministries).sort();
      let html = `<table class="ministry-table">
        <thead>
          <tr>
            <th style="width: 15%">省庁名 (コード)</th>
            <th style="width: 30%">省庁トップページURL</th>
            <th style="width: 42%">審議会等ページURL (複数可)</th>
            <th style="width: 13%">審議会等の有無</th>
          </tr>
        </thead>
        <tbody>`;
      codes.forEach(code => {
        const min = ministries[code];
        const update = ministryUpdates[code] || {};
        const oUrl = update.officialUrl !== undefined ? update.officialUrl : (min.officialUrl || '');
        const cUrls = getMinistryCouncilsUrls(code);
        const hasC = update.hasCouncils !== undefined ? update.hasCouncils : (min.hasCouncils !== false);
        const isCUrlsChanged = update.councilsUrls !== undefined;

        let cUrlsHtml = '';
        if (cUrls.length === 0) {
          cUrlsHtml = `<div class="url-cell-flex" style="margin-bottom:0.35rem;">
            <input type="url" value="" oninput="updateMinistryCouncilUrl('${code}', 0, this.value, this)" class="${isCUrlsChanged ? 'changed' : ''}" placeholder="審議会等一覧ページのURL" />
            <button class="btn-open-url" onclick="openMinistryUrl('${code}', 'councilsUrls', 0)">開く ↗</button>
          </div>`;
        } else {
          cUrlsHtml = cUrls.map((u, idx) => `
            <div class="url-cell-flex" style="margin-bottom:0.35rem;">
              <input type="url" value="${escAttr(u)}" oninput="updateMinistryCouncilUrl('${code}', ${idx}, this.value, this)" class="${isCUrlsChanged ? 'changed' : ''}" placeholder="審議会等一覧ページのURL" />
              <button class="btn-open-url" onclick="openMinistryUrl('${code}', 'councilsUrls', ${idx})">開く ↗</button>
              ${cUrls.length > 1 ? `<button class="btn-remove-url" onclick="removeMinistryCouncilUrl('${code}', ${idx})" title="削除">✕</button>` : ''}
            </div>
          `).join('');
        }

        html += `<tr>
          <td><strong>${min.name}</strong><br><span style="font-size:0.75rem;color:var(--text-muted);">${code}</span></td>
          <td>
            <div class="url-cell-flex">
              <input type="url" value="${escAttr(oUrl)}" oninput="updateMinistry('${code}', 'officialUrl', this.value, this)" class="${update.officialUrl !== undefined ? 'changed' : ''}" />
              <button class="btn-open-url" onclick="openMinistryUrl('${code}', 'officialUrl')">開く ↗</button>
            </div>
          </td>
          <td>
            ${cUrlsHtml}
            <button class="btn-add-url" onclick="addMinistryCouncilUrl('${code}')">＋ URLを追加</button>
          </td>
          <td>
            <label class="toggle-switch">
              <input type="checkbox" ${hasC ? 'checked' : ''} onchange="updateMinistry('${code}', 'hasCouncils', this.checked, this)" />
              <span>${hasC ? 'あり' : 'なし'}</span>
            </label>
          </td>
        </tr>`;
      });
      html += `</tbody></table>`;
      container.innerHTML = html;
    }

    window.openMinistryUrl = function(code, field, idx = 0) {
      if (field === 'officialUrl') {
        const min = ministries[code];
        const update = ministryUpdates[code] || {};
        const url = update.officialUrl !== undefined ? update.officialUrl : (min ? min.officialUrl : '');
        if (url) window.open(url, '_blank');
      } else {
        const cUrls = getMinistryCouncilsUrls(code);
        const url = cUrls[idx];
        if (url) window.open(url, '_blank');
      }
    };

    window.updateMinistry = function(code, field, value, el) {
      if (!ministryUpdates[code]) ministryUpdates[code] = {};
      const min = ministries[code];
      const originalValue = min[field] !== undefined ? min[field] : (field === 'hasCouncils' ? true : '');
      if (value === originalValue) {
        delete ministryUpdates[code][field];
        if (Object.keys(ministryUpdates[code]).length === 0) delete ministryUpdates[code];
        if (el && el.tagName === 'INPUT') el.classList.remove('changed');
      } else {
        ministryUpdates[code][field] = value;
        if (el && el.tagName === 'INPUT' && el.type === 'url') el.classList.add('changed');
      }
    };

    window.updateMinistryCouncilUrl = function(code, idx, value, el) {
      if (!ministryUpdates[code]) ministryUpdates[code] = {};
      const current = [...getMinistryCouncilsUrls(code)];
      current[idx] = value;
      ministryUpdates[code].councilsUrls = current;
      if (el && el.tagName === 'INPUT') {
        el.classList.add('changed');
      }
    };

    window.addMinistryCouncilUrl = function(code) {
      const scrollY = window.scrollY;
      if (!ministryUpdates[code]) ministryUpdates[code] = {};
      const current = [...getMinistryCouncilsUrls(code)];
      current.push('');
      ministryUpdates[code].councilsUrls = current;
      renderMinistryList();
      window.scrollTo(0, scrollY);
    };

    window.removeMinistryCouncilUrl = function(code, idx) {
      const scrollY = window.scrollY;
      if (!ministryUpdates[code]) ministryUpdates[code] = {};
      const current = [...getMinistryCouncilsUrls(code)];
      current.splice(idx, 1);
      ministryUpdates[code].councilsUrls = current;
      renderMinistryList();
      window.scrollTo(0, scrollY);
    };

    async function saveJsonFile(report, defaultFilename) {
      const jsonStr = JSON.stringify(report, null, 2);
      if ('showSaveFilePicker' in window) {
        try {
          const handle = await window.showSaveFilePicker({
            suggestedName: defaultFilename,
            types: [{ description: 'JSON File', accept: { 'application/json': ['.json'] } }]
          });
          const writable = await handle.createWritable();
          await writable.write(jsonStr);
          await writable.close();
          alert(`保存が完了しました: ${handle.name}`);
          return;
        } catch (err) {
          if (err.name === 'AbortError' || err.name === 'NotAllowedError' || err.name === 'SecurityError') return;
          console.warn('showSaveFilePicker failed, fallback to direct download:', err);
        }
      }
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = defaultFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }

    window.exportMinistryJson = async function() {
      const updates = Object.keys(ministryUpdates);
      if (updates.length === 0) {
        alert('変更された省庁データはありません。');
        return;
      }
      const corrections = [];
      updates.forEach(code => {
        const u = ministryUpdates[code];
        if (u.officialUrl !== undefined) {
          corrections.push({ action: 'update_field', target: 'MINISTRIES', targetId: code, field: 'officialUrl', oldValue: ministries[code].officialUrl, newValue: u.officialUrl.trim(), reason: 'Admin corrected ministry officialUrl' });
        }
        if (u.councilsUrls !== undefined) {
          const cleaned = u.councilsUrls.map(x => x.trim()).filter(x => x !== '');
          const old = ministries[code].councilsUrls || (ministries[code].councilsUrl ? [ministries[code].councilsUrl] : []);
          corrections.push({ action: 'update_field', target: 'MINISTRIES', targetId: code, field: 'councilsUrls', oldValue: old, newValue: cleaned, reason: 'Admin updated councilsUrls' });
        }
        if (u.hasCouncils !== undefined) {
          corrections.push({ action: 'update_field', target: 'MINISTRIES', targetId: code, field: 'hasCouncils', oldValue: ministries[code].hasCouncils, newValue: u.hasCouncils, reason: 'Admin toggled hasCouncils' });
        }
      });
      const report = {
        _format: 'pmhub-verification-report-v2',
        _description: '省庁データ更新',
        exportedAt: new Date().toISOString(),
        targetFile: 'docs/data.json',
        corrections: corrections
      };
      await saveJsonFile(report, `ministry_updates_${new Date().toISOString().split('T')[0]}.json`);
    };

    let isSavingMinistryDirect = false;
    window.saveDirectToDataJson = async function() {
      if (isSavingMinistryDirect) return;
      isSavingMinistryDirect = true;
      try {
      const updates = Object.keys(ministryUpdates);
      if (updates.length === 0) {
        alert('変更された省庁データはありません。');
        return;
      }

      const corrections = [];
      updates.forEach(code => {
        const u = ministryUpdates[code];
        if (u.officialUrl !== undefined) {
          corrections.push({ action: 'update_field', target: 'MINISTRIES', targetId: code, field: 'officialUrl', oldValue: ministries[code].officialUrl, newValue: u.officialUrl.trim(), reason: 'Admin corrected ministry officialUrl' });
        }
        if (u.councilsUrls !== undefined) {
          const cleaned = u.councilsUrls.map(x => x.trim()).filter(x => x !== '');
          const old = ministries[code].councilsUrls || (ministries[code].councilsUrl ? [ministries[code].councilsUrl] : []);
          corrections.push({ action: 'update_field', target: 'MINISTRIES', targetId: code, field: 'councilsUrls', oldValue: old, newValue: cleaned, reason: 'Admin updated councilsUrls' });
        }
        if (u.hasCouncils !== undefined) {
          corrections.push({ action: 'update_field', target: 'MINISTRIES', targetId: code, field: 'hasCouncils', oldValue: ministries[code].hasCouncils, newValue: u.hasCouncils, reason: 'Admin toggled hasCouncils' });
        }
      });

      try {
        const res = await fetch('/api/save-ministry-updates', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ exportedAt: new Date().toISOString(), corrections })
        });
        if (res.ok) {
          updates.forEach(code => {
            const u = ministryUpdates[code];
            if (!ministries[code]) ministries[code] = { name: code, code: code, color: 'var(--color-cao)' };
            if (u.officialUrl !== undefined) ministries[code].officialUrl = u.officialUrl.trim();
            if (u.councilsUrls !== undefined) ministries[code].councilsUrls = u.councilsUrls.map(x => x.trim()).filter(x => x !== '');
            if (u.hasCouncils !== undefined) ministries[code].hasCouncils = u.hasCouncils;
          });
          Object.keys(ministryUpdates).forEach(k => delete ministryUpdates[k]);
          renderMinistryList();
          alert('【サーバー経由】docs/data.json への直接保存が完了しました！');
          return;
        } else {
          const errData = await res.json().catch(() => ({}));
          console.warn('Server error on save-ministry-updates:', errData);
        }
      } catch (e) {
        console.warn('Network error on save-ministry-updates:', e);
      }

      if ('showOpenFilePicker' in window && window.location.protocol !== 'file:') {
        try {
          const [fileHandle] = await window.showOpenFilePicker({
            types: [{ description: 'JavaScript File', accept: { 'text/javascript': ['.js'] } }]
          });
          if (!fileHandle.name.endsWith('data.json')) {
            if (!confirm(`選択されたファイル (${fileHandle.name}) は data.json ではありませんが、続行しますか？`)) return;
          }
          const file = await fileHandle.getFile();
          let text = await file.text();

          updates.forEach(code => {
            const u = ministryUpdates[code];
            if (!ministries[code]) ministries[code] = { name: code, code: code, color: 'var(--color-cao)' };
            if (u.officialUrl !== undefined) ministries[code].officialUrl = u.officialUrl.trim();
            if (u.councilsUrls !== undefined) ministries[code].councilsUrls = u.councilsUrls.map(x => x.trim()).filter(x => x !== '');
            if (u.hasCouncils !== undefined) ministries[code].hasCouncils = u.hasCouncils;
          });

          const formattedMinistries = 'const MINISTRIES = ' + JSON.stringify(ministries, null, 2)
            .replace(/"([^"]+)":/g, '$1:')
            .replace(/"/g, "'") + ';';

          const updatedText = text.replace(/const MINISTRIES = \{[\s\S]*?\n\};/, formattedMinistries);

          const writable = await fileHandle.createWritable();
          await writable.write(updatedText);
          await writable.close();

          Object.keys(ministryUpdates).forEach(k => delete ministryUpdates[k]);
          renderMinistryList();
          alert('docs/data.json に直接反映・更新しました！');
          return;
        } catch (err) {
          if (err.name === 'AbortError' || err.name === 'NotAllowedError' || err.name === 'SecurityError') return;
        }
      }

      const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      await exportMinistryJson();
      if (isLocalhost) {
        alert('【サーバー保存エラー】localhost:8000 への保存処理が完了できませんでした。\nローカルサーバー (py admin/server.py) が正常に起動しているかご確認ください。\n\nバックアップとしてJSONを出力しました。');
      } else {
        alert('file:// 直開きのブラウザ制限によりファイル直接上書きが制限されているため、JSONを出力しました。\n\nターミナルで以下を実行すると docs/data.json に反映できます：\npy admin/apply_report.py admin/ministry_updates_*.json');
      }
      } finally {
        isSavingMinistryDirect = false;
      }
    };
    window.saveDirectToDataJs = window.saveDirectToDataJson;

    renderMinistryList();

    // ─── Render Rejected Councils Management (TAB 4) ───
    function renderRejectedList() {
      window.renderRejectedList = renderRejectedList;
      const listEl = document.getElementById('rejectedList');
      if (!listEl) return;

      const sEl = document.getElementById('filterRejectedSearch');
      const mEl = document.getElementById('filterRejectedMinistry');
      const cEl = document.getElementById('filterRejectedCategory');

      const searchTerm = sEl ? sEl.value.toLowerCase() : '';
      const fMinistry  = mEl ? mEl.value : '';
      const fCategory  = cEl ? cEl.value : '';

      let filtered = (rejectedCouncils || []).filter(c => {
        const minName = ministries[c.ministry] ? ministries[c.ministry].name : c.ministry;
        const text = `${c.name || ''} ${c.id || ''} ${minName || ''} ${c.ministry || ''} ${c.reason || ''}`.toLowerCase();
        if (searchTerm && !text.includes(searchTerm)) return false;
        if (fMinistry && c.ministry !== fMinistry) return false;
        if (fCategory && c.category !== fCategory) return false;
        return true;
      });

      const statTotalEl = document.getElementById('statRejectedTotal');
      const statFilteredEl = document.getElementById('statRejectedFiltered');
      const filterResultBadge = document.getElementById('filterRejectedResultBadge');

      if (statTotalEl) statTotalEl.textContent = (rejectedCouncils || []).length;
      if (statFilteredEl) statFilteredEl.textContent = `${filtered.length} 件`;
      if (filterResultBadge) filterResultBadge.textContent = `表示中: 却下会議体 ${filtered.length} 件`;

      if (filtered.length === 0) {
        listEl.innerHTML = `<div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <p>該当する却下会議体はありません</p>
        </div>`;
        return;
      }

      listEl.innerHTML = filtered.map((c, i) => {
        const minName = ministries[c.ministry] ? ministries[c.ministry].name : c.ministry;
        const catLabel = categories[c.category] || c.category || 'COUNCIL';
        const accentColor = getMinistryColor(c.ministry);
        const globalIdx = i + 1;
        const totalCount = rejectedCouncils.length;

        return `<div class="council-card verdict-rejected" style="--card-accent: ${accentColor};" id="rej-card-${c.id}">
          <div class="card-top">
            <div class="card-title-area">
              <div class="card-idx">#${globalIdx} / ${totalCount}</div>
              <div class="card-name">${escHtml(c.name || c.id)} <span class="meta-chip" style="color:#ef4444;border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.08);">✗ 却下済み</span></div>
              <div class="card-id">ID: ${c.id}</div>
            </div>
            <div class="card-actions">
              <button class="btn-revert" onclick="revertRejectedCouncil('${c.id}')">↩ 却下を解除（再レビューへ戻す）</button>
            </div>
          </div>
          <div class="card-meta">
            <span class="meta-chip"><span class="chip-icon">🏛</span> ${minName} (${c.ministry || '—'})</span>
            <span class="category-badge cat-${c.category || 'COUNCIL'}">${catLabel}</span>
            <span class="meta-chip"><span class="chip-icon">🔗</span> <a href="${escAttr(sanitizeUrl(c.officialUrl))}" target="_blank" rel="noopener">${truncateUrl(c.officialUrl, 55) || 'URLなし'}</a></span>
            <span class="meta-chip"><span class="chip-icon">📅</span> 却下日: ${c.rejectedAt || '—'}</span>
          </div>
          <div style="margin-top:0.75rem; padding:0.6rem 0.85rem; background:rgba(239,68,68,0.06); border:1px solid rgba(239,68,68,0.2); border-radius:var(--radius-md); font-size:0.8rem; color:#f87171;">
            <b>🚫 却下理由:</b> ${escHtml(c.reason || '手動却下')}
          </div>
        </div>`;
      }).join('');
    }

    window.revertRejectedCouncil = async function(id) {
      const idx = rejectedCouncils.findIndex(c => c.id === id);
      if (idx === -1) return;
      const target = rejectedCouncils[idx];
      if (!confirm(`「${target.name || target.id}」の却下を解除し、未レビュー状態に戻しますか？`)) return;

      // 却下リストから削除
      rejectedCouncils.splice(idx, 1);
      window.rejectedCouncils = rejectedCouncils;

      // 会議体リストのステータスを戻す
      if (verdicts[id]) {
        verdicts[id].verdict = null;
        saveSavedVerdicts(verdicts);
      } else {
        verdicts[id] = { verdict: null, notes: '', correctedUrl: '' };
        saveSavedVerdicts(verdicts);
      }

      if (!allCouncils.some(c => c.id === id)) {
        const restoredCouncil = {
          id: target.id,
          name: target.name,
          ministry: target.ministry,
          category: target.category || 'COUNCIL',
          officialUrl: target.officialUrl || '',
          isNew: true,
          status: 'pending'
        };
        allCouncils.push(restoredCouncil);
        window.allCouncils = allCouncils;
      }

      // サーバーAPI呼び出し: rejected_councils.json から削除 & docs/data.json の discoveredCouncils に復帰
      try {
        await fetch('/api/revert-rejected-council', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: target.id })
        });
      } catch (err) {
        console.warn('Failed to call /api/revert-rejected-council, falling back to saveRejectedCouncilsDirect:', err);
        await saveRejectedCouncilsDirect(true);
      }

      renderRejectedList();
      renderCards();
      alert(`「${target.name || target.id}」を再レビュー対象に戻しました。`);
    };

    window.saveRejectedCouncilsDirect = async function(silent = false) {
      try {
        const res = await fetch('/api/save-rejected-councils', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(rejectedCouncils)
        });
        if (res.ok) {
          if (!silent) alert('【サーバー経由】admin/rejected_councils.json への保存が完了しました！');
          return;
        }
      } catch (e) {
        console.warn('Network error on save-rejected-councils:', e);
      }
      if (!silent) {
        await saveJsonFile(rejectedCouncils, 'rejected_councils.json');
        alert('rejected_councils.json をエクスポートしました。');
      }
    };

    window.exportRejectedJson = async function() {
      await saveJsonFile(rejectedCouncils, `rejected_councils_${new Date().toISOString().slice(0,10)}.json`);
      alert(`${rejectedCouncils.length} 件の却下会議体データをJSONエクスポートしました。`);
    };

    if (document.getElementById('filterRejectedSearch')) document.getElementById('filterRejectedSearch').addEventListener('input', renderRejectedList);
    if (document.getElementById('filterRejectedMinistry')) document.getElementById('filterRejectedMinistry').addEventListener('change', renderRejectedList);
    if (document.getElementById('filterRejectedCategory')) document.getElementById('filterRejectedCategory').addEventListener('change', renderRejectedList);

    // ─── URL Liveness Check ───
    async function checkUrl(council, skipRender = false) {
      urlStatus[council.id] = 'checking';
      if (!skipRender) renderCards();
      
      if (!council.officialUrl) {
        urlStatus[council.id] = 'error';
        if (!skipRender) renderCards();
        return;
      }

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3500);
        await fetch(council.officialUrl, { mode: 'no-cors', signal: controller.signal });
        clearTimeout(timeoutId);
        urlStatus[council.id] = 'ok';
      } catch (e) {
        console.warn(`URL Check failed for ${council.id} (${council.officialUrl}):`, e);
        urlStatus[council.id] = 'error';
      }
      if (!skipRender) renderCards();
    }

    document.getElementById('btnCheckUrls').addEventListener('click', async () => {
      const btn = document.getElementById('btnCheckUrls');
      btn.disabled = true;
      const total = allCouncils.length;
      let completed = 0;
      btn.textContent = `🔗 チェック中 (0 / ${total} 件)…`;
      console.log(`Starting URL check for ${total} councils...`);

      try {
        const batchSize = 10;
        for (let i = 0; i < total; i += batchSize) {
          const batch = allCouncils.slice(i, i + batchSize);
          console.log(`Checking batch ${i} to ${i + batch.length} / ${total}`);
          
          // Promise.allSettled を使用してどれかがクラッシュしても他が完了するのを待つ
          await Promise.allSettled(batch.map(c => checkUrl(c, true)));
          
          completed += batch.length;
          btn.textContent = `🔗 チェック中 (${Math.min(completed, total)} / ${total} 件)…`;
          
          // renderCards でエラーが起きても止まらないようにする
          try {
            renderCards();
          } catch(re) {
            console.error('renderCards error during url check:', re);
          }
        }
        console.log('URL check completed successfully.');
      } catch (err) {
        console.error('URL Check Error:', err);
      } finally {
        btn.disabled = false;
        btn.textContent = '🔗 URL一括疎通チェック';
        try { renderCards(); } catch(e){}
      }
    });

    document.getElementById('btnLoadAiReport').addEventListener('click', async () => {
      const btn = document.getElementById('btnLoadAiReport');
      btn.disabled = true;
      btn.textContent = '🤖 読み込み中...';
      try {
        const response = await fetch('ai_verification_report.json');
        if (!response.ok) throw new Error('Report not found');
        const reportData = await response.json();
        
        let updateCount = 0;
        for (const [cId, aiResult] of Object.entries(reportData)) {
          if (!verdicts[cId]) verdicts[cId] = { verdict: null, notes: '', correctedUrl: '' };
          // 既に手動判定済みの場合は上書きしない
          if (verdicts[cId].verdict === 'approved' || verdicts[cId].verdict === 'rejected') continue;
          
          if (aiResult.verdict === 'approved' || aiResult.verdict === 'rejected') {
            verdicts[cId].verdict = aiResult.verdict;
            verdicts[cId].notes = `[AI判定] ${aiResult.reason || ''}`;
            updateCount++;
          }
        }
        
        alert(`AIによる判定結果を ${updateCount} 件ロードしました。`);
        renderCards();
      } catch (err) {
        console.error('Failed to load AI report:', err);
        alert('AIの判定結果 (ai_verification_report.json) の読み込みに失敗しました。先にバックエンドで python ai_autonomous_verifier.py を実行してください。');
      } finally {
        btn.disabled = false;
        btn.textContent = '🤖 AIの自動判定をロードする';
      }
    });

    document.getElementById('btnApproveAll').addEventListener('click', () => {
      const pending = allCouncils.filter(c => verdicts[c.id].verdict === null || verdicts[c.id].verdict === 'pending');
      if (pending.length === 0) { alert('未レビューの会議体はありません。'); return; }
      if (!confirm(`未レビューの ${pending.length} 件を全て承認しますか？`)) return;
      
      const btn = document.getElementById('btnApproveAll');
      const originalText = btn.textContent;
      btn.textContent = '🔄 処理中...';
      btn.disabled = true;

      // requestAnimationFrame でUI描画をブロックしないようにする
      requestAnimationFrame(() => {
        pending.forEach(c => {
          if (!verdicts[c.id]) verdicts[c.id] = { verdict: null, notes: '', correctedUrl: '' };
          verdicts[c.id].verdict = 'approved';
          
          const card = document.getElementById(`card-${c.id}`);
          if (card) {
            card.classList.remove('verdict-approved', 'verdict-rejected');
            card.classList.add('verdict-approved');
            const radios = card.querySelectorAll(`input[name="verdict-${c.id}"]`);
            radios.forEach(r => { r.checked = (r.value === 'approved'); });
            
            const filterV = document.getElementById('filterVerdict');
            if (filterV && filterV.value === 'pending') {
              card.style.display = 'none';
            }
          }
        });
        saveSavedVerdicts(verdicts);
        if (typeof updateStats === 'function') updateStats();
        
        btn.textContent = originalText;
        btn.disabled = false;
      });
    });

    // ─── Save Council to docs/data.json (including new discovered councils) ───
    let isSavingCouncilDirect = false;
    window.saveCouncilDirectToDataJson = async function() {
      if (isSavingCouncilDirect) return;
      isSavingCouncilDirect = true;
      const btn = document.getElementById('btnSaveCouncilDirect');
      let origText = '';
      if (btn) { origText = btn.textContent; btn.disabled = true; btn.textContent = '💾 保存中…'; }
      try {
      const approvedCouncils = allCouncils.filter(c => verdicts[c.id] && verdicts[c.id].verdict === 'approved');
      const corrections = [];

      allCouncils.forEach(c => {
        const v = verdicts[c.id];
        if (v && v.verdict === 'approved') {
          const finalName = (v.correctedName && v.correctedName.trim() !== '') ? v.correctedName.trim() : c.name;
          const finalUrl = (v.correctedUrl && v.correctedUrl.trim() !== '') ? v.correctedUrl.trim() : c.officialUrl;

          // 新規検出された会議体で baseCouncils に存在しないものは追加
          if (c.isNew && !baseCouncils.some(bc => bc.id === c.id)) {
            corrections.push({
              action: 'add_council',
              council: {
                id: c.id,
                name: finalName,
                ministry: c.ministry,
                category: c.category,
                officialUrl: finalUrl
              }
            });
          } else {
            if (v.correctedUrl && v.correctedUrl.trim() !== '') {
              corrections.push({
                action: 'update_field',
                target: 'COUNCILS',
                targetId: c.id,
                field: 'officialUrl',
                oldValue: c.officialUrl,
                newValue: v.correctedUrl.trim(),
                reason: 'Admin corrected council top page URL'
              });
            }
            if (v.correctedName && v.correctedName.trim() !== '' && v.correctedName.trim() !== c.name) {
              corrections.push({
                action: 'update_field',
                target: 'COUNCILS',
                targetId: c.id,
                field: 'name',
                oldValue: c.name,
                newValue: v.correctedName.trim(),
                reason: 'Admin corrected council name'
              });
            }
          }
        } else if (v && v.verdict === 'rejected' && baseCouncils.some(bc => bc.id === c.id)) {
          corrections.push({
            action: 'remove_council',
            targetId: c.id,
            reason: 'Admin rejected council'
          });
        }

        const cMeetings = meetingMap[c.id] || [];
        cMeetings.forEach(m => {
          const mCorr = meetingUrlCorrections[m.id];
          if (mCorr && mCorr.trim() !== '') {
            corrections.push({
              action: 'update_field',
              target: 'MEETINGS',
              targetId: m.id,
              field: 'officialUrl',
              oldValue: m.officialUrl,
              newValue: mCorr.trim(),
              reason: `Admin corrected meeting page URL for ${m.id}`
            });
          }
        });
      });

      if (corrections.length === 0) {
        alert('変更または新規承認された会議体情報がありません。');
        return;
      }

      const report = {
        _format: 'pmhub-verification-report-v2',
        _description: '会議体・会議ページURL更新および新規会議体追加',
        exportedAt: new Date().toISOString(),
        targetFile: 'docs/data.json',
        corrections: corrections
      };

      function applyCouncilInMemory() {
        corrections.forEach(corr => {
          if (corr.action === 'add_council' && corr.council) {
            const added = corr.council;
            const target = allCouncils.find(c => c.id === added.id);
            if (target) {
              target.isNew = false;
              if (!baseCouncils.some(bc => bc.id === added.id)) {
                baseCouncils.push(added);
              }
            }
          } else if (corr.target === 'COUNCILS') {
            const targetCouncil = allCouncils.find(c => c.id === corr.targetId);
            if (targetCouncil) targetCouncil.officialUrl = corr.newValue;
            if (verdicts[corr.targetId]) verdicts[corr.targetId].correctedUrl = '';
          } else if (corr.target === 'MEETINGS') {
            const targetMeeting = meetings.find(m => m.id === corr.targetId);
            if (targetMeeting) targetMeeting.officialUrl = corr.newValue;
            delete meetingUrlCorrections[corr.targetId];
          }
        });
        saveSavedVerdicts(verdicts);
        renderCards();
      }

      try {
        const res = await fetch('/api/save-verification-report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(report)
        });
        if (res.ok) {
          try {
            applyCouncilInMemory();
          } catch(errMem) {
            console.warn('applyCouncilInMemory warning:', errMem);
          }
          alert('【サーバー経由】docs/data.json への直接保存が完了しました！');
          return;
        } else {
          const errData = await res.json().catch(() => ({}));
          console.warn('Server error on save-verification-report:', errData);
        }
      } catch (e) {
        console.warn('Network error on save-verification-report:', e);
      }

      if ('showOpenFilePicker' in window && window.location.protocol !== 'file:') {
        try {
          const [fileHandle] = await window.showOpenFilePicker({
            types: [{ description: 'JavaScript File', accept: { 'text/javascript': ['.js'] } }]
          });
          if (!fileHandle.name.endsWith('data.json')) {
            if (!confirm(`選択されたファイル (${fileHandle.name}) は data.json ではありませんが、続行しますか？`)) return;
          }
          const file = await fileHandle.getFile();
          let text = await file.text();

          corrections.forEach(corr => {
            if (corr.action === 'update_field') {
              const pattern = new RegExp(`(id:\\s*'${corr.targetId}'[\\s\\S]*?officialUrl:\\s*')[^']+(')`);
              text = text.replace(pattern, `$1${corr.newValue}$2`);
            } else if (corr.action === 'add_council' && corr.council) {
              const added = corr.council;
              if (!text.includes(`id: '${added.id}'`)) {
                const cFormatted = `  {\n    id: '${added.id}',\n    name: '${added.name.replace(/'/g, "\\'")}',\n    ministry: '${added.ministry}',\n    category: '${added.category}',\n    officialUrl: '${added.officialUrl}'\n  },\n];\nconst MEETINGS`;
                text = text.replace(/\n\];[\s\n]*const MEETINGS/, `,\n${cFormatted}`);
              }
            }
          });

          const writable = await fileHandle.createWritable();
          await writable.write(text);
          await writable.close();

          applyCouncilInMemory();
          alert('docs/data.json に直接反映・更新しました！');
          return;
        } catch (err) {
          if (err.name === 'AbortError' || err.name === 'NotAllowedError' || err.name === 'SecurityError') return;
        }
      }

      const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      await saveJsonFile(report, `verification_report_${new Date().toISOString().slice(0,10)}.json`);
      if (isLocalhost) {
        alert('【サーバー保存エラー】localhost:8000 への保存処理が完了できませんでした。\nローカルサーバー (py admin/server.py) が正常に起動しているかご確認ください。\n\nバックアップとしてJSONを出力しました。');
      } else {
        alert('file:// 直開きのブラウザ制限によりファイル直接上書きが制限されているため、JSONを出力しました。\n\nターミナルで以下を実行すると docs/data.json に反映できます：\npy admin/apply_report.py admin/verification_report_*.json');
      }
      } finally {
        isSavingCouncilDirect = false;
        if (btn) { btn.disabled = false; btn.textContent = origText || '💾 docs/data.json に直接反映'; }
      }
    };
    window.saveCouncilDirectToDataJs = window.saveCouncilDirectToDataJson;

    document.getElementById('btnExportJson').addEventListener('click', async () => {
      const approvedCouncils = allCouncils.filter(c => verdicts[c.id] && verdicts[c.id].verdict === 'approved');

      if (approvedCouncils.length === 0) {
        alert('承認済の会議体がありません。先に会議体を承認してください。');
        return;
      }

      const corrections = [];

      allCouncils.forEach(c => {
        const v = verdicts[c.id];

        if (v && v.verdict === 'approved') {
          const finalName = (v.correctedName && v.correctedName.trim() !== '') ? v.correctedName.trim() : c.name;
          const finalUrl = (v.correctedUrl && v.correctedUrl.trim() !== '') ? v.correctedUrl.trim() : c.officialUrl;

          if (c.isNew && !baseCouncils.some(bc => bc.id === c.id)) {
            corrections.push({
              action: 'add_council',
              council: {
                id: c.id,
                name: finalName,
                ministry: c.ministry,
                category: c.category,
                officialUrl: finalUrl
              }
            });
          } else {
            if (v.correctedUrl && v.correctedUrl.trim() !== '') {
              corrections.push({
                action: 'update_field',
                target: 'COUNCILS',
                targetId: c.id,
                field: 'officialUrl',
                oldValue: c.officialUrl,
                newValue: v.correctedUrl.trim(),
                reason: 'Admin corrected council top page URL'
              });
            }
            if (v.correctedName && v.correctedName.trim() !== '' && v.correctedName.trim() !== c.name) {
              corrections.push({
                action: 'update_field',
                target: 'COUNCILS',
                targetId: c.id,
                field: 'name',
                oldValue: c.name,
                newValue: v.correctedName.trim(),
                reason: 'Admin corrected council name'
              });
            }
          }
        } else if (v && v.verdict === 'rejected' && baseCouncils.some(bc => bc.id === c.id)) {
          corrections.push({
            action: 'remove_council',
            targetId: c.id,
            reason: 'Admin rejected council'
          });
        }

        const cMeetings = meetingMap[c.id] || [];
        cMeetings.forEach(m => {
          const mCorr = meetingUrlCorrections[m.id];
          if (mCorr && mCorr.trim() !== '') {
            corrections.push({
              action: 'update_field',
              target: 'MEETINGS',
              targetId: m.id,
              field: 'officialUrl',
              oldValue: m.officialUrl,
              newValue: mCorr.trim(),
              reason: `Admin corrected meeting page URL for ${m.id}`
            });
          }
        });
      });

      const report = {
        _format: 'pmhub-verification-report-v2',
        _description: 'AI Agent向け検証レポート。corrections配列の各エントリをdocs/data.jsonに適用してください。',
        exportedAt: new Date().toISOString(),
        targetFile: 'docs/data.json',
        summary: {
          totalApproved: approvedCouncils.length,
          totalCorrections: corrections.length
        },
        corrections: corrections
      };

      await saveJsonFile(report, `verification_report_${new Date().toISOString().slice(0,10)}.json`);
      alert(`${approvedCouncils.length} 件の承認済会議体の検証データをJSONエクスポートしました。`);
    });

    // ─── Filter Listeners ───
    document.getElementById('filterSearch').addEventListener('input', renderCards);
    document.getElementById('filterMinistry').addEventListener('change', renderCards);
    document.getElementById('filterCategory').addEventListener('change', renderCards);
    document.getElementById('filterVerdict').addEventListener('change', renderCards);

    // デフォルトの絞り込み条件として「未レビュー (pending)」を設定
    const filterVerdictEl = document.getElementById('filterVerdict');
    if (filterVerdictEl) {
      filterVerdictEl.value = 'pending';
    }

    renderCards();

    // ─── 1. Council Discovery Crawler Logic ───
    const btnStartDiscovery = document.getElementById('btnStartDiscovery');
    const discoveryProgressFill = document.getElementById('discoveryProgressFill');
    const discoveryTerminalLogs = document.getElementById('discoveryTerminalLogs');
    const discoverySummaryBar = document.getElementById('discoverySummaryBar');
    const discoveryResultCount = document.getElementById('discoveryResultCount');

    let currentKeywords = {
      commonKeywords: [],
      commonExcludeKeywords: [],
      ministryAddKeywords: {},
      ministryExcludeKeywords: {}
    };

    async function loadKeywordConfig() {
      try {
        const res = await fetch('/api/discovery-keywords');
        if (res.ok) {
          currentKeywords = await res.json();
          renderKeywordsUI();
          return;
        }
      } catch(e) {}
      const saved = localStorage.getItem('pmhub_discovery_keywords');
      if (saved) {
        try { currentKeywords = JSON.parse(saved); } catch(e) {}
      } else {
        currentKeywords = {
          commonKeywords: ["審議会", "検討会", "委員会", "部会", "分科会", "懇談会", "ワーキンググループ", "WG", "研究会", "プロジェクトチーム", "タスクフォース", "円卓会議", "会議"],
          commonExcludeKeywords: ["過去", "名簿", "委員名簿", "議事録", "議事要旨", "資料一覧", "配付資料", "法令", "設置根拠", "傍聴", "更新履歴", "PDF", "Excel"],
          ministryAddKeywords: {},
          ministryExcludeKeywords: {}
        };
      }
      renderKeywordsUI();
    }

    function renderKeywordsUI() {
      document.getElementById('kwCommonInput').value = (currentKeywords.commonKeywords || []).join(', ');
      document.getElementById('kwExcludeInput').value = (currentKeywords.commonExcludeKeywords || []).join(', ');
      const selMin = document.getElementById('kwMinistrySelect').value;
      if (selMin) {
        document.getElementById('kwMinAddInput').value = (currentKeywords.ministryAddKeywords && currentKeywords.ministryAddKeywords[selMin] || []).join(', ');
        document.getElementById('kwMinExcInput').value = (currentKeywords.ministryExcludeKeywords && currentKeywords.ministryExcludeKeywords[selMin] || []).join(', ');
      } else {
        document.getElementById('kwMinAddInput').value = '';
        document.getElementById('kwMinExcInput').value = '';
      }
    }

    document.getElementById('kwMinistrySelect').addEventListener('change', () => {
      const selMin = document.getElementById('kwMinistrySelect').value;
      if (selMin) {
        document.getElementById('kwMinAddInput').value = (currentKeywords.ministryAddKeywords && currentKeywords.ministryAddKeywords[selMin] || []).join(', ');
        document.getElementById('kwMinExcInput').value = (currentKeywords.ministryExcludeKeywords && currentKeywords.ministryExcludeKeywords[selMin] || []).join(', ');
      }
    });

    document.getElementById('btnSaveKeywords').addEventListener('click', async () => {
      const commonKws = document.getElementById('kwCommonInput').value.split(',').map(s => s.trim()).filter(s => s);
      const excKws = document.getElementById('kwExcludeInput').value.split(',').map(s => s.trim()).filter(s => s);
      const selMin = document.getElementById('kwMinistrySelect').value;
      if (selMin) {
        const addKws = document.getElementById('kwMinAddInput').value.split(',').map(s => s.trim()).filter(s => s);
        const minExcKws = document.getElementById('kwMinExcInput').value.split(',').map(s => s.trim()).filter(s => s);
        if (!currentKeywords.ministryAddKeywords) currentKeywords.ministryAddKeywords = {};
        if (!currentKeywords.ministryExcludeKeywords) currentKeywords.ministryExcludeKeywords = {};
        currentKeywords.ministryAddKeywords[selMin] = addKws;
        currentKeywords.ministryExcludeKeywords[selMin] = minExcKws;
      }
      currentKeywords.commonKeywords = commonKws;
      currentKeywords.commonExcludeKeywords = excKws;

      try {
        const res = await fetch('/api/save-discovery-keywords', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentKeywords)
        });
        if (res.ok) {
          alert('キーワード設定を保存しました。');
          return;
        }
      } catch(e) {}
      localStorage.setItem('pmhub_discovery_keywords', JSON.stringify(currentKeywords));
      alert('キーワード設定をブラウザに保存しました。');
    });

    loadKeywordConfig();

    

    

    // ─── 2. Meeting Crawler Logic (Tab 1 Block 2) ───
    const crawlBtn = document.getElementById('adminStartCrawlBtn');
    const progressFill = document.getElementById('adminProgressFill');
    const logs = document.getElementById('adminTerminalLogs');
    const aiToggleBtn = document.getElementById('adminAiToggleBtn');
    const aiToggleLabel = document.getElementById('adminAiToggleLabel');
    const jsonInspector = document.getElementById('adminJsonInspector');

    let aiEnabled = localStorage.getItem('pmhub_enable_ai_summary') === 'true';

    function updateAiUI() {
      if (aiEnabled) {
        aiToggleLabel.textContent = '状態: ON (有効)';
        aiToggleBtn.style.background = 'rgba(16, 185, 129, 0.2)';
        aiToggleBtn.style.borderColor = '#10b981';
        aiToggleBtn.style.color = '#10b981';
      } else {
        aiToggleLabel.textContent = '状態: OFF (抑止中)';
        aiToggleBtn.style.background = 'rgba(255, 255, 255, 0.08)';
        aiToggleBtn.style.borderColor = 'var(--border-color)';
        aiToggleBtn.style.color = 'var(--text-secondary)';
      }
    }
    updateAiUI();

    aiToggleBtn.addEventListener('click', () => {
      aiEnabled = !aiEnabled;
      localStorage.setItem('pmhub_enable_ai_summary', aiEnabled);
      updateAiUI();
      alert(`AI要約機能を ${aiEnabled ? 'ON (有効)' : 'OFF (無効)'} に設定しました。`);
    });

    const llmToggleBtn = document.getElementById('adminLlmToggleBtn');
    const llmToggleLabel = document.getElementById('adminLlmToggleLabel');
    let llmEnabled = true; // Default

    async function loadLlmConfig() {
      try {
        const res = await fetch('/api/get-crawler-config');
        if (res.ok) {
          const config = await res.json();
          llmEnabled = config.llm_mode !== false; // true unless explicitly false
        }
      } catch (e) {
        console.warn('Could not load crawler config', e);
      }
      updateLlmUI();
    }

    function updateLlmUI() {
      if (llmEnabled) {
        llmToggleLabel.textContent = '状態: ON (LLM抽出)';
        llmToggleBtn.style.background = 'rgba(16, 185, 129, 0.2)';
        llmToggleBtn.style.borderColor = '#10b981';
        llmToggleBtn.style.color = '#10b981';
      } else {
        llmToggleLabel.textContent = '状態: OFF (既存ルール抽出)';
        llmToggleBtn.style.background = 'rgba(255, 255, 255, 0.08)';
        llmToggleBtn.style.borderColor = 'var(--border-color)';
        llmToggleBtn.style.color = 'var(--text-secondary)';
      }
    }

    llmToggleBtn.addEventListener('click', async () => {
      llmEnabled = !llmEnabled;
      updateLlmUI();
      try {
        const res = await fetch('/api/save-crawler-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ llm_mode: llmEnabled })
        });
        if (!res.ok) throw new Error('Network error');
        alert(`LLM抽出モードを ${llmEnabled ? 'ON' : 'OFF'} に設定しました。次回クローラー実行時から適用されます。`);
      } catch (e) {
        alert('設定の保存に失敗しました。ローカルサーバーが起動しているか確認してください。');
        llmEnabled = !llmEnabled; // rollback
        updateLlmUI();
      }
    });

    loadLlmConfig();

    function updateDataJsonInspector() {
      fetch('../docs/data.json?t=' + new Date().getTime())
        .then(res => res.json())
        .then(data => {
          const summary = {
            lastCrawlTime: data.lastCrawlTime || '未実行',
            crawlerConfig: data.crawlerConfig || { llm_mode: false },
            totalCouncils: (data.councils || []).length,
            totalMeetings: (data.meetings || []).length,
            discoveryKeywordsCount: (data.discoveryKeywords?.commonKeywords || []).length,
            autoBackupsLocation: "admin/backups/"
          };
          if (jsonInspector) jsonInspector.textContent = JSON.stringify(summary, null, 2);
          
          // バックアップステータスバッジの更新
          if (window.loadBackupStatus) window.loadBackupStatus();

          // ヘッダーやステータスバーの最終同期日時を同期
          const syncLabels = document.querySelectorAll('.last-sync-time, #lastSyncTimeLabel');
          syncLabels.forEach(el => {
            el.textContent = data.lastCrawlTime || '未実行';
          });
        })
        .catch(err => {
          if (jsonInspector) jsonInspector.textContent = '// docs/data.json の読み込み完了';
        });
    }
    updateDataJsonInspector();
    if (window.loadBackupStatus) window.loadBackupStatus();

    if (crawlBtn) {
      crawlBtn.onclick = function(e) {
        if (e) e.preventDefault();
        window.startMeetingCrawl();
      };
      crawlBtn.addEventListener('click', function(e) {
        if (e) e.preventDefault();
        window.startMeetingCrawl();
      });
    }

    // ─── 3. Crawl Status Dashboard ───
    function renderCrawlStatusDashboard() {
      if (!window.COUNCILS || !Array.isArray(window.COUNCILS)) return;
      
      let successCount = 0;
      let partialCount = 0;
      let failedCount = 0;
      let neverCount = 0;
      
      const errorList = [];
      
      window.COUNCILS.forEach(council => {
        const status = council.crawlStatus || { result: 'never' };
        
        if (status.result === 'success') {
          successCount++;
        } else if (status.result === 'partial') {
          partialCount++;
        } else if (status.result === 'failed') {
          failedCount++;
          errorList.push({ council, status });
        } else {
          neverCount++;
          errorList.push({ council, status: { result: 'never', lastAttempt: '未取得', failureReason: 'クロール未実行' } });
        }
      });
      
      const elSuccess = document.getElementById('statCrawlSuccess');
      if (elSuccess) elSuccess.textContent = successCount;
      const elPartial = document.getElementById('statCrawlPartial');
      if (elPartial) elPartial.textContent = partialCount;
      const elFailed = document.getElementById('statCrawlFailed');
      if (elFailed) elFailed.textContent = failedCount;
      const elNever = document.getElementById('statCrawlNever');
      if (elNever) elNever.textContent = neverCount;
      
      const container = document.getElementById('crawlErrorListContainer');
      if (container) {
        if (errorList.length === 0) {
          container.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-muted);">失敗・未実行の会議体はありません。</div>';
        } else {
          container.innerHTML = errorList.map(item => {
            const failuresCount = item.status.consecutiveFailures ? ` (連続失敗: ${item.status.consecutiveFailures}回)` : '';
            return `
              <div class="crawl-error-item">
                <div class="crawl-error-title">${item.council.name}</div>
                <div class="crawl-error-meta">🏢 ${item.council.ministry} | 🕒 最終試行: ${item.status.lastAttempt || '未取得'}${failuresCount}</div>
                <div class="crawl-error-reason">⚠️ ${item.status.failureReason || '原因不明'}</div>
              </div>
            `;
          }).join('');
        }
      }
    }
    
    const toggleErrorBtn = document.getElementById('toggleCrawlErrorList');
    const toggleErrorIcon = document.getElementById('toggleCrawlErrorIcon');
    const errorContainer = document.getElementById('crawlErrorListContainer');
    if (toggleErrorBtn && errorContainer && toggleErrorIcon) {
      toggleErrorBtn.addEventListener('click', () => {
        if (errorContainer.style.display === 'none') {
          errorContainer.style.display = 'block';
          toggleErrorIcon.innerHTML = '<polyline points="18 15 12 9 6 15"/>';
        } else {
          errorContainer.style.display = 'none';
          toggleErrorIcon.innerHTML = '<polyline points="6 9 12 15 18 9"/>';
        }
      });
    }

    renderCrawlStatusDashboard();

    // 全タブの初回データ一括描画を確実に実行
    if (typeof renderCards === 'function') renderCards();
    if (typeof renderMeetingsList === 'function') renderMeetingsList();
    if (typeof renderRejectedList === 'function') renderRejectedList();
    if (typeof renderMinistryList === 'function') renderMinistryList();

    // タブボタンへのイベントリスナー安全設定
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', function(e) {
        const tabId = this.getAttribute('data-tab') || (this.getAttribute('onclick') || '').match(/switchTab\(['"]([^'"]+)['"]/)?.[1];
        if (tabId) {
          switchTab(tabId, this);
        }
      });
    });

    const initHash = (window.location && window.location.hash ? window.location.hash : '').replace('#', '');
    if (initHash === 'ministries') switchTab('tab-ministries');
    else if (initHash === 'meetings') switchTab('tab-meetings');
    else if (initHash === 'councils') switchTab('tab-councils');
    else if (initHash === 'rejected') switchTab('tab-rejected');
    else if (initHash === 'crawler') switchTab('tab-crawler');
  });
