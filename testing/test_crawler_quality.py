#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 14: クロール成否判定の厳格化 & プレースホルダー日付自動検知 単体テストスイート
- CR-12: determine_crawl_result による success / partial / failed の精密判定
- CR-13: get_unconfirmed_meetings_count による 2099/01/01 ダミー日付自動検知
"""

import unittest
import sys
import os

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))

from crawler import (
    determine_crawl_result,
    get_unconfirmed_meetings_count
)


class TestCrawlerQualityDrop14(unittest.TestCase):
    """Drop 14 で実装されたクロール品質判定および要確認日付検知の単体テスト"""

    def test_determine_crawl_result_success_with_pdf_and_date(self):
        """CR-12: PDF配付資料と正常開催日が存在し、タイトルが正常な場合は success と判定されること"""
        materials = [{"name": "議事次第", "url": "https://example.com/01.pdf", "type": "PDF"}]
        dates = ["2026-05-15"]
        result, reason = determine_crawl_result(materials, dates, page_title="第1回 水資源保全検討会")

        self.assertEqual(result, "success")
        self.assertIn("PDF配付資料", reason)
        self.assertIn("正常取得", reason)

    def test_determine_crawl_result_success_with_subpages(self):
        """CR-12: サブページ開催回（資料・日付完備）が検出された場合は success と判定されること"""
        subpages = [
            {
                "name": "第1回 水資源保全検討会",
                "materials": [{"name": "資料1", "url": "https://example.com/01.pdf"}],
                "extractedDates": ["2026-05-15"]
            }
        ]
        result, reason = determine_crawl_result([], [], subpage_meetings=subpages, page_title="水資源保全検討会")

        self.assertEqual(result, "success")
        self.assertIn("開催回 1 件を検出", reason)

    def test_determine_crawl_result_partial_when_generic_title(self):
        """CR-12: 資料・日付が取れていてもタイトルがジェネリック（会議資料詳細等）な場合は partial と判定されること"""
        materials = [{"name": "資料1", "url": "https://example.com/01.pdf", "type": "PDF"}]
        dates = ["2026-05-15"]
        result, reason = determine_crawl_result(materials, dates, page_title="会議資料詳細")

        self.assertEqual(result, "partial")
        self.assertIn("汎用見出し", reason)

    def test_determine_crawl_result_partial_when_only_placeholder_date(self):
        """CR-12: 日付が 2099/01/01 ダミーのみの場合は success ではなく partial と判定されること"""
        materials = [{"name": "資料1", "url": "https://example.com/01.pdf", "type": "PDF"}]
        dates = ["2099/01/01"]
        result, reason = determine_crawl_result(materials, dates, page_title="第1回 水資源保全検討会")

        self.assertEqual(result, "partial")
        self.assertIn("未確定", reason)

    def test_determine_crawl_result_partial_when_materials_only(self):
        """CR-12: 資料はあるが開催日がない場合は partial と判定されること"""
        materials = [{"name": "資料1", "url": "https://example.com/01.pdf", "type": "PDF"}]
        dates = []
        result, reason = determine_crawl_result(materials, dates, page_title="第1回 水資源保全検討会")

        self.assertEqual(result, "partial")
        self.assertIn("開催日未取得", reason)

    def test_determine_crawl_result_partial_when_dates_only(self):
        """CR-12: 開催日はあるが配付資料が0件の場合は partial と判定されること"""
        materials = []
        dates = ["2026-05-15"]
        result, reason = determine_crawl_result(materials, dates, page_title="第1回 水資源保全検討会")

        self.assertEqual(result, "partial")
        self.assertIn("開催日のみ検出", reason)

    def test_determine_crawl_result_failed_when_both_empty(self):
        """CR-12: 資料も日付も開催回も0件の場合は failed と判定されること"""
        result, reason = determine_crawl_result([], [], page_title="水資源保全検討会")
        self.assertEqual(result, "failed")
        self.assertIn("いずれも検出できませんでした", reason)

    def test_get_unconfirmed_meetings_count(self):
        """CR-13: 2099/01/01 または isDateUnconfirmed が正確にカウントされること"""
        sample_data = {
            "meetings": [
                {"id": "m1", "date": "2026/05/10"},
                {"id": "m2", "date": "2099/01/01", "isDateUnconfirmed": True},
                {"id": "m3", "date": "2026/06/15"},
                {"id": "m4", "date": "2099-01-01"},
                {"id": "m5", "date": "2026/07/20", "isDateUnconfirmed": True}
            ]
        }
        # m2, m4, m5 の計3件が未確定
        count = get_unconfirmed_meetings_count(sample_data)
        self.assertEqual(count, 3)

        # 空データへの耐性
        self.assertEqual(get_unconfirmed_meetings_count({}), 0)
        self.assertEqual(get_unconfirmed_meetings_count(None), 0)


if __name__ == '__main__':
    unittest.main()
