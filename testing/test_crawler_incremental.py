#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スマート差分探索エンジン・並行レートリミット・中断制御 単体テストスイート (test_crawler_incremental.py)
- CR-10: _normalize_url_for_comparison のURL正規化ロジック
- CR-10 / CR-23: _filter_incremental_subpages の既登録スキップ・最新更新確認・未登録最大50件判定
- CR-26: ホスト単位並行巡回エンジン（スレッドセーフなレートリミット検証）
- CR-27: 中断耐性と安全チェックポイント保存（stop_event中断検証）
"""

import unittest
import sys
import os
import io
import time
import threading
from unittest.mock import patch

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))
from utils import setup_win32_utf8
setup_win32_utf8()

import crawler
from crawler import (
    _normalize_url_for_comparison,
    _filter_incremental_subpages,
    _sort_subpage_urls_by_recency,
    _rate_limit_host
)


class TestCrawlerIncremental(unittest.TestCase):
    """スマート差分探索エンジン・レートリミット・中断制御の単体テスト"""

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

        self.assertEqual(_normalize_url_for_comparison(""), "")
        self.assertEqual(_normalize_url_for_comparison(None), "")

    def test_filter_all_new_subpages(self):
        """すべて未登録の場合、最大 max_unvisited（50件）まで未登録として採択されること"""
        candidates = [
            f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html"
            for i in range(1, 61)
        ]
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)
        existing = set()

        targets, stats = _filter_incremental_subpages(sorted_candidates, existing, max_unvisited=50, max_recent=2)

        self.assertEqual(len(targets), 50)
        self.assertEqual(stats["unvisited"], 50)
        self.assertEqual(stats["recent_update"], 0)
        self.assertEqual(stats["skipped_known"], 0)
        self.assertEqual(stats["total_targets"], 50)
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
        known = [f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html" for i in range(1, 11)]
        new_items = [f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html" for i in range(11, 14)]
        candidates = known + new_items
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)

        targets, stats = _filter_incremental_subpages(sorted_candidates, set(known), max_unvisited=50, max_recent=2)

        self.assertEqual(len(targets), 5)
        self.assertEqual(stats["unvisited"], 3)
        self.assertEqual(stats["recent_update"], 2)
        self.assertEqual(stats["skipped_known"], 8)
        self.assertEqual(stats["total_targets"], 5)

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

    def test_cr23_incremental_default_latest_only(self):
        """CR-23: デフォルト（max_recent=1）で最新1件のみ更新確認され、過去回は再検査ゼロ化されること"""
        candidates = [
            "https://www.example.go.jp/meeting/003.html",
            "https://www.example.go.jp/meeting/002.html",
            "https://www.example.go.jp/meeting/001.html",
            "https://www.example.go.jp/meeting/000.html",
        ]
        known_urls = {
            "https://www.example.go.jp/meeting/002.html",
            "https://www.example.go.jp/meeting/001.html",
            "https://www.example.go.jp/meeting/000.html"
        }

        target_urls, stats = _filter_incremental_subpages(candidates, known_urls, max_recent=1, full_check=False)
        self.assertEqual(stats["unvisited"], 1)
        self.assertEqual(stats["recent_update"], 1)
        self.assertEqual(stats["skipped_known"], 2)
        self.assertIn("https://www.example.go.jp/meeting/003.html", target_urls)
        self.assertIn("https://www.example.go.jp/meeting/002.html", target_urls)
        self.assertNotIn("https://www.example.go.jp/meeting/001.html", target_urls)
        self.assertNotIn("https://www.example.go.jp/meeting/000.html", target_urls)

        target_urls_full, stats_full = _filter_incremental_subpages(candidates, known_urls, full_check=True)
        self.assertEqual(stats_full["unvisited"], 1)
        self.assertEqual(stats_full["recent_update"], 3)
        self.assertEqual(stats_full["skipped_known"], 0)
        self.assertEqual(len(target_urls_full), 4)

        target_urls_zero, stats_zero = _filter_incremental_subpages(candidates, known_urls, max_recent=0, full_check=False)
        self.assertEqual(stats_zero["unvisited"], 1)
        self.assertEqual(stats_zero["recent_update"], 0)
        self.assertEqual(stats_zero["skipped_known"], 3)
        self.assertEqual(len(target_urls_zero), 1)

    def test_cr26_thread_safe_rate_limiting(self):
        """CR-26: マルチスレッド下でも同一ホストへのアクセス間隔が _MIN_HOST_INTERVAL 以上保たれること"""
        test_host = "test.domain.go.jp"
        call_times = []
        lock = threading.Lock()

        orig_interval = crawler._MIN_HOST_INTERVAL
        crawler._MIN_HOST_INTERVAL = 0.05
        try:
            def worker():
                _rate_limit_host(test_host)
                with lock:
                    call_times.append(time.time())

            threads = [threading.Thread(target=worker) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            call_times.sort()
            self.assertEqual(len(call_times), 3)
            for i in range(len(call_times) - 1):
                interval = call_times[i + 1] - call_times[i]
                self.assertGreaterEqual(interval, crawler._MIN_HOST_INTERVAL - 0.015, f"間隔が短すぎます: {interval:.3f}s")
        finally:
            crawler._MIN_HOST_INTERVAL = orig_interval

    def test_cr27_stop_event_interruption(self):
        """CR-27: stop_event がセットされた場合、直ちにクローラーが安全中断すること"""
        stop_event = threading.Event()
        stop_event.set()

        mock_targets = [{"id": "test-c", "name": "テスト会議体", "ministry": "CAS", "officialUrl": "https://example.com"}]
        with patch('crawler.load_councils_from_data_json', return_value=mock_targets), \
             patch('crawler.save_data_json_with_backup', return_value=True), \
             patch('sys.stdout', new_callable=io.StringIO):
            stats = crawler.run_meeting_crawler(
                stop_event=stop_event,
                workers=1,
                recent_years=2
            )
        self.assertTrue(stats.get("stopped"), "stop_event により stopped=True が返却されること")
        self.assertEqual(stats["processed_councils"], 0, "即時停止のため処理件数が0であること")


if __name__ == '__main__':
    unittest.main()
