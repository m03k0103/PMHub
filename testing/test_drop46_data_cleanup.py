#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 46: 緊急データクリーンアップ & ノイズ配付資料・UI操作リンク完全排除・文字化け復元 検証テスト

【検証内容】
1. javascript: リンクが配付資料URLに一切存在しないこと (0件)
2. SNS広報リンク (twitter, x, facebook, instagram, youtubeチャンネル等) が配付資料URLに一切存在しないこと (0件)
3. 非PDFアンカーリンク (#siryou, #contents 等) が配付資料URLに一切存在しないこと (0件)
4. mic-nenkin_kiroku_daisansha の配付資料に文字化け（\\u0000-\\u001f, 不正シーケンス等）が存在しないこと (0件)
5. 会議体 cao-233 の配付資料タイトルが「答申」「答申（参考資料）」に正規化されていること
6. 会議名（meeting.name）に <br> 等のHTMLタグが存在しないこと (0件)
7. 同一開催回内（meeting.materials）で URL 重複が存在しないこと (0件)
8. crawler.py の is_sns_pr_url, is_non_pdf_anchor_url, clean_meeting_title 単体動作確認
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
from utils import load_data_json

class TestDrop46DataCleanup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        data_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        cls.data = load_data_json(data_path)
        cls.meetings = cls.data.get("meetings", [])

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

    def test_no_javascript_urls(self):
        """2. docs/data.json の配付資料に javascript: リンクが0件であること"""
        js_materials = []
        for m in self.meetings:
            for mat in m.get("materials", []):
                u = mat.get("url", "")
                if u.startswith("javascript:"):
                    js_materials.append((m["id"], mat.get("name"), u))
        self.assertEqual(len(js_materials), 0, f"javascript: リンクが残存しています: {js_materials}")

    def test_no_sns_pr_urls(self):
        """3. docs/data.json の配付資料に SNS広報リンクが0件であること"""
        sns_materials = []
        for m in self.meetings:
            for mat in m.get("materials", []):
                u = mat.get("url", "")
                if is_sns_pr_url(u):
                    sns_materials.append((m["id"], mat.get("name"), u))
        self.assertEqual(len(sns_materials), 0, f"SNS広報リンクが残存しています: {sns_materials}")

    def test_no_non_pdf_anchor_urls(self):
        """4. docs/data.json の配付資料に 非PDFアンカーリンクが0件であること"""
        anchor_materials = []
        for m in self.meetings:
            for mat in m.get("materials", []):
                u = mat.get("url", "")
                if is_non_pdf_anchor_url(u):
                    anchor_materials.append((m["id"], mat.get("name"), u))
        self.assertEqual(len(anchor_materials), 0, f"非PDFアンカーリンクが残存しています: {anchor_materials}")

    def test_mojibake_restoration(self):
        """5. mic-nenkin_kiroku_daisansha の文字化けが完全に修復されていること"""
        nenkin_meetings = [m for m in self.meetings if m.get("councilId") == "mic-nenkin_kiroku_daisansha"]
        self.assertGreater(len(nenkin_meetings), 0)
        for m in nenkin_meetings:
            for mat in m.get("materials", []):
                name = mat.get("name", "")
                self.assertNotIn("\x00", name)
                self.assertNotIn("\ufffd", name)
                self.assertFalse(re.search(r'[\x00-\x1f]', name), f"制御文字・文字化けが残存: {name}")
                if mat.get("url", "").endswith("000222335.pdf"):
                    self.assertEqual(name, "年金記録に係る申し立てに対するあっせんに当たっての基本方針")
                if mat.get("url", "").endswith("000302818.pdf"):
                    self.assertEqual(name, "委員名簿")

    def test_cao_print_buttons_fixed(self):
        """6. cao-233 の配付資料名が「答申」「答申（参考資料）」に正規化されていること"""
        cao_meetings = [m for m in self.meetings if m.get("councilId") == "cao-233"]
        self.assertGreater(len(cao_meetings), 0)
        found_toushin = False
        found_sankou = False
        for m in cao_meetings:
            for mat in m.get("materials", []):
                name = mat.get("name", "")
                self.assertNotIn("印刷する", name)
                if mat.get("url", "").endswith("toushin.pdf"):
                    self.assertEqual(name, "答申")
                    found_toushin = True
                if mat.get("url", "").endswith("toushin_sankou.pdf"):
                    self.assertEqual(name, "答申（参考資料）")
                    found_sankou = True
        self.assertTrue(found_toushin)
        self.assertTrue(found_sankou)

    def test_no_html_tags_in_titles(self):
        """7. docs/data.json の会議名に <br> 等のHTMLタグが0件であること"""
        tag_titles = []
        for m in self.meetings:
            m_name = m.get("name", "")
            if "<br" in m_name.lower() or "<span" in m_name.lower():
                tag_titles.append((m["id"], m_name))
        self.assertEqual(len(tag_titles), 0, f"HTMLタグを含む会議タイトルが残存しています: {tag_titles}")

    def test_no_intra_meeting_duplicate_materials(self):
        """8. 同一開催回内で重複する資料URLが0件であること"""
        dup_cases = []
        for m in self.meetings:
            seen = set()
            for mat in m.get("materials", []):
                u = mat.get("url", "").strip()
                if not u or u == "#":
                    continue
                if u in seen:
                    dup_cases.append((m["id"], u))
                seen.add(u)
        self.assertEqual(len(dup_cases), 0, f"同一開催回内で重複する資料URLが存在します ({len(dup_cases)}件): {dup_cases[:5]}")

if __name__ == "__main__":
    unittest.main()
