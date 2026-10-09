"""
test_drop48_zero_materials_rescue.py - Drop 48 配付資料0件開催回救済 & 議事録テキスト正式資料化検証
"""

import unittest
import json
import os
import sys

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('admin'))

from admin.crawler import parse_txt_minutes


class TestDrop48ZeroMaterialsRescue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        json_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data.json')
        cls.json_path = os.path.abspath(json_path)
        with open(cls.json_path, 'r', encoding='utf-8') as f:
            cls.data = json.load(f)
        cls.meetings = cls.data.get('meetings', [])
        cls.councils = cls.data.get('councils', [])

    def test_parse_txt_minutes_unit(self):
        """CR-114, CR-116: parse_txt_minutes による日付・回次・タイトル・配付資料抽出の単体検証"""
        sample_txt = (
            "07/04/26 社会保障審議会年金部会第4回議事録\n"
            "日　時：平成19年4月26日（木）10:00～12:00\n"
            "場　所：厚生労働省専用第21会議室\n"
            "出席者：委員一同\n"
        )
        url = "https://www.mhlw.go.jp/shingi/2007/04/txt/shingi-nenkin_070426.txt"
        res = parse_txt_minutes(sample_txt, url)

        self.assertEqual(res['date'], "2007/04/26")
        self.assertEqual(res['round_number'], 4)
        self.assertEqual(res['title'], "社会保障審議会年金部会第4回")
        self.assertEqual(len(res['materials']), 1)
        self.assertEqual(res['materials'][0]['name'], "議事録")
        self.assertEqual(res['materials'][0]['type'], "TXT")
        self.assertEqual(res['materials'][0]['url'], url)
        self.assertTrue(res['materials'][0].get('manualLock', False))

    def test_no_zero_materials_for_txt_meetings(self):
        """CR-114: officialUrl が .txt の開催回において配付資料が0件のレコードが残存しないことの検証"""
        txt_zero = [
            m for m in self.meetings
            if m.get('officialUrl', '').endswith('.txt') and len(m.get('materials', [])) == 0
        ]
        self.assertEqual(
            len(txt_zero), 0,
            f"Found {len(txt_zero)} .txt meetings with 0 materials. All .txt meetings must have materials."
        )

    def test_txt_meeting_id_and_date_conformance(self):
        """CR-114: .txt 議事録開催回の日付・IDが正規フォーマットになっていることの検証"""
        txt_meetings = [
            m for m in self.meetings
            if m.get('officialUrl', '').endswith('.txt')
        ]
        self.assertGreater(len(txt_meetings), 100, "Should have more than 100 .txt meetings")

        for m in txt_meetings:
            # 開催日未確定の2099やダミー日付でないこと
            self.assertNotEqual(m.get('date'), "2099/01/01")
            self.assertRegex(m.get('date', ''), r'^\d{4}/\d{2}/\d{2}$')
            # ID が 4セグメントフォーマットであること
            parts = m.get('id', '').split('-')
            self.assertEqual(len(parts), 4, f"Meeting ID {m.get('id')} should have 4 segments")
            self.assertEqual(len(parts[2]), 8, f"Date part in ID {m.get('id')} should be 8 digits")

    def test_overall_zero_materials_reduction(self):
        """CR-115: 配付資料0件開催回の全体件数が救済され大幅に減少していることの検証"""
        total_zero = sum(1 for m in self.meetings if len(m.get('materials', [])) == 0)
        total_meetings = len(self.meetings)
        zero_ratio = (total_zero / total_meetings) * 100

        # 元の 1,002件から大幅に削減（336件救済、666件、約3.5%）されたことを確認
        self.assertLess(total_zero, 700, f"Zero material meetings ({total_zero}) should be significantly less than 700")
        self.assertLess(zero_ratio, 4.0, f"Zero material ratio ({zero_ratio:.2f}%) should be less than 4.0%")


if __name__ == '__main__':
    unittest.main()
