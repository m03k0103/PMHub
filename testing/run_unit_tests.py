#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 単体関数検証スイート (Unit Test Suite Runner)

関数の仕様（ロジック）を修正した場合に限り実施される、純粋関数モック単体検証ランナー。
モックHTMLやテスト文字列、一時SQLite DBを用いた純粋関数・パイプラインの動作検証を実行します。
"""

import sys
import os
import unittest
import subprocess
import time
import argparse
import io
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")
TESTING_DIR = os.path.join(PROJECT_ROOT, "testing")
for p in [ADMIN_DIR, TESTING_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import setup_win32_utf8
setup_win32_utf8()


def get_node_command():
    """Node.js 実行バイナリのパスを安全に解決"""
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


def run_node_unit_test():
    """U1: フロントエンド JS ユーティリティ単体テスト (app.test.js)"""
    node_cmd = get_node_command()
    test_script = os.path.join(TESTING_DIR, "app.test.js")
    if not os.path.exists(test_script):
        return True, "app.test.js が見つかりません (スキップ)"
    try:
        res = subprocess.run([node_cmd, "--test", test_script], cwd=PROJECT_ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            return True, "escapeHtml / sanitizeUrl / formatDate 単体テスト全件通過 (node:test)"
        else:
            err = res.stderr or res.stdout
            return False, f"JS単体テスト失敗:\n{err.strip()}"
    except FileNotFoundError:
        return True, "Node.js が見つからないためスキップ"
    except Exception as e:
        return False, f"実行時例外: {e}"


def run_python_test_cases(test_case_classes_or_methods):
    """単一プロセス内で unittest TestCase 群を実行し (ok, output) を返す"""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for item in test_case_classes_or_methods:
        if isinstance(item, type) and issubclass(item, unittest.TestCase):
            suite.addTests(loader.loadTestsFromTestCase(item))
        elif isinstance(item, tuple) and len(item) == 2:
            cls, method_name = item
            suite.addTest(cls(method_name))
        elif isinstance(item, unittest.TestCase):
            suite.addTest(item)

    f_out = io.StringIO()
    runner = unittest.TextTestRunner(stream=f_out, verbosity=1)
    result = runner.run(suite)
    output = f_out.getvalue().strip()
    return result.wasSuccessful(), output


# 定義されている全単体テストカタログ（全12種: U1〜U12）
UNIT_TEST_REGISTRY = {
    "u_front": {
        "id": "U1",
        "name": "フロントエンド関数単体テスト (app.test.js)",
        "description": "escapeHtml, sanitizeUrl, formatDate 等のJSユーティリティ関数",
        "runner": run_node_unit_test
    },
    "u_crawler_foundation": {
        "id": "U2",
        "name": "クローラー基盤・正規化・ナビ除外単体テスト (test_crawler_foundation.py)",
        "description": "clean_html_for_dates, 最新優先ソート, 親一覧除外, タイトル抽出, normalize_text, safe_emit_log, ナビ/常設資料除外",
        "runner": lambda: _run_py_class("test_crawler_foundation", "TestCrawlerFoundation")
    },
    "u_parent_table": {
        "id": "U3",
        "name": "親テーブル開催回抽出・HTML資料展開単体テスト (test_crawler_parent_table.py)",
        "description": "_extract_meetings_from_parent_table のテーブル解析・資料抽出・HTML資料リンクからの末端PDF展開",
        "runner": lambda: _run_py_class("test_crawler_parent_table", "TestCrawlerParentTable")
    },
    "u_incremental": {
        "id": "U4",
        "name": "スマート差分探索・レートリミット・中断制御単体テスト (test_crawler_incremental.py)",
        "description": "_normalize_url_for_comparison, 既登録スキップ, 最新更新確認, スレッドセーフレートリミット, stop_event中断",
        "runner": lambda: _run_py_class("test_crawler_incremental", "TestCrawlerIncremental")
    },
    "u_quality_eval": {
        "id": "U5",
        "name": "クロール成否判定・サブページ探索・品質ガード・URLフォールバック単体テスト (test_crawler_quality.py)",
        "description": "determine_crawl_result, extract_actual_subpage_links, clean_meeting_title, 開催案内除外, タイトル幹類似度ガード, URL逆引き",
        "runner": lambda: _run_py_class("test_crawler_quality", "TestCrawlerQuality")
    },
    "u_waf": {
        "id": "U6",
        "name": "WAF判定・動的レートリミット・省庁ドメイン設定単体テスト (test_waf_resilience.py)",
        "description": "_get_host_interval, is_waf_challenge, HTTP 202リトライ待機, 省庁ドメインDB一元化",
        "runner": lambda: _run_py_class("test_waf_resilience", "TestWafResilience")
    },
    "u_date_parsing": {
        "id": "U7",
        "name": "日付パース・元号略記・開催回ID命名規約単体テスト (test_date_and_id_parsing.py)",
        "description": "parse_japanese_date (元号略記・ドット元号・西暦), URL日付抽出, validate_meeting_id (4桁回次・3桁臨時回次許容)",
        "runner": lambda: _run_py_class("test_date_and_id_parsing", "TestDateAndIdParsing")
    },
    "u_material_extraction": {
        "id": "U8",
        "name": "配付資料コンテキスト復元・ノイズ除去・TXT議事録・中間HTML判定単体テスト (test_material_extraction.py)",
        "description": "is_generic_material_name, recover_material_context, SNS/アンカー除外, parse_txt_minutes, is_intermediate_html_material",
        "runner": lambda: _run_py_class("test_material_extraction", "TestMaterialExtraction")
    },
    "u_db_pipeline": {
        "id": "U9",
        "name": "SQLiteマスターDB・自動エクスポート・可逆性・PMM保護単体テスト (test_db_pipeline.py)",
        "description": "db_manager CRUD, 自動エクスポート, フェイルセーフ復元, 双方向可逆性, PMMダウンロードステータス保護",
        "runner": lambda: _run_py_class("test_db_pipeline", "TestDbPipeline")
    },
    "u_pmm": {
        "id": "U10",
        "name": "PMM配付資料ローカル資産管理単体テスト (test_pmm.py)",
        "description": "Windows禁止文字置換, 資料名クレンジング, フォルダ命名規約, 安全ファイル操作",
        "runner": lambda: _run_py_class("test_pmm", "TestPmmCommonUtilities")
    },
    "u_discover": {
        "id": "U11",
        "name": "新規会議体ディスカバリー精度向上・親URL逆引き単体テスト (test_discover_councils.py)",
        "description": "名称クレンジング, 西暦テーマ保護, ノイズ除外, コア名称・サフィックス突合, 一覧URL非破壊, 報道発表URL遮断",
        "runner": lambda: _run_py_class("test_discover_councils", "TestDiscoverCouncils")
    },
    "u_llm_discovery": {
        "id": "U12",
        "name": "決定論的1ファイル新着ダイジェスト & LLMディスカバリー単体テスト (test_llm_discovery.py)",
        "description": "SHA-256ダイジェスト不変性, 5段階事前フィルタ, ID参照限定ハルシネーション遮断, 呼出予算上限(3/10/30)&SQLiteキャッシュ, 新着フラグ保護",
        "runner": lambda: _run_py_class("test_llm_discovery", "TestLlmDiscovery")
    }
}


def _run_py_class(mod_name, class_name):
    import importlib
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, class_name)
    return run_python_test_cases([cls])


def run_unit_tests(target_keys=None):
    """
    指定された単体テスト種類（target_keys）を実行。
    None の場合は全12テストを実行。
    Returns: bool (全件成功時 True)
    """
    keys_to_run = target_keys if target_keys else list(UNIT_TEST_REGISTRY.keys())
    print("==================================================")
    print(" PMHub 単体関数検証スイート (Unit Test Runner)")
    print("==================================================")
    print(f"  実行対象テスト種類: {len(keys_to_run)} 件")

    all_passed = True
    results = []

    t0 = time.perf_counter()
    for key in keys_to_run:
        info = UNIT_TEST_REGISTRY.get(key)
        if not info:
            continue
        test_id = info["id"]
        test_name = info["name"]
        print(f"\n--------------------------------------------------")
        print(f" [{test_id}] {test_name}")
        print(f"  検証内容: {info['description']}")
        print(f"--------------------------------------------------")
        t_sub = time.perf_counter()
        try:
            ok, msg = info["runner"]()
            elapsed = time.perf_counter() - t_sub
            if ok:
                print(f"  [PASS] 合格 ({elapsed:.2f}s)")
                results.append((test_id, test_name, "PASS", elapsed))
            else:
                print(f"  [FAIL] 失敗 ({elapsed:.2f}s): {msg}")
                results.append((test_id, test_name, "FAIL", elapsed))
                all_passed = False
        except Exception as e:
            elapsed = time.perf_counter() - t_sub
            print(f"  [FAIL] 例外発生 ({elapsed:.2f}s): {e}")
            results.append((test_id, test_name, "FAIL", elapsed))
            all_passed = False

    total_elapsed = time.perf_counter() - t0
    print("\n==================================================")
    print(" 単体関数検証 実行結果サマリー")
    print("==================================================")
    for tid, tname, st, el in results:
        print(f"  - {tid}: {tname} ({el:.2f}s) : {st}")
    print("--------------------------------------------------")
    pass_cnt = sum(1 for r in results if r[2] == "PASS")
    fail_cnt = sum(1 for r in results if r[2] == "FAIL")
    print(f" 総実行時間: {total_elapsed:.2f}秒 | 合格: {pass_cnt}件 | 失敗: {fail_cnt}件")
    print("==================================================")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="PM-HUB Unit Test Suite Runner")
    parser.add_argument("--type", choices=list(UNIT_TEST_REGISTRY.keys()), help="特定の単体テスト種類のみ実行")
    parser.add_argument("-k", "--keyword", help="テスト名に含まれるキーワードで絞り込み")
    args = parser.parse_args()

    targets = None
    if args.type:
        targets = [args.type]
    elif args.keyword:
        kw = args.keyword.lower()
        targets = [k for k, v in UNIT_TEST_REGISTRY.items() if kw in k.lower() or kw in v["name"].lower()]
        if not targets:
            print(f"キーワード '{args.keyword}' に一致する単体テストが見つかりませんでした。")
            sys.exit(1)

    ok = run_unit_tests(targets)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
