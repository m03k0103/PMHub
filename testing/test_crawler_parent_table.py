#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 11: 親ページ直結型（テーブル/リスト型）抽出エンジン 単体テストスイート
- CR-5: _extract_meetings_from_parent_table による回次・日付・資料の一体抽出
- CR-6: 親URL同一開催回の回次・日付重複判定と sync_new_meetings_from_crawl 統合
"""

import unittest
import sys
import os

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))

from crawler import (
    _extract_meetings_from_parent_table,
    sync_new_meetings_from_crawl
)


class TestCrawlerParentTableDrop11(unittest.TestCase):
    """Drop 11 で実装された親ページテーブル解析エンジンの単体テスト"""

    def test_cr5_extract_meetings_from_table_rows(self):
        """CR-5: テーブル行から回次・日付・配付資料リストが正確に抽出されること"""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>廃炉・汚染水対策関係閣僚等会議</title></head>
        <body>
            <table>
                <tr>
                    <th>回数</th>
                    <th>日時</th>
                    <th>会議関係資料</th>
                </tr>
                <tr>
                    <td>第1回</td>
                    <td>平成25年 9月10日</td>
                    <td>
                        <a href="dai1/shiryo1.pdf">配付資料1（PDF形式：500KB）</a>
                        <a href="dai1/gijiroku.pdf">議事録（PDF形式：200KB）</a>
                        <a href="dai1/index.html">詳細ページ</a>
                    </td>
                </tr>
                <tr>
                    <td>第2回</td>
                    <td>令和3年\u20034月16日</td>
                    <td>
                        <a href="dai2/shiryo.pdf">配付資料</a>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        target_url = "https://www.cas.go.jp/jp/seisakukaigi/hairo_osensui/index.html"
        council_name = "廃炉・汚染水対策関係閣僚等会議"

        meetings = _extract_meetings_from_parent_table(sample_html, target_url, council_name)
        self.assertEqual(len(meetings), 2)

        # 第1回
        m1 = meetings[0]
        self.assertEqual(m1["name"], "第1回 廃炉・汚染水対策関係閣僚等会議")
        self.assertEqual(m1["extractedDates"], ["2013/09/10"])
        self.assertEqual(m1["subpageUrl"], "https://www.cas.go.jp/jp/seisakukaigi/hairo_osensui/dai1/index.html")
        self.assertEqual(len(m1["materials"]), 2)
        self.assertEqual(m1["materials"][0]["name"], "配付資料1")
        self.assertEqual(m1["materials"][1]["name"], "議事録")

        # 第2回（特殊空白 \u2003 混入日付）
        m2 = meetings[1]
        self.assertEqual(m2["name"], "第2回 廃炉・汚染水対策関係閣僚等会議")
        self.assertEqual(m2["extractedDates"], ["2021/04/16"])
        self.assertEqual(len(m2["materials"]), 1)
        self.assertEqual(m2["materials"][0]["name"], "配付資料")

    def test_cr5_cell_text_fallback_for_generic_link_names(self):
        """CR-5: リンクテキストが「PDF」等の汎用文字列の場合、セル内テキストから資料名が補正されること"""
        sample_html = """
        <table>
            <tr><th>回次</th><th>開催日</th><th>議事概要</th><th>配付資料</th></tr>
            <tr>
                <td>第3回</td>
                <td>2026年5月20日</td>
                <td>議事概要（案） <a href="gaiyou.pdf">PDF</a></td>
                <td>説明資料について <a href="shiryo.pdf">ダウンロード</a></td>
            </tr>
        </table>
        """
        meetings = _extract_meetings_from_parent_table(sample_html, "https://example.com/kaigi.html", "有識者会議")
        self.assertEqual(len(meetings), 1)
        m = meetings[0]
        self.assertEqual(m["name"], "第3回 有識者会議")
        self.assertEqual(m["extractedDates"], ["2026/05/20"])
        self.assertEqual(len(m["materials"]), 2)
        # セルの親テキストから補正されていること
        self.assertIn("議事概要", m["materials"][0]["name"])
        self.assertIn("説明資料", m["materials"][1]["name"])

    def test_cr5_skips_non_meeting_rows(self):
        """CR-5: 名簿テーブルや回次・日付のない行がスキップされること"""
        sample_html = """
        <table>
            <tr><th>氏名</th><th>所属</th><th>役職</th></tr>
            <tr><td>山田太郎</td><td>○○大学</td><td>教授</td></tr>
            <tr><td>佐藤花子</td><td>○○研究所</td><td>所長</td></tr>
        </table>
        """
        meetings = _extract_meetings_from_parent_table(sample_html, "https://example.com/meibo.html", "有識者会議")
        self.assertEqual(len(meetings), 0)

    def test_cr6_sync_new_meetings_parent_table_integration(self):
        """CR-6: 親URLと同一のサブURLを持つ開催回が正しく新規追加および重複防止されること"""
        target = {
            "id": "test-table_council",
            "name": "テスト親テーブル会議体",
            "ministry": "CAS",
            "officialUrl": "https://example.com/table_council/index.html"
        }
        data = {
            "councils": [dict(target)],
            "meetings": []
        }
        scraped_item = {
            "subpageMeetings": [
                {
                    "subpageUrl": "https://example.com/table_council/index.html",
                    "name": "第1回 テスト親テーブル会議体",
                    "title": "第1回 テスト親テーブル会議体",
                    "extractedMaterialsCount": 1,
                    "materials": [{"name": "資料1", "url": "https://example.com/table_council/shiryo1.pdf", "type": "PDF"}],
                    "extractedDates": ["2026/04/01"],
                    "isFromParentTable": True
                },
                {
                    "subpageUrl": "https://example.com/table_council/index.html",
                    "name": "第2回 テスト親テーブル会議体",
                    "title": "第2回 テスト親テーブル会議体",
                    "extractedMaterialsCount": 1,
                    "materials": [{"name": "資料2", "url": "https://example.com/table_council/shiryo2.pdf", "type": "PDF"}],
                    "extractedDates": ["2026/05/01"],
                    "isFromParentTable": True
                }
            ]
        }

        # 1回目の同期: 2件追加されること
        added = sync_new_meetings_from_crawl(data, target, scraped_item)
        self.assertEqual(added, 2)
        self.assertEqual(len(data["meetings"]), 2)
        self.assertEqual(data["meetings"][0]["id"], "test-table_council-20260501-002")
        self.assertEqual(data["meetings"][1]["id"], "test-table_council-20260401-001")

        # 2回目の同期: 既に同一回次・同一日付が存在するため 0 件追加（安全にスキップ）されること
        added2 = sync_new_meetings_from_crawl(data, target, scraped_item)
        self.assertEqual(added2, 0)
        self.assertEqual(len(data["meetings"]), 2)


if __name__ == "__main__":
    unittest.main()
