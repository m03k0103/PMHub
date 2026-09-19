#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - クローラー統合テストスイート (test_crawler_suite.py)
Drop 10 〜 Drop 17 (CR-1 〜 CR-27) の全クローラー単体・統合テストを
単一プロセスで一括実行し、プロセス起動オーバーヘッドおよび多重 JSON ロードを根絶する。
"""

import os
import sys
import unittest
import time

TESTING_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTING_DIR)
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")

for p in [ADMIN_DIR, TESTING_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import setup_win32_utf8, load_data_json
setup_win32_utf8()

# 各テストモジュールから TestCase クラスをインポート
from test_crawler_foundation import TestCrawlerFoundationPhaseJ
from test_crawler_parent_table import TestCrawlerParentTableDrop11
from test_scraping_rules_reorg import TestScrapingRulesReorganization
from test_crawler_incremental import TestCrawlerIncrementalDrop13
from test_crawler_quality import TestCrawlerQualityDrop14
from test_crawler_quality_v2 import TestCrawlerQualityV2Drop15
from test_crawler_drop16 import TestDrop16CrawlerRobustness
from test_crawler_speedup import TestDrop17CrawlerSpeedup


CRAWLER_TEST_CLASSES = [
    ("テスト 10: クローラー基盤・誤判定防止 (CR-1, CR-2, CR-4)", TestCrawlerFoundationPhaseJ),
    ("テスト 11: 親テーブル開催回抽出 (CR-5, CR-6)", TestCrawlerParentTableDrop11),
    ("テスト 12: スクレイピングルール整合性 (CR-7, CR-8, CR-9)", TestScrapingRulesReorganization),
    ("テスト 13: スマート差分探索エンジン (CR-10, CR-11)", TestCrawlerIncrementalDrop13),
    ("テスト 14: クロール品質判定・2099日付検知 (CR-12, CR-13)", TestCrawlerQualityDrop14),
    ("テスト 15: クロール網羅性・実リンク解析・URL日付復元 (CR-14 〜 CR-17)", TestCrawlerQualityV2Drop15),
    ("テスト 16: クロール堅牢化・共通ナビ除外・ホスト分散 (CR-18 〜 CR-22)", TestDrop16CrawlerRobustness),
    ("テスト 17: クロール超高速化 & 直近重点化 (CR-23 〜 CR-27)", TestDrop17CrawlerSpeedup),
]


def create_crawler_test_suite():
    """全 8 クラスのテストを統合した TestSuite を構築"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for _, cls in CRAWLER_TEST_CLASSES:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    return suite


def run_crawler_test_case(test_case_class, verbosity=1):
    """個別の TestCase クラスをインプロセスで実行し (success: bool, output: str) を返す"""
    import io
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=verbosity)
    suite = unittest.TestLoader().loadTestsFromTestCase(test_case_class)
    result = runner.run(suite)
    return result.wasSuccessful(), stream.getvalue()


def run_all(verbosity=2):
    """全クローラー統合テストを実行"""
    print("==================================================")
    print(" クローラー統合テストスイート (test_crawler_suite.py)")
    print(" 全 8 大テスト (CR-1 〜 CR-27) を単一プロセスで実行")
    print("==================================================")

    # 事前に data.json をキャッシュに載せておく
    data_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
    load_data_json(data_path, cached=True)

    suite = create_crawler_test_suite()
    t0 = time.time()
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    dt = time.time() - t0

    print(f"\n実行完了: {result.testsRun} テスト中 {len(result.failures)} 件失敗, {len(result.errors)} 件エラー ({dt:.2f}秒)")
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
