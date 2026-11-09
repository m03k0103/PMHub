#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配付資料コンテキスト復元・ノイズ除去・TXT議事録解析・中間HTML判定 単体テストスイート (test_material_extraction.py)
- CR-110: is_generic_material_name() / recover_material_context() スマートコンテキスト復元
- is_sns_pr_url / is_non_pdf_anchor_url / clean_meeting_title ノイズ除外・タイトル整形
- CR-114: parse_txt_minutes による .txt 議事録からの日付・回次・タイトル・配付資料抽出
- CR-209: is_intermediate_html_material 中間HTMLコンテナ判定ロジック
"""

import os
import sys
import unittest
from bs4 import BeautifulSoup

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ADMIN_DIR = os.path.join(REPO_ROOT, 'admin')
TESTING_DIR = os.path.dirname(os.path.abspath(__file__))
for p in (REPO_ROOT, ADMIN_DIR, TESTING_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from crawler import (
    is_generic_material_name,
    recover_material_context,
    normalize_text,
    is_sns_pr_url,
    is_non_pdf_anchor_url,
    clean_meeting_title,
    parse_txt_minutes
)
from test_no_duplicate_meetings import is_intermediate_html_material


class TestMaterialExtraction(unittest.TestCase):
    """配付資料コンテキスト復元・ノイズ除去・TXT議事録・中間HTML判定の単体テスト"""

    def test_generic_material_name_detection(self):
        """ジェネリック資料名の判定ロジック検証 (CR-110)"""
        generics = [
            'PDF', 'pdf', '資料', 'ダウンロード', '配付資料', '配布資料',
            '別紙', '別添', '添付', '添付資料', '一覧', '詳細',
            '[ PDF ]', '(PDF)', '［PDF形式：120KB］', '（資料）', '【配付資料】'
        ]
        for g in generics:
            self.assertTrue(is_generic_material_name(g), f"'{g}' はジェネリックと判定されるべき")

        legit_names = [
            '議事次第',
            '資料1 今後の進め方について',
            '参考資料2 委員名簿',
            '社会保障審議会年金部会報告書（案）',
            '第1回検討会配付資料 (01.pdf)',
            '議事録'
        ]
        for name in legit_names:
            self.assertFalse(is_generic_material_name(name), f"'{name}' はジェネリックではないと判定されるべき")

    def test_recover_mhlw_td_inline_pattern(self):
        """厚労省型: 親td内の直前テキストからの資料名スマート復元 (CR-110)"""
        html = """
        <td>
            （１）今後の勤労者財産形成促進制度について（中間報告）（案）について
            ( <a href="dl/s0412-2a.pdf">PDF</a> :318KB)
        </td>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="PDF")
        self.assertIn("今後の勤労者財産形成促進制度について", recovered)
        self.assertFalse(is_generic_material_name(recovered))

    def test_recover_mof_table_row_pattern(self):
        """財務省型: 同一tr内の先行th/td見出しセルからの資料名復元 (CR-110)"""
        html = """
        <table>
            <tr>
                <th scope="row">財政健全化に向けた建議（案）</th>
                <td>[ <a href="./01.pdf">PDF(PDF:2068KB)</a> ]</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="PDF")
        self.assertEqual(recovered, normalize_text("財政健全化に向けた建議（案）"))

    def test_recover_list_item_pattern(self):
        """リスト項目型: li要素内のテキストからの資料名復元 (CR-110)"""
        html = """
        <ul>
            <li>
                議題1：デジタル行財政改革の推進状況について
                <a href="mat01.pdf">資料［PDF形式：450KB］</a>
            </li>
        </ul>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="資料")
        self.assertIn("デジタル行財政改革の推進状況について", recovered)

    def test_recover_gijiroku_filename_pattern(self):
        """ファイル名に gijiroku を含む場合の「議事録」フォールバック自動命名検証"""
        html = """
        <div>
            <a href="https://www.cao.go.jp/consumer/content/260806_gijiroku.pdf">PDF形式:152KB</a>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        a_tag = soup.find('a')
        recovered = recover_material_context(a_tag, initial_name="PDF形式:152KB")
        self.assertEqual(recovered, "議事録")

    def test_unit_crawler_helpers(self):
        """crawler.py のノイズ除去ガード関数の単体動作検証"""
        self.assertTrue(is_sns_pr_url("https://twitter.com/MOJ_HOUMU"))
        self.assertTrue(is_sns_pr_url("https://x.com/Gaikoshiryokan"))
        self.assertTrue(is_sns_pr_url("https://www.youtube.com/user/MOJchannel"))
        self.assertTrue(is_sns_pr_url("https://www.facebook.com/mofa.japan"))
        self.assertFalse(is_sns_pr_url("https://www.youtube.com/live/abcdefgh"))
        self.assertFalse(is_sns_pr_url("https://www.youtube.com/watch?v=12345678"))
        self.assertFalse(is_sns_pr_url("https://www.mhlw.go.jp/content/12345.pdf"))

        self.assertTrue(is_non_pdf_anchor_url("#siryou"))
        self.assertTrue(is_non_pdf_anchor_url("https://www.maff.go.jp/index.html#siryou"))
        self.assertTrue(is_non_pdf_anchor_url("https://www.soumu.go.jp/page.html#contents"))
        self.assertFalse(is_non_pdf_anchor_url("https://www.soumu.go.jp/doc.pdf#page=1"))
        self.assertFalse(is_non_pdf_anchor_url("https://www.cao.go.jp/sample.pdf"))

        self.assertEqual(clean_meeting_title("第5回 会議<br>（新時代）"), "第5回 会議 (新時代)")
        self.assertEqual(clean_meeting_title("第1回 検討会<span>（資料）</span>"), "第1回 検討会 (資料)")

    def test_mock_meeting_noise_detection(self):
        """モック開催回リストに対するノイズ検出ロジック単体検証"""
        mock_meetings = [
            {
                "id": "test-c1-20260101-001",
                "name": "第1回 テスト会合",
                "materials": [
                    {"name": "正常資料", "url": "https://example.com/mat1.pdf"},
                    {"name": "JSリンク", "url": "javascript:void(0)"},
                    {"name": "SNSリンク", "url": "https://twitter.com/test"},
                    {"name": "アンカー", "url": "#contents"}
                ]
            }
        ]
        js_detected = [m["url"] for m in mock_meetings[0]["materials"] if m["url"].startswith("javascript:")]
        sns_detected = [m["url"] for m in mock_meetings[0]["materials"] if is_sns_pr_url(m["url"])]
        anchor_detected = [m["url"] for m in mock_meetings[0]["materials"] if is_non_pdf_anchor_url(m["url"])]

        self.assertEqual(len(js_detected), 1)
        self.assertEqual(len(sns_detected), 1)
        self.assertEqual(len(anchor_detected), 1)

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

    def test_helper_detection_logic(self):
        """中間HTML判定ロジックが正しく判定すること"""
        self.assertTrue(is_intermediate_html_material('会議資料', 'https://www.cao.go.jp/zei-cho/gijiroku/digital-noukan/2025/7digital-noukan4kai.html'))
        self.assertTrue(is_intermediate_html_material('配付資料一覧ページ (HTML)', 'https://www.chisou.go.jp/tiiki/kokusentoc/dai69/shiryou.html'))
        self.assertTrue(is_intermediate_html_material('第16回 議事次第・配付資料 (HTML)', 'https://www.cas.go.jp/jp/seisaku/kagayakujosei/dai16/gijisidai.html'))
        self.assertTrue(is_intermediate_html_material('会議資料', 'https://www.mof.go.jp/about_mof/councils/fiscal_system_council/sub-of_filp/proceedings/material/zaitoa20250731.html'))
        self.assertTrue(is_intermediate_html_material('配付資料', 'https://www.mhlw.go.jp/stf/newpage_76614.html'))
        self.assertTrue(is_intermediate_html_material('開催案内', 'https://www.mhlw.go.jp/stf/newpage_76613.html'))
        self.assertFalse(is_intermediate_html_material('次第', 'https://www.cao.go.jp/zei-cho/content/7digital-noukan4kai.pdf'))
        self.assertFalse(is_intermediate_html_material('議事要旨', 'https://www.soumu.go.jp/main_sosiki/singi/gijiyoushi.html'))
        self.assertFalse(is_intermediate_html_material('議事録', 'https://www.mof.go.jp/about_mof/councils/fiscal_system_council/sub-of_filp/proceedings/proceedings/zaitoa20250731.html'))


if __name__ == '__main__':
    unittest.main()
