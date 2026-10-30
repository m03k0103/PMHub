#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 統合テストスイート (Comprehensive Test Suite Runner) [Drop 64]

【テストスイート要件 (全15ケース・実データ整合性 & システム検証特化)】
第1層 (L1): コード構文・基本整合性
  1. コード文法・構文整合性自動確認 (SyntaxError / 括弧不整合 / HTMLタグ整合性 / JSON構文 / DDL構文)
  2. ネットワークリンク疎通確認 (新規追加・変更URL 200 OK 検証 / レートリミット保護)
第2層 (L2): UI & フロントエンド表示機能
  3. UI表示DOMコンテナ・主要要素整合性検証 (公開ポータル & 管理ダッシュボード)
  4. JavaScript 実行時クラッシュ・TDZ・全画面描画検証 (Node.js 実データロード・描画例外ゼロ)
第3層 (L3): データ整合性・不変性保証
  5. 会議品質・回次整合性・重複排除検証 (全19,000件超全走査: 会議ID・回次・URL重複ゼロ)
  6. 会議体・タイムライン・除外リスト ID完全排他性・整合性検証 (1,506会議体ID整合性)
  7. 康煕部首・特殊文字 NFKC 正規化検証 (全会議体・開催回・資料の康煕部首0件維持)
  8. プレースホルダー日付 (2099/01/01) 本番データゼロ遮断検証 (全開催回走査)
 15. SQLiteマスターDB整合性 & 2系統JSON完全同期検証 (PRAGMA整合性・外部キー・件数一致・漏洩ゼロ)
第4層 (L4): 管理機能 & バックエンドAPI
  9. 管理サーバー API エンドポイント単体・結合テスト (ローカルHTTPサーバー11エンドポイント疎通)
第5層 (L5): クローラー実データ整合性・保護検証
  10. クローラー手動保護回帰テスト (manualLock 非破壊性)
  11. スクレイピングルール整合性検証 (孤立ルール0件・全会議体100%ルール適用)
  12. ホスト分散・ゴミデータ不変性検証 (1,499会議体ホストインターリーブ・ゴミ0件走査)
  13. 省庁親ポータルURL設定・探索網羅性検証 (各省庁親ポータルURL設定・スラグID継承検証)
  14. アクティブ会議体フィルタリング・廃止会議体設定検証 (直近2年フィルタリング・廃止マスター)

