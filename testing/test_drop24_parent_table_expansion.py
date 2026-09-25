#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
testing/test_drop24_parent_table_expansion.py
============================================
Drop 24: 親ページテーブル HTML 資料展開エンジンの単体テスト (CR-51)
- テーブル行内の HTML 資料リンクから末端 PDF 資料が展開されること
- 直接 PDF がない場合に HTML ページ自体が資料としてフォールバック保持されること
"""

import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))
from crawler import _extract_meetings_from_parent_table


class TestDrop24ParentTableExpansion(unittest.TestCase):
    """Drop 24: 親ページテーブル HTML 資料展開エンジンの単体テスト"""

    def test_cr51_expand_html_material_pages_to_pdf(self):
        """CR-51: テーブル行内の HTML 資料リンクから内部の PDF 資料が展開されること"""
        parent_html = """
        <!DOCTYPE html>
        <html>
        <head><title>感染症・予防接種審査分科会</title></head>
        <body>
            <table>
                <tr>
                    <th>回数</th><th>開催日</th><th>資料等</th>
                </tr>
                <tr>
                    <td>第44回</td>
                    <td>2026年9月17日</td>
                    <td>
                        <a href="newpage_76327.html">審議結果NEW9月18日</a>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        sub_html = """
        <!DOCTYPE html>
        <html>
        <head><title>審議結果詳細</title></head>
        <body>
            <div id="content">
                <a href="/content/10900000/001751519.pdf">審議結果［PDF形式：280KB］</a>
            </div>
        </body>
        </html>
        """

        def mock_fetch(url, timeout=6):
            if "newpage_76327.html" in url:
                return sub_html
            return None

        with patch('crawler.fetch_url', side_effect=mock_fetch):
            meetings = _extract_meetings_from_parent_table(
                parent_html,
                "https://www.mhlw.go.jp/stf/shingi/shingi-shippei.html",
                "感染症・予防接種審査分科会"
            )

        self.assertEqual(len(meetings), 1)
        m = meetings[0]
        self.assertEqual(m["name"], "第44回 感染症・予防接種審査分科会")
        self.assertEqual(m["extractedDates"], ["2026/09/17"])
        self.assertEqual(len(m["materials"]), 1)
        self.assertEqual(m["materials"][0]["type"], "PDF")
        self.assertIn("001751519.pdf", m["materials"][0]["url"])

    def test_cr51_fallback_to_html_doc_when_no_pdf(self):
        """CR-51: HTML リンク先に PDF がない場合、当該 HTML ページが資料として保持されること"""
        parent_html = """
        <!DOCTYPE html>
        <html>
        <body>
            <table>
                <tr><th>回数</th><th>開催日</th><th>資料</th></tr>
                <tr>
                    <td>第1回</td>
                    <td>令和8年5月10日</td>
                    <td><a href="doc1.html">答申</a></td>
                </tr>
            </table>
        </body>
        </html>
        """
        sub_html_no_pdf = """
        <!DOCTYPE html>
        <html>
        <body><p>答申本文テキスト...</p></body>
        </html>
        """

        def mock_fetch(url, timeout=6):
            if "doc1.html" in url:
                return sub_html_no_pdf
            return None

        with patch('crawler.fetch_url', side_effect=mock_fetch):
            meetings = _extract_meetings_from_parent_table(
                parent_html,
                "https://www.cao.go.jp/sample/index.html",
                "テスト審議会"
            )

        self.assertEqual(len(meetings), 1)
        m = meetings[0]
        self.assertEqual(len(m["materials"]), 1)
        self.assertEqual(m["materials"][0]["type"], "HTML")
        self.assertIn("doc1.html", m["materials"][0]["url"])


if __name__ == "__main__":
    unittest.main()
