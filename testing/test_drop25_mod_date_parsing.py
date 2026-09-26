import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "admin"))
from utils import setup_win32_utf8, parse_japanese_date
setup_win32_utf8()

from crawler import _extract_meetings_from_parent_table


class TestDrop25ModDateParsing(unittest.TestCase):

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


if __name__ == "__main__":
    unittest.main()
