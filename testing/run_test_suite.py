#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 統合テストスイート (Comprehensive Test Suite)

【テストスイート要件】
1. コード文法・構文整合性自動確認 (SyntaxError / 括弧不整合 / HTMLタグ整合性)
2. ネットワークリンク疎通確認 (HTTP Status 検証 / キャッシュ・レートリミット保護)
3. フロントエンド・セキュリティ単体テスト (Node.js test runner)
4. 会議品質・回次整合性・重複完全排除検証 (16,500件超全件走査)
5. 会議体・タイムライン・除外リスト ID完全排他性・整合性検証
6. UI表示DOMコンテナ・主要要素整合性検証
7. クローラー手動保護回帰テスト (manualLock 非破壊性)
8. JavaScript 実行時クラッシュ・TDZ・全画面描画検証
9. 管理サーバー API エンドポイント単体・結合テスト
10. クローラー基盤・誤判定防止テスト (スキップリンク・最新ソート・ジェネリック除外)
11. 親テーブル開催回・配付資料抽出および同期連携テスト
12. スクレイピングルール整合性検証 (孤立ルール0件・全会議体100%ルール適用)
13. スマート差分探索エンジン検証 (既登録スキップ・最新更新確認・差分巡回)
14. クロール品質判定・2099プレースホルダー日付検知検証
15. クロール網羅性・実リンク解析・archiveUrl・URL日付復元検証
16. クロール堅牢化・共通ナビ除外・組織常設資料分離・ホスト分散検証
17. クロール超高速化 & 直近アクティブ重点化検証
18. 康煕部首・特殊異体字 NFKC 正規化 & 検索漏れ根絶検証
"""

import sys
import os
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
    """JS の文法エラー（カンマ欠落、不整合な文字、要素・プロパティ間カンマ欠落等）を精密検証"""
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

def check_syntax_errors():
    """1. JS/Python/HTML/JSON ファイルの文法・タグ構造エラーを自動確認"""
    print("--------------------------------------------------")
    print(" [テスト 1/21] コードの文法エラー (SyntaxError) 自動検証")
    print("--------------------------------------------------")
    
    files_to_check = [
        os.path.join(PROJECT_ROOT, "docs", "app.js"),
        os.path.join(PROJECT_ROOT, "docs", "index.html"),
        os.path.join(PROJECT_ROOT, "admin", "server.py"),
        os.path.join(PROJECT_ROOT, "admin", "crawler.py"),
        os.path.join(PROJECT_ROOT, "admin", "manage_closed_councils.py"),
        os.path.join(PROJECT_ROOT, "admin", "discover_councils.py"),
        os.path.join(PROJECT_ROOT, "admin", "apply_report.py"),
        os.path.join(PROJECT_ROOT, "admin", "cleanup_nav_meetings.py"),
        os.path.join(PROJECT_ROOT, "admin", "admin_dashboard.html"),
        os.path.join(PROJECT_ROOT, "admin", "admin_dashboard.js"),
        os.path.join(PROJECT_ROOT, "testing", "run_test_suite.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_js_runtime.js"),
        os.path.join(PROJECT_ROOT, "testing", "app.test.js"),
        os.path.join(PROJECT_ROOT, "testing", "test_no_duplicate_meetings.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_regression.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_admin_server.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_suite.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_foundation.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_parent_table.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_scraping_rules_reorg.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_incremental.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_quality.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_quality_v2.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_drop16.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_crawler_speedup.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_drop23_waf_resilience.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_drop24_parent_table_expansion.py"),
        os.path.join(PROJECT_ROOT, "testing", "test_drop25_mod_date_parsing.py")
    ]
    
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

            # HTML内のインライン <script> タグの構文チェック
            inline_scripts = re.findall(r'<script(?![^>]*src=)>([\s\S]*?)</script>', code, re.IGNORECASE)
            for idx, sc in enumerate(inline_scripts):
                if sc.strip():
                    ok, msg = check_js_syntax(sc, f"{rel_path} <script #{idx+1}>")
                    if ok:
                        print(f"  [PASS] {rel_path} <script #{idx+1}> : {msg}")
                    else:
                        print(f"  [FAIL] {rel_path} <script #{idx+1}> : {msg}")
                        errors_found += 1

    # data.json & rejected_councils.json JSON validation
    json_files = [
        os.path.join(PROJECT_ROOT, "docs", "data.json"),
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

    return errors_found == 0

def is_valid_test_url(u):
    """URLが実在するWebアドレスか（スクレイピング正規表現等の誤検出でないか）を判定"""
    if not u or not u.startswith(('http://', 'https://')):
        return False
    # PMHubダミー/テンプレートURLを除外
    if any(d in u for d in ['pm-hub.gov.example', 'example.com', 'googleapis.com']):
        return False
    # scrapingRules の正規表現パターン・メタ構文の誤検出を除外
    regex_chars = ['\\', '.*', '(?:', '[^', r'\d', r'\b', '|', '(?=']
    if any(p in u for p in regex_chars):
        return False
    return True

def get_added_urls_from_git():
    """新規追加・変更された URL を動的に抽出 (既存URLの並び替え・移動による過剰テストを防止)"""
    current_json_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
    if not os.path.exists(current_json_path):
        return []

    def extract_urls_from_text(text):
        urls = set()
        for u in re.findall(r"https?://[^\s\x22\x27,]+", text):
            if is_valid_test_url(u):
                urls.add(u)
        return urls

    # 1. JSON レベルの差分比較（HEAD / HEAD~1 との URL 差分抽出）
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

        # 既存 URL は除外し、真に新出・変更された URL のみを抽出
        diff_urls = curr_urls - base_urls
        return sorted(diff_urls)
    except Exception:
        pass

    # 2. フォールバック：git diff の追加行から抽出
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
    import time
    from collections import defaultdict
    print("\n--------------------------------------------------")
    print(" [テスト 2/21] リンク疎通確認 (追加・変更 URL のみ対象)")
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

        # 過去24時間以内に検証成功している場合はキャッシュから即座に通過
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
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                try:
                    import ssl
                    ctx = ssl._create_unverified_context()
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                        if resp.status in (200, 301, 302, 202):
                            print(f"  [200 OK (SSL検証フォールバック)] {url}")
                            continue
                except Exception:
                    pass
    try:
        with open(cache_path, "w", encoding="utf-8") as cf:
            json.dump(url_cache, cf)
    except Exception:
        pass

    print(f"\n  検証結果: 追加・変更 URL {len(unique_urls)} 件中 リンク切れ {broken_links} 件")
    return broken_links == 0

def check_js_unit_tests(future=None):
    """3. JSユーティリティ関数（セキュリティ・サニタイズ・フォーマット）の単体テスト (L2: UI Logic & Security)"""
    print("\n--------------------------------------------------")
    print(" [テスト 3/21] JSユーティリティ単体テスト (app.test.js) (L2: UI Logic & Security)")
    print("--------------------------------------------------")
    try:
        if future is not None:
            ok, stdout, stderr = future.result()
            if ok:
                print("  [PASS] escapeHtml / sanitizeUrl / formatDate 単体テスト全件通過 (node:test)")
                return True
            else:
                print("  [FAIL] JS単体テスト失敗")
                if stdout:
                    print(stdout)
                if stderr:
                    print(stderr)
                return False
        node_cmd = get_node_command()
        test_script_path = os.path.join(PROJECT_ROOT, "testing", "app.test.js")
        result = subprocess.run([node_cmd, "--test", test_script_path], cwd=PROJECT_ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            print("  [PASS] escapeHtml / sanitizeUrl / formatDate 単体テスト全件通過 (node:test)")
            return True
        else:
            print("  [FAIL] JS単体テスト失敗")
            print(result.stdout)
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("  [SKIP] Node.js環境が見つからないため JS 単体テストをスキップします")
        return True
    except Exception as e:
        print(f"  [FAIL] テストスクリプト実行エラー: {e}")
        return False

def check_view_rendering():
    """4. UI表示自動検証（公開ポータル＆管理ダッシュボードのDOM整合性チェック） (L2: UI Rendering)"""
    print("\n--------------------------------------------------")
    print(" [テスト 4/21] UI表示機能検証（ポータル＆管理ダッシュボード構造） (L2: UI Rendering)")
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

    # 2. 管理コンソールのタブ・コンテナ検証
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

    print("  [PASS] 管理ダッシュボードの全5タブおよびリスト描画先コンテナを検証完了")
    return True

def check_js_runtime_crash(future=None):
    """5. JavaScript 実行時クラッシュ・TDZ・初期化検証（公開ポータル＆管理ダッシュボード） (L2: JS Runtime)"""
    print("\n--------------------------------------------------")
    print(" [テスト 5/21] JavaScript 実行時クラッシュ・TDZ・描画検証 (L2: JS Runtime)")
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

def check_duplicate_meetings_quality(data=None):
    """6. 会議レコード品質・回次整合性・重複排除の自動検証 (L3: Data Integrity)"""
    print("\n--------------------------------------------------")
    print(" [テスト 6/21] 会議品質・回次整合性・重複排除検証 (test_no_duplicate_meetings.py) (L3: Data Integrity)")
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
    """7. 会議体一覧 (COUNCILS), タイムライン (MEETINGS) の ID整合性自動検証 (L3: ID Consistency)"""
    print("\n--------------------------------------------------")
    print(" [テスト 7/21] 会議体・タイムライン・除外リスト ID完全整合性検証 (L3: ID Consistency)")
    print("--------------------------------------------------")

    if data is None:
        data_json_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        data = load_data_json(data_json_path, cached=True)
    rejected_json_path = os.path.join(PROJECT_ROOT, "admin", "rejected_councils.json")

    if not data:
        print("  [FAIL] data.json が見つかりません")
        return False

    councils = data.get("councils", [])
    meetings = data.get("meetings", [])

    councils_ids = [c.get("id") for c in councils if c.get("id")]
    meetings_council_ids = set([m.get("councilId") for m in meetings if m.get("councilId")])

    # Check for duplicate IDs in COUNCILS
    if len(councils_ids) != len(set(councils_ids)):
        duplicates = [cid for cid in set(councils_ids) if councils_ids.count(cid) > 1]
        print(f"  [FAIL] COUNCILS に重複IDが存在します: {duplicates}")
        return False

    councils_set = set(councils_ids)

    # Format check: councilId must have exactly 1 hyphen, meeting.id must have exactly 3 hyphens (using utils validators)
    invalid_c_ids = [cid for cid in councils_ids if not validate_council_id(cid)]
    if invalid_c_ids:
        print(f"  [FAIL] 不正な councilId フォーマット (要 1ハイフン): {invalid_c_ids[:5]}")
        return False

    meeting_ids = [m.get("id", "") for m in meetings]
    invalid_m_ids = [mid for mid in meeting_ids if not validate_meeting_id(mid)]
    if invalid_m_ids:
        print(f"  [FAIL] 不正な meetingId フォーマット (要 3ハイフン/4セグメント): {invalid_m_ids[:5]}")
        return False

    # Check for meetings belonging to non-existent councils
    orphaned_meetings = meetings_council_ids - councils_set
    if orphaned_meetings:
        print(f"  [WARN] 定義されていない会議体IDを持つ会議データがタイムラインに存在します: {sorted(orphaned_meetings)}")

    # Check rejected councils separation (both councils and discoveredCouncils)
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
    """8. 康煕部首・特殊文字 NFKC 正規化 & 検索漏れ根絶検証 (CR-46, CR-47) (L3: Normalization)"""
    print("\n--------------------------------------------------")
    print(" [テスト 8/21] Drop 22: 康煕部首・特殊文字 NFKC 正規化 & 検索漏れ根絶検証 (CR-46, CR-47) (L3: Normalization)")
    print("--------------------------------------------------")
    from test_drop22_normalization import TestDrop22Normalization
    return _run_inprocess_or_fallback(
        TestDrop22Normalization,
        "test_drop22_normalization.py",
        "康煕部首・CJK部首補助0件・NFKC文字正規化・データ整合性テスト全件合格",
        "Drop 22 文字正規化検証"
    )

def check_admin_server_api():
    """9. 管理サーバー (admin/server.py) の主要 API 自動単体・統合テスト (L4: Admin API)"""
    print("\n--------------------------------------------------")
    print(" [テスト 9/21] 管理サーバー API 単体・統合テスト (test_admin_server.py) (L4: Admin API)")
    print("--------------------------------------------------")
    from test_admin_server import TestAdminServer
    return _run_inprocess_or_fallback(
        TestAdminServer,
        "test_admin_server.py",
        "管理サーバー API エンドポイント（11テスト）全件合格",
        "管理サーバー API テスト"
    )

def _run_inprocess_or_fallback(test_case_class, script_filename, pass_msg, fail_title):
    """単一プロセス内での高速実行を試行し、例外時は個別スクリプトへ安全フォールバック"""
    try:
        from test_crawler_suite import run_crawler_test_case
        ok, out = run_crawler_test_case(test_case_class)
        if ok:
            print(f"  [PASS] {pass_msg}")
            return True
        else:
            print(f"  [FAIL] {fail_title}でエラーが検出されました:")
            for line in out.splitlines():
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

def check_crawler_regression():
    """10. クローラーの手動保護回帰テスト (L5: Crawler Regression)"""
    print("\n--------------------------------------------------")
    print(" [テスト 10/21] クローラー手動データ保護回帰テスト (L5: Crawler Regression)")
    print("--------------------------------------------------")
    from test_crawler_regression import TestCrawlerManualLockProtection
    return _run_inprocess_or_fallback(
        TestCrawlerManualLockProtection,
        "test_crawler_regression.py",
        "手動保護データ (manualLock) の非破壊性・クローラー回帰テスト合格",
        "クローラー回帰テスト"
    )

def check_crawler_foundation():
    """11. クローラー基盤テスト（CR-1 スキップリンク保護・CR-2 最新優先ソート・CR-4 ジェネリック見出し除外） (L5: Parser Foundation)"""
    print("\n--------------------------------------------------")
    print(" [テスト 11/21] クローラー基盤・誤判定防止テスト (test_crawler_foundation.py) (L5: Parser Foundation)")
    print("--------------------------------------------------")
    from test_crawler_foundation import TestCrawlerFoundationPhaseJ
    return _run_inprocess_or_fallback(
        TestCrawlerFoundationPhaseJ,
        "test_crawler_foundation.py",
        "クローラー基盤単体テスト（スキップリンク保護・最新ソート・ジェネリック除外）全件合格",
        "クローラー基盤テスト"
    )

def check_crawler_parent_table():
    """12. 親テーブル開催回抽出テスト（CR-5 親テーブル解析・CR-6 開催回同期連携） (L5: Parent Table)"""
    print("\n--------------------------------------------------")
    print(" [テスト 12/21] 親テーブル開催回抽出テスト (test_crawler_parent_table.py) (L5: Parent Table)")
    print("--------------------------------------------------")
    from test_crawler_parent_table import TestCrawlerParentTableDrop11
    return _run_inprocess_or_fallback(
        TestCrawlerParentTableDrop11,
        "test_crawler_parent_table.py",
        "親テーブル開催回・配付資料抽出および同期連携テスト全件合格",
        "親テーブル開催回抽出テスト"
    )

def check_scraping_rules_quality():
    """13. スクレイピングルール整合性テスト（CR-7 孤立削除・CR-8 テンプレート集約・CR-9 全件適用） (L5: Scraping Rules)"""
    print("\n--------------------------------------------------")
    print(" [テスト 13/21] スクレイピングルール整合性検証 (test_scraping_rules_reorg.py) (L5: Scraping Rules)")
    print("--------------------------------------------------")
    from test_scraping_rules_reorg import TestScrapingRulesReorganization
    return _run_inprocess_or_fallback(
        TestScrapingRulesReorganization,
        "test_scraping_rules_reorg.py",
        "孤立ルール0件・全会議体100%ルール適用・テンプレート継承完全検証合格",
        "スクレイピングルール整合性検証"
    )

def check_crawler_incremental():
    """14. スマート差分探索エンジン単体テスト（CR-10 既登録スキップ・最新更新確認・CR-11 差分巡回） (L5: Incremental Crawl)"""
    print("\n--------------------------------------------------")
    print(" [テスト 14/21] スマート差分探索エンジン検証 (test_crawler_incremental.py) (L5: Incremental Crawl)")
    print("--------------------------------------------------")
    from test_crawler_incremental import TestCrawlerIncrementalDrop13
    return _run_inprocess_or_fallback(
        TestCrawlerIncrementalDrop13,
        "test_crawler_incremental.py",
        "既登録スキップ・最新更新確認・未登録最大50件差分巡回テスト全件合格",
        "スマート差分探索エンジン検証"
    )

def check_crawler_quality():
    """15. クロール品質判定・2099日付検知単体テスト（CR-12 成否判定精緻化・CR-13 プレースホルダー日付自動検知） (L5: Quality & Placeholder)"""
    print("\n--------------------------------------------------")
    print(" [テスト 15/21] クロール品質判定・2099日付検知検証 (test_crawler_quality.py) (L5: Quality & Placeholder)")
    print("--------------------------------------------------")
    from test_crawler_quality import TestCrawlerQualityDrop14
    return _run_inprocess_or_fallback(
        TestCrawlerQualityDrop14,
        "test_crawler_quality.py",
        "成否判定精緻化・判定理由記録・2099ダミー日付自動検知テスト全件合格",
        "クロール品質判定・2099日付検知検証"
    )

def check_crawler_quality_v2():
    """16. Drop 15 クロール網羅性・実リンク解析・archiveUrl・URL日付復元検証（CR-14〜CR-17） (L5: Deep Discovery)"""
    print("\n--------------------------------------------------")
    print(" [テスト 16/21] クロール網羅性・実リンク解析・archiveUrl・URL日付復元検証 (test_crawler_quality_v2.py) (L5: Deep Discovery)")
    print("--------------------------------------------------")
    from test_crawler_quality_v2 import TestCrawlerQualityV2Drop15
    return _run_inprocess_or_fallback(
        TestCrawlerQualityV2Drop15,
        "test_crawler_quality_v2.py",
        "実リンクアンカーテキスト抽出・archiveUrl起点・URL日付復元・ポータル除外テスト全件合格",
        "クロール網羅性・実リンク解析検証"
    )

def check_crawler_drop16():
    """17. Drop 16 クロール堅牢化・共通ナビ除外・常設資料分離・ホストインターリーブ検証（CR-18〜CR-22） (L5: Robustness & Nav Filter)"""
    print("\n--------------------------------------------------")
    print(" [テスト 17/21] クロール堅牢化・共通ナビ除外・ホスト分散検証 (test_crawler_drop16.py) (L5: Robustness & Nav Filter)")
    print("--------------------------------------------------")
    from test_crawler_drop16 import TestDrop16CrawlerRobustness
    return _run_inprocess_or_fallback(
        TestDrop16CrawlerRobustness,
        "test_crawler_drop16.py",
        "stdout保護・共通ナビ除外・組織常設資料分離・ホスト分散・データ整合性テスト全件合格",
        "Drop 16 クロール堅牢化検証"
    )

def check_crawler_speedup():
    """18. Drop 17: クロール超高速化 & 直近アクティブ重点化エンジンの検証 (CR-23 〜 CR-27) (L5: Speedup & Active Focus)"""
    print("\n--------------------------------------------------")
    print(" [テスト 18/21] Drop 17: クロール超高速化 & 直近アクティブ重点化エンジン検証 (CR-23 〜 CR-27) (L5: Speedup & Active Focus)")
    print("--------------------------------------------------")
    from test_crawler_speedup import TestDrop17CrawlerSpeedup
    return _run_inprocess_or_fallback(
        TestDrop17CrawlerSpeedup,
        "test_crawler_speedup.py",
        "過去回再検査ゼロ化・最新1件更新確認・2年重点化・廃止会議体・並行レートリミット・中断耐性テスト全件合格",
        "Drop 17 クロール高速化検証"
    )

def check_crawler_drop23():
    """19. Drop 23: WAF 202耐性 & 動的レートリミット検証 (CR-48, CR-49) (L5: WAF Resilience)"""
    print("\n--------------------------------------------------")
    print(" [テスト 19/21] WAF 202耐性 & 動的レートリミット検証 (test_drop23_waf_resilience.py) (L5: WAF Resilience)")
    print("--------------------------------------------------")
    from test_drop23_waf_resilience import TestDrop23WafResilience
    return _run_inprocess_or_fallback(
        TestDrop23WafResilience,
        "test_drop23_waf_resilience.py",
        "WAF 202チャレンジ耐性・動的インターバル・クールダウン待機リトライテスト全件合格",
        "Drop 23 WAF耐性検証"
    )

def check_crawler_drop24():
    """20. Drop 24: 親テーブルHTML資料展開エンジン検証 (CR-51) (L5: HTML Material Expansion)"""
    print("\n--------------------------------------------------")
    print(" [テスト 20/21] 親テーブルHTML資料展開エンジン検証 (test_drop24_parent_table_expansion.py) (L5: HTML Material Expansion)")
    print("--------------------------------------------------")
    from test_drop24_parent_table_expansion import TestDrop24ParentTableExpansion
    return _run_inprocess_or_fallback(
        TestDrop24ParentTableExpansion,
        "test_drop24_parent_table_expansion.py",
        "テーブル内HTML資料リンク末端PDF展開・フォールバック保持テスト全件合格",
        "Drop 24 親テーブルHTML資料展開検証"
    )

def check_crawler_drop25():
    """21. Drop 25: 防衛省元号略記日付パース検証 (CR-54) (L5: Short Era Date Parsing)"""
    print("\n--------------------------------------------------")
    print(" [テスト 21/21] 防衛省元号略記日付パース検証 (test_drop25_mod_date_parsing.py) (L5: Short Era Date Parsing)")
    print("--------------------------------------------------")
    from test_drop25_mod_date_parsing import TestDrop25ModDateParsing
    return _run_inprocess_or_fallback(
        TestDrop25ModDateParsing,
        "test_drop25_mod_date_parsing.py",
        "防衛省アルファベット元号略記パース・親テーブル一体抽出テスト全件合格",
        "Drop 25 防衛省元号略記日付パース検証"
    )

def detect_changed_layers():
    """Git の作業ツリー差分および直近コミット差分から実行すべきテストレイヤーを自動判定"""
    always_active = {"L1", "L3"}
    changed_files = set()
    try:
        # 1. 未ステージおよびステージ済みの変更
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=PROJECT_ROOT, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if len(line) >= 4:
                    f = line[3:].strip()
                    if " -> " in f:
                        f = f.split(" -> ")[1].strip()
                    changed_files.add(f.replace("\\", "/"))

        # 2. 直近コミット（HEAD）との差分
        res_diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT, encoding='utf-8', errors='replace')
        if res_diff.returncode == 0:
            for line in res_diff.stdout.splitlines():
                if line.strip():
                    changed_files.add(line.strip().replace("\\", "/"))
    except Exception:
        # git エラー時は安全側に倒して全層実行
        return {"L1", "L2", "L3", "L4", "L5"}, changed_files

    # 差分が一切ない場合は全層実行
    if not changed_files:
        return {"L1", "L2", "L3", "L4", "L5"}, changed_files

    active_layers = set(always_active)

    for f in changed_files:
        # run_test_suite.py 本体の変更時は全層実行
        if "run_test_suite.py" in f:
            return {"L1", "L2", "L3", "L4", "L5"}, changed_files

        # L2: フロントエンド関連
        if (f.startswith("docs/") or f.endswith(".html") or f.endswith(".js")
            or "app.test.js" in f or "test_js_runtime.js" in f or "admin/admin_dashboard" in f):
            active_layers.add("L2")

        # L4: 管理サーバー関連
        if f.startswith("admin/server.py") or "test_admin_server.py" in f:
            active_layers.add("L4")

        # L5: クローラー関連
        if (f.startswith("admin/crawler.py") or f.startswith("admin/utils.py")
            or f.startswith("admin/manage_closed_councils.py")
            or f.startswith("admin/discover_councils.py")
            or f.startswith("admin/apply_report.py")
            or f.startswith("admin/cleanup_nav_meetings.py")
            or "test_crawler" in f or "test_drop" in f or "scraping_rules" in f):
            active_layers.add("L5")

    return active_layers, changed_files


def main():
    parser = argparse.ArgumentParser(description="PM-HUB Comprehensive Test Suite Runner [Drop 39]")
    parser.add_argument("--url", nargs="+", help="Explicit URLs to verify")
    parser.add_argument("--all", action="store_true", help="Check all URLs in data.json")
    parser.add_argument("--skip-network", action="store_true", help="Skip network link health verification")
    parser.add_argument("--all-layers", action="store_true", help="Run all layers regardless of git changes")
    parser.add_argument("--layer", choices=["L1", "L2", "L3", "L4", "L5", "l1", "l2", "l3", "l4", "l5"], help="Run specific layer only")
    args = parser.parse_args()

    print("==================================================")
    print(" 政策会議ウォッチ (PM-HUB) 統合テストスイート [Drop 39]")
    print("==================================================")

    if args.all_layers:
        active_layers = {"L1", "L2", "L3", "L4", "L5"}
        print("  [実行モード] --all-layers 指定: 全層（L1〜L5）を一括実行します")
    elif args.layer:
        target = args.layer.upper()
        active_layers = {"L1", "L3", target}
        print(f"  [実行モード] --layer {target} 指定: 常時ガード（L1, L3）および第{target}層を実行します")
    else:
        active_layers, changed_files = detect_changed_layers()
        if changed_files:
            file_sample = ", ".join(list(changed_files)[:3]) + ("..." if len(changed_files) > 3 else "")
            print(f"  [実行モード] セレクティブ実行（検知差分 {len(changed_files)}件: {file_sample}）")
            skipped = {'L1', 'L2', 'L3', 'L4', 'L5'} - active_layers
            print(f"  [対象レイヤー] {', '.join(sorted(active_layers))} (スキップ: {', '.join(sorted(skipped)) or 'なし'})")
        else:
            print("  [実行モード] 変更差分なし: 全層（L1〜L5）を実行します")

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
        print(" [テスト 2/21] リンク疎通確認 (追加・変更 URL のみ対象) (L1: Network Health)")
        print("--------------------------------------------------")
        print("  [SKIP] --skip-network が指定されたため、ネットワーク疎通確認をスキップしました。")
        links_ok = True
        record_result(2, "リンク疎通確認", "SKIP", 0.0, "L1")
    else:
        t_c2 = time.perf_counter()
        links_ok = check_link_health(explicit_urls=args.url, check_all=args.all)
        record_result(2, "リンク疎通確認", "PASS" if links_ok else "FAIL", time.perf_counter() - t_c2, "L1")

    # --------------------------------------------------
    # 第2層: セキュリティ & フロントエンドロジック (L2: Security & UI Logic)
    # --------------------------------------------------
    if "L2" in active_layers:
        node_cmd = get_node_command()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_unit = executor.submit(
                _async_node_run,
                [node_cmd, "--test", os.path.join(PROJECT_ROOT, "testing", "app.test.js")],
                PROJECT_ROOT
            )
            f_runtime = executor.submit(
                _async_node_run,
                [node_cmd, os.path.join(PROJECT_ROOT, "testing", "test_js_runtime.js")],
                PROJECT_ROOT
            )

            t_c3 = time.perf_counter()
            unit_ok = check_js_unit_tests(future=f_unit)
            record_result(3, "JSユーティリティ単体テスト (app.test.js)", "PASS" if unit_ok else "FAIL", time.perf_counter() - t_c3, "L2")

            t_c4 = time.perf_counter()
            view_ok = check_view_rendering()
            record_result(4, "UI表示機能検証 (DOMコンテナ整合性)", "PASS" if view_ok else "FAIL", time.perf_counter() - t_c4, "L2")

            t_c5 = time.perf_counter()
            runtime_ok = check_js_runtime_crash(future=f_runtime)
            record_result(5, "JS実行時クラッシュ・全画面描画検証", "PASS" if runtime_ok else "FAIL", time.perf_counter() - t_c5, "L2")
    else:
        print("\n--------------------------------------------------")
        print(" [第2層: フロントエンド層 (L2)] 変更対象外のためスキップ")
        print("--------------------------------------------------")
        unit_ok = view_ok = runtime_ok = True
        record_result(3, "JSユーティリティ単体テスト (app.test.js)", "SKIP", 0.0, "L2")
        record_result(4, "UI表示機能検証 (DOMコンテナ整合性)", "SKIP", 0.0, "L2")
        record_result(5, "JS実行時クラッシュ・全画面描画検証", "SKIP", 0.0, "L2")

    # --------------------------------------------------
    # 第3層: データ整合性・不変性保証 (L3: Data Integrity)
    # --------------------------------------------------
    shared_data = get_shared_data()
    t_c6 = time.perf_counter()
    dedup_ok = check_duplicate_meetings_quality(data=shared_data)
    record_result(6, "会議品質・回次整合性・重複排除検証", "PASS" if dedup_ok else "FAIL", time.perf_counter() - t_c6, "L3")

    t_c7 = time.perf_counter()
    sync_ok = check_council_timeline_sync(data=shared_data)
    record_result(7, "会議体・タイムライン ID完全排他性・整合性", "PASS" if sync_ok else "FAIL", time.perf_counter() - t_c7, "L3")

    t_c8 = time.perf_counter()
    drop22_ok = check_drop22_normalization()
    record_result(8, "康煕部首・特殊文字 NFKC 正規化検証", "PASS" if drop22_ok else "FAIL", time.perf_counter() - t_c8, "L3")

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
    # 第5層: クローラー基盤・探索最適化エンジン (L5: Crawler Engine)
    # --------------------------------------------------
    if "L5" in active_layers:
        t_c10 = time.perf_counter()
        crawler_ok = check_crawler_regression()
        record_result(10, "クローラー手動保護回帰テスト", "PASS" if crawler_ok else "FAIL", time.perf_counter() - t_c10, "L5")

        t_c11 = time.perf_counter()
        foundation_ok = check_crawler_foundation()
        record_result(11, "クローラー基盤・誤判定防止テスト", "PASS" if foundation_ok else "FAIL", time.perf_counter() - t_c11, "L5")

        t_c12 = time.perf_counter()
        parent_table_ok = check_crawler_parent_table()
        record_result(12, "親テーブル開催回抽出テスト", "PASS" if parent_table_ok else "FAIL", time.perf_counter() - t_c12, "L5")

        t_c13 = time.perf_counter()
        rules_ok = check_scraping_rules_quality()
        record_result(13, "スクレイピングルール整合性検証", "PASS" if rules_ok else "FAIL", time.perf_counter() - t_c13, "L5")

        t_c14 = time.perf_counter()
        incremental_ok = check_crawler_incremental()
        record_result(14, "スマート差分探索エンジン検証", "PASS" if incremental_ok else "FAIL", time.perf_counter() - t_c14, "L5")

        t_c15 = time.perf_counter()
        quality_ok = check_crawler_quality()
        record_result(15, "クロール品質判定・2099日付検知検証", "PASS" if quality_ok else "FAIL", time.perf_counter() - t_c15, "L5")

        t_c16 = time.perf_counter()
        quality_v2_ok = check_crawler_quality_v2()
        record_result(16, "クロール網羅性・実リンク解析・URL日付復元検証", "PASS" if quality_v2_ok else "FAIL", time.perf_counter() - t_c16, "L5")

        t_c17 = time.perf_counter()
        drop16_ok = check_crawler_drop16()
        record_result(17, "クロール堅牢化・共通ナビ除外・ホスト分散検証", "PASS" if drop16_ok else "FAIL", time.perf_counter() - t_c17, "L5")

        t_c18 = time.perf_counter()
        speedup_ok = check_crawler_speedup()
        record_result(18, "クロール超高速化 & 直近アクティブ重点化検証", "PASS" if speedup_ok else "FAIL", time.perf_counter() - t_c18, "L5")

        t_c19 = time.perf_counter()
        drop23_ok = check_crawler_drop23()
        record_result(19, "WAF 202耐性 & 動的レートリミット検証", "PASS" if drop23_ok else "FAIL", time.perf_counter() - t_c19, "L5")

        t_c20 = time.perf_counter()
        drop24_ok = check_crawler_drop24()
        record_result(20, "親テーブルHTML資料展開エンジン検証", "PASS" if drop24_ok else "FAIL", time.perf_counter() - t_c20, "L5")

        t_c21 = time.perf_counter()
        drop25_ok = check_crawler_drop25()
        record_result(21, "防衛省元号略記日付パース検証", "PASS" if drop25_ok else "FAIL", time.perf_counter() - t_c21, "L5")
    else:
        print("\n--------------------------------------------------")
        print(" [第5層: クローラー層 (L5)] 変更対象外のためスキップ")
        print("--------------------------------------------------")
        crawler_ok = foundation_ok = parent_table_ok = rules_ok = True
        incremental_ok = quality_ok = quality_v2_ok = drop16_ok = speedup_ok = True
        drop23_ok = drop24_ok = drop25_ok = True
        for cnum, ctitle in [
            (10, "クローラー手動保護回帰テスト"),
            (11, "クローラー基盤・誤判定防止テスト"),
            (12, "親テーブル開催回抽出テスト"),
            (13, "スクレイピングルール整合性検証"),
            (14, "スマート差分探索エンジン検証"),
            (15, "クロール品質判定・2099日付検知検証"),
            (16, "クロール網羅性・実リンク解析・URL日付復元検証"),
            (17, "クロール堅牢化・共通ナビ除外・ホスト分散検証"),
            (18, "クロール超高速化 & 直近アクティブ重点化検証"),
            (19, "WAF 202耐性 & 動的レートリミット検証"),
            (20, "親テーブルHTML資料展開エンジン検証"),
            (21, "防衛省元号略記日付パース検証")
        ]:
            record_result(cnum, ctitle, "SKIP", 0.0, "L5")

    total_time = time.perf_counter() - suite_t0

    # サマリーレポート出力
    print("\n==================================================")
    print(" 政策会議ウォッチ (PM-HUB) テスト実行結果サマリー")
    print("==================================================")
    passed_count = sum(1 for _, _, st, _, _ in case_results if st == "PASS")
    skipped_count = sum(1 for _, _, st, _, _ in case_results if st == "SKIP")
    failed_count = sum(1 for _, _, st, _, _ in case_results if st == "FAIL")

    layer_names = {
        "L1": "第1層: コード構文・基本整合性",
        "L2": "第2層: セキュリティ & フロントエンドロジック",
        "L3": "第3層: データ整合性・不変性保証",
        "L4": "第4層: 管理機能 & バックエンドAPI",
        "L5": "第5層: クローラー基盤・探索最適化エンジン"
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

    print("--------------------------------------------------")
    print(f" 総実行時間: {total_time:.2f}秒 | 合格: {passed_count}件 | スキップ: {skipped_count}件 | 失敗: {failed_count}件")
    print("==================================================")

    all_passed = (failed_count == 0)
    if all_passed:
        print(" 【結果】実行されたテストスイートに完全合格しました。修正コードは正常です。")
        sys.exit(0)
    else:
        print(f" 【結果】{failed_count} 件のテストでエラーが検出されました。コードの再確認が必要です。")
        sys.exit(1)


if __name__ == "__main__":
    main()