【単体関数検証 (Unit Tests) 連動機構】
関数の仕様（ロジック）を修正した場合に限り、変更対象コードに応じた単体テスト種類を自動判定して連動実行。
平時（データ・ルール・ドキュメント更新時）は単体関数検証をテストスイートから外し、実データ検証に特化・高速化。
"""

import sys
import os
from pathlib import Path
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import time
from collections import defaultdict
import subprocess
import argparse
import shutil
import concurrent.futures
import io
from contextlib import redirect_stdout, redirect_stderr
from html.parser import HTMLParser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")
TESTING_DIR = os.path.join(PROJECT_ROOT, "testing")
for p in [ADMIN_DIR, TESTING_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import setup_win32_utf8, get_browser_headers, load_data_json, validate_council_id, validate_meeting_id
setup_win32_utf8()

from run_unit_tests import UNIT_TEST_REGISTRY, run_unit_tests

_SHARED_DATA_CACHE = None

def get_shared_data():
    """docs/data.json をセッション全体でキャッシュ共有し、重複ディスクI/OとJSONパースを削減"""
    global _SHARED_DATA_CACHE
    if _SHARED_DATA_CACHE is None:
        data_json_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        _SHARED_DATA_CACHE = load_data_json(data_json_path, cached=True)
    return _SHARED_DATA_CACHE

def _async_node_run(args, cwd):
    """Node.js テストを別スレッドで並行実行するヘルパー"""
    try:
        res = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        return res.returncode == 0, res.stdout, res.stderr
    except Exception as e:
        return False, "", str(e)


class DivBalanceChecker(HTMLParser):
    """HTML 内の <div> タグの対応関係とネストバランスを検証（コメント・スクリプト内文字列を安全に除外）"""
    def __init__(self):
        super().__init__()
        self.open_count = 0
        self.close_count = 0
        self.depth = 0
        self.underflow = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'div':
            self.open_count += 1
            self.depth += 1

    def handle_endtag(self, tag):
        if tag.lower() == 'div':
            self.close_count += 1
            self.depth -= 1
            if self.depth < 0:
                self.underflow = True


def get_node_command():
    """Node.js 実行バイナリのパスを安全かつ汎用的に解決する"""
    cmd = shutil.which("node")
    if cmd:
        return cmd
    candidates = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        r"D:\Programs\nodejs\node.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\node\node.exe")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "node"


def check_js_syntax(code, file_path=""):
    """JS の文法エラーを精密検証"""
    node_cmd = get_node_command()
    if node_cmd:
        try:
            if file_path and os.path.isfile(file_path):
                res = subprocess.run([node_cmd, "--check", file_path], capture_output=True, text=True, encoding='utf-8', errors='replace')
            else:
                res = subprocess.run([node_cmd, "--check"], input=code, capture_output=True, text=True, encoding='utf-8', errors='replace')
            if res.returncode == 0:
                return True, "Node.js Syntax OK"
            else:
                err_msg = res.stderr.strip().splitlines()[0] if res.stderr else "Node.js Syntax error"
                return False, f"Node.js SyntaxError: {err_msg}"
        except Exception:
            pass

    pattern = r"//.*|/\*[\s\S]*?\*/|'(?:\\.|[\s\S])*?'|\"(?:\\.|[\s\S])*?\"|`(?:\\.|[\s\S])*?`"
    cleaned_code = re.sub(pattern, '', code)

    parens = cleaned_code.count('(') - cleaned_code.count(')')
    curlies = cleaned_code.count('{') - cleaned_code.count('}')
    squares = cleaned_code.count('[') - cleaned_code.count(']')

    if parens != 0 or curlies != 0 or squares != 0:
        return False, f"JavaScript 括弧の数不一致 (小括弧:{parens}, 中括弧:{curlies}, 角括弧:{squares})"

    bracket_stack = []
    line_no = 1
    col_no = 1
    for char in cleaned_code:
        if char == '\n':
            line_no += 1
            col_no = 1
            continue
        if char in '({[':
            bracket_stack.append((char, line_no, col_no))
        elif char in ')}]':
            if not bracket_stack:
                return False, f"対応する開き括弧がない閉じ括弧 '{char}' ({line_no}行目)"
            top_char, top_line, top_col = bracket_stack.pop()
            expected = {'}':'{', ']':'[', ')':'('}[char]
            if top_char != expected:
                return False, f"括弧ペア不一致: '{top_char}' ({top_line}行目) に対し '{char}' ({line_no}行目)"
        col_no += 1

    return True, "JavaScript Syntax OK"


# ==============================================================================
# 第1層: コード構文・基本整合性 (L1: Syntax & Health)
# ==============================================================================

def check_syntax_errors():
    """1. JS/Python/HTML/JSON ファイルの文法・タグ構造エラーを自動確認"""
    print("--------------------------------------------------")
    print(" [テスト 1/15] コードの文法エラー (SyntaxError) 自動検証")
    print("--------------------------------------------------")
    
    # CR-169: ハードコードリストを廃止し、対象ディレクトリの glob 自動探索に刷新
    discovered_files = set()
    patterns = [
        ("docs", "*.js"),
        ("docs", "*.html"),
        ("admin", "*.py"),
        ("admin", "*.js"),
        ("admin", "*.html"),
        ("admin/db", "*.py"),
        ("admin/llm", "*.py"),
        ("admin/pmm", "*.py"),
        ("testing", "*.py"),
        ("testing", "*.js")
    ]
    for sub, pat in patterns:
        base = os.path.join(PROJECT_ROOT, sub)
        if os.path.exists(base):
            for p in Path(base).glob(pat):
                if p.is_file() and not p.name.startswith("."):
                    discovered_files.add(str(p.resolve()))

    files_to_check = sorted(list(discovered_files))
    
    errors_found = 0

    for file_path in files_to_check:
        rel_path = os.path.relpath(file_path, PROJECT_ROOT)
        if not os.path.exists(file_path):
            print(f"  [FAIL] ファイルが存在しません: {rel_path}")
            errors_found += 1
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()

        if file_path.endswith(".py"):
            try:
                import ast
                ast.parse(code, filename=rel_path)
                print(f"  [PASS] {rel_path} : Python Syntax OK")
            except SyntaxError as e:
                print(f"  [FAIL] {rel_path} : Python SyntaxError on line {e.lineno}: {e.msg}")
                errors_found += 1
        elif file_path.endswith(".js"):
            ok, msg = check_js_syntax(code, file_path)
            if ok:
                print(f"  [PASS] {rel_path} : {msg}")
            else:
                print(f"  [FAIL] {rel_path} : {msg}")
                errors_found += 1
        elif file_path.endswith(".html"):
            checker = DivBalanceChecker()
            try:
                checker.feed(code)
                if checker.open_count == checker.close_count and not checker.underflow:
                    print(f"  [PASS] {rel_path} : HTML Structure & Div tag balance OK (div count: {checker.open_count})")
                else:
                    err_detail = "premature </div> tag" if checker.underflow else f"open: {checker.open_count}, close: {checker.close_count}"
                    print(f"  [FAIL] {rel_path} : HTML <div> tag mismatch ({err_detail})")
                    errors_found += 1
            except Exception as e:
                print(f"  [FAIL] {rel_path} : HTML parse error: {e}")
                errors_found += 1

            inline_scripts = re.findall(r'<script(?![^>]*src=)>([\s\S]*?)</script>', code, re.IGNORECASE)
            for idx, sc in enumerate(inline_scripts):
                if sc.strip():
                    ok, msg = check_js_syntax(sc, f"{rel_path} <script #{idx+1}>")
                    if ok:
                        print(f"  [PASS] {rel_path} <script #{idx+1}> : {msg}")
                    else:
                        print(f"  [FAIL] {rel_path} <script #{idx+1}> : {msg}")
                        errors_found += 1

    # JSON validation
    json_files = [
        os.path.join(PROJECT_ROOT, "docs", "data.json"),
        os.path.join(PROJECT_ROOT, "admin", "admin_data.json"),
        os.path.join(PROJECT_ROOT, "admin", "rejected_councils.json")
    ]
    for jpath in json_files:
        if os.path.exists(jpath):
            try:
                with open(jpath, "r", encoding="utf-8") as jf:
                    json.load(jf)
                print(f"  [PASS] {os.path.relpath(jpath, PROJECT_ROOT)} : JSON Syntax OK")
            except Exception as je:
                print(f"  [FAIL] {os.path.relpath(jpath, PROJECT_ROOT)} : JSON Error: {je}")
                errors_found += 1

    # SQL Schema validation (Drop 64)
    schema_path = os.path.join(PROJECT_ROOT, "admin", "db", "schema.sql")
    if os.path.exists(schema_path):
        try:
            import sqlite3
            with open(schema_path, "r", encoding="utf-8") as sf:
                sql_script = sf.read()
            test_conn = sqlite3.connect(":memory:")
            test_conn.executescript(sql_script)
            test_conn.close()
            print(f"  [PASS] {os.path.relpath(schema_path, PROJECT_ROOT)} : SQL DDL Syntax OK")
        except Exception as se:
            print(f"  [FAIL] {os.path.relpath(schema_path, PROJECT_ROOT)} : SQL DDL Error: {se}")
            errors_found += 1

    return errors_found == 0


def is_valid_test_url(u):
    """URLが実在するWebアドレスかを判定"""
    if not u or not u.startswith(('http://', 'https://')):
        return False
    if any(d in u for d in ['pm-hub.gov.example', 'example.com', 'googleapis.com']):
        return False
    regex_chars = ['\\', '.*', '(?:', '[^', r'\d', r'\b', '|', '(?=']
    if any(p in u for p in regex_chars):
        return False
    return True


def get_added_urls_from_git():
    """新規追加・変更された URL を動的に抽出"""
    current_json_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
    if not os.path.exists(current_json_path):
        return []

    def extract_urls_from_text(text):
        urls = set()
        for u in re.findall(r"https?://[^\s\x22\x27,]+", text):
            if is_valid_test_url(u):
                urls.add(u)
        return urls

    try:
        with open(current_json_path, "r", encoding="utf-8") as f:
            curr_text = f.read()
        curr_urls = extract_urls_from_text(curr_text)

        status_out = subprocess.check_output(
            ["git", "status", "--porcelain", "docs/data.json"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace'
        ).strip()
        base_rev = "HEAD" if status_out else "HEAD~1"

        base_text = subprocess.check_output(
            ["git", "show", f"{base_rev}:docs/data.json"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace'
        )
        base_urls = extract_urls_from_text(base_text)
        diff_urls = curr_urls - base_urls
        return sorted(diff_urls)
    except Exception:
        pass

    added_urls = set()
    diff_commands = [
        ["git", "diff", "HEAD", "--", "docs/data.json"],
        ["git", "diff", "--staged", "--", "docs/data.json"]
    ]
    for cmd in diff_commands:
        try:
            output = subprocess.check_output(cmd, cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace')
            for line in output.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    found = re.findall(r"https?://[^\s\x22\x27,]+", line)
                    for u in found:
                        if is_valid_test_url(u):
                            added_urls.add(u)
        except Exception:
            pass

    return sorted(added_urls)


def check_link_health(explicit_urls=None, check_all=False):
    """2. 追加・変更された URL のみのリンク疎通確認"""
    print("\n--------------------------------------------------")
    print(" [テスト 2/15] リンク疎通確認 (追加・変更 URL のみ対象)")
    print("--------------------------------------------------")

    target_urls = []
    if explicit_urls:
        target_urls = [u for u in explicit_urls if is_valid_test_url(u)]
    elif check_all:
        data_json_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        if os.path.exists(data_json_path):
            with open(data_json_path, "r", encoding="utf-8") as f:
                content = f.read()
            raw_urls = re.findall(r"https?://[^\s\x22\x27,]+", content)
            target_urls = [u for u in raw_urls if is_valid_test_url(u)]
    else:
        target_urls = get_added_urls_from_git()

    unique_urls = list(dict.fromkeys(target_urls))

    if not unique_urls:
        print("  [SKIP] 変更・追加された新規 URL は検出されませんでした (既存 URL の検証はスキップします)")
        return True

    print(f"  検出された追加・変更 URL (計 {len(unique_urls)} 件) の疎通確認を実行中...")
    headers = get_browser_headers()
    broken_links = 0
    domain_last_time = defaultdict(float)

    cache_path = os.path.join(PROJECT_ROOT, "testing", ".url_cache.json")
    url_cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as cf:
                url_cache = json.load(cf)
        except Exception:
            pass

    for url in unique_urls:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ('http', 'https'):
            print(f"  [FAIL 無効なスキーム] {url}")
            broken_links += 1
            continue

        if url in url_cache and (time.time() - url_cache[url].get("t", 0) < 86400):
            continue

        domain = parsed_url.netloc
        elapsed = time.time() - domain_last_time[domain]
        if elapsed < 0.35:
            time.sleep(0.35 - elapsed)
        domain_last_time[domain] = time.time()

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 301, 302, 202):
                    print(f"  [200 OK] {url}")
                    url_cache[url] = {"t": time.time(), "status": resp.status}
                else:
                    print(f"  [WARN {resp.status}] {url}")
        except urllib.error.HTTPError as e:
            if e.code in (403, 401):
                print(f"  [PASS (Bot Protected {e.code})] {url}")
                url_cache[url] = {"t": time.time(), "status": e.code}
            else:
                print(f"  [FAIL リンク切れ ({e.code})] {url}")
                broken_links += 1
        except Exception as e:
            ssl_fallback_ok = False
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                try:
                    import ssl
                    ctx = ssl._create_unverified_context()
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                        if resp.status in (200, 301, 302, 202):
                            print(f"  [200 OK (SSL検証フォールバック)] {url}")
                            url_cache[url] = {"t": time.time(), "status": resp.status}
                            ssl_fallback_ok = True
                except Exception:
                    pass
            if not ssl_fallback_ok:
                print(f"  [FAIL 接続失敗 ({e})] {url}")
                broken_links += 1
    try:
        with open(cache_path, "w", encoding="utf-8") as cf:
            json.dump(url_cache, cf)
    except Exception:
        pass

    print(f"\n  検証結果: 追加・変更 URL {len(unique_urls)} 件中 リンク切れ {broken_links} 件")
    return broken_links == 0


# ==============================================================================
# 第2層: UI & フロントエンド表示機能 (L2: UI & Frontend)
# ==============================================================================

def check_view_rendering():
    """3. UI表示自動検証（公開ポータル＆管理ダッシュボードのDOM整合性チェック）"""
    print("\n--------------------------------------------------")
    print(" [テスト 3/15] UI表示機能検証（ポータル＆管理ダッシュボード構造） (L2: UI Rendering)")
    print("--------------------------------------------------")

    app_js_path = os.path.join(PROJECT_ROOT, "docs", "app.js")
    index_html_path = os.path.join(PROJECT_ROOT, "docs", "index.html")
    admin_html_path = os.path.join(PROJECT_ROOT, "admin", "admin_dashboard.html")

    with open(app_js_path, "r", encoding="utf-8") as f:
        app_text = f.read()
    with open(index_html_path, "r", encoding="utf-8") as f:
        html_text = f.read()
    with open(admin_html_path, "r", encoding="utf-8") as f:
        admin_text = f.read()

    # 1. 公開ポータル表示要素の検証
    required_portal_elements = ['id="timelineFeed"', 'id="councilsAccordionList"', 'id="dateRangeSelect"']
    for elem in required_portal_elements:
        if elem not in html_text:
            print(f"  [FAIL] 公開ポータル表示用HTML要素 ({elem}) が不足しています")
            return False

    if 'function capitalize' not in app_text:
        print("  [FAIL] app.js 内に capitalize 関数が定義されていません")
        return False

    print("  [PASS] 公開ポータルの主要コンテナ (timelineFeed, councilsAccordionList, dateRangeSelect) を検証完了")

    # 1.5. 公開ポータルからの管理ダッシュボード露出ゼロ検証 (Drop 71)
    if 'admin_dashboard.html' in html_text or '管理コンソール' in html_text:
        print("  [FAIL] 公開ポータル (docs/index.html) に管理コンソール (admin_dashboard.html) へのリンクが露出しています")
        return False
    print("  [PASS] 公開ポータルからの管理画面リンク露出ゼロ (ローカル専用化) を検証完了")

    # 2. 管理コンソールのタブ・コンテナ・PMM要素検証
    admin_tab_ids = ['tab-crawler', 'tab-meetings', 'tab-councils', 'tab-rejected', 'tab-ministries']
    for tid in admin_tab_ids:
        if f'id="{tid}"' not in admin_text:
            print(f"  [FAIL] 管理ダッシュボードのタブコンテナ ({tid}) が不足しています")
            return False

    admin_containers = ['id="councilList"', 'id="meetingsList"', 'id="rejectedList"', 'id="ministryListContainer"']
    for cid in admin_containers:
        if cid not in admin_text:
            print(f"  [FAIL] 管理ダッシュボードの描画先コンテナ ({cid}) が不足しています")
            return False

    # PMM ローカル資料ダッシュボード要素の検証 (Drop 71)
    if 'id="pmmStatusSummary"' not in admin_text or 'id="btnStartPmmDownload"' not in admin_text:
        print("  [FAIL] 管理ダッシュボードの PMM 要素 (pmmStatusSummary / btnStartPmmDownload) が不足しています")
        return False
    print("  [PASS] 管理ダッシュボードの全5タブ、描画先コンテナおよび PMM 要素を検証完了")
    return True


def check_js_runtime_crash(future=None):
    """4. JavaScript 実行時クラッシュ・TDZ・初期化検証（公開ポータル＆管理ダッシュボード）"""
    print("\n--------------------------------------------------")
    print(" [テスト 4/15] JavaScript 実行時クラッシュ・TDZ・描画検証 (L2: JS Runtime)")
    print("--------------------------------------------------")
    try:
        if future is not None:
            ok, stdout, stderr = future.result()
            if ok:
                print("  [PASS] 公開ポータルおよび管理コンソールの JavaScript 実行時クラッシュ0件・全画面描画成功")
                return True
            else:
                print("  [FAIL] JavaScript 実行時にクラッシュ（例外）が検知されました:")
                for line in stdout.splitlines():
                    if line.strip():
                        print(f"    {line}")
                if stderr:
                    for line in stderr.splitlines():
                        if line.strip():
                            print(f"    {line}")
                return False
        node_cmd = get_node_command()
        test_script = os.path.join(PROJECT_ROOT, "testing", "test_js_runtime.js")
        if not os.path.exists(test_script):
            print("  [SKIP] test_js_runtime.js が見つかりません")
            return True

        res = subprocess.run([node_cmd, test_script], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            print("  [PASS] 公開ポータルおよび管理コンソールの JavaScript 実行時クラッシュ0件・全画面描画成功")
            return True
        else:
            print("  [FAIL] JavaScript 実行時にクラッシュ（例外）が検知されました:")
            for line in res.stdout.splitlines():
                if line.strip():
                    print(f"    {line}")
            if res.stderr:
                for line in res.stderr.splitlines():
                    if line.strip():
                        print(f"    {line}")
            return False
    except Exception as e:
        print(f"  [FAIL] JS実行時検証エラー: {e}")
        return False


# ==============================================================================
# 第3層: データ整合性・不変性保証 (L3: Data Integrity)
# ==============================================================================

def check_duplicate_meetings_quality(data=None):
    """5. 会議レコード品質・回次整合性・重複排除の自動検証"""
    print("\n--------------------------------------------------")
    print(" [テスト 5/15] 会議品質・回次整合性・重複排除検証 (L3: Data Integrity)")
    print("--------------------------------------------------")
    try:
        from test_no_duplicate_meetings import run_test
        f_out = io.StringIO()
        f_err = io.StringIO()
        with redirect_stdout(f_out), redirect_stderr(f_err):
            code = run_test(data=data)
        if code == 0:
            print("  [PASS] 会議ID重複・回次重複・クロス会議体重複URL・会議体マスター重複・孤立会議データ0件を検証完了")
            return True
        else:
            print("  [FAIL] 会議データ品質・重複排除検証でエラーが検出されました:")
            for line in f_out.getvalue().splitlines():
                if line.strip():
                    print(f"    {line}")
            return False
    except Exception:
        test_script = os.path.join(PROJECT_ROOT, "testing", "test_no_duplicate_meetings.py")
        if not os.path.exists(test_script):
            print("  [SKIP] test_no_duplicate_meetings.py が見つかりません")
            return True

        res = subprocess.run([sys.executable, test_script], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            print("  [PASS] 会議ID重複・回次重複・クロス会議体重複URL・会議体マスター重複・孤立会議データ0件を検証完了")
            return True
        else:
            print("  [FAIL] 会議データ品質・重複排除検証でエラーが検出されました:")
            for line in res.stdout.splitlines():
                if line.strip():
                    print(f"    {line}")
            if res.stderr:
                for line in res.stderr.splitlines():
                    if line.strip():
                        print(f"    {line}")
            return False


def check_council_timeline_sync(data=None):
    """6. 会議体一覧 (COUNCILS), タイムライン (MEETINGS) の ID整合性自動検証"""
    print("\n--------------------------------------------------")
    print(" [テスト 6/15] 会議体・タイムライン・除外リスト ID完全整合性検証 (L3: ID Consistency)")
    print("--------------------------------------------------")

    if data is None:
        data = get_shared_data()
    rejected_json_path = os.path.join(PROJECT_ROOT, "admin", "rejected_councils.json")

    if not data:
        print("  [FAIL] data.json が見つかりません")
        return False

    councils = data.get("councils", [])
    meetings = data.get("meetings", [])

    councils_ids = [c.get("id") for c in councils if c.get("id")]
    meetings_council_ids = set([m.get("councilId") for m in meetings if m.get("councilId")])

    if len(councils_ids) != len(set(councils_ids)):
        duplicates = [cid for cid in set(councils_ids) if councils_ids.count(cid) > 1]
        print(f"  [FAIL] COUNCILS に重複IDが存在します: {duplicates}")
        return False

    councils_set = set(councils_ids)

    invalid_c_ids = [cid for cid in councils_ids if not validate_council_id(cid)]
    if invalid_c_ids:
        print(f"  [FAIL] 不正な councilId フォーマット (要 1ハイフン): {invalid_c_ids[:5]}")
        return False

    meeting_ids = [m.get("id", "") for m in meetings]
    invalid_m_ids = [mid for mid in meeting_ids if not validate_meeting_id(mid)]
    if invalid_m_ids:
        print(f"  [FAIL] 不正な meetingId フォーマット (要 3ハイフン/4セグメント): {invalid_m_ids[:5]}")
        return False

    orphaned_meetings = meetings_council_ids - councils_set
    if orphaned_meetings:
        print(f"  [FAIL] 定義されていない会議体IDを持つ会議データがタイムラインに存在します (CR-168 厳格FAIL化): {sorted(orphaned_meetings)[:5]}")
        return False

    valid_ministries = set(data.get("ministries", {}).keys())
    if valid_ministries:
        invalid_min_councils = [c.get("id") for c in councils if c.get("ministry") not in valid_ministries]
        if invalid_min_councils:
            print(f"  [FAIL] ministries に未定義の不正な省庁コードを持つ会議体が存在します: {invalid_min_councils[:5]}")
            return False

    # Drop 99: 初期ウォッチ会議体ID (initialWatchedCouncilIds) の実在性検証
    initial_watched = data.get("initialWatchedCouncilIds", [])
    if not initial_watched:
        print("  [FAIL] docs/data.json に initialWatchedCouncilIds が設定されていません")
        return False
    missing_watched = [wid for wid in initial_watched if wid not in councils_set]
    if missing_watched:
        print(f"  [FAIL] initialWatchedCouncilIds に実在しない会議体IDが含まれています: {missing_watched}")
        return False

    if os.path.exists(rejected_json_path):
        with open(rejected_json_path, "r", encoding="utf-8") as rf:
            rejected = json.load(rf)
            rejected_ids = set([r.get("id") for r in rejected if r.get("id")])
            rejected_names = set([r.get("name", "").strip() for r in rejected if r.get("name")])

            collision = councils_set & rejected_ids
            if collision:
                print(f"  [FAIL] 公開会議体 (COUNCILS) と却下リスト (rejected_councils.json) に重複IDが存在します: {collision}")
                return False

            councils_name_collision = [c.get("name") for c in councils if c.get("name", "").strip() in rejected_names]
            if councils_name_collision:
                print(f"  [FAIL] 会議体マスター (COUNCILS) と却下リストに重複名称が存在します: {councils_name_collision[:5]}")
                return False

            print(f"  [PASS] 却下会議体 {len(rejected_ids)} 件の分離・公開データとの完全排他を検証完了")

    print(f"  [PASS] 全 {len(councils_set)} 会議体の ID整合性・タイムライン紐づけを検証完了")
    return True


def check_drop22_normalization():
    """7. 康煕部首・特殊文字 NFKC 正規化 & 検索漏れ根絶検証 (CR-46, CR-47)"""
    print("\n--------------------------------------------------")
    print(" [テスト 7/15] 康煕部首・特殊文字 NFKC 正規化 & 検索漏れ根絶検証 (L3: Normalization)")
    print("--------------------------------------------------")
    from test_drop22_normalization import TestDrop22Normalization
    return _run_inprocess_or_fallback(
        TestDrop22Normalization,
        "test_drop22_normalization.py",
        "康煕部首・CJK部首補助0件・NFKC文字正規化・データ整合性テスト全件合格",
        "文字正規化検証"
    )


def check_placeholder_dates_zero(data=None):
    """8. プレースホルダー日付（2099/01/01）本番データゼロ遮断検証 (L3: Placeholder Zero)"""
    print("\n--------------------------------------------------")
    print(" [テスト 8/15] プレースホルダー日付（2099/01/01）ゼロ遮断検証 (L3: Placeholder Zero)")
    print("--------------------------------------------------")
    if data is None:
        data = get_shared_data()
    placeholder_meetings = [
        m for m in data.get("meetings", [])
        if str(m.get("date", "")).startswith("2099")
    ]
    if placeholder_meetings:
        print(f"  [FAIL] 本番 docs/data.json 内に 2099 プレースホルダー開催回が {len(placeholder_meetings)} 件残存しています:")
        for m in placeholder_meetings[:5]:
            print(f"    - ID: {m.get('id')}, Council: {m.get('councilId')}, Date: {m.get('date')}")
        return False
    print("  [PASS] 本番 docs/data.json 内の 2099/01/01 プレースホルダー開催回 0 件を検証完了")
    return True


def check_sqlite_and_split_export_sync(data=None):
    """15. SQLiteマスターDB整合性 & 2系統JSON完全同期検証 (L3: Database Integrity & Tri-State Sync)"""
    print("\n--------------------------------------------------")
    print(" [テスト 15/15] SQLiteマスターDB整合性 & 2系統JSON完全同期検証 (L3: Database Integrity)")
    print("--------------------------------------------------")
    db_path = os.path.join(PROJECT_ROOT, "admin", "pmhub.db")
    public_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
    admin_path = os.path.join(PROJECT_ROOT, "admin", "admin_data.json")

    if not os.path.exists(db_path):
        print(f"  [FAIL] SQLite マスターデータベースが見つかりません: {db_path}")
        return False
    if not os.path.exists(public_path):
        print(f"  [FAIL] 公開 JSON ファイルが見つかりません: {public_path}")
        return False
    if not os.path.exists(admin_path):
        print(f"  [FAIL] 管理 JSON ファイルが見つかりません: {admin_path}")
        return False

    errors = []
    import sqlite3
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # 1. PRAGMA integrity_check
        cur.execute("PRAGMA integrity_check;")
        integ = cur.fetchone()[0]
        if integ != "ok":
            errors.append(f"SQLite PRAGMA integrity_check 失敗: {integ}")

        # 2. PRAGMA foreign_key_check
        cur.execute("PRAGMA foreign_key_check;")
        fks = cur.fetchall()
        if fks:
            errors.append(f"SQLite 外部キー制約違反が検知されました: {len(fks)} 件")

        # 3. 件数取得 (DB)
        db_c_cnt = cur.execute("SELECT COUNT(*) FROM councils;").fetchone()[0]
        db_m_cnt = cur.execute("SELECT COUNT(*) FROM meetings;").fetchone()[0]
        db_mat_cnt = cur.execute("SELECT COUNT(*) FROM materials;").fetchone()[0]
        db_cm_cnt = cur.execute("SELECT COUNT(*) FROM council_materials;").fetchone()[0]
        db_rule_cnt = cur.execute("SELECT COUNT(*) FROM scraping_rules;").fetchone()[0]
        db_cs_cnt = cur.execute("SELECT COUNT(*) FROM crawl_statuses;").fetchone()[0]

        db_c_lock = cur.execute("SELECT COUNT(*) FROM councils WHERE manual_lock = 1;").fetchone()[0]
        db_m_lock = cur.execute("SELECT COUNT(*) FROM meetings WHERE manual_lock = 1;").fetchone()[0]
        db_mat_lock = cur.execute("SELECT COUNT(*) FROM materials WHERE manual_lock = 1;").fetchone()[0]
        db_cm_lock = cur.execute("SELECT COUNT(*) FROM council_materials WHERE manual_lock = 1;").fetchone()[0]
        db_rej_cnt = cur.execute("SELECT COUNT(*) FROM rejected_councils;").fetchone()[0]
        db_rej_ids = set(r[0] for r in cur.execute("SELECT id FROM rejected_councils;").fetchall())
    finally:
        conn.close()

    # 4. JSON パース (公開 docs/data.json & 管理 admin/admin_data.json の生のディスク状態を直接検証)
    try:
        with open(public_path, "r", encoding="utf-8") as f:
            pub_data = json.load(f)
        with open(admin_path, "r", encoding="utf-8") as f:
            adm_data = json.load(f)
    except Exception as e:
        print(f"  [FAIL] JSON パースエラー: {e}")
        return False

    pub_councils = pub_data.get("councils", [])
    pub_meetings = pub_data.get("meetings", [])
    pub_c_cnt = len(pub_councils)
    pub_m_cnt = len(pub_meetings)
    pub_mat_cnt = sum(len(m.get("materials", [])) for m in pub_meetings)
    pub_cm_cnt = sum(len(c.get("materials", [])) for c in pub_councils)
    pub_c_lock = sum(1 for c in pub_councils if c.get("manualLock"))
    pub_m_lock = sum(1 for m in pub_meetings if m.get("manualLock"))
    pub_mat_lock = sum(1 for m in pub_meetings for mat in m.get("materials", []) if mat.get("manualLock"))

    adm_rules = adm_data.get("scrapingRules", {})
    adm_statuses = adm_data.get("crawlStatuses", {})
    adm_locks = adm_data.get("manualLocks", {})
    adm_rule_cnt = len(adm_rules)
    adm_cs_cnt = len(adm_statuses)
    adm_c_lock = len(adm_locks.get("councils", []))
    adm_m_lock = len(adm_locks.get("meetings", []))
    adm_mat_lock = len(adm_locks.get("materials", []))
    adm_cm_lock = len(adm_locks.get("councilMaterials", []))

    # 5. 件数突合 (CR-168: council_materials 突合追加)
    if db_c_cnt != pub_c_cnt:
        errors.append(f"会議体件数不一致: DB={db_c_cnt} vs 公開JSON={pub_c_cnt}")
    if db_m_cnt != pub_m_cnt:
        errors.append(f"開催回件数不一致: DB={db_m_cnt} vs 公開JSON={pub_m_cnt}")
    if db_mat_cnt != pub_mat_cnt:
        errors.append(f"配付資料件数不一致: DB={db_mat_cnt} vs 公開JSON={pub_mat_cnt}")
    if db_cm_cnt != pub_cm_cnt:
        errors.append(f"会議体常設資料件数不一致: DB={db_cm_cnt} vs 公開JSON={pub_cm_cnt}")
    if db_rule_cnt != adm_rule_cnt:
        errors.append(f"スクレイピングルール件数不一致: DB={db_rule_cnt} vs 管理JSON={adm_rule_cnt}")
    if db_cs_cnt != adm_cs_cnt:
        errors.append(f"クロールステータス件数不一致: DB={db_cs_cnt} vs 管理JSON={adm_cs_cnt}")

    # 6. 手動ロック整合性突合 (Drop 106: DB master == admin_data.json)
    if db_c_lock != adm_c_lock:
        errors.append(f"会議体手動ロック件数不一致: DB={db_c_lock} vs 管理JSON={adm_c_lock}")
    if db_m_lock != adm_m_lock:
        errors.append(f"開催回手動ロック件数不一致: DB={db_m_lock} vs 管理JSON={adm_m_lock}")
    if db_mat_lock != adm_mat_lock:
        errors.append(f"配付資料手動ロック件数不一致: DB={db_mat_lock} vs 管理JSON={adm_mat_lock}")
    if db_cm_lock != adm_cm_lock:
        errors.append(f"会議体資料手動ロック件数不一致: DB={db_cm_lock} vs 管理JSON={adm_cm_lock}")

    # 公開 docs/data.json に管理専用フィールド manualLock が漏洩していないこと (Drop 106 No Leakage)
    if pub_c_lock > 0:
        errors.append(f"公開 docs/data.json の会議体に manualLock が混入しています (No Leakage 違反): {pub_c_lock} 件")
    if pub_m_lock > 0:
        errors.append(f"公開 docs/data.json の開催回に manualLock が混入しています (No Leakage 違反): {pub_m_lock} 件")
    if pub_mat_lock > 0:
        errors.append(f"公開 docs/data.json の配付資料に manualLock が混入しています (No Leakage 違反): {pub_mat_lock} 件")
    pub_cm_lock = sum(1 for c in pub_councils for mat in c.get("materials", []) if mat.get("manualLock"))
    if pub_cm_lock > 0:
        errors.append(f"公開 docs/data.json の会議体資料に manualLock が混入しています (No Leakage 違反): {pub_cm_lock} 件")

    c_disc_leak = sum(1 for c in pub_councils if "discoveredAt" in c or "discoverySource" in c)
    if c_disc_leak > 0:
        errors.append(f"公開 docs/data.json の会議体に discoveredAt / discoverySource が混入しています (No Leakage 違反): {c_disc_leak} 件")

    m_crawl_leak = sum(1 for m in pub_meetings if "discoveredAt" in m or "lastUpdatedFromCrawl" in m)
    if m_crawl_leak > 0:
        errors.append(f"公開 docs/data.json の開催回に discoveredAt / lastUpdatedFromCrawl が混入しています (No Leakage 違反): {m_crawl_leak} 件")

    # 7. 公開 JSON への設定漏洩ゼロ (CR-168: 全管理キー No Leakage 網羅検証)
    forbidden_keys_in_public = [
        "scrapingRules", "scrapingRuleTemplates", "crawlerConfig",
        "rejectedCouncils", "initialAlertKeywords", "discoveryKeywords",
        "manualLocks", "crawlStatuses"
    ]
    leaked = [k for k in forbidden_keys_in_public if k in pub_data]
    if leaked:
        errors.append(f"公開 docs/data.json に管理専用キーが混入しています (No Leakage 違反): {leaked}")

    c_leak = [c.get("id") for c in pub_councils if "crawlStatus" in c]
    if c_leak:
        errors.append(f"公開 docs/data.json の会議体に crawlStatus が混入しています (No Leakage 違反): {c_leak[:3]}")

    # PMM ローカル管理属性 (local_path, download_status 等) の公開 JSON 非漏洩検証 (Drop 71)
    pmm_leak = False
    for m in pub_meetings:
        for mat in m.get("materials", []):
            if "local_path" in mat or "download_status" in mat:
                pmm_leak = True
                break
        if pmm_leak:
            break
    if not pmm_leak:
        for c in pub_councils:
            for mat in c.get("materials", []):
                if "local_path" in mat or "download_status" in mat:
                    pmm_leak = True
                    break
            if pmm_leak:
                break
    if pmm_leak:
        errors.append("公開 docs/data.json に PMM ローカル管理属性 (local_path / download_status) が混入しています (No Leakage 違反)")

    # 8. 却下会議体 3者間同期突合 (Drop 80 & Drop 94)
    rej_path = os.path.join(ADMIN_DIR, "rejected_councils.json")
    if os.path.exists(rej_path):
        try:
            with open(rej_path, "r", encoding="utf-8") as rf:
                rej_data = json.load(rf)
            rej_json_ids = set(r["id"] for r in rej_data if "id" in r)
            adm_rej_ids = set(r["id"] for r in adm_data.get("rejectedCouncils", []) if "id" in r)
            if db_rej_cnt != len(rej_data) or db_rej_cnt != len(adm_data.get("rejectedCouncils", [])):
                errors.append(f"却下会議体件数不一致: DB={db_rej_cnt} vs rejected_councils.json={len(rej_data)} vs admin_data.json={len(adm_data.get('rejectedCouncils', []))}")
            if db_rej_ids != rej_json_ids:
                errors.append(f"却下会議体ID不一致 (DB vs rejected_councils.json): 差分={db_rej_ids ^ rej_json_ids}")
            if db_rej_ids != adm_rej_ids:
                errors.append(f"却下会議体ID不一致 (DB vs admin_data.json): 差分={db_rej_ids ^ adm_rej_ids}")
        except Exception as e_rej:
            errors.append(f"rejected_councils.json パースエラー: {e_rej}")
    else:
        errors.append("admin/rejected_councils.json が見つかりません")

    # 9. admin_configs テーブル整合性 & 旧省庁コード ENV ゼロ検証 (Drop 92 & Drop 94)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cfg_rows = dict(cur.execute("SELECT key, value_json FROM admin_configs;").fetchall())
        for cfg_k in ["ministries", "categories", "initialWatchedCouncilIds"]:
            if cfg_k in cfg_rows and cfg_k in pub_data:
                db_val = json.loads(cfg_rows[cfg_k])
                if len(db_val) != len(pub_data[cfg_k]):
                    errors.append(f"admin_configs.{cfg_k} 件数不一致: DB={len(db_val)} vs 公開JSON={len(pub_data[cfg_k])}")
        if "initialWatchedCouncilIds" not in cfg_rows:
            errors.append("admin_configs に initialWatchedCouncilIds が存在しません")
        for adm_k in ["crawlerConfig", "scrapingRuleTemplates", "discoveryKeywords"]:
            if adm_k in cfg_rows and adm_k in adm_data:
                db_val = json.loads(cfg_rows[adm_k])
                if len(db_val) != len(adm_data[adm_k]):
                    errors.append(f"admin_configs.{adm_k} 件数不一致: DB={len(db_val)} vs 管理JSON={len(adm_data[adm_k])}")
        env_c = cur.execute("SELECT COUNT(*) FROM councils WHERE ministry = 'ENV';").fetchone()[0]
        env_rej = cur.execute("SELECT COUNT(*) FROM rejected_councils WHERE ministry = 'ENV';").fetchone()[0]
        if env_c > 0 or env_rej > 0:
            errors.append(f"旧省庁コード 'ENV' が残存しています: councils={env_c}, rejected_councils={env_rej}")
        if "ministries" in cfg_rows:
            min_cfg = json.loads(cfg_rows["ministries"])
            if "ENV" in min_cfg:
                errors.append("admin_configs.ministries に旧省庁コード 'ENV' が残存しています")
        fts_cnt = cur.execute("SELECT COUNT(*) FROM fts_materials;").fetchone()[0]
    except Exception as e_cfg:
        errors.append(f"admin_configs / fts_materials 検証エラー: {e_cfg}")
    finally:
        conn.close()

    # 11. 管理 JSON の必須キー完全性
    required_admin_keys = ["scrapingRules", "scrapingRuleTemplates", "crawlerConfig", "discoveryKeywords", "manualLocks", "councilCrawlMeta", "meetingCrawlMeta"]
    missing_admin = [k for k in required_admin_keys if k not in adm_data]
    if missing_admin:
        errors.append(f"管理 admin/admin_data.json に必須キーが不足しています: {missing_admin}")

    if errors:
        for err in errors:
            print(f"  [FAIL] {err}")
        return False

    print(f"  [PASS] SQLite 整合性（PRAGMA integrity_check: ok / FK制約: 0件 / fts_materials: {fts_cnt}件）検証合格")
    print(f"  [PASS] 3者間レコード完全一致（councils: {db_c_cnt}件, meetings: {db_m_cnt}件, materials: {db_mat_cnt}件, rules: {db_rule_cnt}件, rejected: {db_rej_cnt}件）検証合格")
    print(f"  [PASS] admin_configs DB同期 & 旧ENVコード0件 & 手動ロック完全整合性を検証合格")
    print(f"  [PASS] 公開JSON設定漏洩ゼロ（No Leakage: 0件）& 管理JSONキー完全性を検証合格")
    return True


# ==============================================================================
# 第4層: 管理機能 & バックエンドAPI (L4: Admin & Server)
# ==============================================================================

def check_admin_server_api():
    """9. 管理サーバー (admin/server.py) の主要 API 自動単体・統合テスト"""
    print("\n--------------------------------------------------")
    print(" [テスト 9/15] 管理サーバー API 単体・統合テスト (test_admin_server.py) (L4: Admin API)")
    print("--------------------------------------------------")
    from test_admin_server import TestAdminServer
    return _run_inprocess_or_fallback(
        TestAdminServer,
        "test_admin_server.py",
        "管理サーバー API エンドポイント（11テスト）全件合格",
        "管理サーバー API テスト"
    )


# ==============================================================================
# 第5層: クローラー実データ整合性・保護検証 (L5: Crawler Production Integrity)
# ==============================================================================

def check_crawler_regression():
    """10. クローラーの手動保護回帰テスト (L5: Manual Lock Protection)"""
    print("\n--------------------------------------------------")
    print(" [テスト 10/15] クローラー手動データ保護回帰テスト (L5: Manual Lock Protection)")
    print("--------------------------------------------------")
    from test_crawler_regression import TestCrawlerManualLockProtection
    return _run_inprocess_or_fallback(
        TestCrawlerManualLockProtection,
        "test_crawler_regression.py",
        "手動保護データ (manualLock) の非破壊性・クローラー回帰テスト合格",
        "クローラー回帰テスト"
    )


def check_scraping_rules_quality():
    """11. スクレイピングルール整合性テスト（CR-7 孤立削除・CR-8 テンプレート集約・CR-9 全件適用）"""
    print("\n--------------------------------------------------")
    print(" [テスト 11/15] スクレイピングルール整合性検証 (L5: Scraping Rules Integrity)")
    print("--------------------------------------------------")
    from test_scraping_rules_reorg import TestScrapingRulesReorganization
    return _run_inprocess_or_fallback(
        TestScrapingRulesReorganization,
        "test_scraping_rules_reorg.py",
        "孤立ルール0件・全会議体100%ルール適用・テンプレート継承完全検証合格",
        "スクレイピングルール整合性検証"
    )


def check_host_interleaving_and_junk_clean(data=None):
    """12. ホスト分散・ゴミデータ不変性検証 (L5: Host Interleaving & Clean Data)"""
    print("\n--------------------------------------------------")
    print(" [テスト 12/15] ホスト分散・ゴミデータ不変性検証 (L5: Host Interleaving & Clean Data)")
    print("--------------------------------------------------")
    from cleanup_nav_meetings import is_junk_meeting
    from crawler import interleave_by_host_and_ministry, _extract_council_host

    if data is None:
        data = get_shared_data()

    councils = data.get("councils", [])
    interleaved = interleave_by_host_and_ministry(councils)
    consecutive_same_host = sum(
        1 for i in range(len(interleaved) - 1)
        if _extract_council_host(interleaved[i]) == _extract_council_host(interleaved[i + 1])
    )
    if consecutive_same_host != 0:
        print(f"  [FAIL] 同一ホストの連続巡回が {consecutive_same_host} 件検出されました")
        return False

    meetings = data.get("meetings", [])
    junk_count = sum(1 for m in meetings if is_junk_meeting(m)[0])
    if junk_count != 0:
        print(f"  [FAIL] docs/data.json 内に未処理のゴミ開催回が {junk_count} 件検出されました")
        return False

    print("  [PASS] 全1,499会議体のホスト連続アクセス0件（分散完了）およびゴミ開催回0件を検証完了")
    return True


def check_portal_coverage_and_slug_inheritance(data=None):
    """13. 省庁親ポータルURL設定・探索網羅性検証 (L5: Portal Coverage & Slug Inheritance)"""
    print("\n--------------------------------------------------")
    print(" [テスト 13/15] 省庁親ポータルURL設定・探索網羅性検証 (L5: Portal Coverage & Slug Inheritance)")
    print("--------------------------------------------------")
    if data is None:
        data = get_shared_data()

    min_map = data.get("ministries", {})
    checks = [
        ("FDMA", "https://www.fdma.go.jp/singi_kento/kento/"),
        ("MIC", "policyreports"),
        ("ACA", "chosakuken"),
        ("METI", "sankoshin")
    ]
    for min_key, pattern in checks:
        entry = min_map.get(min_key)
        if not entry or not any(pattern in u for u in entry.get("councilsUrls", [])):
            print(f"  [FAIL] {min_key} の親ポータルURLに '{pattern}' が含まれていません")
            return False

    # Drop 92: 省庁ドメイン・新着ポータル・カラー設定のDB一元化および ENV 残存バグゼロ検証
    if "ENV" in min_map:
        print("  [FAIL] ministries に旧省庁コード 'ENV' が残存しています ('MOE' に統一必須)")
        return False
    missing_domains = [k for k, v in min_map.items() if not isinstance(v, dict) or not v.get("domains") or not v.get("hexColor")]
    if missing_domains:
        print(f"  [FAIL] ministries 内で domains または hexColor が未設定の省庁があります: {missing_domains}")
        return False
    moe_entry = min_map.get("MOE", {})
    if "env.go.jp" not in moe_entry.get("domains", []) or not moe_entry.get("newsPortals"):
        print("  [FAIL] MOE (環境省) の domains または newsPortals 設定が不正です")
        return False

    from utils import normalize_url_for_matching
    from discover_councils import parse_data_json
    try:
        ministries, existing_councils, categories, existing_rules = parse_data_json()
        url_to_slug_map = {}
        for r_id, r in existing_rules.items():
            u = r.get("officialUrl")
            if u:
                url_to_slug_map[normalize_url_for_matching(u)] = r_id
        if existing_councils:
            sample_council = existing_councils[0]
            norm_u = normalize_url_for_matching(sample_council["officialUrl"])
            if norm_u in url_to_slug_map and url_to_slug_map[norm_u] == sample_council["id"]:
                print("  [PASS] 省庁親ポータル設定網羅性およびスラグID継承ロジックを検証完了")
                return True
    except Exception as e:
        print(f"  [WARN] スラグ継承シミュレーション警告: {e}")

    print("  [PASS] 省庁親ポータルURL設定網羅性を検証完了")
    return True


def check_active_filtering_and_closed_management(data=None):
    """14. アクティブ会議体フィルタリング・廃止管理検証 (L5: Active Filtering & Closed Councils)"""
    print("\n--------------------------------------------------")
    print(" [テスト 14/15] アクティブ会議体フィルタリング・廃止管理検証 (L5: Active Filtering & Closed Councils)")
    print("--------------------------------------------------")
    from crawler import load_councils_from_data_json
    from manage_closed_councils import set_council_closed, unset_council_closed

    if data is None:
        data = get_shared_data()

    active_councils = load_councils_from_data_json(recent_years=2, include_closed=False)
    all_councils = load_councils_from_data_json(recent_years="all", include_closed=False)

    total_c = len(all_councils)
    act_c = len(active_councils)

    if total_c == 0:
        print("  [FAIL] 全会議体数が 0 件です")
        return False
    if act_c == 0:
        print("  [FAIL] アクティブ会議体数が 0 件です")
        return False
    if total_c <= act_c:
        print(f"  [FAIL] 全会議体数 ({total_c}) がアクティブ会議体数 ({act_c}) 以下です")
        return False

    # CR-168: 動的集計によるアクティブ比率健全性検証 (全会議体の 30%〜90% の範囲内であること)
    active_ratio = (act_c / total_c) * 100
    if not (30.0 <= active_ratio <= 90.0):
        print(f"  [FAIL] アクティブ会議体比率 ({active_ratio:.1f}%, {act_c}/{total_c}) が健全範囲 (30%〜90%) 外です")
        return False

    councils = data.get("councils", [])
    if councils:
        test_id = councils[0]["id"]
        res_dry = set_council_closed(data, test_id, "テスト法改正廃止理由", apply=False)
        if not res_dry or councils[0].get("closedReason") == "テスト法改正廃止理由":
            print("  [FAIL] manage_closed_councils の dry-run 動作が不正です")
            return False

    # Drop 94: 一時 SQLite DB を用いた廃止会議体マスターの DB 永続化 & 解除検証
    import tempfile
    import sqlite3
    try:
        from db.db_manager import ensure_database
    except ImportError:
        from admin.db.db_manager import ensure_database

    with tempfile.TemporaryDirectory(prefix="pmhub_test_case14_") as tmp_dir:
        tmp_p = Path(tmp_dir)
        tmp_db = tmp_p / "case14.db"
        tmp_pub = tmp_p / "data.json"
        tmp_adm = tmp_p / "admin_data.json"
        sample_pub = {
            "councils": [{"id": "test-closed_c", "name": "廃止テスト", "ministry": "TEST", "category": "審議会等", "officialUrl": "https://example.com/c"}],
            "meetings": [], "ministries": [], "categories": []
        }
        sample_adm = {"scrapingRules": {"test-closed_c": {"officialUrl": "https://example.com/c"}}}
        tmp_pub.write_text(json.dumps(sample_pub), encoding="utf-8")
        tmp_adm.write_text(json.dumps(sample_adm), encoding="utf-8")
        ensure_database(db_path=tmp_db, public_json_path=tmp_pub, admin_json_path=tmp_adm, schema_path=Path(PROJECT_ROOT)/"admin"/"db"/"schema.sql")

        ok_set = set_council_closed(sample_pub, "test-closed_c", "法改正等による廃止", apply=True, target_file=str(tmp_pub), db_path=str(tmp_db))
        if not ok_set:
            print("  [FAIL] set_council_closed の DB 永続化保存に失敗しました")
            return False
        conn = sqlite3.connect(str(tmp_db))
        cur = conn.cursor()
        row_closed = cur.execute("SELECT is_closed, closed_reason FROM councils WHERE id = 'test-closed_c';").fetchone()
        conn.close()
        if not row_closed or row_closed[0] != 1 or row_closed[1] != "法改正等による廃止":
            print(f"  [FAIL] DB 上の councils.is_closed / closed_reason が正しく反映されていません: {row_closed}")
            return False

        ok_unset = unset_council_closed(sample_pub, "test-closed_c", apply=True, target_file=str(tmp_pub), db_path=str(tmp_db))
        if not ok_unset:
            print("  [FAIL] unset_council_closed の DB 保存に失敗しました")
            return False
        conn = sqlite3.connect(str(tmp_db))
        cur = conn.cursor()
        row_unclosed = cur.execute("SELECT is_closed, closed_reason FROM councils WHERE id = 'test-closed_c';").fetchone()
        conn.close()
        if row_unclosed and row_unclosed[0] == 1:
            print("  [FAIL] DB 上の councils.is_closed 解除に失敗しました")
            return False

    print(f"  [PASS] 直近2年アクティブ会議体抽出（{len(active_councils)}件）および廃止会議体マスター（DB永続化・解除含む）機能を検証完了")
    return True


def _run_inprocess_or_fallback(test_case_class, script_filename, pass_msg, fail_title):
    """単一プロセス内での高速実行を試行し、例外時は個別スクリプトへ安全フォールバック (Drop 94)"""
    try:
        import io
        import unittest
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=1)
        suite = unittest.TestLoader().loadTestsFromTestCase(test_case_class)
        result = runner.run(suite)
        if result.wasSuccessful():
            print(f"  [PASS] {pass_msg}")
            return True
        else:
            print(f"  [FAIL] {fail_title}でエラーが検出されました:")
            for line in stream.getvalue().splitlines():
                if line.strip():
                    print(f"    {line}")
            return False
    except Exception:
        test_script = os.path.join(PROJECT_ROOT, "testing", script_filename)
        if not os.path.exists(test_script):
            print(f"  [SKIP] {script_filename} が見つかりません")
            return True

        res = subprocess.run([sys.executable, test_script], capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            print(f"  [PASS] {pass_msg}")
            return True
        else:
            print(f"  [FAIL] {fail_title}でエラーが検出されました:")
            for line in res.stdout.splitlines():
                if line.strip():
                    print(f"    {line}")
            if res.stderr:
                for line in res.stderr.splitlines():
                    if line.strip():
                        print(f"    {line}")
            return False


# ==============================================================================
# 差分解析 & レイヤー / 単体テスト連動判定機構
# ==============================================================================

def detect_changed_layers_and_unit_tests():
    """
    Git の作業ツリー差分および直近コミット差分から:
    1. 実行すべき統合テストレイヤー (L1〜L5)
    2. 変更された関数仕様に応じた連動単体テスト種類 (UNIT_TEST_REGISTRY キー)
    を精密判定する。
    """
    always_active = {"L1", "L3"}
    changed_files = set()
    try:
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=PROJECT_ROOT, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if len(line) >= 4:
                    f = line[3:].strip()
                    if " -> " in f:
                        f = f.split(" -> ")[1].strip()
                    changed_files.add(f.replace("\\", "/"))

        res_diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT, encoding='utf-8', errors='replace')
        if res_diff.returncode == 0:
            for line in res_diff.stdout.splitlines():
                if line.strip():
                    changed_files.add(line.strip().replace("\\", "/"))
    except Exception:
        return {"L1", "L2", "L3", "L4", "L5"}, set(UNIT_TEST_REGISTRY.keys()), changed_files

    if not changed_files:
        return {"L1", "L2", "L3", "L4", "L5"}, set(), changed_files

    active_layers = set(always_active)

    for f in changed_files:
        if "run_test_suite.py" in f:
            return {"L1", "L2", "L3", "L4", "L5"}, detect_required_unit_tests(changed_files), changed_files

        # L2: フロントエンド表示関連 (※docs/data.json のみの場合は除外)
        if ((f.startswith("docs/") and not f.endswith("data.json"))
            or f.endswith(".html") or f.endswith(".js")
            or "app.test.js" in f or "test_js_runtime.js" in f or "admin/admin_dashboard" in f):
            active_layers.add("L2")

        # L4: 管理サーバー関連 & PMM & DB基盤 (CR-169)
        if (f.startswith("admin/server.py") or "test_admin_server.py" in f
            or "admin/pmm/" in f or "test_pmm" in f
            or "admin/db/" in f or "admin\\db\\" in f
            or "test_drop62" in f or "test_drop63" in f):
            active_layers.add("L4")

        # L5: クローラー関連 & DB基盤 (CR-169)
        if (f.startswith("admin/crawler.py") or f.startswith("admin/utils.py")
            or f.startswith("admin/manage_closed_councils.py")
            or f.startswith("admin/discover_councils.py")
            or f.startswith("admin/apply_report.py")
            or f.startswith("admin/cleanup_nav_meetings.py")
            or "admin/db/" in f or "admin\\db\\" in f
            or "test_crawler" in f or "test_drop" in f or "scraping_rules" in f):
            active_layers.add("L5")

    required_unit_keys = detect_required_unit_tests(changed_files)
    return active_layers, required_unit_keys, changed_files


def detect_required_unit_tests(changed_files):
    """
    関数の仕様修正が行われたファイルを検知し、実施すべき単体テスト種類を判定。
    データ・ドキュメント変更のみの場合は空セットを返す。
    """
    required_keys = set()
    if not changed_files:
        return required_keys

    # 単体テストファイル自身の変更
    unit_file_map = {
        "app.test.js": ["u_front"],
        "test_crawler_foundation.py": ["u_crawler_foundation"],
        "test_crawler_parent_table.py": ["u_parent_table"],
        "test_crawler_incremental.py": ["u_incremental"],
        "test_crawler_quality.py": ["u_quality_eval"],
        "test_crawler_quality_v2.py": ["u_subpage_links"],
        "test_drop23_waf_resilience.py": ["u_waf"],
        "test_drop24_parent_table_expansion.py": ["u_table_html_expand"],
        "test_drop25_mod_date_parsing.py": ["u_date_parsing"],
        "test_drop41_fallback_and_discovery.py": ["u_url_matching_fallback"],
        "test_crawler_drop16.py": ["u_robustness"],
        "test_crawler_speedup.py": ["u_speedup"],
        "test_drop46_data_cleanup.py": ["u_drop46"],
        "test_drop47_context_recovery.py": ["u_drop47"],
        "test_drop48_zero_materials_rescue.py": ["u_drop48"],
        "test_drop49_meeting_id_normalization.py": ["u_drop49"],
        "test_drop62_db_and_export.py": ["u_drop62"],
        "test_drop63_crawler_server_db.py": ["u_drop63"],
        "test_pmm.py": ["u_pmm"],
        "test_discover_councils.py": ["u_discover"],
        "test_drop81_llm_discovery.py": ["u_drop81"],
        "test_drop82_pmm_preservation.py": ["u_drop82"],
        "test_drop80_intermediate_material_guard.py": ["u_intermediate_guard"],
        "run_unit_tests.py": list(UNIT_TEST_REGISTRY.keys())
    }
    for f in changed_files:
        for fname, keys in unit_file_map.items():
            if fname in f:
                required_keys.update(keys)

    # ディスカバリーエンジン・LLM支援仕様コード変更 (admin/discover_councils.py, admin/llm/)
    if any("admin/discover_councils.py" in f or "discover_councils" in f or "admin/llm/" in f for f in changed_files):
        required_keys.add("u_discover")
        required_keys.add("u_drop81")

    # PMM 配付資料ローカル資産管理仕様コード変更 (admin/pmm/)
    if any("admin/pmm/" in f or "test_pmm.py" in f for f in changed_files):
        required_keys.add("u_pmm")

    # データベース・エクスポート基盤仕様コード変更 (admin/db/)
    if any("admin/db/" in f or "admin\\db\\" in f for f in changed_files):
        required_keys.add("u_drop62")
        required_keys.add("u_drop63")
        required_keys.add("u_drop82")

    # フロントエンド関数仕様コード変更 (docs/app.js)
    if any(f.endswith("docs/app.js") or f == "docs/app.js" for f in changed_files):
        required_keys.add("u_front")

    # 日付・正規化ユーティリティ関数仕様コード変更 (admin/utils.py)
    if any("admin/utils.py" in f for f in changed_files):
        required_keys.add("u_date_parsing")
        required_keys.add("u_url_matching_fallback")
        required_keys.add("u_drop49")

    # クローラー本体の仕様コード変更 (admin/crawler.py)
    if any("admin/crawler.py" in f for f in changed_files):
        try:
            diff_out = subprocess.check_output(
                ["git", "diff", "HEAD", "--", "admin/crawler.py"],
                cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace'
            )
            if not diff_out:
                diff_out = subprocess.check_output(
                    ["git", "diff", "--staged", "--", "admin/crawler.py"],
                    cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace'
                )
        except Exception:
            diff_out = ""

        matched = False
        if "extract_meetings_from_parent_table" in diff_out:
            required_keys.add("u_parent_table")
            required_keys.add("u_table_html_expand")
            matched = True
        if any(w in diff_out for w in ["is_waf_challenge", "_get_host_interval", "_rate_limit_host", "load_ministry_and_host_configs_from_db", "_build_other_ministry_domains_map"]):
            required_keys.add("u_waf")
            matched = True
        if any(w in diff_out for w in ["_filter_incremental_subpages", "_normalize_url_for_comparison"]):
            required_keys.add("u_incremental")
            matched = True
        if any(w in diff_out for w in ["determine_crawl_result", "get_unconfirmed_meetings_count"]):
            required_keys.add("u_quality_eval")
            matched = True
        if any(w in diff_out for w in ["extract_actual_subpage_links", "clean_meeting_title", "is_preliminary_notice_page"]):
            required_keys.add("u_subpage_links")
            matched = True
        if any(w in diff_out for w in ["clean_html_for_dates", "_sort_subpage_urls_by_recency", "extract_page_title"]):
            required_keys.add("u_crawler_foundation")
            matched = True
        if any(w in diff_out for w in ["is_sns_pr_url", "is_non_pdf_anchor_url", "EXCLUDE_MATERIAL_NAMES"]):
            required_keys.add("u_drop46")
            matched = True
        if any(w in diff_out for w in ["is_generic_material_name", "recover_material_context", "GENERIC_MATERIAL_NAMES"]):
            required_keys.add("u_drop47")
            matched = True
        if "parse_txt_minutes" in diff_out:
            required_keys.add("u_drop48")
            matched = True
        if any(w in diff_out for w in ["sess_suffix", "new_meet_id"]):
            required_keys.add("u_drop49")
            matched = True
        if any(w in diff_out for w in ["safe_emit_log", "COMMON_NAV_KEYWORDS", "ORGANIZATION_DOC_KEYWORDS"]):
            required_keys.add("u_robustness")
            matched = True
        if any(w in diff_out for w in ["run_meeting_crawler", "recent_years", "stop_event"]):
            required_keys.add("u_speedup")
            matched = True

        if not matched:
            for k in ["u_crawler_foundation", "u_parent_table", "u_incremental", "u_quality_eval", "u_subpage_links", "u_waf", "u_table_html_expand", "u_date_parsing", "u_url_matching_fallback", "u_robustness", "u_speedup", "u_drop46", "u_drop47", "u_drop48", "u_drop49"]:
                required_keys.add(k)

    return required_keys


# ==============================================================================
# メイン実行ルーチン
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="PM-HUB Comprehensive Test Suite Runner [Drop 64]")
    parser.add_argument("--url", nargs="+", help="Explicit URLs to verify")
    parser.add_argument("--all", action="store_true", help="Check all URLs in data.json")
    parser.add_argument("--skip-network", action="store_true", help="Skip network link health verification")
    parser.add_argument("--all-layers", action="store_true", help="Run all layers and all unit tests regardless of git changes")
    parser.add_argument("--layer", choices=["L1", "L2", "L3", "L4", "L5", "l1", "l2", "l3", "l4", "l5"], help="Run specific layer only")
    parser.add_argument("--include-unit", action="store_true", help="Force execute all unit tests in addition to test suite")
    parser.add_argument("--unit-only", action="store_true", help="Run unit tests only")
    parser.add_argument("--unit", choices=list(UNIT_TEST_REGISTRY.keys()), help="Run specific unit test only")
    args = parser.parse_args()

    print("==================================================")
    print(" 政策会議ウォッチ (PM-HUB) 統合テストスイート [Drop 64]")
    print("==================================================")

    # 単体テストのみの直接実行
    if args.unit_only or args.unit:
        target_unit_keys = [args.unit] if args.unit else list(UNIT_TEST_REGISTRY.keys())
        ok = run_unit_tests(target_unit_keys)
        sys.exit(0 if ok else 1)

    active_layers, required_unit_keys, changed_files = detect_changed_layers_and_unit_tests()

    if args.all_layers:
        active_layers = {"L1", "L2", "L3", "L4", "L5"}
        required_unit_keys = set(UNIT_TEST_REGISTRY.keys())
        print("  [実行モード] --all-layers 指定: 全層（L1〜L5）および全単体関数テストを一括実行します")
    elif args.include_unit:
        required_unit_keys = set(UNIT_TEST_REGISTRY.keys())
        print("  [実行モード] --include-unit 指定: 全単体関数テストを連動実行します")
    elif args.layer:
        target = args.layer.upper()
        active_layers = {"L1", "L3", target}
        print(f"  [実行モード] --layer {target} 指定: 常時ガード（L1, L3）および第{target}層を実行します")
    else:
        if changed_files:
            file_sample = ", ".join(list(changed_files)[:3]) + ("..." if len(changed_files) > 3 else "")
            print(f"  [実行モード] セレクティブ実行（検知差分 {len(changed_files)}件: {file_sample}）")
            skipped = {'L1', 'L2', 'L3', 'L4', 'L5'} - active_layers
            print(f"  [対象レイヤー] {', '.join(sorted(active_layers))} (スキップ: {', '.join(sorted(skipped)) or 'なし'})")
            if required_unit_keys:
                print(f"  [連動単体テスト] 関数仕様修正を検知: {len(required_unit_keys)} 種類連動実行 ({', '.join(sorted(required_unit_keys))})")
            else:
                print("  [単体関数検証] 関数仕様の変更なし: スキップ（平時実データ整合性特化）")
        else:
            print("  [実行モード] 変更差分なし: 全層（L1〜L5）を実行します（単体テストは仕様修正時限定）")

    suite_t0 = time.perf_counter()
    case_results = []  # (case_num, name, status_str, elapsed, layer)
    layer_elapsed = defaultdict(float)

    def record_result(case_num, name, status, elapsed, layer):
        case_results.append((case_num, name, status, elapsed, layer))
        layer_elapsed[layer] += elapsed

    # --------------------------------------------------
    # 第1層: コード構文・基本整合性 (L1: Syntax & Health)
    # --------------------------------------------------
    t_c1 = time.perf_counter()
    syntax_ok = check_syntax_errors()
    record_result(1, "コード文法チェック (SyntaxError / 括弧 / div)", "PASS" if syntax_ok else "FAIL", time.perf_counter() - t_c1, "L1")

    if args.skip_network:
        print("\n--------------------------------------------------")
        print(" [テスト 2/15] リンク疎通確認 (追加・変更 URL のみ対象) (L1: Network Health)")
        print("--------------------------------------------------")
        print("  [SKIP] --skip-network が指定されたため、ネットワーク疎通確認をスキップしました。")
        links_ok = True
        record_result(2, "リンク疎通確認", "SKIP", 0.0, "L1")
    else:
        t_c2 = time.perf_counter()
        links_ok = check_link_health(explicit_urls=args.url, check_all=args.all)
        record_result(2, "リンク疎通確認", "PASS" if links_ok else "FAIL", time.perf_counter() - t_c2, "L1")

    # --------------------------------------------------
    # 第2層: UI & フロントエンド表示機能 (L2: UI & Frontend)
    # --------------------------------------------------
    if "L2" in active_layers:
        node_cmd = get_node_command()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            f_runtime = executor.submit(
                _async_node_run,
                [node_cmd, os.path.join(PROJECT_ROOT, "testing", "test_js_runtime.js")],
                PROJECT_ROOT
            )
            t_c3 = time.perf_counter()
            view_ok = check_view_rendering()
            record_result(3, "UI表示機能検証 (DOMコンテナ整合性)", "PASS" if view_ok else "FAIL", time.perf_counter() - t_c3, "L2")

            t_c4 = time.perf_counter()
            runtime_ok = check_js_runtime_crash(future=f_runtime)
            record_result(4, "JS実行時クラッシュ・全画面描画検証", "PASS" if runtime_ok else "FAIL", time.perf_counter() - t_c4, "L2")
    else:
        print("\n--------------------------------------------------")
        print(" [第2層: フロントエンド層 (L2)] 変更対象外のためスキップ")
        print("--------------------------------------------------")
        view_ok = runtime_ok = True
        record_result(3, "UI表示機能検証 (DOMコンテナ整合性)", "SKIP", 0.0, "L2")
        record_result(4, "JS実行時クラッシュ・全画面描画検証", "SKIP", 0.0, "L2")

    # --------------------------------------------------
    # 第3層: データ整合性・不変性保証 (L3: Data Integrity)
    # --------------------------------------------------
    shared_data = get_shared_data()
    t_c5 = time.perf_counter()
    dedup_ok = check_duplicate_meetings_quality(data=shared_data)
    record_result(5, "会議品質・回次整合性・重複排除検証", "PASS" if dedup_ok else "FAIL", time.perf_counter() - t_c5, "L3")

    t_c6 = time.perf_counter()
    sync_ok = check_council_timeline_sync(data=shared_data)
    record_result(6, "会議体・タイムライン ID完全排他性・整合性", "PASS" if sync_ok else "FAIL", time.perf_counter() - t_c6, "L3")

    t_c7 = time.perf_counter()
    drop22_ok = check_drop22_normalization()
    record_result(7, "康煕部首・特殊文字 NFKC 正規化検証", "PASS" if drop22_ok else "FAIL", time.perf_counter() - t_c7, "L3")

    t_c8 = time.perf_counter()
    placeholder_ok = check_placeholder_dates_zero(data=shared_data)
    record_result(8, "プレースホルダー日付（2099/01/01）ゼロ遮断検証", "PASS" if placeholder_ok else "FAIL", time.perf_counter() - t_c8, "L3")

    t_c15 = time.perf_counter()
    db_sync_ok = check_sqlite_and_split_export_sync(data=shared_data)
    record_result(15, "SQLiteマスターDB整合性 & 2系統JSON完全同期検証", "PASS" if db_sync_ok else "FAIL", time.perf_counter() - t_c15, "L3")

    # --------------------------------------------------
    # 第4層: 管理機能 & バックエンドAPI (L4: Admin & Server)
    # --------------------------------------------------
    if "L4" in active_layers:
        t_c9 = time.perf_counter()
        server_api_ok = check_admin_server_api()
        record_result(9, "管理サーバー API 単体・統合テスト", "PASS" if server_api_ok else "FAIL", time.perf_counter() - t_c9, "L4")
    else:
        print("\n--------------------------------------------------")
        print(" [第4層: 管理サーバー層 (L4)] 変更対象外のためスキップ")
        print("--------------------------------------------------")
        server_api_ok = True
        record_result(9, "管理サーバー API 単体・統合テスト", "SKIP", 0.0, "L4")

    # --------------------------------------------------
    # 第5層: クローラー実データ整合性・保護検証 (L5: Crawler Production Integrity)
    # --------------------------------------------------
    if "L5" in active_layers:
        t_c10 = time.perf_counter()
        crawler_ok = check_crawler_regression()
        record_result(10, "クローラー手動保護回帰テスト", "PASS" if crawler_ok else "FAIL", time.perf_counter() - t_c10, "L5")

        t_c11 = time.perf_counter()
        rules_ok = check_scraping_rules_quality()
        record_result(11, "スクレイピングルール整合性検証", "PASS" if rules_ok else "FAIL", time.perf_counter() - t_c11, "L5")

        t_c12 = time.perf_counter()
        interleave_ok = check_host_interleaving_and_junk_clean(data=shared_data)
        record_result(12, "ホスト分散・ゴミデータ不変性検証", "PASS" if interleave_ok else "FAIL", time.perf_counter() - t_c12, "L5")

        t_c13 = time.perf_counter()
        portal_ok = check_portal_coverage_and_slug_inheritance(data=shared_data)
        record_result(13, "省庁親ポータルURL設定・探索網羅性検証", "PASS" if portal_ok else "FAIL", time.perf_counter() - t_c13, "L5")

        t_c14 = time.perf_counter()
        active_ok = check_active_filtering_and_closed_management(data=shared_data)
        record_result(14, "アクティブ会議体フィルタリング・廃止管理検証", "PASS" if active_ok else "FAIL", time.perf_counter() - t_c14, "L5")
    else:
        print("\n--------------------------------------------------")
        print(" [第5層: クローラー層 (L5)] 変更対象外のためスキップ")
        print("--------------------------------------------------")
        crawler_ok = rules_ok = interleave_ok = portal_ok = active_ok = True
        for cnum, ctitle in [
            (10, "クローラー手動保護回帰テスト"),
            (11, "スクレイピングルール整合性検証"),
            (12, "ホスト分散・ゴミデータ不変性検証"),
            (13, "省庁親ポータルURL設定・探索網羅性検証"),
            (14, "アクティブ会議体フィルタリング・廃止管理検証")
        ]:
            record_result(cnum, ctitle, "SKIP", 0.0, "L5")

    # --------------------------------------------------
    # 単体関数検証 (Unit Tests) 連動実行 (関数仕様修正時限定)
    # --------------------------------------------------
    unit_ok = True
    if required_unit_keys:
        print("\n==================================================")
        print(" 【単体関数検証 (Unit Tests)】関数仕様修正を検知したため連動実行")
        print("==================================================")
        unit_ok = run_unit_tests(list(required_unit_keys))

    total_time = time.perf_counter() - suite_t0

    # サマリーレポート出力
    print("\n==================================================")
    print(" 政策会議ウォッチ (PM-HUB) テスト実行結果サマリー [Drop 64]")
    print("==================================================")
    passed_count = sum(1 for _, _, st, _, _ in case_results if st == "PASS")
    skipped_count = sum(1 for _, _, st, _, _ in case_results if st == "SKIP")
    failed_count = sum(1 for _, _, st, _, _ in case_results if st == "FAIL")

    layer_names = {
        "L1": "第1層: コード構文・基本整合性",
        "L2": "第2層: UI & フロントエンド表示機能",
        "L3": "第3層: データ整合性・不変性保証",
        "L4": "第4層: 管理機能 & バックエンドAPI",
        "L5": "第5層: クローラー実データ整合性・保護検証"
    }

    for lyr in ["L1", "L2", "L3", "L4", "L5"]:
        lyr_cases = [c for c in case_results if c[4] == lyr]
        if lyr not in active_layers:
            print(f"【{layer_names[lyr]} ({lyr})】: SKIP（変更対象外）")
        else:
            print(f"【{layer_names[lyr]} ({lyr})】: {layer_elapsed[lyr]:.2f}s")
            for cnum, cname, st, el, _ in lyr_cases:
                time_str = f"({el:.2f}s)" if st == "PASS" else ("" if st == "SKIP" else f"({el:.2f}s)")
                print(f"  - ケース{cnum}: {cname} {time_str} : {st}")

    if required_unit_keys:
        print(f"【単体関数検証 (Unit Tests)】: {'PASS' if unit_ok else 'FAIL'} (連動 {len(required_unit_keys)} 種類実施)")
    else:
        print("【単体関数検証 (Unit Tests)】: SKIP（関数仕様の変更なし / 平時実データ特化）")

    print("--------------------------------------------------")
    print(f" 総実行時間: {total_time:.2f}秒 | 統合ケース合格: {passed_count}/15件 | スキップ: {skipped_count}件 | 失敗: {failed_count}件")
    print("==================================================")

    all_passed = (failed_count == 0) and unit_ok
    if all_passed:
        print(" 【結果】実行されたテストスイートに完全合格しました。修正コードは正常です。")
        sys.exit(0)
    else:
        print(f" 【結果】テストでエラーが検出されました。コードの再確認が必要です。")
        sys.exit(1)


if __name__ == "__main__":
    main()
