import os
import sys
import unittest
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "admin"))
from utils import setup_win32_utf8, normalize_url_for_matching
setup_win32_utf8()

from crawler import build_url_rule_index, get_rule_for_target, is_preliminary_notice_page


class TestDrop41FallbackAndDiscovery(unittest.TestCase):

    def test_normalize_url_for_matching(self):
        """CR-91: URL正規化関数がスキーム・末尾・クエリ・フラグメントの差異を吸収すること"""
        u1 = "http://www.cao.go.jp/council.html"
        u2 = "https://www.cao.go.jp/council.html"
        u3 = "https://www.cao.go.jp/council.html#section1"
        u4 = "https://www.CAO.go.jp/council.html"
        u5 = "https://www.cao.go.jp/council/"
        u6 = "https://www.cao.go.jp/council/index.html"
        u7 = "https://www.cao.go.jp/council"

        self.assertEqual(normalize_url_for_matching(u1), normalize_url_for_matching(u2))
        self.assertEqual(normalize_url_for_matching(u2), normalize_url_for_matching(u3))
        self.assertEqual(normalize_url_for_matching(u2), normalize_url_for_matching(u4))
        self.assertEqual(normalize_url_for_matching(u5), normalize_url_for_matching(u6))
        self.assertEqual(normalize_url_for_matching(u5), normalize_url_for_matching(u7))

        # クエリパラメータのソート
        q1 = "https://example.com/page?b=2&a=1"
        q2 = "https://example.com/page?a=1&b=2"
        self.assertEqual(normalize_url_for_matching(q1), normalize_url_for_matching(q2))

    def test_scraping_rules_url_fallback(self):
        """CR-91: 未知IDでもofficialUrl/archiveUrlから既存ルールが逆引き適用されること"""
        mock_rules = {
            "cao-ai_strategy": {
                "template": "tpl-cas-gijisidai-nested",
                "officialUrl": "https://www.cao.go.jp/ai/index.html",
                "deep_crawl_enabled": True
            },
            "mof-ebpm": {
                "template": "tpl-cas-gijisidai-nested",
                "officialUrl": "https://www.mof.go.jp/about_mof/councils/ebpm/index.html",
                "archiveUrl": "https://www.mof.go.jp/archive/ebpm/",
                "deep_crawl_enabled": True
            }
        }
        url_rule_index = build_url_rule_index(mock_rules)

        # 1. 正常なID一致
        rule_direct = get_rule_for_target(mock_rules, {"id": "cao-ai_strategy"}, url_rule_index)
        self.assertIsNotNone(rule_direct)
        self.assertEqual(rule_direct["template"], "tpl-cas-gijisidai-nested")

        # 2. 未知IDだが officialUrl が一致（http/https揺れ、index.html省略等含む）
        target_unknown = {
            "id": "cao-unknown_999",
            "officialUrl": "http://www.cao.go.jp/ai/"
        }
        rule_fallback = get_rule_for_target(mock_rules, target_unknown, url_rule_index)
        self.assertIsNotNone(rule_fallback)
        self.assertEqual(rule_fallback["template"], "tpl-cas-gijisidai-nested")
        self.assertTrue(rule_fallback["deep_crawl_enabled"])

        # 3. 未知IDだが archiveUrl が一致
        target_archive = {
            "id": "mof-unknown_888",
            "officialUrl": "https://www.mof.go.jp/archive/ebpm"
        }
        rule_archive = get_rule_for_target(mock_rules, target_archive, url_rule_index)
        self.assertIsNotNone(rule_archive)
        self.assertEqual(rule_archive["officialUrl"], "https://www.mof.go.jp/about_mof/councils/ebpm/index.html")

    def test_discover_councils_slug_inheritance_logic(self):
        """CR-92: discover_councils でURL一致時に既存スラグIDが自動継承されること"""
        from discover_councils import parse_data_json
        ministries, existing_councils, categories, existing_rules = parse_data_json()

        # url_to_slug_map の構築シミュレーション
        url_to_slug_map = {}
        for r_id, r in existing_rules.items():
            u = r.get("officialUrl")
            if u:
                url_to_slug_map[normalize_url_for_matching(u)] = r_id

        # 既存会議体のofficialUrlから検索
        sample_council = existing_councils[0]
        sample_url = sample_council["officialUrl"]
        norm_u = normalize_url_for_matching(sample_url)

        self.assertIn(norm_u, url_to_slug_map)
        inherited_slug = url_to_slug_map[norm_u]
        self.assertEqual(inherited_slug, sample_council["id"])

    def test_ministries_portal_urls_coverage(self):
        """CR-93: 拡充された省庁親ポータルURLが正しく設定されていること"""
        data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data.json")
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        min_map = data.get("ministries", {})

        # 消防庁 (FDMA)
        fdma = min_map.get("FDMA")
        self.assertIsNotNone(fdma)
        self.assertIn("https://www.fdma.go.jp/singi_kento/kento/", fdma["councilsUrls"])

        # 総務省 (MIC)
        mic = min_map.get("MIC")
        self.assertIsNotNone(mic)
        self.assertTrue(any("policyreports" in u for u in mic["councilsUrls"]))

        # 文化庁 (ACA)
        aca = min_map.get("ACA")
        self.assertIsNotNone(aca)
        self.assertTrue(any("chosakuken" in u for u in aca["councilsUrls"]))

        # 経産省 (METI)
        meti = min_map.get("METI")
        self.assertIsNotNone(meti)
        self.assertTrue(any("sankoshin" in u for u in meti["councilsUrls"]))

    def test_preliminary_notice_exclusion(self):
        """CR-94: 開催案内・定型文が is_preliminary_notice_page で確実に除外されること"""
        # 除外されるべきタイトル・アンカーテキスト
        notice_cases = [
            "標記の会議について、下記のとおり開催します。",
            "標記の検討会について、下記のとおり開催いたします。",
            "第5回検討会の開催について",
            "第10回 開催案内",
            "傍聴の申込について",
            "取材の案内について",
        ]
        for text in notice_cases:
            with self.subTest(text=text):
                self.assertTrue(is_preliminary_notice_page("https://example.com/notice.html", text), f"Failed to reject notice: {text}")

        # 除外されてはならない正当な会議・資料タイトル
        legit_cases = [
            "第5回 新しい資本主義実現会議 資料",
            "第10回 検討会議事次第",
            "第1回 議事要旨・配付資料",
            "GX実行会議（第3回）",
            "合同部会 配布資料",
        ]
        for text in legit_cases:
            with self.subTest(text=text):
                self.assertFalse(is_preliminary_notice_page("https://example.com/meeting.html", text), f"Incorrectly rejected legitimate title: {text}")


if __name__ == "__main__":
    unittest.main()
