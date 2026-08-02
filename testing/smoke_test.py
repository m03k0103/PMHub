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

def check_js_syntax(code, file_path=""):
    """JS の文法エラー（カンマ欠落、不整合な文字、要素・プロパティ間カンマ欠落等）を精密検証"""
    import shutil
    node_cmd = shutil.which("node")
    if node_cmd:
        try:
            res = subprocess.run([node_cmd, "--check", file_path], capture_output=True, text=True, encoding='utf-8', errors='replace')
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

    if "data.js" in file_path:
        missing_comma_obj = re.search(r'\}\s*\n\s*\{', cleaned_code)
        if missing_comma_obj:
            pos = missing_comma_obj.start()
            line_no = code[:pos].count('\n') + 1
            return False, f"JavaScript オブジェクト間カンマ欠落検知 ({line_no}行目付近の '}}' 直後に ',' がありません)"

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

    if "data.js" in file_path or "const MEETINGS =" in code:
        token_spec = [
            ('COMMENT_SINGLE', r'//.*'),
            ('COMMENT_MULTI',  r'/\*[\s\S]*?\*/'),
            ('STRING',         r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`"),
            ('NUMBER',         r'-?\d+(?:\.\d+)?'),
            ('BOOL_NULL',      r'\b(true|false|null|undefined)\b'),
            ('KEYWORD',        r'\b(const|let|var)\b'),
            ('IDENT',          r'[a-zA-Z_$][a-zA-Z0-9_$]*'),
            ('COLON',          r':'),
            ('COMMA',          r','),
            ('LBRACE',         r'\{'),
            ('RBRACE',         r'\}'),
            ('LBRACK',         r'\['),
            ('RBRACK',         r'\]'),
            ('EQUALS',         r'='),
            ('SEMI',           r';'),
            ('NEWLINE',        r'\n'),
            ('SKIP',           r'[ \t\r]+'),
            ('MISMATCH',       r'.'),
        ]

        tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_spec)
        tok_line = 1
        tok_line_start = 0

        tokens = []
        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            value = mo.group()
            column = mo.start() - tok_line_start
            if kind == 'NEWLINE':
                tok_line += 1
                tok_line_start = mo.end()
                continue
            elif kind in ('SKIP', 'COMMENT_SINGLE', 'COMMENT_MULTI'):
                continue
            elif kind == 'MISMATCH':
                return False, f"不正な文字 '{value}' (行 {tok_line}, 列 {column})"
            tokens.append((kind, value, tok_line, column))

        pos = 0

        def peek():
            return tokens[pos] if pos < len(tokens) else None

        def consume(expected_kind=None):
            nonlocal pos
            t = peek()
            if not t:
                raise SyntaxError(f"予期せぬファイル末尾 (期待: {expected_kind})")
            if expected_kind and t[0] != expected_kind:
                raise SyntaxError(f"行 {t[2]}, 列 {t[3]}: '{expected_kind}' が必要ですが '{t[1]}' が指定されています")
            pos += 1
            return t

        def parse_val():
            t = peek()
            if not t:
                raise SyntaxError("値が必要です")
            if t[0] == 'LBRACE':
                parse_obj()
            elif t[0] == 'LBRACK':
                parse_arr()
            elif t[0] in ('STRING', 'NUMBER', 'BOOL_NULL', 'IDENT', 'KEYWORD'):
                consume()
            else:
                raise SyntaxError(f"行 {t[2]}, 列 {t[3]}: 値のコンテキストで不正なトークン '{t[1]}'")

        def parse_obj():
            consume('LBRACE')
            while True:
                t = peek()
                if not t:
                    raise SyntaxError("閉じ括弧 '}' がありません")
                if t[0] == 'RBRACE':
                    consume('RBRACE')
                    break
                if t[0] not in ('IDENT', 'STRING', 'KEYWORD'):
                    raise SyntaxError(f"行 {t[2]}, 列 {t[3]}: プロパティキーが必要です (実際: '{t[1]}')")
                consume()
                consume('COLON')
                parse_val()
                
                t = peek()
                if t and t[0] == 'COMMA':
                    consume('COMMA')
                    if peek() and peek()[0] == 'RBRACE':
                        consume('RBRACE')
                        break
                elif t and t[0] == 'RBRACE':
                    consume('RBRACE')
                    break
                else:
                    raise SyntaxError(f"行 {t[2]}, 列 {t[3]}: カンマ ',' または '}}' が必要です ('{t[1]}' が存在します)")

        def parse_arr():
            consume('LBRACK')
            while True:
                t = peek()
                if not t:
                    raise SyntaxError("閉じ括弧 ']' がありません")
                if t[0] == 'RBRACK':
                    consume('RBRACK')
                    break
                parse_val()
                
                t = peek()
                if t and t[0] == 'COMMA':
                    consume('COMMA')
                    if peek() and peek()[0] == 'RBRACK':
                        consume('RBRACK')
                        break
                elif t and t[0] == 'RBRACK':
                    consume('RBRACK')
                    break
                else:
                    raise SyntaxError(f"行 {t[2]}, 列 {t[3]}: カンマ ',' または ']' が必要です ('{t[1]}' が存在します)")

        try:
            while pos < len(tokens):
                t = peek()
                if t[0] == 'KEYWORD' and t[1] in ('const', 'let', 'var'):
                    consume('KEYWORD')
                    consume('IDENT')
                    consume('EQUALS')
                    parse_val()
                    if peek() and peek()[0] == 'SEMI':
                        consume('SEMI')
                else:
                    pos += 1
        except SyntaxError as e:
            return False, f"データ構文エラー: {str(e)}"

    return True, "JavaScript Syntax OK"

def check_syntax_errors():
    """1. JS/Python ファイルの文法エラー（SyntaxError / カンマ欠落 / 括弧不整合）を自動確認"""
    print("--------------------------------------------------")
    print(" [テスト 1/2] コードの文法エラー (SyntaxError) 自動検証")
    print("--------------------------------------------------")
    
    files_to_check = [
        os.path.join(PROJECT_ROOT, "public", "data.js"),
        os.path.join(PROJECT_ROOT, "public", "app.js"),
        os.path.join(PROJECT_ROOT, "admin", "crawler.py"),
        os.path.join(PROJECT_ROOT, "admin", "agent_initial_verifier.py"),
        os.path.join(PROJECT_ROOT, "testing", "smoke_test.py")
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
    print(" [テスト 3/4] JSユーティリティ関数の単体テスト実行")
    print("--------------------------------------------------")
    try:
        test_script_path = os.path.join(PROJECT_ROOT, "testing", "test_escapeHtml.js")
        result = subprocess.run(["node", test_script_path], cwd=PROJECT_ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode == 0:
            print("  [PASS] escapeHtml 単体テスト通過")
            return True
        else:
            print("  [FAIL] escapeHtml 単体テスト失敗")
            print(result.stdout)
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("  [SKIP] Node.js環境が見つからないため JS 単体テストをスキップします")
        return True
    except Exception as e:
        print(f"  [FAIL] テストスクリプト実行エラー: {e}")
        return False

def check_council_timeline_sync():
    """4. 会議体一覧 (COUNCILS), タイムライン (MEETINGS), クローラー (CRAWL_TARGETS) の完全一致自動検証"""
    print("\n--------------------------------------------------")
    print(" [テスト 4/4] 会議体・タイムライン・自動クローラー ID完全一致検証")
    print("--------------------------------------------------")

    data_js_path = os.path.join(PROJECT_ROOT, "public", "data.js")
    crawler_py_path = os.path.join(PROJECT_ROOT, "admin", "crawler.py")
    verifier_py_path = os.path.join(PROJECT_ROOT, "admin", "agent_initial_verifier.py")

    with open(data_js_path, "r", encoding="utf-8") as f:
        data_text = f.read()

    councils_part = data_text[:data_text.find("const MEETINGS =")]
    meetings_part = data_text[data_text.find("const MEETINGS ="):]

    councils_ids = re.findall(r"id:\s*['\"]([^'\"]+)['\"]", councils_part)
    meetings_council_ids = set(re.findall(r"councilId:\s*['\"]([^'\"]+)['\"]", meetings_part))

    # Check for duplicate IDs in COUNCILS
    if len(councils_ids) != len(set(councils_ids)):
        duplicates = [cid for cid in set(councils_ids) if councils_ids.count(cid) > 1]
        print(f"  [FAIL] COUNCILS に重複IDが存在します: {duplicates}")
        return False

    councils_set = set(councils_ids)

    # Check for councils without meetings
    missing_meetings = councils_set - meetings_council_ids
    if missing_meetings:
        print(f"  [FAIL] タイムラインに会議データが存在しない会議体が検出されました: {sorted(missing_meetings)}")
        return False

    # Check for meetings belonging to non-existent councils
    orphaned_meetings = meetings_council_ids - councils_set
    if orphaned_meetings:
        print(f"  [FAIL] 定義されていない会議体IDを持つ会議データがタイムラインに存在します: {sorted(orphaned_meetings)}")
        return False

    # Check crawler CRAWL_TARGETS
    with open(crawler_py_path, "r", encoding="utf-8") as f:
        crawler_text = f.read()
    crawler_ids = set(re.findall(r'["\']id["\']:\s*["\']([^"\']+)["\']', crawler_text))

    if crawler_ids != councils_set:
        diff_crawler = councils_set ^ crawler_ids
        print(f"  [FAIL] crawler.py の CRAWL_TARGETS が COUNCILS と不一致です: {sorted(diff_crawler)}")
        return False

    # Check verifier TARGET_COUNCILS
    with open(verifier_py_path, "r", encoding="utf-8") as f:
        verifier_text = f.read()
    verifier_ids = set(re.findall(r'["\']id["\']:\s*["\']([^"\']+)["\']', verifier_text))

    if verifier_ids != councils_set:
        diff_verifier = councils_set ^ verifier_ids
        print(f"  [FAIL] agent_initial_verifier.py の TARGET_COUNCILS が COUNCILS と不一致です: {sorted(diff_verifier)}")
        return False

    print(f"  [PASS] 全 {len(councils_set)} 会議体の ID完全一致・タイムライン紐づけ・自動更新エンジン同期を検証完了")
    return True

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
    sync_ok = check_council_timeline_sync()

    print("\n==================================================")
    if syntax_ok and links_ok and utils_ok and sync_ok:
        print(" 【結果】全スモークテストに合格しました。修正コードは正常です。")
        sys.exit(0)
    else:
        print(" 【結果】スモークテストにてエラーが検出されました。コードの再確認が必要です。")
        sys.exit(1)

if __name__ == "__main__":
    main()

