#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 13: スマート差分探索エンジン（Smart Incremental Crawl）単体テストスイート
- CR-10: _normalize_url_for_comparison のURL正規化ロジック
- CR-10: _filter_incremental_subpages の既登録スキップ・最新更新確認・未登録最大50件判定
- CR-11: _crawl_subpages との連携動作検証
"""

import unittest
import sys
import os

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))

from crawler import (
    _normalize_url_for_comparison,
    _filter_incremental_subpages,
    _sort_subpage_urls_by_recency
)


class TestCrawlerIncrementalDrop13(unittest.TestCase):
    """Drop 13 で実装されたスマート差分探索エンジンの単体テスト"""

    def test_normalize_url_for_comparison(self):
        """URLの末尾スラッシュ、フラグメント、スキームの差異が吸収されること"""
        url1 = "https://www.meti.go.jp/shingikai/energy/025.html"
        url2 = "http://www.meti.go.jp/shingikai/energy/025.html#section1"
        url3 = "https://www.meti.go.jp/shingikai/energy/025.html/"

        norm1 = _normalize_url_for_comparison(url1)
        norm2 = _normalize_url_for_comparison(url2)
        norm3 = _normalize_url_for_comparison(url3)

        self.assertEqual(norm1, "www.meti.go.jp/shingikai/energy/025.html")
        self.assertEqual(norm2, "www.meti.go.jp/shingikai/energy/025.html")
        self.assertEqual(norm3, "www.meti.go.jp/shingikai/energy/025.html")

        # 空値や無効値への耐性
        self.assertEqual(_normalize_url_for_comparison(""), "")
        self.assertEqual(_normalize_url_for_comparison(None), "")

    def test_filter_all_new_subpages(self):
        """すべて未登録の場合、最大 max_unvisited（50件）まで未登録として採択されること"""
        candidates = [
            f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html"
            for i in range(1, 61)
        ]
        # 降順ソート
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)
        existing = set()

        targets, stats = _filter_incremental_subpages(sorted_candidates, existing, max_unvisited=50, max_recent=2)

        self.assertEqual(len(targets), 50)
        self.assertEqual(stats["unvisited"], 50)
        self.assertEqual(stats["recent_update"], 0)
        self.assertEqual(stats["skipped_known"], 0)
        self.assertEqual(stats["total_targets"], 50)
        # 最も新しい 060.html が先頭であること
        self.assertEqual(targets[0], "https://www.meti.go.jp/shingikai/energy/060.html")

    def test_filter_all_known_subpages(self):
        """すべて既登録の場合、最新2件のみ更新確認に選ばれ、残り全件がスキップされること"""
        candidates = [
            f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html"
            for i in range(1, 11)
        ]
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)
        existing = set(candidates)

        targets, stats = _filter_incremental_subpages(sorted_candidates, existing, max_unvisited=50, max_recent=2)

        # 最新の 010.html と 009.html のみ再訪対象
        self.assertEqual(len(targets), 2)
        self.assertEqual(stats["unvisited"], 0)
        self.assertEqual(stats["recent_update"], 2)
        self.assertEqual(stats["skipped_known"], 8)
        self.assertEqual(stats["total_targets"], 2)
        self.assertIn("https://www.meti.go.jp/shingikai/energy/010.html", targets)
        self.assertIn("https://www.meti.go.jp/shingikai/energy/009.html", targets)
        self.assertNotIn("https://www.meti.go.jp/shingikai/energy/008.html", targets)

    def test_filter_mixed_new_and_known_subpages(self):
        """新規と既登録が混在する場合、新規分＋最新2件が選ばれ、既登録過去回がスキップされること"""
        # 001〜010 が既登録、011〜013 が新規
        known = [f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html" for i in range(1, 11)]
        new_items = [f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html" for i in range(11, 14)]
        candidates = known + new_items
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)

        targets, stats = _filter_incremental_subpages(sorted_candidates, set(known), max_unvisited=50, max_recent=2)

        # 新規3件 + 最新既登録2件（010, 009） = 計5件
        self.assertEqual(len(targets), 5)
        self.assertEqual(stats["unvisited"], 3)
        self.assertEqual(stats["recent_update"], 2)
        self.assertEqual(stats["skipped_known"], 8)
        self.assertEqual(stats["total_targets"], 5)

        # 降順で 013, 012, 011, 010, 009 が並んでいること
        expected = [
            "https://www.meti.go.jp/shingikai/energy/013.html",
            "https://www.meti.go.jp/shingikai/energy/012.html",
            "https://www.meti.go.jp/shingikai/energy/011.html",
            "https://www.meti.go.jp/shingikai/energy/010.html",
            "https://www.meti.go.jp/shingikai/energy/009.html"
        ]
        self.assertEqual(targets, expected)

    def test_filter_empty_existing_urls(self):
        """existing_urls が None または空の場合、安全にフォールバックすること"""
        candidates = ["https://www.meti.go.jp/001.html", "https://www.meti.go.jp/002.html"]
        targets, stats = _filter_incremental_subpages(candidates, None)
        self.assertEqual(len(targets), 2)
        self.assertEqual(stats["unvisited"], 2)
        self.assertEqual(stats["skipped_known"], 0)


if __name__ == '__main__':
    unittest.main()
