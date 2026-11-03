#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
クロール成否判定・サブページ探索・品質ガード・URLフォールバック 単体テストスイート (test_crawler_quality.py)
- CR-12 / CR-13: determine_crawl_result / get_unconfirmed_meetings_count
- CR-14 〜 CR-17: 親ページ実リンク解析、URL日付抽出フォールバック、汎用インデックス判定
- 事前告知・開催案内ページの除外、clean_meeting_title、正規表現自動正規化
- 既存開催回タイトル幹（Stem）類似度検証ガード
- URL正規化 & scrapingRules URL逆引きフォールバック
"""

import unittest
import sys
import os

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))
from utils import setup_win32_utf8, normalize_url_for_matching
setup_win32_utf8()

from crawler import (
    determine_crawl_result,
    get_unconfirmed_meetings_count,
    extract_title_stem,
    is_title_inconsistent_with_council,
    extract_actual_subpage_links,
    _extract_date_from_url,
    _resolve_meeting_date,
    is_generic_index_url,
    is_preliminary_notice_page,
    clean_meeting_title,
    build_url_rule_index,
    get_rule_for_target
)


class TestCrawlerQuality(unittest.TestCase):
    """クロール品質判定・サブページ探索・タイトル幹類似度・URLフォールバックの単体テスト"""

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
        """CR-12: 資料・日付が取れていてもタイトルがジェネリックな場合は partial と判定されること"""
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
        count = get_unconfirmed_meetings_count(sample_data)
        self.assertEqual(count, 3)
        self.assertEqual(get_unconfirmed_meetings_count({}), 0)
        self.assertEqual(get_unconfirmed_meetings_count(None), 0)

    def test_cr14_subpage_discovery_from_actual_links_anchor_text(self):
        """CR-14: 親ページHTML内の実在リンクから、アンカーテキストによりサブページが確実に抽出されること"""
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
        self.assertIn("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/001.html", discovered)
        self.assertIn("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/002.html", discovered)
        self.assertIn("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/report.html", discovered)
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
        self.assertNotIn("https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/pdf/member.pdf", discovered)

    def test_cr14_no_speculative_urls(self):
        """CR-14: HTML内に存在しないURL（推測・類推URL）は一切生成されないこと"""
        parent_url = "https://example.com/council/index.html"
        mock_html = """
        <html><body><a href="session1.html">第1回 会議資料</a></body></html>
        """
        discovered = extract_actual_subpage_links(mock_html, parent_url)
        self.assertEqual(discovered, ["https://example.com/council/session1.html"])
        self.assertNotIn("https://example.com/council/session2.html", discovered)
        self.assertNotIn("https://example.com/council/001.html", discovered)

    def test_cr16_url_date_extraction(self):
        """CR-16: _extract_date_from_url による西暦8桁・ハイフン区切り・和暦形式の日付復元検証"""
        self.assertEqual(_extract_date_from_url("https://www.fsa.go.jp/singi/siryou/20070208.html"), "2007/02/08")
        self.assertEqual(_extract_date_from_url("https://www.cas.go.jp/meeting_20240820.html"), "2024/08/20")
        self.assertEqual(_extract_date_from_url("https://example.com/meetings/2026-07-10/index.html"), "2026/07/10")
        self.assertEqual(_extract_date_from_url("https://example.com/2026_05_28_report.html"), "2026/05/28")
        self.assertEqual(_extract_date_from_url("https://example.com/r050720/index.html"), "2023/07/20")
        self.assertEqual(_extract_date_from_url("https://example.com/siryou/r5-12-01.html"), "2023/12/01")
        self.assertEqual(_extract_date_from_url("https://example.com/h290401/gijisidai.html"), "2017/04/01")
        self.assertIsNone(_extract_date_from_url("https://example.com/newpage_75439.html"))
        self.assertIsNone(_extract_date_from_url("https://example.com/doc_20241345.html"))

    def test_cr16_resolve_meeting_date_url_fallback(self):
        """CR-16: 本文から日付が取れない場合でも、URL日付から自動復元されて is_date_unconfirmed == False となること"""
        sub_dates = []
        sub_title = "足利銀行の受皿選定に関するワーキンググループ資料"
        sub_url = "https://www.fsa.go.jp/singi/ashigin_ukezara/siryou/20070208.html"

        meet_date, is_unconfirmed = _resolve_meeting_date(sub_dates, sub_title, sub_url)
        self.assertEqual(meet_date, "2007/02/08")
        self.assertFalse(is_unconfirmed)

    def test_cr17_generic_index_url_and_title_discrimination(self):
        """CR-17: 汎用ポータルインデックスURLおよび目次タイトルが正しく除外され、正規の会議タイトルは保護されること"""
        self.assertTrue(is_generic_index_url("https://www.moj.go.jp/seisakusesaku_index.html"))
        self.assertTrue(is_generic_index_url("https://www.moj.go.jp/shingi_index.html"))
        self.assertTrue(is_generic_index_url("https://www.meti.go.jp/shingikai/index.html"))
        self.assertTrue(is_generic_index_url("https://www.cas.go.jp/jp/seisakukaigi/index.html"))

        self.assertTrue(is_generic_index_url("https://example.com/test", title="審議会"))
        self.assertTrue(is_generic_index_url("https://example.com/test", title="政策・審議会等トップへ"))
        self.assertTrue(is_generic_index_url("https://example.com/test", title="その他会議"))

        self.assertFalse(is_generic_index_url("https://www.mhlw.go.jp/stf/newpage_75439.html", title="第263回社会保障審議会介護給付費分科会資料"))
        self.assertFalse(is_generic_index_url("https://www.bunka.go.jp/seisaku/bunkashingikai/bijutsuhin/", title="文化審議会 美術品補償制度部会"))

    def test_preliminary_notice_detection(self):
        """事前告知・開催案内ページの完全検出と除外"""
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

        self.assertFalse(is_preliminary_notice_page(
            "https://www.soumu.go.jp/main_sosiki/joho_tsusin/policyreports/denpa_kanri/kaisai/02kiban01_04000328.html",
            "第1160回 電波監理審議会"
        ))
        self.assertFalse(is_preliminary_notice_page(
            "https://www.mhlw.go.jp/stf/newpage_75356.html",
            "第112回 厚生科学審議会予防接種・ワクチン分科会副反応検討部会"
        ))

    def test_clean_meeting_title(self):
        """clean_meeting_title による省庁サフィックス・配付資料一覧ノイズの除去"""
        self.assertEqual(
            clean_meeting_title("林政審議会施策部会（令和8年9月1日）配付資料一覧：林野庁"),
            "林政審議会施策部会(令和8年9月1日)"
        )
        self.assertEqual(
            clean_meeting_title("第264回社会保障審議会介護給付費分科会（web会議）資料｜厚生労働省"),
            "第264回社会保障審議会介護給付費分科会(web会議)"
        )
        self.assertEqual(
            clean_meeting_title("ＡＬＰＳ処理水の処分に関する基本方針の着実な実行に向けた関係閣僚等会議（第９回）配付資料一覧"),
            "ALPS処理水の処分に関する基本方針の着実な実行に向けた関係閣僚等会議(第9回)"
        )
        self.assertEqual(
            clean_meeting_title("第１０３７回　食品安全委員会"),
            "第1037回 食品安全委員会"
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
        self.assertNotIn("https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/jinzaikaihatsu/chousa/r1/index_00003.html", discovered)

    def test_extract_title_stem(self):
        """開催回タイトルからの幹（Stem）抽出検証"""
        self.assertEqual(extract_title_stem("第10回 社会資本整備審議会"), "社会資本整備審議会")
        self.assertEqual(extract_title_stem("令和8年 第282回 文化審議会 文化財分科会"), "文化審議会文化財分科会")
        self.assertEqual(extract_title_stem("第290回 動物用医薬品専門調査会(非公開)"), "動物用医薬品専門調査会")
        self.assertEqual(extract_title_stem("1. 第1回 検討会"), "検討会")

    def test_title_inconsistency_guard(self):
        """既存開催回タイトル幹（Stem）類似度検証ガード"""
        cname = "社会資本整備審議会"
        existing = [
            "第10回 社会資本整備審議会",
            "第9回 社会資本整備審議会",
            "第8回 社会資本整備審議会",
            "社会資本整備審議会:基本問題小委員会"
        ]
        self.assertFalse(is_title_inconsistent_with_council("第11回 社会資本整備審議会", cname, existing))
        self.assertFalse(is_title_inconsistent_with_council("社会資本整備審議会（第11回）", cname, existing))
        self.assertFalse(is_title_inconsistent_with_council("第2回 社会資本整備審議会:基本問題小委員会", cname, existing))

        self.assertTrue(is_title_inconsistent_with_council(
            "社会資本整備審議会・交通政策審議会「今後のインフラのマネジメントのあり方について」中間答申の手交について",
            cname, existing
        ))
        self.assertTrue(is_title_inconsistent_with_council(
            "モビリティとインフラを活用したエネルギーの自律性向上 に向けた議論を行います ~社会資本整備審議会環境部会・交通政策審議会交通体系分科会環境部会 エネルギー・経済安全保障小委員会第3回合同会議を開催~",
            cname, existing
        ))
        self.assertTrue(is_title_inconsistent_with_council(
            "最上川水系、赤川水系、紀の川水系及び川内川水系に係る河川整備基本方針の変更等について審議します~社会資本整備審議会河川分科会(第78回)を開催~",
            cname, existing
        ))
        self.assertTrue(is_title_inconsistent_with_council(
            "AI活用を通じたイノベーション・エコシステムの好循環・加速化に向けて議論を行います!~社会資本整備審議会・交通政策審議会技術分科会 第41回技術部会を開催~",
            cname, existing
        ))

        nra_cname = "原子力規制委員会"
        nra_existing = [
            "第62回 原子力規制委員会",
            "米国原子力学会 原子力臨界安全部会 最優秀論文賞を受賞"
        ]
        self.assertTrue(is_title_inconsistent_with_council(
            "2025年米国機械学会 圧力容器・配管の国際会議で複数の賞を受賞",
            nra_cname, nra_existing
        ))
        self.assertFalse(is_title_inconsistent_with_council(
            "第63回 原子力規制委員会",
            nra_cname, nra_existing
        ))

        self.assertFalse(is_title_inconsistent_with_council("第10回", cname, existing))
        self.assertFalse(is_title_inconsistent_with_council("平成24年第7回（2013年2月6日）", cname, existing))
        self.assertFalse(is_title_inconsistent_with_council("第1回（持ち回り開催）", cname, existing))
        self.assertFalse(is_title_inconsistent_with_council("2026年10月8日", cname, existing))

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

        rule_direct = get_rule_for_target(mock_rules, {"id": "cao-ai_strategy"}, url_rule_index)
        self.assertIsNotNone(rule_direct)
        self.assertEqual(rule_direct["template"], "tpl-cas-gijisidai-nested")

        target_unknown = {
            "id": "cao-unknown_999",
            "officialUrl": "http://www.cao.go.jp/ai/"
        }
        rule_fallback = get_rule_for_target(mock_rules, target_unknown, url_rule_index)
        self.assertIsNotNone(rule_fallback)
        self.assertEqual(rule_fallback["template"], "tpl-cas-gijisidai-nested")
        self.assertTrue(rule_fallback["deep_crawl_enabled"])

        target_archive = {
            "id": "mof-unknown_888",
            "officialUrl": "https://www.mof.go.jp/archive/ebpm"
        }
        rule_archive = get_rule_for_target(mock_rules, target_archive, url_rule_index)
        self.assertIsNotNone(rule_archive)
        self.assertEqual(rule_archive["officialUrl"], "https://www.mof.go.jp/about_mof/councils/ebpm/index.html")


if __name__ == '__main__':
    unittest.main()
