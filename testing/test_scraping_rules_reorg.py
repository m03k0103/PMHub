#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - スクレイピングルール再編・標準化 テストスイート (Drop 12: CR-7, CR-8, CR-9)
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "admin"))

from utils import load_data_json
from crawler import load_scraping_rules

class TestScrapingRulesReorganization(unittest.TestCase):
    """Drop 12: スクレイピングルール再編・標準化の整合性検証"""

    @classmethod
    def setUpClass(cls):
        data_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        cls.data = load_data_json(data_path)
        cls.councils = {c["id"]: c for c in cls.data.get("councils", [])}
        cls.raw_rules = cls.data.get("scrapingRules", {})
        cls.templates = cls.data.get("scrapingRuleTemplates", {})
        cls.resolved_rules = load_scraping_rules()

    def test_cr7_zero_orphan_rules(self):
        """CR-7: 存在しない会議体IDを指す孤立ルールが0件であること"""
        orphans = [k for k in self.raw_rules if k not in self.councils]
        self.assertEqual(len(orphans), 0, f"孤立ルールが残存しています: {orphans}")

    def test_cr7_no_deep_crawl_enabled_flag(self):
        """CR-7: 形骸化した deep_crawl_enabled フラグが全ルールから除去されていること"""
        rules_with_flag = [k for k, r in self.raw_rules.items() if "deep_crawl_enabled" in r]
        self.assertEqual(len(rules_with_flag), 0, f"deep_crawl_enabled が残存しています: {len(rules_with_flag)} 件")

    def test_cr8_templates_unnested_and_valid(self):
        """CR-8: scrapingRuleTemplates がネスト辞書を持たずフラットに整備されていること"""
        standard_templates = [
            "tpl-general-round-subpage",
            "tpl-mhlw-stf-subpage",
            "tpl-parent-table-direct",
            "tpl-ministry-hybrid-kaisai",
            "tpl-general-shingikai-report"
        ]
        for st in standard_templates:
            self.assertIn(st, self.templates, f"標準テンプレート {st} が未定義です")
            self.assertNotIn("rules", self.templates[st], f"{st} にネストされた rules が残存しています")

    def test_cr9_100_percent_coverage(self):
        """CR-9: 全 1,505 会議体に対するルール定義率が 100% であること"""
        missing = [cid for cid in self.councils if cid not in self.raw_rules]
        self.assertEqual(len(missing), 0, f"ルール未定義の会議体が存在します: {missing[:10]}")
        self.assertEqual(len(self.raw_rules), len(self.councils))

    def test_load_scraping_rules_completeness(self):
        """CR-8: load_scraping_rules による全会議体のルール完全解決とプロパティ整合性"""
        active_rules_count = len([r for r in self.raw_rules.values() if r.get("is_active") is not False and r.get("isActive") is not False])
        self.assertEqual(len(self.resolved_rules), active_rules_count)
        for cid, r in self.resolved_rules.items():
            self.assertTrue(bool(r.get("pdf_selector")), f"{cid} に pdf_selector がありません")
            self.assertTrue(bool(r.get("date_regex")), f"{cid} に date_regex がありません")
            self.assertTrue(r.get("manualLock") is True, f"{cid} の manualLock が True ではありません")
            self.assertNotIn("rules", r, f"{cid} の rules 辞書がアンパックされていません")
            has_subpage = bool(r.get("subpage_discovery_pattern"))
            is_table = bool(r.get("extract_from_parent_table"))
            self.assertTrue(has_subpage or is_table, f"{cid} はサブページパターンも親テーブル設定も持っていません")

if __name__ == '__main__':
    unittest.main()
