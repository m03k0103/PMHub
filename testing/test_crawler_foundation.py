#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
クローラー基盤の重大バグ修正・誤判定防止・正規化 単体テストスイート (test_crawler_foundation.py)
- CR-1: clean_html_for_dates のスキップリンク誤認識遮断と本文保護
- CR-2: _sort_subpage_urls_by_recency および _is_parent_or_nav_url による最新優先・親一覧除外
- CR-4: GENERIC_TITLE_KEYWORDS 拡充と extract_page_title の汎用小見出しスキップ
- CR-18〜CR-20: safe_emit_log 例外保護、共通ナビ・組織常設資料除外ガード
- CR-46: normalize_text の康煕部首・CJK部首補助・全角英数正規化
"""

import unittest
import sys
import os
import io
from bs4 import BeautifulSoup

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))
from utils import setup_win32_utf8
setup_win32_utf8()

from crawler import (
    is_preliminary_notice_page,
    clean_html_for_dates,
    extract_clean_dates_from_html,
    _sort_subpage_urls_by_recency,
    _is_parent_or_nav_url,
    extract_page_title,
    GENERIC_TITLE_KEYWORDS,
    safe_emit_log,
    extract_actual_subpage_links,
    normalize_text
)


class TestCrawlerFoundation(unittest.TestCase):
    """クローラー基盤改善・正規化・ナビ除外ロジックの単体テスト"""

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

    def test_cr18_emit_stdout_safety(self):
        """CR-18: stdout が OSError や UnicodeEncodeError を投げても safe_emit_log() が例外を上位へ伝播させないこと"""
        class BrokenStdout(io.StringIO):
            def write(self, s):
                raise OSError(22, "Invalid argument")

        orig_stdout = sys.stdout
        try:
            sys.stdout = BrokenStdout()
            safe_emit_log("テスト出力 📦 絵文字含む")
        finally:
            sys.stdout = orig_stdout

    def test_cr19_common_nav_exclusion(self):
        """CR-19: 共通ナビ・広報リンク（施策紹介、オンライン利用率引上げ等）がサブページ候補から確実に除外されること"""
        html = """
        <html><body>
          <a href="/shisaku/123.html">施策紹介</a>
          <a href="/online/456.html">オンライン利用率引上げ</a>
          <a href="/links/789.html">関連リンク</a>
          <a href="/pr/pamphlet.html">パンフレット</a>
          <a href="/meeting/session/001.html">第1回 委員会</a>
        </body></html>
        """
        base_url = "https://www.mhlw.go.jp/stf/shingi/test.html"
        candidates = extract_actual_subpage_links(html, base_url)

        self.assertNotIn("https://www.mhlw.go.jp/shisaku/123.html", candidates)
        self.assertNotIn("https://www.mhlw.go.jp/online/456.html", candidates)
        self.assertNotIn("https://www.mhlw.go.jp/links/789.html", candidates)
        self.assertNotIn("https://www.mhlw.go.jp/pr/pamphlet.html", candidates)
        self.assertIn("https://www.mhlw.go.jp/meeting/session/001.html", candidates)

    def test_cr20_organization_doc_exclusion(self):
        """CR-20: 組織常設資料（設置要綱、委員名簿等）が開催回サブページとして抽出されないこと"""
        html = """
        <html><body>
          <a href="/about/youkou.html">設置要綱</a>
          <a href="/about/meibo.html">委員名簿</a>
          <a href="/about/kitei.html">運営規程</a>
          <a href="/meeting/dai2kai.html">第2回 会議</a>
        </body></html>
        """
        base_url = "https://www.cas.go.jp/jp/seisaku/test/index.html"
        candidates = extract_actual_subpage_links(html, base_url)

        self.assertNotIn("https://www.cas.go.jp/about/youkou.html", candidates)
        self.assertNotIn("https://www.cas.go.jp/about/meibo.html", candidates)
        self.assertNotIn("https://www.cas.go.jp/about/kitei.html", candidates)
        self.assertIn("https://www.cas.go.jp/meeting/dai2kai.html", candidates)

    def test_cr46_normalize_text_kangxi_and_supplements(self):
        """CR-46: 康煕部首およびCJK部首補助・全角英数が通常の標準文字へ正しく変換されること"""
        kangxi_samples = {
            '⼈⼯知能': '人工知能',
            '⽂化審議会': '文化審議会',
            '１２⽉２７⽇': '12月27日',
            '⾷品安全': '食品安全',
            '地域課題解決⽀援': '地域課題解決支援',
            '在り⽅': '在り方',
            '⾒直し': '見直し',
            '動物⽤医薬品': '動物用医薬品',
            '再⽣医療': '再生医療',
            '⾻⼦': '骨子',
            '意⾒募集': '意見募集',
            '中期⽬標': '中期目標',
        }
        for bad_str, expected in kangxi_samples.items():
            normalized = normalize_text(bad_str)
            self.assertEqual(normalized, expected, f"康煕部首 '{bad_str}' が '{expected}' に正規化されませんでした (結果: '{normalized}')")

        cjk_supp = '国⺠の健康の増進'
        self.assertEqual(normalize_text(cjk_supp), '国民の健康の増進')

        fullwidth_samples = {
            'ＡＩ戦略本部': 'AI戦略本部',
            'ＷＧ第１回': 'WG第1回',
            '（ＰＤＦ／１００ＫＢ）': '(PDF/100KB)',
        }
        for bad_str, expected in fullwidth_samples.items():
            self.assertEqual(normalize_text(bad_str), expected)

    def test_notice_and_correction_page_exclusion(self):
        """資料訂正告知および単独報告書公表ページの除外判定検証"""
        # 訂正告知・正誤表（除外されるべき）
        self.assertTrue(is_preliminary_notice_page(
            "https://www.mof.go.jp/sample/material/20260212164807.html",
            "「関税・外国為替等審議会 外国為替等分科会 資料(令和7年12月12日開催)」を一部訂正しました"
        ))
        self.assertTrue(is_preliminary_notice_page(
            "https://www.example.go.jp/notice.html",
            "配付資料の一部訂正について"
        ))
        # 報告書公表の報道発表（回次なし・除外されるべき）
        self.assertTrue(is_preliminary_notice_page(
            "https://www.fsa.go.jp/news/22/singi/20101217-6.html",
            "「「金融庁・開示制度ワーキング・グループ報告」～ 英文開示の範囲拡大について ～ 」の公表について"
        ))
        # 正規の開催回（除外されてはならない）
        self.assertFalse(is_preliminary_notice_page(
            "https://www.cao.go.jp/sample/014/index.html",
            "第14回 人工知能(AI)技術の利用と消費者問題に関する専門調査会"
        ))


if __name__ == "__main__":
    unittest.main()
