#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 15 クロール網羅性・品質向上エンジン（CR-14 〜 CR-17）単体・結合テスト
- CR-14: 親ページ実リンク解析型 サブページ探索エンジン（投機的類推排除、アンカーテキスト判定）
- CR-15: 2段階目URL（archiveUrl）の保持と起点探索連携
- CR-16: URL日付抽出フォールバック（西暦8桁、ハイフン区切り、和暦形式）
- CR-17: 汎用インデックス・ポータル目次判定の厳格化と誤除外防止
"""

import sys
import os
import unittest
from datetime import datetime

# PMHub root and admin in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADMIN_DIR = os.path.join(BASE_DIR, "admin")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if ADMIN_DIR not in sys.path:
    sys.path.insert(0, ADMIN_DIR)

from crawler import (
    extract_actual_subpage_links,
    _extract_date_from_url,
    _resolve_meeting_date,
    is_generic_index_url,
    load_councils_from_data_json,
    _GENERIC_INDEX_EXACT_TITLES,
    _GENERIC_INDEX_TITLE_KEYWORDS
)


class TestCrawlerQualityV2Drop15(unittest.TestCase):

    def test_cr14_subpage_discovery_from_actual_links_anchor_text(self):
        """CR-14: 親ページHTML内の実在リンクから、アンカーテキスト（第X回、期、日付等）によりサブページが確実に抽出されること"""
        parent_url = "https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/index.html"
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head><title>PETボトルリサイクル検討会</title></head>
        <body>
            <div class="nav">
                <a href="/index.html">ホーム</a>
                <a href="/sitemap.html">サイトマップ</a>
                <a href="../index.html">トップへ戻る</a>
            </div>
            <div class="main">
                <h2>開催実績</h2>
                <ul>
                    <li><a href="001.html">2026年8月5日 第1回</a></li>
                    <li><a href="002.html">令和8年9月10日 第2回</a></li>
                    <li><a href="report.html">中間取りまとめ 配付資料</a></li>
                    <li><a href="notice.html">第3回 開催案内</a></li>
                </ul>
            </div>
        </body>
        </html>
        """
        discovered = extract_actual_subpage_links(mock_html, parent_url)
        # 001.html, 002.html, report.html が抽出され、ナビゲーションや開催案内のみは除外されること
        self.assertIn("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/001.html", discovered)
        self.assertIn("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/002.html", discovered)
        self.assertIn("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/report.html", discovered)
        # 汎用ナビは除外されていること
        self.assertNotIn("https://www.meti.go.jp/index.html", discovered)
        self.assertNotIn("https://www.meti.go.jp/sitemap.html", discovered)

    def test_cr14_bunka_nendo_period_links(self):
        """CR-14: 文化庁等の「第16期（令和8年度）」のような期・年度リンクが確実に捕捉されること"""
        parent_url = "https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/"
        mock_html = """
        <html>
        <body>
            <a href="/seisaku/bunkashingikai/index.html">文化審議会・懇談会等</a>
            <a href="pdf/member.pdf">第16期美術品補償制度部会委員</a>
            <a href="r08/index.html">第16期（令和8年度）</a>
            <a href="r07/index.html">第15期（令和7年度）</a>
            <a href="h30/index.html">第8期（平成30年度）</a>
        </body>
        </html>
        """
        discovered = extract_actual_subpage_links(mock_html, parent_url)
        self.assertIn("https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/r08/index.html", discovered)
        self.assertIn("https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/r07/index.html", discovered)
        self.assertIn("https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/h30/index.html", discovered)
        # PDF直接リンクはサブページとしては除外（資料パーサーで取得）
        self.assertNotIn("https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/pdf/member.pdf", discovered)

    def test_cr14_no_speculative_urls(self):
        """CR-14: HTML内に存在しないURL（推測・類推URL）は一切生成されないこと"""
        parent_url = "https://example.com/council/index.html"
        mock_html = """
        <html><body><a href="session1.html">第1回 会議資料</a></body></html>
        """
        discovered = extract_actual_subpage_links(mock_html, parent_url)
        self.assertEqual(discovered, ["https://example.com/council/session1.html"])
        # 存在しない session2.html や 001.html 等は含まれない
        self.assertNotIn("https://example.com/council/session2.html", discovered)
        self.assertNotIn("https://example.com/council/001.html", discovered)

    def test_cr15_archive_url_loaded_as_crawl_starting_url(self):
        """CR-15: data.json に archiveUrl が設定されている会議体は、archiveUrl がクロール起点URLとしてロードされること"""
        councils = load_councils_from_data_json()
        cao_245 = next((c for c in councils if c["id"] == "cao-245"), None)
        self.assertIsNotNone(cao_245, "cao-245（男女共同参画会議）が存在すること")
        self.assertEqual(cao_245["archiveUrl"], "https://www.gender.go.jp/kaigi/danjo_kaigi/list.html")
        # クロール起点 url が archiveUrl になっていること
        self.assertEqual(cao_245["url"], "https://www.gender.go.jp/kaigi/danjo_kaigi/list.html")
        # officialUrl も保存されていること
        self.assertEqual(cao_245["officialUrl"], "https://www.gender.go.jp/kaigi/danjo_kaigi/index.html")

    def test_cr16_url_date_extraction(self):
        """CR-16: _extract_date_from_url による西暦8桁・ハイフン区切り・和暦形式の日付復元検証"""
        # 1. 西暦連続8桁
        self.assertEqual(_extract_date_from_url("https://www.fsa.go.jp/singi/siryou/20070208.html"), "2007/02/08")
        self.assertEqual(_extract_date_from_url("https://www.cas.go.jp/meeting_20240820.html"), "2024/08/20")
        # 2. 西暦ハイフン/アンダースコア区切り
        self.assertEqual(_extract_date_from_url("https://example.com/meetings/2026-07-10/index.html"), "2026/07/10")
        self.assertEqual(_extract_date_from_url("https://example.com/2026_05_28_report.html"), "2026/05/28")
        # 3. 令和形式
        self.assertEqual(_extract_date_from_url("https://example.com/r050720/index.html"), "2023/07/20")
        self.assertEqual(_extract_date_from_url("https://example.com/siryou/r5-12-01.html"), "2023/12/01")
        # 4. 平成形式
        self.assertEqual(_extract_date_from_url("https://example.com/h290401/gijisidai.html"), "2017/04/01")
        # 5. 不正な日付（範囲外の月日・乱数）は None となること
        self.assertIsNone(_extract_date_from_url("https://example.com/newpage_75439.html"))
        self.assertIsNone(_extract_date_from_url("https://example.com/doc_20241345.html"))

    def test_cr16_resolve_meeting_date_url_fallback(self):
        """CR-16: 本文から日付が取れない場合でも、URL日付から自動復元されて is_date_unconfirmed == False となること"""
        sub_dates = [] # 本文から抽出できず空
        sub_title = "足利銀行の受皿選定に関するワーキンググループ資料"
        sub_url = "https://www.fsa.go.jp/singi/ashigin_ukezara/siryou/20070208.html"

        meet_date, is_unconfirmed = _resolve_meeting_date(sub_dates, sub_title, sub_url)
        self.assertEqual(meet_date, "2007/02/08")
        self.assertFalse(is_unconfirmed, "URLから実在日付が復元されたため未確定フラグはFalseであること")

    def test_cr17_generic_index_url_and_title_discrimination(self):
        """CR-17: 汎用ポータルインデックスURLおよび目次タイトルが正しく除外され、正規の会議タイトルは保護されること"""
        # ポータルURL判定
        self.assertTrue(is_generic_index_url("https://www.moj.go.jp/seisakusesaku_index.html"))
        self.assertTrue(is_generic_index_url("https://www.moj.go.jp/shingi_index.html"))
        self.assertTrue(is_generic_index_url("https://www.meti.go.jp/shingikai/index.html"))
        self.assertTrue(is_generic_index_url("https://www.cas.go.jp/jp/seisakukaigi/index.html"))

        # 完全一致タイトル判定（単体ポータル見出し）
        self.assertTrue(is_generic_index_url("https://example.com/test", title="審議会"))
        self.assertTrue(is_generic_index_url("https://example.com/test", title="政策・審議会等トップへ"))
        self.assertTrue(is_generic_index_url("https://example.com/test", title="その他会議"))

        # 正規の会議タイトルは「審議会」を含んでいても除外されないこと（誤判定防止）
        self.assertFalse(is_generic_index_url("https://www.mhlw.go.jp/stf/newpage_75439.html", title="第263回社会保障審議会介護給付費分科会資料"))
        self.assertFalse(is_generic_index_url("https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/", title="文化審議会 美術品補償制度部会"))


def run_tests():
    print("==================================================")
    print(" Drop 15 クロール網羅性・品質向上テスト (test_crawler_quality_v2.py)")
    print("==================================================")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCrawlerQualityV2Drop15)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
