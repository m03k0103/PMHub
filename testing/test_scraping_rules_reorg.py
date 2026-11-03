#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - スクレイピングルール再編・標準化 テストスイート (Drop 12 / Drop 129)
"""

import os
import re
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "admin"))

from utils import load_data_json
from crawler import load_scraping_rules

DEPRECATED_RULE_KEYS = frozenset({
    "deep_crawl_enabled",
    "rule_id",
    "official_url",
    "target_url",
    "list_url",
    "source_url",
    "councilId",
    "council_id",
    "target_council_id",
    "council_name",
    "created_at",
    "generator",
    "top_page_pdf_count",
    "detect_private_materials",
    "extract_all_materials",
    "extract_subpage_materials_primary",
    "prefer_subpage_date",
    "private_doc_keyword",
    "resolve_absolute_urls",
    "ministryQuirk",
    "encoding",
})


class TestScrapingRulesReorganization(unittest.TestCase):
    """スクレイピングルール再編・標準化の整合性検証 (Drop 12 / Drop 129)"""

    @classmethod
    def setUpClass(cls):
        data_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        cls.data = load_data_json(data_path, cached=True)
        cls.councils = {c["id"]: c for c in cls.data.get("councils", [])}
        cls.raw_rules = cls.data.get("scrapingRules", {})
        cls.templates = cls.data.get("scrapingRuleTemplates", {})
        cls.resolved_rules = load_scraping_rules(cls.data)

    def test_cr7_zero_orphan_rules(self):
        """CR-7: 存在しない会議体IDを指す孤立ルールが0件であること"""
        orphans = [k for k in self.raw_rules if k not in self.councils]
        self.assertEqual(len(orphans), 0, f"孤立ルールが残存しています: {orphans}")

    def test_cr7_no_deprecated_or_dead_keys(self):
        """CR-7 / Drop 129: 形骸化したフラグや死にキー・重複メタデータがテンプレートおよび全ルールから除去されていること"""
        for tpl_name, tpl_obj in self.templates.items():
            bad_tpl_keys = set(tpl_obj.keys()) & DEPRECATED_RULE_KEYS
            self.assertEqual(len(bad_tpl_keys), 0, f"テンプレート {tpl_name} に廃止キーが残存しています: {bad_tpl_keys}")

        rules_with_bad_keys = []
        for cid, r in self.raw_rules.items():
            bad_k = set(r.keys()) & DEPRECATED_RULE_KEYS
            if bad_k:
                rules_with_bad_keys.append((cid, sorted(bad_k)))
        self.assertEqual(
            len(rules_with_bad_keys), 0,
            f"個別ルールに廃止・冗長キーが残存しています ({len(rules_with_bad_keys)}件): {rules_with_bad_keys[:5]}"
        )

    def test_cr8_templates_unnested_and_valid(self):
        """CR-8 / Drop 129: scrapingRuleTemplates が全10種の標準・省庁CMSテンプレートに整理され、未定義・未使用テンプレートが0件であること"""
        expected_templates = {
            "tpl-general-round-subpage",
            "tpl-parent-table-direct",
            "tpl-mhlw-stf-subpage",
            "tpl-ministry-hybrid-kaisai",
            "tpl-general-shingikai-report",
            "tpl-mic-soumu-singi",
            "tpl-councils-uuid-subpage",
            "tpl-mof-proceedings-subpage",
            "tpl-fsc-kai-subpage",
            "tpl-nra-detail-subpage",
        }
        for st in expected_templates:
            self.assertIn(st, self.templates, f"標準テンプレート {st} が未定義です")
            self.assertNotIn("rules", self.templates[st], f"{st} にネストされた rules が残存しています")

        used_templates = {r.get("template") for r in self.raw_rules.values()}
        undefined_refs = [
            (cid, r.get("template"))
            for cid, r in self.raw_rules.items()
            if not r.get("template") or r.get("template") not in self.templates
        ]
        self.assertEqual(len(undefined_refs), 0, f"未定義またはNoneのテンプレート参照が存在します: {undefined_refs[:10]}")

        unused_templates = set(self.templates.keys()) - used_templates
        self.assertEqual(len(unused_templates), 0, f"未使用の孤立テンプレートが残存しています: {unused_templates}")

    def test_cr9_100_percent_coverage(self):
        """CR-9: 全会議体に対するルール定義率が 100% であること"""
        missing = [cid for cid in self.councils if cid not in self.raw_rules]
        self.assertEqual(len(missing), 0, f"ルール未定義の会議体が存在します: {missing[:10]}")
        self.assertEqual(len(self.raw_rules), len(self.councils))

    def test_load_scraping_rules_completeness(self):
        """CR-8 / Drop 129: load_scraping_rules による全会議体のルール完全解決と正規表現・プロパティ整合性"""
        active_rules_count = len([
            r for r in self.raw_rules.values()
            if r.get("is_active") is not False and r.get("isActive") is not False
        ])
        self.assertEqual(len(self.resolved_rules), active_rules_count)
        for cid, r in self.resolved_rules.items():
            self.assertTrue(bool(r.get("pdf_selector")), f"{cid} に pdf_selector がありません")
            self.assertTrue(bool(r.get("date_regex")), f"{cid} に date_regex がありません")
            self.assertTrue(r.get("manualLock") is True, f"{cid} の manualLock が True ではありません")
            self.assertTrue(bool(r.get("officialUrl")), f"{cid} に officialUrl が解決されていません")
            self.assertNotIn("rules", r, f"{cid} の rules 辞書がアンパックされていません")
            has_subpage = bool(r.get("subpage_discovery_pattern"))
            is_table = bool(r.get("extract_from_parent_table"))
            self.assertTrue(has_subpage or is_table, f"{cid} はサブページパターンも親テーブル設定も持っていません")
            if has_subpage:
                self.assertNotEqual(r.get("subpage_discovery_pattern"), ".*", f"{cid} に無差別ワイルドカード '.*' が設定されています")
            compiled_date = re.compile(r["date_regex"])
            self.assertLessEqual(compiled_date.groups, 1, f"{cid} の date_regex に複数キャプチャグループが含まれています: {r['date_regex']}")


if __name__ == '__main__':
    unittest.main()
