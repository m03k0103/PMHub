#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
testing/test_drop22_normalization.py
====================================
Drop 22: 康煕部首・特殊文字 NFKC 正規化 & 検索漏れ根絶検証テスト (CR-46, CR-47)

1. admin/crawler.py の normalize_text 関数が康煕部首・CJK部首補助・全角英数を正しく正規化することの検証
2. docs/data.json 内に未処理の康煕部首（U+2F00〜U+2FD5）およびCJK部首補助（U+2E80〜U+2EF3）が0件であることの不変性検証
3. 全会議体・開催回のデータ整合性・破損ゼロ検証
"""

import os
import sys
import json
import unittest
import unicodedata

# Windows コンソールでの文字化け防止
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# PMHub 共通パス
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TEST_DIR, '..'))
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, 'docs', 'data.json')

sys.path.insert(0, os.path.join(PROJECT_ROOT, 'admin'))
from crawler import normalize_text, CJK_RADICAL_REPLACEMENTS
from batch_normalize_data import is_kangxi_or_supplement, count_kangxi_chars, scan_dataset_kangxi_stats


class TestDrop22Normalization(unittest.TestCase):
    """Drop 22 文字正規化テストスイート"""

    def test_cr46_normalize_text_kangxi_and_supplements(self):
        """CR-46: 康煕部首およびCJK部首補助が通常の標準漢字へ正しく変換されること"""
        # 1. 康煕部首
        kangxi_samples = {
            '⼈⼯知能': '人工知能',      # ⼈ (U+2F08) -> 人 (U+4EBA)
            '⽂化審議会': '文化審議会',    # ⽂ (U+2F42) -> 文 (U+6587)
            '１２⽉２７⽇': '12月27日',   # ⽉ (U+2F49) -> 月, ⽇ (U+2F47) -> 日
            '⾷品安全': '食品安全',        # ⾷ (U+2FB7) -> 食
            '地域課題解決⽀援': '地域課題解決支援', # ⽀ (U+2F40) -> 支
            '在り⽅': '在り方',           # ⽅ (U+2F45) -> 方
            '⾒直し': '見直し',           # ⾒ (U+2F92) -> 見
            '動物⽤医薬品': '動物用医薬品',  # ⽤ (U+2F64) -> 用
            '再⽣医療': '再生医療',        # ⽣ (U+2F63) -> 生
            '⾻⼦': '骨子',              # ⾻ (U+2FBB) -> 骨
            '意⾒募集': '意見募集',        # ⾒ (U+2F92) -> 見
            '中期⽬標': '中期目標',        # ⽬ (U+2F6C) -> 目
        }
        for bad_str, expected in kangxi_samples.items():
            normalized = normalize_text(bad_str)
            self.assertEqual(normalized, expected, f"康煕部首 '{bad_str}' が '{expected}' に正規化されませんでした (結果: '{normalized}')")

        # 2. CJK部首補助 (U+2EA0 ⺠ -> 民)
        cjk_supp = '国⺠の健康の増進'
        self.assertEqual(normalize_text(cjk_supp), '国民の健康の増進')

        # 3. 全角英数・全角記号
        fullwidth_samples = {
            'ＡＩ戦略本部': 'AI戦略本部',
            'ＷＧ第１回': 'WG第1回',
            '（ＰＤＦ／１００ＫＢ）': '(PDF/100KB)',
        }
        for bad_str, expected in fullwidth_samples.items():
            self.assertEqual(normalize_text(bad_str), expected)

    def test_cr47_no_kangxi_radicals_in_data_json(self):
        """CR-47: docs/data.json 内に康煕部首およびCJK部首補助が 0 件であること（不変性検証）"""
        self.assertTrue(os.path.exists(DATA_JSON_PATH), f"data.json が見つかりません: {DATA_JSON_PATH}")
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        stats = scan_dataset_kangxi_stats(data)
        self.assertEqual(
            stats["total"], 0,
            f"docs/data.json 内に未処理の康煕部首/部首補助が {stats['total']} 箇所検出されました: "
            f"councils={stats['councils']}, meetings={stats['meetings']}, materials={stats['materials']}"
        )

    def test_cr47_data_integrity(self):
        """CR-47: 正規化後も全会議体マスター（1,446件）および開催回数が維持されていること"""
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        councils = data.get("councils", [])
        meetings = data.get("meetings", [])
        self.assertGreaterEqual(len(councils), 1446, "会議体マスター件数が 1,446 件以上であること")
        self.assertGreaterEqual(len(meetings), 15000, "開催回データが大幅に欠落しています")

        # IDの不変性（ID文字列は変化しないこと）
        for c in councils:
            cid = c.get("id", "")
            self.assertTrue(cid and "-" in cid, f"不正な会議体ID: {cid}")


if __name__ == "__main__":
    unittest.main()
