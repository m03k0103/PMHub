#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フェーズ J: クローラー基盤の重大バグ修正・誤判定防止 単体テストスイート
- CR-1: clean_html_for_dates のスキップリンク誤認識遮断と本文保護
- CR-2: _sort_subpage_urls_by_recency および _is_parent_or_nav_url による最新優先・親一覧除外
- CR-4: GENERIC_TITLE_KEYWORDS 拡充と extract_page_title の汎用小見出しスキップ
"""

import unittest
import sys
import os
from bs4 import BeautifulSoup

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))

from crawler import (
    clean_html_for_dates,
    extract_clean_dates_from_html,
    _sort_subpage_urls_by_recency,
    _is_parent_or_nav_url,
    extract_page_title,
    GENERIC_TITLE_KEYWORDS
)


class TestCrawlerFoundationPhaseJ(unittest.TestCase):
    """フェーズ J で実装された基盤改善ロジックの単体テスト"""

    def test_cr1_clean_html_for_dates_preserves_body_with_skiplinks(self):
        """CR-1: スキップリンクが存在しても本文が破棄されず、日付が正常に抽出されること"""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>総務省｜地方制度調査会</title></head>
        <body>
            <a id="jumpToContents" href="#contents">本文へ移動</a>
            <a id="jumpToNavi" href="#navi">ナビゲーションへ移動</a>
            <div id="header">
                <h1>総務省ポータル</h1>
            </div>
            <div id="main_contents" class="contentsBody">
                <h2>第33次地方制度調査会総会</h2>
                <p>開催日: 2026年9月17日（木曜日）</p>
                <p>次回開催予定: 2026年10月20日</p>
                <p>過去開催: 令和5年12月21日</p>
            </div>
            <div id="footer">
                <p>Copyright © Ministry of Internal Affairs and Communications</p>
            </div>
        </body>
        </html>
        """
        cleaned = clean_html_for_dates(sample_html)
        self.assertNotIn("jumpToContents", cleaned)
        self.assertIn("第33次地方制度調査会総会", cleaned)

        # 日付抽出テスト
        dates = extract_clean_dates_from_html(sample_html)
        self.assertIn("2026年9月17日", dates)
        self.assertIn("2026年10月20日", dates)
        self.assertIn("令和5年12月21日", dates)

    def test_cr2_sort_subpage_urls_by_recency(self):
        """CR-2: URL 内の数字（回次・年度・番号）を元に降順（最新優先）でソートされること"""
        urls = [
            "https://www.meti.go.jp/shingikai/energy/001.html",
            "https://www.meti.go.jp/shingikai/energy/025.html",
            "https://www.meti.go.jp/shingikai/energy/003.html",
            "https://www.meti.go.jp/shingikai/energy/010.html",
        ]
        sorted_urls = _sort_subpage_urls_by_recency(urls)
        expected = [
            "https://www.meti.go.jp/shingikai/energy/025.html",
            "https://www.meti.go.jp/shingikai/energy/010.html",
            "https://www.meti.go.jp/shingikai/energy/003.html",
            "https://www.meti.go.jp/shingikai/energy/001.html",
        ]
        self.assertEqual(sorted_urls, expected)

    def test_cr2_is_parent_or_nav_url(self):
        """CR-2: ターゲットURLの上位一覧や親インデックスが除外判定されること"""
        target_url = "https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/index.html"

        # 親ディレクトリのインデックスや共通トップは除外対象
        self.assertTrue(_is_parent_or_nav_url("https://www.meti.go.jp/shingikai/index.html", target_url))
        self.assertTrue(_is_parent_or_nav_url("https://www.meti.go.jp/shingikai/energy_environment/index.html", target_url))
        self.assertTrue(_is_parent_or_nav_url(target_url, target_url))

        # 個別開催回（サブページ）は除外されないこと
        self.assertFalse(_is_parent_or_nav_url("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/001.html", target_url))
        self.assertFalse(_is_parent_or_nav_url("https://www.meti.go.jp/shingikai/energy_environment/plastic_bottle/002.html", target_url))

    def test_cr4_extract_page_title_skips_generic_subheadings(self):
        """CR-4: <h3>開催日</h3> などの小見出しをスキップし、本物の会議名見出しタグを取得できること"""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>プラスチック製容器包装検討会 開催日</title></head>
        <body>
            <div id="contents">
                <h3>開催日</h3>
                <p>2026年9月1日</p>
                <h2>第1回 プラスチック製容器包装に関する検討会</h2>
                <h3>配付資料一覧</h3>
                <ul>
                    <li><a href="shiryo1.pdf">資料1</a></li>
                </ul>
            </div>
        </body>
        </html>
        """
        soup = BeautifulSoup(sample_html, 'html.parser')
        title = extract_page_title(soup)
        self.assertEqual(title, "第1回 プラスチック製容器包装に関する検討会")

    def test_cr4_generic_title_keywords_expansion(self):
        """CR-4: GENERIC_TITLE_KEYWORDS に小見出しキーワードが含まれていること"""
        required_keywords = ['開催日', '開催日時', '開催期間', '議事次第等', '資料一覧', '配付資料等', '配布資料等']
        for kw in required_keywords:
            self.assertIn(kw, GENERIC_TITLE_KEYWORDS)


if __name__ == "__main__":
    unittest.main()
