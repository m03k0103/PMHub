"""
test_drop49_meeting_id_normalization.py - Drop 49 開催回ID命名規約の整合化 & 4桁回次許容仕様の標準化検証
"""

import unittest
import json
import os
import sys
import re

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('admin'))

from admin.utils import validate_meeting_id, _RE_MEETING_ID


class TestDrop49MeetingIdNormalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        json_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data.json')
        cls.json_path = os.path.abspath(json_path)
        with open(cls.json_path, 'r', encoding='utf-8') as f:
            cls.data = json.load(f)
        cls.meetings = cls.data.get('meetings', [])
        cls.councils = cls.data.get('councils', [])

    def test_validate_meeting_id_unit(self):
        """CR-118: validate_meeting_id 関数の単体検証（4桁通常回次・3桁臨時回次許容 & プレフィックス遮断）"""
        # 正常系: 通常3桁
        self.assertTrue(validate_meeting_id("cas-kokudo_kyoujinka-20260703-024"))
        # 正常系: 通常4桁 (CR-118: 1,000回超公式回次)
        self.assertTrue(validate_meeting_id("nra-genshiryoku_kisei-20261007-1043"))
        # 正常系: 臨時2桁
        self.assertTrue(validate_meeting_id("cas-tokubetsu-20260807-s01"))
        # 正常系: 臨時3桁 (CR-118: 通算100回超)
        self.assertTrue(validate_meeting_id("mic-housou_seisaku-20261001-s100"))

        # 異常系: 年度プレフィックス混入 (CR-119で撲滅)
        self.assertFalse(validate_meeting_id("aca-kokugo_gairai-20260807-r08_003"))
        self.assertFalse(validate_meeting_id("caa-shouhisha_iinkai-20100521-h22_005"))
        # 異常系: 部会名プレフィックス混入 (CR-120で撲滅)
        self.assertFalse(validate_meeting_id("fsc-osen_tou-20140912-kanji_012"))
        # 異常系: 末尾アンダースコアノイズ
        self.assertFalse(validate_meeting_id("cas-grassroots_tf-20170426-001_2"))
        # 異常系: セグメント数不一致
        self.assertFalse(validate_meeting_id("cas-nousui-20220628-20231227"))

    def test_meeting_id_conformance_100_percent(self):
        """CR-119, CR-120: 全開催回IDが AGENTS.md 規約に 100% 準拠していること（非規約ID 0件）"""
        non_conforming = [
            m.get('id') for m in self.meetings
            if not validate_meeting_id(m.get('id', ''))
        ]
        self.assertEqual(
            len(non_conforming), 0,
            f"Found {len(non_conforming)} non-conforming meeting IDs: {non_conforming[:10]}"
        )

    def test_no_duplicate_meeting_ids(self):
        """CR-119: マイグレーション後の全開催回IDに重複が一切存在しないこと（重複 0件）"""
        id_counts = {}
        for m in self.meetings:
            mid = m.get('id', '')
            id_counts[mid] = id_counts.get(mid, 0) + 1

        duplicates = {k: v for k, v in id_counts.items() if v > 1}
        self.assertEqual(
            len(duplicates), 0,
            f"Found {len(duplicates)} duplicate meeting IDs: {duplicates}"
        )

    def test_four_digit_and_special_round_support(self):
        """CR-118: 4桁通常回次（\\d{4}）および3桁臨時回次（s\\d{3}）の存在確認"""
        four_digit_meetings = [
            m for m in self.meetings
            if re.match(r'^[a-z0-9]+-[a-z0-9_]+-\d{8}-\d{4}$', m.get('id', ''))
        ]
        special_3digit_meetings = [
            m for m in self.meetings
            if re.match(r'^[a-z0-9]+-[a-z0-9_]+-\d{8}-[a-z]\d{3}$', m.get('id', ''))
        ]
        self.assertGreater(len(four_digit_meetings), 30, "Should have more than 30 4-digit meetings")
        self.assertGreater(len(special_3digit_meetings), 10, "Should have more than 10 s\\d{3} meetings")


if __name__ == '__main__':
    unittest.main()
