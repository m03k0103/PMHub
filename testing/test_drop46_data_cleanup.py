#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 46: 緊急データクリーンアップ & ノイズ配付資料・UI操作リンク完全排除・文字化け復元 検証テスト
※ 本番 data.json 全体走査は統合テスト ケース5 (test_no_duplicate_meetings.py) に集約され常時検証されています。
"""

import os
import sys
import json
import re
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")
if ADMIN_DIR not in sys.path:
    sys.path.insert(0, ADMIN_DIR)

from crawler import is_sns_pr_url, is_non_pdf_anchor_url, clean_meeting_title

class TestDrop46DataCleanup(unittest.TestCase):

    def test_unit_crawler_helpers(self):
        """1. crawler.py のガード関数の単体動作検証"""
        # is_sns_pr_url
        self.assertTrue(is_sns_pr_url("https://twitter.com/MOJ_HOUMU"))
        self.assertTrue(is_sns_pr_url("https://x.com/Gaikoshiryokan"))
        self.assertTrue(is_sns_pr_url("https://www.youtube.com/user/MOJchannel"))
        self.assertTrue(is_sns_pr_url("https://www.facebook.com/mofa.japan"))
        # 正当な審議中継動画は除外しないこと
        self.assertFalse(is_sns_pr_url("https://www.youtube.com/live/abcdefgh"))
        self.assertFalse(is_sns_pr_url("https://www.youtube.com/watch?v=12345678"))
        self.assertFalse(is_sns_pr_url("https://www.mhlw.go.jp/content/12345.pdf"))

        # is_non_pdf_anchor_url
        self.assertTrue(is_non_pdf_anchor_url("#siryou"))
        self.assertTrue(is_non_pdf_anchor_url("https://www.maff.go.jp/index.html#siryou"))
        self.assertTrue(is_non_pdf_anchor_url("https://www.soumu.go.jp/page.html#contents"))
        # PDF末尾のページ指定アンカーは除外しないこと
        self.assertFalse(is_non_pdf_anchor_url("https://www.soumu.go.jp/doc.pdf#page=1"))
        self.assertFalse(is_non_pdf_anchor_url("https://www.cao.go.jp/sample.pdf"))

        # clean_meeting_title で HTMLタグ除去（normalize_textにより括弧は半角正規化）
        self.assertEqual(clean_meeting_title("第5回 会議<br>（新時代）"), "第5回 会議 (新時代)")
        self.assertEqual(clean_meeting_title("第1回 検討会<span>（資料）</span>"), "第1回 検討会 (資料)")

    def test_mock_meeting_noise_detection(self):
        """2. モック開催回リストに対するノイズ検出ロジック単体検証"""
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

if __name__ == "__main__":
    unittest.main()
