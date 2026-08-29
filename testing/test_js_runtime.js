#!/usr/bin/env node
/**
 * 政策会議ウォッチ (PM-HUB) - JavaScript Runtime Crash & TDZ Validator
 * 
 * 公開ポータル (docs/app.js) および 管理ダッシュボード (admin/admin_dashboard.html) の
 * JavaScript が、実際のデータをロードして初期化・描画を行う際に
 * TDZ (Temporal Dead Zone)、ReferenceError、TypeError 等の例外で途中で停止（クラッシュ）しないかを自動検証します。
 */

const fs = require('fs');
const path = require('path');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const DATA_JSON_PATH = path.join(PROJECT_ROOT, 'docs', 'data.json');
const REJECTED_JSON_PATH = path.join(PROJECT_ROOT, 'admin', 'rejected_councils.json');
const APP_JS_PATH = path.join(PROJECT_ROOT, 'docs', 'app.js');
const ADMIN_HTML_PATH = path.join(PROJECT_ROOT, 'admin', 'admin_dashboard.html');

function logPass(msg) {
  console.log(`  [PASS] ${msg}`);
}
function logFail(msg) {
  console.error(`  [FAIL] ${msg}`);
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
          json: async () => sampleRejected
        };
      }
      return {
        ok: true,
        status: 200,
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
  console.log("--------------------------------------------------");
  console.log(" [ランタイムテスト 1/2] 公開ポータル (docs/app.js) 実行時クラッシュ検証");
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
    return true;
  } else {
    logFail("app.js 必須描画コンテナへの出力が確認できませんでした");
    return false;
  }
}

async function testAdminDashboardRuntime(sampleData, sampleRejected) {
  console.log("\n--------------------------------------------------");
  console.log(" [ランタイムテスト 2/2] 管理コンソール (admin_dashboard.html) 実行時クラッシュ検証");
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
  const scriptMatches = [...adminHtml.matchAll(/<script(?![^>]*src=)>([\s\S]*?)<\/script>/gi)];

  if (scriptMatches.length === 0) {
    logFail("admin_dashboard.html 内にインライン <script> が見つかりません");
    return false;
  }

  let executionError = null;
  for (const m of scriptMatches) {
    try {
      eval(m[1]);
    } catch (err) {
      executionError = err;
      break;
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
      elements['filterVerdict'].value = ''; // 全件表示
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
  console.log(" JavaScript Runtime Crash & TDZ Validation");
  console.log("==================================================");

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
  if (portalOk && adminOk) {
    console.log(" 【結果】全JavaScriptランタイムテストに合格しました（クラッシュ0件）。");
    process.exit(0);
  } else {
    console.error(" 【結果】JavaScriptランタイムエラーが検知されました。");
    process.exit(1);
  }
}

run().catch(err => {
  console.error("予期せぬテスト実行時エラー:", err);
  process.exit(1);
});
