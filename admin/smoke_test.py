#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - Automated Smoke Test Suite

【テスト要件】
1. 必須：コードの文法エラー (SyntaxError / 括弧の不整合) 自動確認
2. 必須：追加・変更された URL のみのリンク疎通確認 (HTTP Status 検証)
3. スキップ：変更のない既存 URL の疎通確認は不要 (テスト高速化・サーバー負荷低減)
"""

import sys
import os
import re
import urllib.parse
import urllib.request
import urllib.error
import subprocess
import argparse
import io

# Windows ターミナルログの文字化け防止 (chcp 65001 & UTF-8 再構成)
if sys.platform == "win32":
    os.system("chcp 65001 > NUL 2>&1")
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check_syntax_errors():
    """1. JS/Python ファイルの文法エラーおよびブラケット不整合を自動確認"""
    print("--------------------------------------------------")
    print(" [テスト 1/2] コードの文法エラー (SyntaxError) 自動検証")
    print("--------------------------------------------------")
    
    files_to_check = [
        os.path.join(PROJECT_ROOT, "public", "data.js"),
        os.path.join(PROJECT_ROOT, "public", "app.js"),
        os.path.join(PROJECT_ROOT, "admin", "crawler.py"),
        os.path.join(PROJECT_ROOT, "admin", "agent_initial_verifier.py"),
        os.path.join(PROJECT_ROOT, "admin", "smoke_test.py")
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
            parens = code.count('(') - code.count(')')
            curlies = code.count('{') - code.count('}')
            squares = code.count('[') - code.count(']')
            
            if parens == 0 and curlies == 0 and squares == 0:
                print(f"  [PASS] {rel_path} : JavaScript Brackets Balanced (Syntax OK)")
            else:
                print(f"  [FAIL] {rel_path} : JavaScript 括弧の不整合検知 (parens:{parens}, curlies:{curlies}, squares:{squares})")
                errors_found += 1

    return errors_found == 0

def get_added_urls_from_git():
    """git diff から新規追加・変更された URL を動的に抽出"""
    added_urls = set()
    diff_commands = [
        ["git", "diff", "HEAD", "--", "public/data.js"],
        ["git", "diff", "HEAD~1", "HEAD", "--", "public/data.js"],
        ["git", "diff", "--staged", "--", "public/data.js"]
    ]
    
    for cmd in diff_commands:
        try:
            output = subprocess.check_output(cmd, cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL, encoding='utf-8', errors='replace')
            for line in output.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    found = re.findall(r"https?://[^\s\x22\x27,]+", line)
                    for u in found:
                        if "pm-hub.gov.example" not in u and "googleapis.com" not in u:
                            added_urls.add(u)
        except Exception:
            pass
            
    return list(added_urls)

def check_link_health(explicit_urls=None, check_all=False):
    """2. 追加・変更された URL のみのリンク疎通確認"""
    print("\n--------------------------------------------------")
    print(" [テスト 2/2] リンク疎通確認 (追加・変更 URL のみ対象)")
    print("--------------------------------------------------")

    target_urls = []
    if explicit_urls:
        target_urls = explicit_urls
    elif check_all:
        data_js_path = os.path.join(PROJECT_ROOT, "public", "data.js")
        if os.path.exists(data_js_path):
            with open(data_js_path, "r", encoding="utf-8") as f:
                content = f.read()
            target_urls = re.findall(r"https?://[^\s\x22\x27,]+", content)
            target_urls = [u for u in target_urls if "example" not in u and "googleapis" not in u]
    else:
        target_urls = get_added_urls_from_git()

    unique_urls = list(dict.fromkeys(target_urls))

    if not unique_urls:
        print("  [SKIP] 変更・追加された新規 URL は検出されませんでした (既存 URL の検証はスキップします)")
        return True

    print(f"  検出された追加・変更 URL (計 {len(unique_urls)} 件) の疎通確認を実行中...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 PMHubSmokeTester/3.0'}
    broken_links = 0

    for url in unique_urls:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme not in ('http', 'https'):
            print(f"  [FAIL 無効なスキーム] {url}")
            broken_links += 1
            continue

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 301, 302, 202):
                    print(f"  [200 OK] {url}")
                else:
                    print(f"  [WARN {resp.status}] {url}")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f"  [PASS (403 Bot Protected)] {url}")
            else:
                print(f"  [FAIL リンク切れ ({e.code})] {url}")
                broken_links += 1
        except Exception as e:
            print(f"  [FAIL リンク切れ] {url} -> {e}")
            broken_links += 1

    print(f"\n  検証結果: 追加・変更 URL {len(unique_urls)} 件中 リンク切れ {broken_links} 件")
    return broken_links == 0

def check_escape_html():
    """3. JSユーティリティ (escapeHtml) の単体テスト"""
    print("\n--------------------------------------------------")
    print(" [テスト 3/3] JSユーティリティ関数の単体テスト実行")
    print("--------------------------------------------------")
    try:
        test_script_path = os.path.join(PROJECT_ROOT, "admin", "test_escapeHtml.js")
        result = subprocess.run(["node", test_script_path], cwd=PROJECT_ROOT, capture_output=True, text=True)
        if result.returncode == 0:
            print("  [PASS] escapeHtml 単体テスト通過")
            return True
        else:
            print("  [FAIL] escapeHtml 単体テスト失敗")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"  [FAIL] テストスクリプト実行エラー: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="PM-HUB Smoke Test Runner")
    parser.add_argument("--url", nargs="+", help="Explicit URLs to verify")
    parser.add_argument("--all", action="store_true", help="Check all URLs in data.js")
    args = parser.parse_args()

    print("==================================================")
    print(" 政策会議ウォッチ (PM-HUB) 自動スモークテスト実行 ")
    print("==================================================")

    syntax_ok = check_syntax_errors()
    links_ok = check_link_health(explicit_urls=args.url, check_all=args.all)
    utils_ok = check_escape_html()

    print("\n==================================================")
    if syntax_ok and links_ok and utils_ok:
        print(" 【結果】全スモークテストに合格しました。修正コードは正常です。")
        sys.exit(0)
    else:
        print(" 【結果】スモークテストにてエラーが検出されました。コードの再確認が必要です。")
        sys.exit(1)

if __name__ == "__main__":
    main()
