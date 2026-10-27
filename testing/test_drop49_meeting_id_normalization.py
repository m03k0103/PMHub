#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_drop49_meeting_id_normalization.py - Drop 49 開催回ID命名規約の整合化 & 4桁回次許容仕様の標準化検証 (U16)
※ 本番 data.json 全開催回IDの準拠性・重複ゼロ検証は統合テスト ケース5 (test_no_duplicate_meetings.py Check 1 & 9) に集約されています。
"""

import unittest
import os
import sys
import re

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('admin'))

from admin.utils import validate_meeting_id, _RE_MEETING_ID


class TestDrop49MeetingIdNormalization(unittest.TestCase):

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


if __name__ == '__main__':
    unittest.main()
