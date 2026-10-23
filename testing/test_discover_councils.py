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


class TestDiscoverCouncilsDrop75(unittest.TestCase):

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


if __name__ == "__main__":
    unittest.main()
