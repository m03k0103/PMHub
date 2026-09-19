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


class TestCrawlerQualityFix20260919(unittest.TestCase):
    """
    2026-09-19 クロール品質修正・再発防止テスト
    - 事前告知・開催案内ページの完全検出と除外（AGENTS.md 第11条・第12条）
    - clean_meeting_title による省庁サフィックス・配付資料一覧ノイズの除去
    - scrapingRules subpage_discovery_pattern の正規表現自動正規化
    - 非会議リンク（能力開発基本調査等）の確実な除外
    """

    def test_preliminary_notice_detection(self):
        from crawler import is_preliminary_notice_page
        # 開催案内・告知パターン
        self.assertTrue(is_preliminary_notice_page(
            "https://www.mhlw.go.jp/stf/newpage_76036.html",
            "第78回労働政策審議会人材開発分科会監理団体審査部会 開催案内｜厚生労働省"
        ))
        self.assertTrue(is_preliminary_notice_page(
            "https://www.nta.go.jp/about/council/zeirishi/260818/120.htm",
            "第120回　国税審議会 税理士分科会の開催について｜国税庁"
        ))
        self.assertTrue(is_preliminary_notice_page(
            "https://www.mext.go.jp/b_menu/shingi/kokurituken/kaisai/1416001_00030.htm",
            "国立研究開発法人審議会（第39回）の開催について：文部科学省"
        ))
        self.assertTrue(is_preliminary_notice_page(
            "https://www.fsc.go.jp/senmon/sonota/annai/wg_amr_annai_64.html",
            "薬剤耐性菌に関するワーキンググループ（第64回）の開催について（非公開） | 食品安全委員会"
        ))
        self.assertTrue(is_preliminary_notice_page(
            "https://www.mhlw.go.jp/churoi/roushi/index.html",
            "令和８年度 労使関係セミナーのご案内 (開催日不明)"
        ))
        self.assertTrue(is_preliminary_notice_page(
            "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/jinzaikaihatsu/chousa/r1/index_00003.html",
            "能力開発基本調査｜厚生労働省"
        ))

        # 本物の会議は除外されないこと（誤爆防止）
        self.assertFalse(is_preliminary_notice_page(
            "https://www.soumu.go.jp/main_sosiki/joho_tsusin/policyreports/denpa_kanri/kaisai/02kiban01_04000328.html",
            "第1160回 電波監理審議会"
        ))
        self.assertFalse(is_preliminary_notice_page(
            "https://www.mhlw.go.jp/stf/newpage_75356.html",
            "第112回 厚生科学審議会予防接種・ワクチン分科会副反応検討部会"
        ))

    def test_clean_meeting_title(self):
        from crawler import clean_meeting_title
        # 1. 林野庁サフィックス・配付資料一覧
        self.assertEqual(
            clean_meeting_title("林政審議会施策部会（令和8年9月1日）配付資料一覧：林野庁"),
            "林政審議会施策部会（令和8年9月1日）"
        )
        # 2. 厚労省サフィックス・資料
        self.assertEqual(
            clean_meeting_title("第264回社会保障審議会介護給付費分科会（web会議）資料｜厚生労働省"),
            "第264回社会保障審議会介護給付費分科会（web会議）"
        )
        # 3. ALPS処理水・配付資料一覧
        self.assertEqual(
            clean_meeting_title("ＡＬＰＳ処理水の処分に関する基本方針の着実な実行に向けた関係閣僚等会議（第９回）配付資料一覧"),
            "ＡＬＰＳ処理水の処分に関する基本方針の着実な実行に向けた関係閣僚等会議（第９回）"
        )
        # 4. 全角空白の正規化
        self.assertEqual(
            clean_meeting_title("第１０３７回　食品安全委員会"),
            "第１０３７回 食品安全委員会"
        )

    def test_custom_rule_normalization_in_subpage_discovery(self):
        """href=['\"](...)['\"] 形式のルールテンプレートが自動正規化されて実リンクを抽出できること"""
        rule = {
            "subpage_discovery_pattern": 'href=["\\\'](https://www\\.mhlw\\.go\\.jp/stf/(?:newpage_\\d+|shingi2/\\d+_\\d+)\\.html)["\\\']'
        }
        parent_url = "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126720.html"
        mock_html = """
        <html><body>
            <a href="https://www.mhlw.go.jp/stf/newpage_75356.html">第112回会議資料</a>
            <a href="https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/jinzaikaihatsu/chousa/r1/index_00003.html">能力開発基本調査</a>
        </body></html>
        """
        discovered = extract_actual_subpage_links(mock_html, parent_url, rule=rule)
        self.assertIn("https://www.mhlw.go.jp/stf/newpage_75356.html", discovered)
        # 能力開発基本調査は非会議リンクとして除外されること
        self.assertNotIn("https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/jinzaikaihatsu/chousa/r1/index_00003.html", discovered)


def run_tests():
    print("==================================================")
    print(" Drop 15 クロール網羅性・品質向上テスト (test_crawler_quality_v2.py)")
    print("==================================================")
    suite = unittest.TestSuite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCrawlerQualityV2Drop15))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCrawlerQualityFix20260919))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
