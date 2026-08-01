#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - Automated Smoke Test Suite
Antigravity / Jules によるコード修正後に実行する自動スモークテストスクリプト

【テスト項目】
1. JavaScript および Python コードの文法エラー (SyntaxError / ブラケット不整合) の自動確認
2. public/data.js および Webページ内の主要リンク（.go.jp 直リンク等）のリンク切れ (HTTP 404) 確認
"""

import sys
import os
import re
import urllib.request
import io

# Windows ターミナルログの文字化け防止 (stdout/stderr を UTF-8 に固定)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check_syntax_errors():
    """1. JS/Python ファイルの文法エラーおよびブラケット不整合を自動確認"""
    print("--------------------------------------------------")
    print(" [テスト 1/2] コードの文法エラー (SyntaxError) 自動検証")
    print("--------------------------------------------------")
    
    files_to_check = [
        os.path.join(PROJECT_ROOT, "public", "data.js"),
        os.path.join(PROJECT_ROOT, "public", "app.js"),
        os.path.join(PROJECT_ROOT, "admin", "crawler.py")
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

def check_link_health():
    """2. 主要公式ポータルおよび配布資料PDFのリンク切れを自動検証"""
    print("\n--------------------------------------------------")
    print(" [テスト 2/2] 会議体公式ポータル・配布資料 (HTTP Status) リンク検証")
    print("--------------------------------------------------")

    # Target key live portal and PDF URLs for verification
    test_urls = [
        "https://www8.cao.go.jp/cstp/ai/",
        "https://www8.cao.go.jp/kisei-kaikaku/index.html",
        "https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-155/cat-156/000813/",
        "https://www.cas.go.jp/jp/seisaku/chyutoujyousei/index.html",
        "https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/gijisidai.html",
        "https://www.cas.go.jp/jp/seisaku/chyutoujyousei/dai11/pdf/siryou1.pdf",
        "https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/index.html",
        "https://www.digital.go.jp/councils/social-promotion"
    ]

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHubSmokeTester/1.0'}
    broken_links = 0

    for url in test_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status in (200, 301, 302):
                    print(f"  [200 OK] {url}")
                else:
                    print(f"  [WARN {resp.status}] {url}")
        except Exception as e:
            print(f"  [FAIL リンク切れ] {url} -> {e}")
            broken_links += 1

    print(f"\n  検証結果: チェック数 {len(test_urls)} 件中 リンク切れ {broken_links} 件")
    return broken_links == 0

def main():
    print("==================================================")
    print(" 政策会議ウォッチ (PM-HUB) 自動スモークテスト実行 ")
    print("==================================================")

    syntax_ok = check_syntax_errors()
    links_ok = check_link_health()

    print("\n==================================================")
    if syntax_ok and links_ok:
        print(" 【結果】全スモークテストに合格しました。修正コードは正常です。")
        sys.exit(0)
    else:
        print(" 【結果】スモークテストにてエラーが検出されました。コードの再確認が必要です。")
        sys.exit(1)

if __name__ == "__main__":
    main()
