#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
和暦略記・URL日付解析 & 開催回ID正規化規約 単体テストスイート (test_date_and_id_parsing.py)
- CR-54: parse_japanese_date 元号略記パース、防衛省形式テーブル抽出
- URL埋め込み日付（kaiYYYYMMDD, meetingYYYYMMDD 等）の抽出
- CR-118: validate_meeting_id 開催回ID命名規約・4桁通常回次・3桁臨時回次許容検証
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "admin"))
from utils import setup_win32_utf8, parse_japanese_date, validate_meeting_id
setup_win32_utf8()

from crawler import _extract_meetings_from_parent_table, _extract_date_from_url


class TestDateAndIdParsing(unittest.TestCase):

    def test_parse_japanese_date_short_era(self):
        """CR-54: parse_japanese_date が元号略記形式を正確にパースすること"""
        cases = [
            ("R3.12.6", datetime(2021, 12, 6)),
            ("R2.12.15", datetime(2020, 12, 15)),
            ("R1.11.27", datetime(2019, 11, 27)),
            ("R元.5.1", datetime(2019, 5, 1)),
            ("H30.11.28", datetime(2018, 11, 28)),
            ("H22.12.14", datetime(2010, 12, 14)),
            ("R06/05/20", datetime(2024, 5, 20)),
            ("H23-05-17", datetime(2011, 5, 17)),
            ("08.8.13", datetime(2026, 8, 13)),
            ("08.2.27", datetime(2026, 2, 27)),
            ("07.12.18", datetime(2025, 12, 18)),
            ("07.8.21", datetime(2025, 8, 21)),
            ("07.8.5", datetime(2025, 8, 5)),
            ("07.2.26", datetime(2025, 2, 26)),
            ("07.1.10", datetime(2025, 1, 10)),
            ("18.3.7", datetime(2006, 3, 7)),
        ]
        for inp, expected in cases:
            with self.subTest(inp=inp):
                dt = parse_japanese_date(inp)
                self.assertIsNotNone(dt, f"Failed to parse: {inp}")
                self.assertEqual(dt, expected)

    def test_extract_meetings_from_parent_table_mod_structure(self):
        """CR-54: 防衛省の元号略記テーブルから開催回・日付・資料が一体抽出されること"""
        sample_html = """
        <html>
        <body>
        <table class="table_01">
          <tr><th>回数</th><th>開催日</th><th>議事次第</th><th>議事概要</th></tr>
          <tr>
            <td>第9回</td>
            <td>R3.12.6</td>
            <td><a href="/j/policy/agenda/meeting/ijime-boushi/pdf/09_01.pdf">議事次第（PDF）</a></td>
            <td><a href="/j/policy/agenda/meeting/ijime-boushi/pdf/09_02.pdf">議事概要（PDF）</a></td>
          </tr>
          <tr>
            <td>第8回</td>
            <td>R2.12.15</td>
            <td><a href="/j/policy/agenda/meeting/ijime-boushi/pdf/08_01.pdf">議事次第（PDF）</a></td>
            <td><a href="/j/policy/agenda/meeting/ijime-boushi/pdf/08_02.pdf">議事概要（PDF）</a></td>
          </tr>
        </table>
        </body>
        </html>
        """
        target_url = "https://www.mod.go.jp/j/policy/agenda/meeting/ijime-boushi/index.html"
        council_name = "防衛省におけるパワー・ハラスメントの防止に関する検討委員会"

        meetings = _extract_meetings_from_parent_table(sample_html, target_url, council_name)
        self.assertEqual(len(meetings), 2)

        m1 = meetings[0]
        self.assertEqual(m1["extractedDates"], ["2021/12/06"])
        self.assertIn("第9回", m1["name"])
        self.assertEqual(len(m1["materials"]), 2)
        self.assertTrue(m1["materials"][0]["url"].endswith("09_01.pdf"))

        m2 = meetings[1]
        self.assertEqual(m2["extractedDates"], ["2020/12/15"])
        self.assertIn("第8回", m2["name"])
        self.assertEqual(len(m2["materials"]), 2)

    def test_extract_date_from_url_kai_pattern(self):
        """FSC等のURL埋め込み日付（kaiYYYYMMDD, meetingYYYYMMDD等）が正確に抽出されること"""
        cases = [
            ("https://www.fsc.go.jp/fsciis/meetingMaterial/show/kai20200731ff1", "2020/07/31"),
            ("https://www.fsc.go.jp/fsciis/meetingMaterial/show/kai20111121ki1", "2011/11/21"),
            ("https://example.go.jp/meeting20240820_report.html", "2024/08/20"),
            ("https://example.go.jp/giji20210514.pdf", "2021/05/14"),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                res = _extract_date_from_url(url)
                self.assertEqual(res, expected, f"Failed for {url}")

    def test_validate_meeting_id_unit(self):
        """CR-118: validate_meeting_id 関数の単体検証（4桁通常回次・3桁臨時回次許容 & プレフィックス遮断）"""
        self.assertTrue(validate_meeting_id("cas-kokudo_kyoujinka-20260703-024"))
        self.assertTrue(validate_meeting_id("nra-genshiryoku_kisei-20261007-1043"))
        self.assertTrue(validate_meeting_id("cas-tokubetsu-20260807-s01"))
        self.assertTrue(validate_meeting_id("mic-housou_seisaku-20261001-s100"))

        self.assertFalse(validate_meeting_id("aca-kokugo_gairai-20260807-r08_003"))
        self.assertFalse(validate_meeting_id("caa-shouhisha_iinkai-20100521-h22_005"))
        self.assertFalse(validate_meeting_id("fsc-osen_tou-20140912-kanji_012"))
        self.assertFalse(validate_meeting_id("cas-grassroots_tf-20170426-001_2"))
        self.assertFalse(validate_meeting_id("cas-nousui-20220628-20231227"))


if __name__ == "__main__":
    unittest.main()
