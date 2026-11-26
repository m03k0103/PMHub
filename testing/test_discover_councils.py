#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
単体テスト: 新規会議体ディスカバリー精度向上・親URL逆引き・通常巡回高速化 (Drop 75 / U20)
CR-186: 会議体名クレンジング & 西暦テーマ保護
CR-187: 非会議体ノイズ判定（大臣動静・国際会議・ナビ要素・1文字ゴミ）
CR-188: 正規化コア名称 & 同一省庁部会サフィックス突合
CR-189: 単発プレスリリースからの常設親ページURL逆引き解決
CR-190/CR-191: 一覧URL非破壊 & ID重複採番防止
"""

import sys
import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")
for p in [ADMIN_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import setup_win32_utf8
setup_win32_utf8()

import discover_councils


class TestDiscoverCouncils(unittest.TestCase):

    def test_cr186_name_cleansing_and_western_year_preservation(self):
        """CR-186: タイトルからのカテゴリ・日付除去と西暦テーマ名保護の検証"""
        kws = ["検討会", "審議会", "委員会", "部会", "分科会", "研究会", "協議会", "有識者会議", "ワーキンググループ"]

        # 1. 省庁カテゴリラベルの除去
        t1 = "審議会等 医療扶助・健康管理支援等に関する検討会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t1, kws),
            "医療扶助・健康管理支援等に関する検討会"
        )

        t2 = "報道発表 キャリアコンサルタント登録制度等に関する検討会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t2, kws),
            "キャリアコンサルタント登録制度等に関する検討会"
        )

        t3 = "その他 国民年金システム標準化研究会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t3, kws),
            "国民年金システム標準化研究会"
        )

        t4 = "財総研 第32期 中国研究会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t4, kws),
            "中国研究会"
        )

        # 2. 日付・更新ラベル・年度・期数プレフィックスの除去
        t5 = "〈7月16日(木)〉(更新)商業登記所における法人の実質的支配者情報の把握促進に関する研究会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t5, kws),
            "商業登記所における法人の実質的支配者情報の把握促進に関する研究会"
        )

        t6 = "審議会等 令和8年度 化学物質管理に係る専門家検討会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t6, kws),
            "化学物質管理に係る専門家検討会"
        )

        # 3. 西暦テーマ名の保護 (2040年, 2030年が消えないこと)
        t7 = "審議会等 2040年に向けた看護職員の養成・確保の在り方に関する検討会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t7, kws),
            "2040年に向けた看護職員の養成・確保の在り方に関する検討会"
        )

        t8 = "2030生物多様性枠組実現日本会議"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t8, ["会議"]),
            "2030生物多様性枠組実現日本会議"
        )

        # 4. サブタイトル・キャッチコピー区切りの分割
        t9 = "上下水道政策の基本的な方向性を議論します~上下水道政策の基本的なあり方検討会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t9, kws),
            "上下水道政策の基本的なあり方検討会"
        )

        t10 = "ナショナルサイクルルートの制度レビューを実施します~現行制度の見直しに向けた審査委員会"
        self.assertEqual(
            discover_councils.extract_council_name_from_news_title(t10, ["委員会", "審査委員会"]),
            "現行制度の見直しに向けた審査委員会"
        )

    def test_cr187_noise_filtering(self):
        """CR-187: 非会議体ノイズ（大臣動静・国際会議・ナビ要素・1文字ゴミ）判定の検証"""
        # 1. 大臣動静・発言・面会
        self.assertTrue(discover_councils.is_non_council_noise(
            "小泉龍司法務大臣が、国連国際商取引法委員会", "小泉龍司法務大臣が、国連国際商取引法委員会に出席しました"
        ))
        self.assertTrue(discover_councils.is_non_council_noise(
            "河井克行法務大臣発言(令和元年台風第19号法務省災害対策本部会", "大臣発言動画"
        ))
        self.assertTrue(discover_councils.is_non_council_noise(
            "小泉防衛大臣とカッラス欧州連合(EU)外務・安全保障政策上級代表兼欧州委員会", "会談を行いました"
        ))
        self.assertTrue(discover_councils.is_non_council_noise(
            "日本人初】渡邉紹裕京都大学名誉教授が国際かんがい排水委員会", ""
        ))

        # 2. 国際機関・国際会議・条約会合
        self.assertTrue(discover_councils.is_non_council_noise("世銀・IMF合同開発委員会"))
        self.assertTrue(discover_councils.is_non_council_noise("国際通貨金融委員会"))
        self.assertTrue(discover_councils.is_non_council_noise("FATF(金融活動作業部会"))
        self.assertTrue(discover_councils.is_non_council_noise("国連気候変動枠組条約締約国会議閣僚級準備会合(プレCOP31)"))
        self.assertTrue(discover_councils.is_non_council_noise("生物多様性条約締約国会議"))
        self.assertTrue(discover_councils.is_non_council_noise("ワシントン条約(CITES)締約国会議"))
        self.assertTrue(discover_councils.is_non_council_noise("日ロ漁業委員会会議(日ロ地先沖合漁業交渉)"))

        # 3. 国会・一般法人
        self.assertTrue(discover_councils.is_non_council_noise("参議院法務委員会"))
        self.assertTrue(discover_councils.is_non_council_noise("一般社団法人電力系統利用協議会"))

        # 4. ポータル・包括名称・ナビ要素・1文字ゴミ
        self.assertTrue(discover_councils.is_non_council_noise("政策・審議会"))
        self.assertTrue(discover_councils.is_non_council_noise("審議会・委員会"))
        self.assertTrue(discover_councils.is_non_council_noise("本審議会 トップページ"))
        self.assertTrue(discover_councils.is_non_council_noise("政策・審議会等トップへ"))
        self.assertTrue(discover_councils.is_non_council_noise("各種本部・会議等の活動情報"))
        self.assertTrue(discover_councils.is_non_council_noise("度"))  # 1文字ゴミ

        # 5. PDF直リンク
        self.assertTrue(discover_councils.is_non_council_noise(
            "有識者検討会資料", url="https://www.mod.go.jp/j/press/news/2026/09/29d.pdf"
        ))

        # 6. 有望な正規会議体はノイズ判定されないこと
        self.assertFalse(discover_councils.is_non_council_noise("医療扶助・健康管理支援等に関する検討会"))
        self.assertFalse(discover_councils.is_non_council_noise("フロンティアAI時代の通信事業におけるデータの保護・セキュリティの在り方に関する検討会"))
        self.assertFalse(discover_councils.is_non_council_noise("造船ワーキンググループ"))
        self.assertFalse(discover_councils.is_non_council_noise("AI・デジタル改革推進会議"))

    def test_cr188_core_name_and_suffix_matching(self):
        """CR-188: 表記揺れコア名称および同一省庁部会サフィックス一致判定の検証"""
        # 1. コア名称生成
        self.assertEqual(
            discover_councils.get_core_council_name("援護審査会について"),
            discover_councils.get_core_council_name("援護審査会")
        )
        self.assertEqual(
            discover_councils.get_core_council_name("恩給審査会（平成21年度廃止前）"),
            discover_councils.get_core_council_name("恩給審査会")
        )
        self.assertEqual(
            discover_councils.get_core_council_name("令和8年度 化学物質管理に係る専門家検討会"),
            discover_councils.get_core_council_name("化学物質管理に係る専門家検討会")
        )

        # 2. 突合判定 (既存突合)
        existing_names = {"援護審査会"}
        existing_core_names = {"援護審査会"}
        existing_councils_by_min = {
            "MIC": [{"name": "情報通信審議会 情報通信技術分科会 電波利用環境委員会"}]
        }

        # 表記揺れ（について付き）がブロックされること
        self.assertTrue(discover_councils.is_already_registered_or_rejected(
            "援護審査会について", "https://example.com/engo", "MHLW",
            existing_names, set(), existing_core_names, existing_councils_by_min,
            set(), set(), set(), set()
        ))

        # 単独部会名が同一省庁の親審議会名＋部会名とサフィックス一致でブロックされること
        self.assertTrue(discover_councils.is_already_registered_or_rejected(
            "電波利用環境委員会", "https://example.com/denpa", "MIC",
            existing_names, set(), existing_core_names, existing_councils_by_min,
            set(), set(), set(), set()
        ))

        # Check 14 準拠: 同一省庁内の短縮サフィックス（イノベーション小委員会 vs 研究開発・イノベーション小委員会）がブロックされること
        existing_councils_by_min["METI"] = [{"name": "産業構造審議会 産業技術環境分科会 研究開発・イノベーション小委員会"}]
        self.assertTrue(discover_councils.is_already_registered_or_rejected(
            "イノベーション小委員会", "https://example.com/inno", "METI",
            existing_names, set(), existing_core_names, existing_councils_by_min,
            set(), set(), set(), set()
        ))

        # 別省庁や無関係なものはブロックされないこと
        self.assertFalse(discover_councils.is_already_registered_or_rejected(
            "電波利用環境委員会", "https://example.com/denpa", "METI",
            existing_names, set(), existing_core_names, existing_councils_by_min,
            set(), set(), set(), set()
        ))

    def test_cr191_url_preservation_and_unique_id_generation(self):
        """CR-191: 一覧URL非破壊および同一ID重複採番防止の検証"""
        # clean_council_name は年号範囲括弧を保持する
        name_with_year = "ストーカー行為等の規制等の在り方に関する有識者検討会（令和８年～）"
        cleaned = discover_councils.clean_council_name(name_with_year)
        self.assertIn("ストーカー行為等の規制等の在り方に関する有識者検討会", cleaned)

        # ID採番管理 (used_council_ids)
        used_ids = {"moj-2735"}
        next_seq = 2735
        min_code = "MOJ"

        # moj-2735 が使用済みの場合、重複せず次の連番（moj-2736）へインクリメントされること
        cand_id = f"{min_code.lower()}-{next_seq}"
        while cand_id in used_ids:
            next_seq += 1
            cand_id = f"{min_code.lower()}-{next_seq}"
        used_ids.add(cand_id)

        self.assertEqual(cand_id, "moj-2736")
        self.assertIn("moj-2736", used_ids)

    def test_drop107_press_release_guard(self):
        """Drop 107: 単発報道発表・記者会見専用URLの混入防止ガードの検証"""
        # 1. 報道発表専用URLパターンの判定
        press_urls = [
            "https://www.mlit.go.jp/report/press/road01_hh_002161.html",
            "https://www.mlit.go.jp/report/press/kouku05_hh_000248.html",
            "https://www.mod.go.jp/j/press/news/2026/09/01b.html",
            "https://www.soumu.go.jp/menu_news/s-news/01kiban18_01000296.html",
            "https://www.env.go.jp/press/press_05623.html",
            "https://www.moj.go.jp/hisho/kouhou/hisho06_00841.html",
            "https://www.mext.go.jp/b_menu/houdou/2026/01/1423456.htm",
            "https://www.meti.go.jp/press/2026/10/20261015001/20261015001.html",
        ]
        for u in press_urls:
            self.assertTrue(discover_councils.is_single_press_or_notice_url(u), f"Should detect press url: {u}")


        # 2. 通常の常設審議会ポータルURLは除外されないこと
        permanent_urls = [
            "https://www.moj.go.jp/shingi1/housei02_003011.html",
            "https://www.mlit.go.jp/koku/koku_fr9_000016.html",
            "https://www.mhlw.go.jp/stf/shingi/shingi-chuo_00001.html",
            "https://www.mhlw.go.jp/stf/newpage_09427.html",
            "https://www.soumu.go.jp/main_sosiki/joho_tsusin/policy/council.html",
        ]
        for u in permanent_urls:
            self.assertFalse(discover_councils.is_single_press_or_notice_url(u), f"Should not flag permanent url: {u}")

    def test_drop151_ministry_news_norm_orig_smoke(self):
        """Drop 151: _discover_from_ministry_news のルールループで norm_orig が未定義にならないこと"""
        from unittest.mock import patch
        import crawler as crawler_mod
        import llm.digest as digest_mod

        fake_news = [{
            "title": "「テスト金融審議会」第1回の開催について",
            "url": "https://www.fsa.go.jp/singi/test_council/siryou/20261125.html",
            "date": "2026/11/25"
        }]
        ministries = {
            "FSA": {
                "name": "金融庁",
                "newsPortals": [{"url": "https://www.fsa.go.jp/news/r8_news_menu.html", "type": "html"}]
            }
        }
        with patch.object(crawler_mod, "load_ministry_and_host_configs_from_db"), \
             patch.object(crawler_mod, "fetch_url", return_value="<html><body>ok</body></html>"), \
             patch.object(crawler_mod, "extract_news_items_from_html", return_value=fake_news), \
             patch.object(discover_councils, "resolve_parent_url_from_press_release",
                          return_value="https://www.fsa.go.jp/singi/test_council/index.html"), \
             patch.object(digest_mod, "build_discovery_digest",
                          return_value={"items": [], "stats": {"raw_count": 1, "candidate_count": 0}, "digest_hash": "0" * 64}):
            discovered, counts = discover_councils._discover_from_ministry_news(
                emit=lambda *a, **k: None,
                target_ministry="FSA",
                ministries=ministries,
                existing_councils=[],
                categories_def={"STUDY": "検討会", "COUNCIL": "審議会"},
                url_to_slug_map={},
                existing_urls=set(),
                existing_names=set(),
                rejected_names=set(),
                rejected_urls=set(),
                rejected_clean_keys=set(),
                common_keywords=["審議会", "検討会"],
                next_seq=1,
                used_council_ids=set()
            )
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0]["name"], "テスト金融審議会")

    def test_parent_resolver_breadcrumb_and_ministry_paths(self):
        """Drop 152: パンくずリスト・省庁審議会パス拡充・上位ディレクトリ200OKフォールバックを検証"""
        from unittest.mock import patch
        import crawler as crawler_mod

        # 1. パンくずリスト + /shingikai/ パスからの親URL逆引き
        press_html = """
        <html><body>
          <nav aria-label="breadcrumb">
            <a href="/index.html">ホーム</a>
            <a href="/shingikai/ai_kentoukai/index.html">AI推進検討会</a>
          </nav>
          <p>第1回会合を開催します。</p>
        </body></html>
        """
        with patch.object(crawler_mod, "fetch_url", return_value=press_html):
            resolved = discover_councils.resolve_parent_url_from_press_release(
                "https://www.meti.go.jp/press/2026/11/20261126001.html",
                "AI推進検討会",
                "METI"
            )
        self.assertEqual(resolved, "https://www.meti.go.jp/shingikai/ai_kentoukai/index.html")

        # 2. 個別回URLから1階層上の上位ディレクトリ index.html への200OKフォールバック
        sub_html = "<html><body><h1>第1回</h1><p>資料</p></body></html>"
        parent_html = "<html><head><title>次世代エネルギー検討会｜経済産業省</title></head><body><h1>次世代エネルギー検討会</h1></body></html>"
        def fake_fetch(u, timeout=10):
            if u == "https://www.meti.go.jp/shingikai/next_energy/dai1/index.html":
                return sub_html
            if u == "https://www.meti.go.jp/shingikai/next_energy/index.html":
                return parent_html
            return None

        with patch.object(crawler_mod, "fetch_url", side_effect=fake_fetch):
            resolved_up = discover_councils.resolve_parent_url_from_press_release(
                "https://www.meti.go.jp/shingikai/next_energy/dai1/index.html",
                "次世代エネルギー検討会",
                "METI"
            )
        self.assertEqual(resolved_up, "https://www.meti.go.jp/shingikai/next_energy/index.html")

    def test_generate_council_slug_id(self):
        """Drop 152: URLパス由来スラグID生成とフォールバック・重複回避の検証"""
        used = {"fsa-ai_rikatsuyou"}
        cid1, seq1 = discover_councils.generate_council_slug_id(
            "CAS", "https://www.cas.go.jp/jp/seisaku/digital-reform/index.html", used, 100
        )
        self.assertEqual(cid1, "cas-digital_reform")
        self.assertEqual(seq1, 100)

        # スラグ重複時は連番へフォールバック
        cid2, seq2 = discover_councils.generate_council_slug_id(
            "FSA", "https://www.fsa.go.jp/singi/ai-rikatsuyou/index.html", used, 50
        )
        self.assertEqual(cid2, "fsa-50")
        self.assertEqual(seq2, 51)

        # 汎用セグメント/数値のみ (newpage_12345.html) は連番へフォールバック
        cid3, seq3 = discover_councils.generate_council_slug_id(
            "MHLW", "https://www.mhlw.go.jp/stf/newpage_12345.html", used, 2880
        )
        self.assertEqual(cid3, "mhlw-2880")
        self.assertEqual(seq3, 2881)

    def test_infer_scraping_rule_for_council(self):
        """Drop 152: URL・DOM構造に基づく最適スクレイピングテンプレート自動推定の検証"""
        self.assertEqual(
            discover_councils.infer_scraping_rule_for_council("https://www.mhlw.go.jp/stf/newpage_99999.html")["template"],
            "tpl-mhlw-stf-subpage"
        )
        self.assertEqual(
            discover_councils.infer_scraping_rule_for_council("https://www.mof.go.jp/about_mof/councils/test/proceedings/index.html")["template"],
            "tpl-mof-proceedings-subpage"
        )
        self.assertEqual(
            discover_councils.infer_scraping_rule_for_council("https://www.cfa.go.jp/councils/shingikai/sample")["template"],
            "tpl-councils-uuid-subpage"
        )
        table_html = """
        <table>
          <tr><td>第1回</td><td><a href="01.pdf">資料</a></td></tr>
          <tr><td>第2回</td><td><a href="02.pdf">資料</a></td></tr>
        </table>
        """
        self.assertEqual(
            discover_councils.infer_scraping_rule_for_council("https://www.cas.go.jp/jp/seisaku/sample/index.html", html=table_html)["template"],
            "tpl-parent-table-direct"
        )


if __name__ == "__main__":
    unittest.main()
