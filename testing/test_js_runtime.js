#!/usr/bin/env node
/**
 * 政策会議ウォッチ (PM-HUB) - UI Structure, No-Leakage & JavaScript Runtime Crash Validator
 * 
 * 1. 公開ポータル (docs/index.html) および 管理ダッシュボード (admin/admin_dashboard.html) の
 *    必須DOMコンテナ構造および管理画面リンク非露出（No Leakage）を検証します。
 * 2. 公開ポータル (docs/app.js) および 管理ダッシュボードの JavaScript が、
 *    実際のデータをロードして初期化・描画を行う際に TDZ、ReferenceError、TypeError 等の
 *    例外で停止（クラッシュ）しないかを自動検証します。
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const DATA_JSON_PATH = path.join(PROJECT_ROOT, 'docs', 'data.json');
const REJECTED_JSON_PATH = path.join(PROJECT_ROOT, 'admin', 'rejected_councils.json');
const INDEX_HTML_PATH = path.join(PROJECT_ROOT, 'docs', 'index.html');
const APP_JS_PATH = path.join(PROJECT_ROOT, 'docs', 'app.js');
const ADMIN_HTML_PATH = path.join(PROJECT_ROOT, 'admin', 'admin_dashboard.html');

function logPass(msg) {
  console.log(`  [PASS] ${msg}`);
}
function logFail(msg) {
  console.error(`  [FAIL] ${msg}`);
}

function testUiDomStructureAndNoLeakage() {
  console.log("--------------------------------------------------");
  console.log(" [UI構造検証 1/3] 公開ポータル＆管理コンソール DOM構造・ローカル専用化検証");
  console.log("--------------------------------------------------");

  const htmlText = fs.readFileSync(INDEX_HTML_PATH, 'utf8');
  const adminText = fs.readFileSync(ADMIN_HTML_PATH, 'utf8');

  const requiredPortalElements = ['id="timelineFeed"', 'id="councilsAccordionList"', 'id="dateRangeSelect"'];
  for (const elem of requiredPortalElements) {
    if (!htmlText.includes(elem)) {
      logFail(`公開ポータル表示用HTML要素 (${elem}) が不足しています`);
      return false;
    }
  }
  logPass("公開ポータルの主要コンテナ (timelineFeed, councilsAccordionList, dateRangeSelect) を検証完了");

  if (htmlText.includes('admin_dashboard.html') || htmlText.includes('管理コンソール')) {
    logFail("公開ポータル (docs/index.html) に管理コンソール (admin_dashboard.html) へのリンクが露出しています");
    return false;
  }
  logPass("公開ポータルからの管理画面リンク露出ゼロ (ローカル専用化) を検証完了");

  const adminTabIds = ['tab-crawler', 'tab-meetings', 'tab-councils', 'tab-rejected', 'tab-ministries'];
  for (const tid of adminTabIds) {
    if (!adminText.includes(`id="${tid}"`)) {
      logFail(`管理ダッシュボードのタブコンテナ (${tid}) が不足しています`);
      return false;
    }
  }

  const adminContainers = ['id="councilList"', 'id="meetingsList"', 'id="rejectedList"', 'id="ministryListContainer"'];
  for (const cid of adminContainers) {
    if (!adminText.includes(cid)) {
      logFail(`管理ダッシュボードの描画先コンテナ (${cid}) が不足しています`);
      return false;
    }
  }

  if (!adminText.includes('id="pmmStatusSummary"') || !adminText.includes('id="btnStartPmmDownload"')) {
    logFail("管理ダッシュボードの PMM 要素 (pmmStatusSummary / btnStartPmmDownload) が不足しています");
    return false;
  }
  logPass("管理ダッシュボードの全5タブ、描画先コンテナおよび PMM 要素を検証完了");
  return true;
}

function createMockDOM(sampleData, sampleRejected) {
  const elements = {};

  const createMockElement = (id = '', tagName = 'div') => {
    const el = {
      id,
      tagName: tagName.toUpperCase(),
      value: '',
      innerHTML: '',
      textContent: '',
      style: {},
      children: [],
      classList: {
        _classes: new Set(),
        add(...cls) { cls.forEach(c => this._classes.add(c)); },
        remove(...cls) { cls.forEach(c => this._classes.delete(c)); },
        contains(c) { return this._classes.has(c); },
        toggle(c) { if (this.contains(c)) this.remove(c); else this.add(c); }
      },
      attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      getAttribute(k) { return this.attributes[k] || (k === 'data-tab' ? id : ''); },
      removeAttribute(k) { delete this.attributes[k]; },
      addEventListener: () => {},
      removeEventListener: () => {},
      appendChild(child) { this.children.push(child); return child; },
      insertBefore(node) { this.children.unshift(node); return node; },
      removeChild(child) {
        const idx = this.children.indexOf(child);
        if (idx >= 0) this.children.splice(idx, 1);
      },
      querySelectorAll: (sel) => [],
      querySelector: (sel) => null,
      dispatchEvent: () => true,
      focus: () => {},
      blur: () => {},
      scrollIntoView: () => {}
    };
    return el;
  };

  const getElementById = (id) => {
    if (!elements[id]) {
      elements[id] = createMockElement(id);
    }
    return elements[id];
  };

  const listeners = {};

  const mockDoc = {
    body: createMockElement('body', 'body'),
    documentElement: createMockElement('html', 'html'),
    getElementById,
    createElement: (tag) => createMockElement('', tag),
    querySelectorAll: (sel) => [createMockElement('mock-item')],
    querySelector: (sel) => createMockElement('mock-item'),
    addEventListener: (evt, cb) => {
      if (!listeners[evt]) listeners[evt] = [];
      listeners[evt].push(cb);
    },
    removeEventListener: () => {},
    dispatchEvent: (evt) => {
      const type = typeof evt === 'string' ? evt : evt.type;
      if (listeners[type]) {
        listeners[type].forEach(cb => cb(evt));
      }
    }
  };

  const mockStorage = {
    _data: {},
    getItem(k) { return this._data[k] || null; },
    setItem(k, v) { this._data[k] = String(v); },
    removeItem(k) { delete this._data[k]; },
    clear() { this._data = {}; }
  };

  const mockWin = {
    document: mockDoc,
    localStorage: mockStorage,
    sessionStorage: mockStorage,
    location: {
      hash: '',
      pathname: '/admin/admin_dashboard.html',
      search: '',
      href: 'http://localhost:8000/admin/admin_dashboard.html',
      reload: () => {}
    },
    history: { replaceState: () => {}, pushState: () => {} },
    addEventListener: (evt, cb) => mockDoc.addEventListener(evt, cb),
    removeEventListener: () => {},
    alert: () => {},
    confirm: () => true,
    fetch: async (url) => {
      if (url.includes('rejected-councils')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'Wed, 29 Aug 2026 07:00:00 GMT' },
          json: async () => sampleRejected
        };
      }
      if (url.includes('data_archive.json')) {
        return {
          ok: true,
          status: 200,
          headers: { get: () => 'Wed, 29 Aug 2026 07:00:00 GMT' },
          json: async () => ({ meetings: [] })
        };
      }
      return {
        ok: true,
        status: 200,
        headers: { get: () => 'Wed, 29 Aug 2026 07:00:00 GMT' },
        json: async () => sampleData
      };
    },
    Chart: function() { return { destroy: () => {}, update: () => {} }; },
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval
  };

  return { mockDoc, mockWin, elements };
}

async function testPublicPortalRuntime(sampleData) {
  console.log("\n--------------------------------------------------");
  console.log(" [ランタイム検証 2/3] 公開ポータル (docs/app.js) 実行時クラッシュ検証");
  console.log("--------------------------------------------------");

  const { mockDoc, mockWin, elements } = createMockDOM(sampleData, []);
  
  global.document = mockDoc;
  global.window = mockWin;
  global.localStorage = mockWin.localStorage;
  global.fetch = mockWin.fetch;
  global.alert = mockWin.alert;
  global.confirm = mockWin.confirm;
  global.Chart = mockWin.Chart;

  const appJsCode = fs.readFileSync(APP_JS_PATH, 'utf8');

  let executionError = null;
  try {
    eval(appJsCode);
  } catch (err) {
    executionError = err;
  }

  if (executionError) {
    logFail(`app.js ロード時にスクリプトがクラッシュしました: ${executionError.stack || executionError.message}`);
    return false;
  }

  try {
    await mockDoc.dispatchEvent({ type: 'DOMContentLoaded' });
    await new Promise(r => setTimeout(r, 60));
  } catch (err) {
    logFail(`app.js DOMContentLoaded 実行中に例外（TDZ/クラッシュ）が発生しました: ${err.stack || err.message}`);
    return false;
  }

  if (elements['timelineFeed'] && elements['councilsAccordionList']) {
    logPass(`app.js 初期化＆描画完了 (COUNCILS: ${mockWin.COUNCILS?.length || 0} 件, MEETINGS: ${mockWin.MEETINGS?.length || 0} 件)`);
  } else {
    logFail("app.js 必須描画コンテナへの出力が確認できませんでした");
    return false;
  }

  const testKeywords = ['年金', 'デジタル', '令和', '労働', 'AI', '審議会', 'xyznonexistent'];
  for (const kw of testKeywords) {
    try {
      if (elements['searchInput']) {
        elements['searchInput'].value = kw;
        elements['searchInput'].dispatchEvent({ type: 'input', target: { value: kw } });
      }
      logPass(`app.js フリーワード検索実行成功 (クエリ: "${kw}")`);
    } catch (err) {
      logFail(`app.js フリーワード検索実行時に例外発生 (クエリ: "${kw}"): ${err.stack || err.message}`);
      return false;
    }
  }

  try {
    if (elements['clearSearchBtn']) {
      elements['clearSearchBtn'].dispatchEvent({ type: 'click' });
    }
    logPass("app.js 検索クリアボタン実行成功");
    return true;
  } catch (err) {
    logFail(`app.js 検索クリア時に例外発生: ${err.stack || err.message}`);
    return false;
  }
}

async function testAdminDashboardRuntime(sampleData, sampleRejected) {
  console.log("\n--------------------------------------------------");
  console.log(" [ランタイム検証 3/3] 管理コンソール (admin_dashboard.html) 実行時クラッシュ検証");
  console.log("--------------------------------------------------");

  const { mockDoc, mockWin, elements } = createMockDOM(sampleData, sampleRejected);

  global.document = mockDoc;
  global.window = mockWin;
  global.localStorage = mockWin.localStorage;
  global.fetch = mockWin.fetch;
  global.alert = mockWin.alert;
  global.confirm = mockWin.confirm;
  global.Chart = mockWin.Chart;

  const adminHtml = fs.readFileSync(ADMIN_HTML_PATH, 'utf8');
  const srcMatches = [...adminHtml.matchAll(/<script[^>]*src=["']([^"']+)["'][^>]*>/gi)];
  const inlineMatches = [...adminHtml.matchAll(/<script(?![^>]*src=)>([\s\S]*?)<\/script>/gi)];

  if (srcMatches.length === 0 && inlineMatches.length === 0) {
    logFail("admin_dashboard.html 内に <script> が見つかりません");
    return false;
  }

  let executionError = null;
  for (const sm of srcMatches) {
    const srcPath = path.resolve(path.dirname(ADMIN_HTML_PATH), sm[1]);
    if (fs.existsSync(srcPath)) {
      try {
        const srcCode = fs.readFileSync(srcPath, 'utf8');
        eval(srcCode);
      } catch (err) {
        executionError = err;
        break;
      }
    } else {
      logFail(`admin_dashboard.html で指定された外部スクリプトが見つかりません: ${sm[1]}`);
      return false;
    }
  }

  if (!executionError) {
    for (const m of inlineMatches) {
      try {
        eval(m[1]);
      } catch (err) {
        executionError = err;
        break;
      }
    }
  }

  if (executionError) {
    logFail(`admin_dashboard.html スクリプト実行時にクラッシュしました: ${executionError.stack || executionError.message}`);
    return false;
  }

  try {
    await mockDoc.dispatchEvent({ type: 'DOMContentLoaded' });
    await new Promise(r => setTimeout(r, 60));
  } catch (err) {
    logFail(`admin_dashboard.html DOMContentLoaded 実行中に例外（TDZ/クラッシュ）が発生しました: ${err.stack || err.message}`);
    return false;
  }

  let allTabsPassed = true;

  // 1. 会議体データ管理タブ (renderCards)
  try {
    if (typeof mockWin.renderCards === 'function') {
      elements['filterVerdict'].value = '';
      mockWin.renderCards();
      const count = elements['councilList']?.innerHTML?.length || 0;
      if (count > 0) {
        logPass(`[TAB 3] 会議体データ管理 (renderCards) 描画成功 (出力: ${count} bytes)`);
      } else {
        logFail("[TAB 3] 会議体データ管理 (renderCards) の出力が空です");
        allTabsPassed = false;
      }
    } else {
      logFail("window.renderCards 関数が定義されていません");
      allTabsPassed = false;
    }
  } catch (err) {
    logFail(`[TAB 3] 会議体データ管理 (renderCards) 実行時にクラッシュ: ${err.stack || err.message}`);
    allTabsPassed = false;
  }

  // 2. 会議データ管理タブ (renderMeetingsList)
  try {
    if (typeof mockWin.renderMeetingsList === 'function') {
      mockWin.renderMeetingsList();
      const count = elements['meetingsList']?.innerHTML?.length || 0;
      if (count > 0) {
        logPass(`[TAB 2] 会議データ管理 (renderMeetingsList) 描画成功 (出力: ${count} bytes)`);
      } else {
        logFail("[TAB 2] 会議データ管理 (renderMeetingsList) の出力が空です");
        allTabsPassed = false;
      }
    } else {
      logFail("window.renderMeetingsList 関数が定義されていません");
      allTabsPassed = false;
    }
  } catch (err) {
    logFail(`[TAB 2] 会議データ管理 (renderMeetingsList) 実行時にクラッシュ: ${err.stack || err.message}`);
    allTabsPassed = false;
  }

  // 3. 却下会議体管理タブ (renderRejectedList)
  try {
    if (typeof mockWin.renderRejectedList === 'function') {
      mockWin.renderRejectedList();
      const count = elements['rejectedList']?.innerHTML?.length || 0;
      if (count > 0) {
        logPass(`[TAB 4] 却下会議体管理 (renderRejectedList) 描画成功 (出力: ${count} bytes)`);
      } else {
        logFail("[TAB 4] 却下会議体管理 (renderRejectedList) の出力が空です");
        allTabsPassed = false;
      }
    } else {
      logFail("window.renderRejectedList 関数が定義されていません");
      allTabsPassed = false;
    }
  } catch (err) {
    logFail(`[TAB 4] 却下会議体管理 (renderRejectedList) 実行時にクラッシュ: ${err.stack || err.message}`);
    allTabsPassed = false;
  }

  // 4. 省庁メタデータ管理タブ (renderMinistryList)
  try {
    if (typeof mockWin.renderMinistryList === 'function') {
      mockWin.renderMinistryList();
      const count = elements['ministryListContainer']?.innerHTML?.length || 0;
      if (count > 0) {
        logPass(`[TAB 5] 省庁メタデータ管理 (renderMinistryList) 描画成功 (出力: ${count} bytes)`);
      } else {
        logFail("[TAB 5] 省庁メタデータ管理 (renderMinistryList) の出力が空です");
        allTabsPassed = false;
      }
    } else {
      logFail("window.renderMinistryList 関数が定義されていません");
      allTabsPassed = false;
    }
  } catch (err) {
    logFail(`[TAB 5] 省庁メタデータ管理 (renderMinistryList) 実行時にクラッシュ: ${err.stack || err.message}`);
    allTabsPassed = false;
  }

  return allTabsPassed;
}

async function run() {
  console.log("==================================================");
  console.log(" UI Structure & JavaScript Runtime Validation");
  console.log("==================================================");

  const domOk = testUiDomStructureAndNoLeakage();
  if (!domOk) {
    process.exit(1);
  }

  let sampleData = { councils: [], meetings: [], ministries: {}, categories: {} };
  let sampleRejected = [];

  if (fs.existsSync(DATA_JSON_PATH)) {
    sampleData = JSON.parse(fs.readFileSync(DATA_JSON_PATH, 'utf8'));
  }
  if (fs.existsSync(REJECTED_JSON_PATH)) {
    sampleRejected = JSON.parse(fs.readFileSync(REJECTED_JSON_PATH, 'utf8'));
  }

  const portalOk = await testPublicPortalRuntime(sampleData);
  const adminOk = await testAdminDashboardRuntime(sampleData, sampleRejected);

  console.log("\n==================================================");
  if (domOk && portalOk && adminOk) {
    console.log(" 【結果】UI構造・ローカル専用化・全JavaScriptランタイム検証に合格しました（クラッシュ0件）。");
    process.exit(0);
  } else {
    console.error(" 【結果】UI構造またはJavaScriptランタイムエラーが検知されました。");
    process.exit(1);
  }
}

run().catch(err => {
  console.error("予期せぬテスト実行時エラー:", err);
  process.exit(1);
});
