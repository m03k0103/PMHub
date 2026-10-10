#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 単体関数検証スイート (Unit Test Suite Runner) [Drop 45]

関数の仕様（ロジック）を修正した場合に限り実施される、純粋関数モック単体検証ランナー。
モックHTMLやテスト文字列、ダミー引数を用いた純粋関数の動作検証を実行します。
"""

import sys
import os
import unittest
import subprocess
import time
import argparse
import io
import shutil
from contextlib import redirect_stdout, redirect_stderr

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


# 定義されている全単体テストカタログ
# key: テスト種別キー
# dict: { name, description, runner_func }
UNIT_TEST_REGISTRY = {
    "u_front": {
        "id": "U1",
        "name": "フロントエンド関数単体テスト (app.test.js)",
        "description": "escapeHtml, sanitizeUrl, formatDate 等のJSユーティリティ関数",
        "runner": run_node_unit_test
    },
    "u_crawler_foundation": {
        "id": "U2",
        "name": "クローラー基盤パース単体テスト (test_crawler_foundation.py)",
        "description": "clean_html_for_dates, 最新優先ソート, 親一覧除外, タイトル抽出",
        "runner": lambda: _run_py_class("test_crawler_foundation", "TestCrawlerFoundationPhaseJ")
    },
    "u_parent_table": {
        "id": "U3",
        "name": "親テーブル開催回抽出単体テスト (test_crawler_parent_table.py)",
        "description": "_extract_meetings_from_parent_table のテーブル解析・資料抽出",
        "runner": lambda: _run_py_class("test_crawler_parent_table", "TestCrawlerParentTableDrop11")
    },
    "u_incremental": {
        "id": "U4",
        "name": "スマート差分探索単体テスト (test_crawler_incremental.py)",
        "description": "_normalize_url_for_comparison, 既登録スキップ, 最新更新確認",
        "runner": lambda: _run_py_class("test_crawler_incremental", "TestCrawlerIncrementalDrop13")
    },
    "u_quality_eval": {
        "id": "U5",
        "name": "クロール成否判定・未確定集計単体テスト (test_crawler_quality.py)",
        "description": "determine_crawl_result, get_unconfirmed_meetings_count の分岐判定",
        "runner": lambda: _run_py_methods("test_crawler_quality", "TestCrawlerQualityDrop14", [
            "test_determine_crawl_result_success_with_pdf_and_date",
            "test_determine_crawl_result_success_with_subpages",
            "test_determine_crawl_result_partial_when_generic_title",
            "test_determine_crawl_result_partial_when_only_placeholder_date",
            "test_determine_crawl_result_partial_when_materials_only",
            "test_determine_crawl_result_partial_when_dates_only",
            "test_determine_crawl_result_failed_when_both_empty",
            "test_get_unconfirmed_meetings_count"
        ])
    },
    "u_subpage_links": {
        "id": "U6",
        "name": "実リンク解析・タイトル正規化・告知除外単体テスト (test_crawler_quality_v2.py)",
        "description": "extract_actual_subpage_links, clean_meeting_title, is_preliminary_notice_page",
        "runner": lambda: _run_py_classes("test_crawler_quality_v2", ["TestCrawlerQualityV2Drop15", "TestCrawlerQualityFix20260919"])
    },
    "u_waf": {
        "id": "U7",
        "name": "WAF判定・動的レートリミット単体テスト (test_drop23_waf_resilience.py)",
        "description": "_get_host_interval, is_waf_challenge, HTTP 202リトライ待機",
        "runner": lambda: _run_py_class("test_drop23_waf_resilience", "TestDrop23WafResilience")
    },
    "u_table_html_expand": {
        "id": "U8",
        "name": "親テーブルHTML資料展開単体テスト (test_drop24_parent_table_expansion.py)",
        "description": "テーブル内HTML資料リンクから末端PDF展開・フォールバック保持",
        "runner": lambda: _run_py_class("test_drop24_parent_table_expansion", "TestDrop24ParentTableExpansion")
    },
    "u_date_parsing": {
        "id": "U9",
        "name": "日付パース・元号略記単体テスト (test_drop25_mod_date_parsing.py)",
        "description": "parse_japanese_date (元号略記・ドット元号・西暦), 防衛省テーブル抽出",
        "runner": lambda: _run_py_class("test_drop25_mod_date_parsing", "TestDrop25ModDateParsing")
    },
    "u_url_matching_fallback": {
        "id": "U10",
        "name": "URL正規化・ルール逆引き・案内文除外単体テスト (test_drop41_fallback_and_discovery.py)",
        "description": "normalize_url_for_matching, get_rule_for_target, is_preliminary_notice_page",
        "runner": lambda: _run_py_methods("test_drop41_fallback_and_discovery", "TestDrop41FallbackAndDiscovery", [
            "test_normalize_url_for_matching",
            "test_scraping_rules_url_fallback",
            "test_preliminary_notice_exclusion"
        ])
    },
    "u_robustness": {
        "id": "U11",
        "name": "クロール堅牢化・ナビ除外単体テスト (test_crawler_drop16.py)",
        "description": "safe_emit_log, 共通ナビ除外, 組織常設資料分離",
        "runner": lambda: _run_py_methods("test_crawler_drop16", "TestDrop16CrawlerRobustness", [
            "test_cr18_emit_stdout_safety",
            "test_cr19_common_nav_exclusion",
            "test_cr20_organization_doc_exclusion"
        ])
    },
    "u_speedup": {
        "id": "U12",
        "name": "クロール高速化・制御単体テスト (test_crawler_speedup.py)",
        "description": "過去回再検査ゼロ化, マルチスレッドレートリミット, 中断耐性",
        "runner": lambda: _run_py_methods("test_crawler_speedup", "TestDrop17CrawlerSpeedup", [
            "test_cr23_incremental_default_latest_only",
            "test_cr26_thread_safe_rate_limiting",
            "test_cr27_stop_event_interruption"
        ])
    },
    "u_drop46": {
        "id": "U13",
        "name": "ノイズ排除・文字化け復元・データ整合性テスト (test_drop46_data_cleanup.py)",
        "description": "is_sns_pr_url, is_non_pdf_anchor_url, HTMLタグ除去, 文字化け復元, 開催回内重複排除",
        "runner": lambda: _run_py_class("test_drop46_data_cleanup", "TestDrop46DataCleanup")
    },
    "u_drop47": {
        "id": "U14",
        "name": "ジェネリック配付資料スマートコンテキスト復元テスト (test_drop47_context_recovery.py)",
        "description": "is_generic_material_name, recover_material_context, data.json 残存ゼロ検証",
        "runner": lambda: _run_py_class("test_drop47_context_recovery", "TestDrop47ContextRecovery")
    },
    "u_drop48": {
        "id": "U15",
        "name": "配付資料0件開催回救済・議事録テキスト正式資料化単体テスト (test_drop48_zero_materials_rescue.py)",
        "description": "parse_txt_minutes, .txt 配付資料登録, 0件開催回救済削減",
        "runner": lambda: _run_py_class("test_drop48_zero_materials_rescue", "TestDrop48ZeroMaterialsRescue")
    },
    "u_drop49": {
        "id": "U16",
        "name": "開催回ID命名規約整合化・4桁回次許容単体テスト (test_drop49_meeting_id_normalization.py)",
        "description": "validate_meeting_id, 年度プレフィックス排除, 重複ゼロ, 4桁回次・3桁臨時回次許容",
        "runner": lambda: _run_py_class("test_drop49_meeting_id_normalization", "TestDrop49MeetingIdNormalization")
    },
    "u_drop62": {
        "id": "U17",
        "name": "DBマスター・2系統エクスポート・可逆性単体テスト (test_drop62_db_and_export.py)",
        "description": "schema.sql DDL, seed_db, export_data 2系統分離, 双方向可逆性検証",
        "runner": lambda: _run_py_class("test_drop62_db_and_export", "TestDrop62DatabaseAndExport")
    }
}


def _run_py_class(mod_name, class_name):
    import importlib
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, class_name)
    return run_python_test_cases([cls])


def _run_py_classes(mod_name, class_names):
    import importlib
    mod = importlib.import_module(mod_name)
    classes = [getattr(mod, cn) for cn in class_names]
    return run_python_test_cases(classes)


def _run_py_methods(mod_name, class_name, method_names):
    import importlib
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, class_name)
    items = [(cls, m) for m in method_names]
    return run_python_test_cases(items)


def run_unit_tests(target_keys=None):
    """
    指定された単体テスト種類（target_keys）を実行。
    None の場合は全12テストを実行。
    Returns: bool (全件成功時 True)
    """
    keys_to_run = target_keys if target_keys else list(UNIT_TEST_REGISTRY.keys())
    print("==================================================")
    print(" PMHub 単体関数検証スイート (Unit Test Runner) [Drop 45]")
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
    parser = argparse.ArgumentParser(description="PM-HUB Unit Test Suite Runner [Drop 45]")
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
