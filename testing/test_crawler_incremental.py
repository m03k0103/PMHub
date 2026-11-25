#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スマート差分探索エンジン・並行レートリミット・中断制御 単体テストスイート (test_crawler_incremental.py)
- CR-10: _normalize_url_for_comparison のURL正規化ロジック
- CR-10 / CR-23: _filter_incremental_subpages の既登録スキップ・最新更新確認・未登録最大50件判定
- CR-26: ホスト単位並行巡回エンジン（スレッドセーフなレートリミット検証）
- CR-27: 中断耐性と安全チェックポイント保存（stop_event中断検証）
"""

import unittest
import sys
import os
import io
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch

# admin モジュールへのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "admin")))
from utils import setup_win32_utf8
setup_win32_utf8()

import crawler
from crawler import (
    _normalize_url_for_comparison,
    _filter_incremental_subpages,
    _sort_subpage_urls_by_recency,
    _rate_limit_host
)


class TestCrawlerIncremental(unittest.TestCase):
    """スマート差分探索エンジン・レートリミット・中断制御の単体テスト"""

    def test_normalize_url_for_comparison(self):
        """URLの末尾スラッシュ、フラグメント、スキームの差異が吸収されること"""
        url1 = "https://www.meti.go.jp/shingikai/energy/025.html"
        url2 = "http://www.meti.go.jp/shingikai/energy/025.html#section1"
        url3 = "https://www.meti.go.jp/shingikai/energy/025.html/"

        norm1 = _normalize_url_for_comparison(url1)
        norm2 = _normalize_url_for_comparison(url2)
        norm3 = _normalize_url_for_comparison(url3)

        self.assertEqual(norm1, "www.meti.go.jp/shingikai/energy/025.html")
        self.assertEqual(norm2, "www.meti.go.jp/shingikai/energy/025.html")
        self.assertEqual(norm3, "www.meti.go.jp/shingikai/energy/025.html")

        self.assertEqual(_normalize_url_for_comparison(""), "")
        self.assertEqual(_normalize_url_for_comparison(None), "")

    def test_filter_all_new_subpages(self):
        """すべて未登録の場合、最大 max_unvisited（50件）まで未登録として採択されること"""
        candidates = [
            f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html"
            for i in range(1, 61)
        ]
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)
        existing = set()

        targets, stats = _filter_incremental_subpages(sorted_candidates, existing, max_unvisited=50, max_recent=2)

        self.assertEqual(len(targets), 50)
        self.assertEqual(stats["unvisited"], 50)
        self.assertEqual(stats["recent_update"], 0)
        self.assertEqual(stats["skipped_known"], 0)
        self.assertEqual(stats["total_targets"], 50)
        self.assertEqual(targets[0], "https://www.meti.go.jp/shingikai/energy/060.html")

    def test_filter_all_known_subpages(self):
        """すべて既登録の場合、最新2件のみ更新確認に選ばれ、残り全件がスキップされること"""
        candidates = [
            f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html"
            for i in range(1, 11)
        ]
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)
        existing = set(candidates)

        targets, stats = _filter_incremental_subpages(sorted_candidates, existing, max_unvisited=50, max_recent=2)

        self.assertEqual(len(targets), 2)
        self.assertEqual(stats["unvisited"], 0)
        self.assertEqual(stats["recent_update"], 2)
        self.assertEqual(stats["skipped_known"], 8)
        self.assertEqual(stats["total_targets"], 2)
        self.assertIn("https://www.meti.go.jp/shingikai/energy/010.html", targets)
        self.assertIn("https://www.meti.go.jp/shingikai/energy/009.html", targets)
        self.assertNotIn("https://www.meti.go.jp/shingikai/energy/008.html", targets)

    def test_filter_mixed_new_and_known_subpages(self):
        """新規と既登録が混在する場合、新規分＋最新2件が選ばれ、既登録過去回がスキップされること"""
        known = [f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html" for i in range(1, 11)]
        new_items = [f"https://www.meti.go.jp/shingikai/energy/{i:03d}.html" for i in range(11, 14)]
        candidates = known + new_items
        sorted_candidates = _sort_subpage_urls_by_recency(candidates)

        targets, stats = _filter_incremental_subpages(sorted_candidates, set(known), max_unvisited=50, max_recent=2)

        self.assertEqual(len(targets), 5)
        self.assertEqual(stats["unvisited"], 3)
        self.assertEqual(stats["recent_update"], 2)
        self.assertEqual(stats["skipped_known"], 8)
        self.assertEqual(stats["total_targets"], 5)

        expected = [
            "https://www.meti.go.jp/shingikai/energy/013.html",
            "https://www.meti.go.jp/shingikai/energy/012.html",
            "https://www.meti.go.jp/shingikai/energy/011.html",
            "https://www.meti.go.jp/shingikai/energy/010.html",
            "https://www.meti.go.jp/shingikai/energy/009.html"
        ]
        self.assertEqual(targets, expected)

    def test_filter_empty_existing_urls(self):
        """existing_urls が None または空の場合、安全にフォールバックすること"""
        candidates = ["https://www.meti.go.jp/001.html", "https://www.meti.go.jp/002.html"]
        targets, stats = _filter_incremental_subpages(candidates, None)
        self.assertEqual(len(targets), 2)
        self.assertEqual(stats["unvisited"], 2)
        self.assertEqual(stats["skipped_known"], 0)

    def test_cr23_incremental_default_latest_only(self):
        """CR-23: デフォルト（max_recent=1）で最新1件のみ更新確認され、過去回は再検査ゼロ化されること"""
        candidates = [
            "https://www.example.go.jp/meeting/003.html",
            "https://www.example.go.jp/meeting/002.html",
            "https://www.example.go.jp/meeting/001.html",
            "https://www.example.go.jp/meeting/000.html",
        ]
        known_urls = {
            "https://www.example.go.jp/meeting/002.html",
            "https://www.example.go.jp/meeting/001.html",
            "https://www.example.go.jp/meeting/000.html"
        }

        target_urls, stats = _filter_incremental_subpages(candidates, known_urls, max_recent=1, full_check=False)
        self.assertEqual(stats["unvisited"], 1)
        self.assertEqual(stats["recent_update"], 1)
        self.assertEqual(stats["skipped_known"], 2)
        self.assertIn("https://www.example.go.jp/meeting/003.html", target_urls)
        self.assertIn("https://www.example.go.jp/meeting/002.html", target_urls)
        self.assertNotIn("https://www.example.go.jp/meeting/001.html", target_urls)
        self.assertNotIn("https://www.example.go.jp/meeting/000.html", target_urls)

        target_urls_full, stats_full = _filter_incremental_subpages(candidates, known_urls, full_check=True)
        self.assertEqual(stats_full["unvisited"], 1)
        self.assertEqual(stats_full["recent_update"], 3)
        self.assertEqual(stats_full["skipped_known"], 0)
        self.assertEqual(len(target_urls_full), 4)

        target_urls_zero, stats_zero = _filter_incremental_subpages(candidates, known_urls, max_recent=0, full_check=False)
        self.assertEqual(stats_zero["unvisited"], 1)
        self.assertEqual(stats_zero["recent_update"], 0)
        self.assertEqual(stats_zero["skipped_known"], 3)
        self.assertEqual(len(target_urls_zero), 1)

    def test_cr26_thread_safe_rate_limiting(self):
        """CR-26: マルチスレッド下でも同一ホストへのアクセス間隔が _MIN_HOST_INTERVAL 以上保たれること"""
        test_host = "test.domain.go.jp"
        call_times = []
        lock = threading.Lock()

        orig_interval = crawler._MIN_HOST_INTERVAL
        crawler._MIN_HOST_INTERVAL = 0.05
        try:
            def worker():
                _rate_limit_host(test_host)
                with lock:
                    call_times.append(time.time())

            threads = [threading.Thread(target=worker) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            call_times.sort()
            self.assertEqual(len(call_times), 3)
            for i in range(len(call_times) - 1):
                interval = call_times[i + 1] - call_times[i]
                self.assertGreaterEqual(interval, crawler._MIN_HOST_INTERVAL - 0.015, f"間隔が短すぎます: {interval:.3f}s")
        finally:
            crawler._MIN_HOST_INTERVAL = orig_interval

    def test_cr27_stop_event_interruption(self):
        """CR-27: stop_event がセットされた場合、直ちにクローラーが安全中断すること"""
        stop_event = threading.Event()
        stop_event.set()

        mock_targets = [{"id": "test-c", "name": "テスト会議体", "ministry": "CAS", "officialUrl": "https://example.com"}]
        with patch('crawler.load_councils_from_data_json', return_value=mock_targets), \
             patch('crawler.save_data_json_with_backup', return_value=True), \
             patch('sys.stdout', new_callable=io.StringIO):
            stats = crawler.run_meeting_crawler(
                stop_event=stop_event,
                workers=1,
                recent_years=2
            )
        self.assertTrue(stats.get("stopped"), "stop_event により stopped=True が返却されること")
        self.assertEqual(stats["processed_councils"], 0, "即時停止のため処理件数が0であること")



    def test_drop133_extract_news_items_since_date_filter(self):
        """Drop 133: 新着情報ポータル走査で since_date より古い記事が除外され、新しい記事のみ抽出されること"""
        mock_html = """
        <html><body>
          <ul>
            <li><time datetime="2026-11-05">2026年11月5日</time><a href="/news/new1.html">第10回 デジタル政策検討会 開催案内</a></li>
            <li><time datetime="2026-11-02">2026年11月2日</time><a href="/news/old1.html">第9回 デジタル政策検討会 配布資料</a></li>
            <li><time datetime="2026-10-15">2026年10月15日</time><a href="/news/old2.html">第8回 デジタル政策検討会 議事録</a></li>
            <li><span>2026年11月6日</span><a href="/news/new2.html">AI推進委員会（第3回）の開催について</a></li>
          </ul>
        </body></html>
        """
        # since_date なし: 全4件
        all_items = crawler.extract_news_items_from_html(mock_html, "https://example.com/news/", "DIGITAL", "general")
        self.assertEqual(len(all_items), 4)

        # since_date = '2026/11/04': 11/05 と 11/06 の2件のみ抽出
        filtered_items = crawler.extract_news_items_from_html(
            mock_html, "https://example.com/news/", "DIGITAL", "general", since_date="2026/11/04"
        )
        self.assertEqual(len(filtered_items), 2)
        urls = [it["url"] for it in filtered_items]
        self.assertIn("https://example.com/news/new1.html", urls)
        self.assertIn("https://example.com/news/new2.html", urls)
        self.assertNotIn("https://example.com/news/old1.html", urls)
        self.assertNotIn("https://example.com/news/old2.html", urls)

    def test_drop133_curl_bin_resolution(self):
        """Drop 133: _fetch_with_curl でクロスプラットフォーム対応の curl バイナリ解決が行われること"""
        import shutil
        expected_bin = shutil.which('curl') or shutil.which('curl.exe') or 'curl'
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = b""
            crawler._fetch_with_curl("https://example.com/test", timeout=5)
            self.assertTrue(mock_run.called)
            cmd_called = mock_run.call_args[0][0]
            self.assertEqual(cmd_called[0], expected_bin)



    def test_drop134_extract_news_items_year_completion(self):
        """Drop 134: 月日のみ表記の年補完、先行見出し日付抽出、日付未特定常設リンクの安全除外"""
        # 1. CAO型: テーブル月日表記 (11月5日 / 10月25日)
        cao_html = """
        <table>
          <tr><td class="date">11月5日</td><td><a href="/news/cao1.html">消費者委員会第100回開催について</a></td></tr>
          <tr><td class="date">10月25日</td><td><a href="/news/cao2.html">食品安全委員会第50回開催について</a></td></tr>
        </table>
        """
        cao_items = crawler.extract_news_items_from_html(
            cao_html, "https://www.cao.go.jp/press/", "CAO", "news_feed", since_date="2026/11/02"
        )
        self.assertEqual(len(cao_items), 1)
        self.assertEqual(cao_items[0]["url"], "https://www.cao.go.jp/news/cao1.html")
        self.assertEqual(cao_items[0]["date"], "2026/11/05")

        # 2. MHLW型: 先行見出しに日付があるリスト構造 (h2 掲載日)
        mhlw_html = """
        <h2>2026年11月6日掲載</h2>
        <ul>
          <li><a href="/news/mhlw1.html">第42回労働政策審議会労働政策基本部会を開催します</a></li>
        </ul>
        <h2>2026年10月15日掲載</h2>
        <ul>
          <li><a href="/news/mhlw2.html">第41回労働政策審議会労働政策基本部会を開催します</a></li>
        </ul>
        """
        mhlw_items = crawler.extract_news_items_from_html(
            mhlw_html, "https://www.mhlw.go.jp/stf/new-info/", "MHLW", "news_feed", since_date="2026/11/02"
        )
        self.assertEqual(len(mhlw_items), 1)
        self.assertEqual(mhlw_items[0]["url"], "https://www.mhlw.go.jp/news/mhlw1.html")
        self.assertEqual(mhlw_items[0]["date"], "2026/11/06")

        # 3. MOJ型: 日付が一切存在しない常設リンク集・目次
        moj_html = """
        <ul>
          <li><a href="/info/moj1.html">法制審議会について（常設案内）</a></li>
          <li><a href="/info/moj2.html">法務省検討会一覧</a></li>
        </ul>
        """
        # since_date あり: 日付未特定リンクは常設とみなしてスキップ（0件）
        moj_items_filtered = crawler.extract_news_items_from_html(
            moj_html, "https://www.moj.go.jp/list_info.html", "MOJ", "news_feed", since_date="2026/11/02"
        )
        self.assertEqual(len(moj_items_filtered), 0)

        # since_date なし (全期間探索): 抽出を許容
        moj_items_all = crawler.extract_news_items_from_html(
            moj_html, "https://www.moj.go.jp/list_info.html", "MOJ", "news_feed", since_date=None
        )
        self.assertEqual(len(moj_items_all), 2)

    def test_extract_news_items_sibling_and_prior_date_containers(self):
        """Drop 146: FSA型兄弟pタグ・MOE型summary・MAFF型先行日付p抽出およびfooterリンク除外"""
        # 1. FSA型: <li>内に p.news-date と p.news-title が兄弟配置
        fsa_html = """
        <html><body>
          <ul class="news-list">
            <li>
              <p class="news-date">2026年11月18日</p>
              <p class="news-title"><a href="/singi/disclosure_wg/20261118.html">金融審議会「ディスクロージャーワーキング・グループ」(第7回)議事次第</a></p>
            </li>
            <li>
              <p class="news-date">2026年10月20日</p>
              <p class="news-title"><a href="/singi/disclosure_wg/20261020.html">金融審議会「ディスクロージャーワーキング・グループ」(第6回)議事次第</a></p>
            </li>
          </ul>
          <footer><a href="/singi/policy_council.html">審議会等一覧</a></footer>
        </body></html>
        """
        fsa_items = crawler.extract_news_items_from_html(
            fsa_html, "https://www.fsa.go.jp/news/r8_news_menu.html", "FSA", "deep_portal", since_date="2026/11/01"
        )
        self.assertEqual(len(fsa_items), 1)
        self.assertEqual(fsa_items[0]["date"], "2026/11/18")
        self.assertEqual(fsa_items[0]["url"], "https://www.fsa.go.jp/singi/disclosure_wg/20261118.html")

        # 2. MOE型: <details><summary>日付</summary><ul><li><a>...</a></li></ul></details>
        moe_html = """
        <html><body>
          <details>
            <summary>2026年11月20日</summary>
            <ul><li><a href="/press/press_05900.html">第12回 中央環境審議会開催について</a></li></ul>
          </details>
          <details>
            <summary>2026年10月10日</summary>
            <ul><li><a href="/press/press_05800.html">第11回 中央環境審議会開催について</a></li></ul>
          </details>
        </body></html>
        """
        moe_items = crawler.extract_news_items_from_html(
            moe_html, "https://www.env.go.jp/press/index.html", "MOE", "news_feed", since_date="2026/11/01"
        )
        self.assertEqual(len(moe_items), 1)
        self.assertEqual(moe_items[0]["date"], "2026/11/20")
        self.assertEqual(moe_items[0]["url"], "https://www.env.go.jp/press/press_05900.html")

        # 3. MAFF/RINYA/JFA型: <p class="list_item_date">日付</p><ul><li><a>...</a></li></ul>
        maff_html = """
        <html><body>
          <p class="list_item_date">令和8年11月16日</p>
          <ul><li><a href="/j/press/261116.html">食料・農業・農村政策審議会第20回検討会の開催について</a></li></ul>
          <p class="list_item_date">令和8年10月28日</p>
          <ul><li><a href="/j/press/261028.html">食料・農業・農村政策審議会第19回検討会の開催について</a></li></ul>
          <nav><a href="/j/press/nav_shingi.html">審議会会議録</a></nav>
        </body></html>
        """
        maff_items = crawler.extract_news_items_from_html(
            maff_html, "https://www.maff.go.jp/j/press/index.html", "MAFF", "news_feed", since_date="2026/11/01"
        )
        self.assertEqual(len(maff_items), 1)
        self.assertEqual(maff_items[0]["date"], "2026/11/16")
        self.assertEqual(maff_items[0]["url"], "https://www.maff.go.jp/j/press/261116.html")

    def test_resolve_news_portal_urls_dynamic_year_month(self):
        """Drop 146: deep_portal が現在年月基準で動的解決され不要ゴミURLが混入しないこと"""
        from datetime import datetime as real_datetime

        class _FixedDatetime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return real_datetime(2026, 11, 21, 9, 0, 0)

        portal_htmls = {
            "https://www.fsa.go.jp/news/": """
                <a href="/news/r8_news_menu.html">令和8事務年度</a>
                <a href="/news/r7_news_menu.html">令和7事務年度</a>
                <a href="/news/r8/202609/260915.html#sp_summary">関連まとめ</a>
            """,
            "https://www.mof.go.jp/public_relations/whats_new/index.html": """
                <a href="/public_relations/whats_new/202611.html">2026年11月</a>
                <a href="/public_relations/whats_new/202610.html">2026年10月</a>
                <a href="/public_relations/whats_new/202609.html">2026年9月</a>
            """,
            "https://www.nra.go.jp/news/index.html": """
                <a href="/news/202610.html">2026年10月</a>
                <a href="/news/202609.html">2026年9月</a>
            """,
            "https://www.ppc.go.jp/news/press/": """
                <a href="/news/press/2026">令和8年</a>
                <a href="/news/press/2025">令和7年</a>
            """,
        }

        with patch('crawler.datetime', _FixedDatetime), patch('crawler.fetch_url', side_effect=lambda u, timeout=10: portal_htmls.get(u, "")):
            fsa_urls = crawler.resolve_news_portal_urls({
                "url": "https://www.fsa.go.jp/news/", "type": "deep_portal", "subpage_pattern": r"r\d+_news_menu\.html"
            })
            self.assertEqual(fsa_urls, ["https://www.fsa.go.jp/news/r8_news_menu.html"])

            mof_urls = crawler.resolve_news_portal_urls({
                "url": "https://www.mof.go.jp/public_relations/whats_new/index.html", "type": "deep_portal", "subpage_pattern": r"whats_new/\d{6}\.html"
            })
            self.assertEqual(mof_urls, [
                "https://www.mof.go.jp/public_relations/whats_new/202611.html",
                "https://www.mof.go.jp/public_relations/whats_new/202610.html"
            ])

            nra_urls = crawler.resolve_news_portal_urls({
                "url": "https://www.nra.go.jp/news/index.html", "type": "deep_portal", "subpage_pattern": r"news/\d{6}\.html"
            })
            self.assertEqual(nra_urls, [
                "https://www.nra.go.jp/news/index.html",
                "https://www.nra.go.jp/news/202610.html"
            ])

            ppc_urls = crawler.resolve_news_portal_urls({
                "url": "https://www.ppc.go.jp/news/press/", "type": "deep_portal", "subpage_pattern": r"press/\d{4}"
            })
            self.assertEqual(ppc_urls, [
                "https://www.ppc.go.jp/news/press/",
                "https://www.ppc.go.jp/news/press/2026"
            ])

    def test_match_council_from_news_item_priority(self):
        """Drop 146: match_council_from_news_item の固有URLパス・鉤括弧完全一致・非廃止最長一致の優先検証"""
        c_old_closed = {
            "id": "fsa-kinyu_dai1_disclose_wg",
            "ministry": "FSA",
            "name": "金融分科会 第一部会 ディスクロージャーワーキング・グループ",
            "officialUrl": "https://www.fsa.go.jp/singi/singi_kinyu/base_gijiroku.html",
            "isClosed": True
        }
        c_active_wg = {
            "id": "fsa-kinyu_disclosure_wg",
            "ministry": "FSA",
            "name": "ディスクロージャーワーキング・グループ",
            "officialUrl": "https://www.fsa.go.jp/singi/singi_kinyu/disclosure_wg/disclosure_wg_index.html",
            "isClosed": False
        }
        c_parent_kaikei = {
            "id": "fsa-kigyou_kaikei_shingi",
            "ministry": "FSA",
            "name": "企業会計審議会",
            "officialUrl": "https://www.fsa.go.jp/singi/singi_kigyou/base_gijiroku.html",
            "isClosed": False
        }
        c_child_sustainability = {
            "id": "fsa-kigyou_sustainability_bukai",
            "ministry": "FSA",
            "name": "企業会計審議会サステナビリティ情報保証部会",
            "officialUrl": "https://www.fsa.go.jp/singi/singi_kigyou/sustainability_bukai/index.html",
            "isClosed": False
        }

        councils = [c_old_closed, c_active_wg, c_parent_kaikei, c_child_sustainability]
        councils_by_url = {c["officialUrl"].rstrip("/"): c for c in councils}
        councils_by_min = {"FSA": councils}

        # 1. 鉤括弧完全一致が廃止済みの部分包含より優先され、固有URLディレクトリ一致が働くこと
        matched1, reason1 = crawler.match_council_from_news_item(
            {
                "title": "金融審議会「ディスクロージャーワーキング・グループ」(第7回)の開催の公表",
                "url": "https://www.fsa.go.jp/news/r8/singi/20261118.html",
                "ministry": "FSA"
            },
            councils_by_url,
            councils_by_min
        )
        self.assertIsNotNone(matched1)
        self.assertEqual(matched1["id"], "fsa-kinyu_disclosure_wg")
        self.assertEqual(reason1, "BRACKET_NAME")

        # 2. 固有ディレクトリURLの配下は URL_PATH_MATCH が最優先されること
        matched2, reason2 = crawler.match_council_from_news_item(
            {
                "title": "第7回会議 議事次第",
                "url": "https://www.fsa.go.jp/singi/singi_kinyu/disclosure_wg/shiryou/20261118.html",
                "ministry": "FSA"
            },
            councils_by_url,
            councils_by_min
        )
        self.assertIsNotNone(matched2)
        self.assertEqual(matched2["id"], "fsa-kinyu_disclosure_wg")
        self.assertEqual(reason2, "URL_PATH_MATCH")

        # 3. 「第3回」を含む子部会名が親審議会へ誤マッチせず最長一致すること
        matched3, reason3 = crawler.match_council_from_news_item(
            {
                "title": "企業会計審議会第3回サステナビリティ情報保証部会の開催について",
                "url": "https://www.fsa.go.jp/news/r8/singi/20261119.html",
                "ministry": "FSA"
            },
            councils_by_url,
            councils_by_min
        )
        self.assertIsNotNone(matched3)
        self.assertEqual(matched3["id"], "fsa-kigyou_sustainability_bukai")
        self.assertEqual(reason3, "TEXT_CONTAINS")

    def test_drop149_tier_dedup_daily_weekly_monthly(self):
        """Drop 149: WeeklyはDaily対象を除外し、MonthlyはDaily・Weekly対象を除外すること"""
        now = datetime.now()
        fmt_date = lambda days_ago: (now - timedelta(days=days_ago)).strftime("%Y/%m/%d")
        fmt_ts = lambda days_ago: (now - timedelta(days=days_ago)).strftime("%Y/%m/%d %H:%M")

        mock_data = {
            "lastCrawlTime": fmt_ts(1),
            "crawlerConfig": {
                "dailyCouncilLastCrawlTime": {
                    "c-daily-recent": fmt_ts(2),
                    "c-daily-old": fmt_ts(10),
                    "c-daily-dormant": fmt_ts(3),
                }
            },
            "scrapingRules": {},
            "councils": [
                {"id": "c-daily-recent", "ministry": "FSA", "name": "Daily直近(map)", "officialUrl": "https://example.com/1"},
                {
                    "id": "c-daily-status",
                    "ministry": "MOF",
                    "name": "Daily直近(crawlStatus)",
                    "officialUrl": "https://example.com/2",
                    "crawlStatus": {"extractionMethod": "ministry_news", "lastAttempt": fmt_ts(5)}
                },
                {"id": "c-daily-old", "ministry": "METI", "name": "Daily8日超前", "officialUrl": "https://example.com/3"},
                {"id": "c-weekly-active", "ministry": "MHLW", "name": "Weekly通常アクティブ", "officialUrl": "https://example.com/4"},
                {"id": "c-weekly-zero", "ministry": "CAO", "name": "Weekly開催0件", "officialUrl": "https://example.com/5"},
                {"id": "c-dormant", "ministry": "MOJ", "name": "Monthly休眠(2年超未開催)", "officialUrl": "https://example.com/6"},
                {"id": "c-daily-dormant", "ministry": "MOD", "name": "Daily巡回済休眠", "officialUrl": "https://example.com/7"},
                {"id": "c-closed", "ministry": "MIC", "name": "廃止会議体", "officialUrl": "https://example.com/8", "isClosed": True},
            ],
            "meetings": [
                {"id": "m1", "councilId": "c-daily-recent", "date": fmt_date(30)},
                {"id": "m2", "councilId": "c-daily-status", "date": fmt_date(40)},
                {"id": "m3", "councilId": "c-daily-old", "date": fmt_date(50)},
                {"id": "m4", "councilId": "c-weekly-active", "date": fmt_date(180)},
                {"id": "m6", "councilId": "c-dormant", "date": fmt_date(900)},
                {"id": "m7", "councilId": "c-daily-dormant", "date": fmt_date(950)},
                {"id": "m8", "councilId": "c-closed", "date": fmt_date(10)},
            ],
        }

        daily_ids = crawler.get_daily_crawled_council_ids(mock_data, daily_window_days=7, ref_dt=now)
        self.assertEqual(daily_ids, {"c-daily-recent", "c-daily-status", "c-daily-dormant"})

        with patch('crawler.load_data_json', return_value=mock_data), \
             patch('crawler.get_rejected_identifiers', return_value=(set(), set(), set())), \
             patch('builtins.print'):
            weekly_ids = {c["id"] for c in crawler.load_councils_from_data_json(recent_years=2, include_closed=False)}
            monthly_ids = {c["id"] for c in crawler.load_councils_from_data_json(recent_years=0, include_closed=False)}
            all_ids = {c["id"] for c in crawler.load_councils_from_data_json(recent_years="all", include_closed=False)}
            weekly_incl_daily_ids = {c["id"] for c in crawler.load_councils_from_data_json(recent_years=2, include_closed=False, exclude_daily=False)}

        # WeeklyはDaily直近巡回済み3件と廃止会議体・休眠会議体を除外し、8日超前＋通常アクティブ＋0件のみ巡回
        self.assertEqual(weekly_ids, {"c-daily-old", "c-weekly-active", "c-weekly-zero"})
        # MonthlyはDaily対象3件とWeekly対象(直近2年・0件)をすべて除外し、休眠会議体のみ巡回
        self.assertEqual(monthly_ids, {"c-dormant"})
        # allモードは非廃止アクティブ全7件を返却
        self.assertEqual(len(all_ids), 7)
        self.assertNotIn("c-closed", all_ids)
        # 3階層の完全排他性と全アクティブ会議体カバー（Daily ∪ Weekly ∪ Monthly == All）
        self.assertEqual(daily_ids & weekly_ids, set())
        self.assertEqual(weekly_ids & monthly_ids, set())
        self.assertEqual(monthly_ids & daily_ids, set())
        self.assertEqual(daily_ids | weekly_ids | monthly_ids, all_ids)
        # exclude_daily=False 指定時は Weekly に Daily直近会議体も含まれる
        self.assertIn("c-daily-recent", weekly_incl_daily_ids)
        self.assertIn("c-daily-status", weekly_incl_daily_ids)

    def test_drop149_run_ministry_news_discovery_records_latest_daily_timestamp(self):
        """Drop 149: run_ministry_news_discovery が会議体ごとの最新Dailyクロール日時1件のみを上書き記録すること"""
        today_str = datetime.now().strftime("%Y/%m/%d")
        mock_data = {
            "lastCrawlTime": "2026/11/20 06:00",
            "crawlerConfig": {
                "dailyCouncilLastCrawlTime": {
                    "test-direct": "2026/11/01 06:00"
                }
            },
            "ministries": {"TEST": {"domains": ["example.com"], "newsPortals": [{"url": "https://example.com/news", "type": "news_feed"}]}},
            "scrapingRules": {},
            "councils": [
                {"id": "test-direct", "ministry": "TEST", "name": "直接抽出会議体", "officialUrl": "https://example.com/c1/index.html"},
                {"id": "test-pinpoint", "ministry": "TEST", "name": "ピンポイント会議体", "officialUrl": "https://example.com/c2/index.html"},
            ],
            "meetings": []
        }

        news_html = (
            f"<html><body><ul>"
            f"<li>{today_str} <a href='https://example.com/news/c1_art.html'>第5回 直接抽出会議体</a></li>"
            f"<li>{today_str} <a href='https://example.com/c2/index.html'>第2回 ピンポイント会議体</a></li>"
            f"</ul></body></html>"
        )
        article_html = (
            f"<html><head><title>第5回 直接抽出会議体</title></head><body>"
            f"<h1>第5回 直接抽出会議体</h1><p>開催日: {today_str}</p>"
            f"<a href='https://example.com/c1/doc1.pdf'>資料1</a></body></html>"
        )
        pinpoint_html = "<html><head><title>ピンポイント会議体</title></head><body><h1>ピンポイント会議体</h1></body></html>"

        def fake_fetch(url, **kwargs):
            if url == "https://example.com/news":
                return news_html
            if url == "https://example.com/news/c1_art.html":
                return article_html
            if url == "https://example.com/c2/index.html":
                return pinpoint_html
            return None

        saved_snapshots = []
        with patch('crawler.init_crawler_logfile', return_value=(None, None, "", "")), \
             patch('crawler.load_data_json', return_value=mock_data), \
             patch('crawler.save_data_json_with_backup', side_effect=lambda d, **kw: saved_snapshots.append(d) or True), \
             patch('crawler.load_ministry_and_host_configs_from_db'), \
             patch('crawler.MINISTRY_NEWS_PORTALS', {"TEST": [{"url": "https://example.com/news", "type": "news_feed"}]}), \
             patch('crawler.fetch_url', side_effect=fake_fetch), \
             patch('crawler.sync_new_meetings_from_crawl', return_value=0), \
             patch('crawler.execute_rule_retrieval', return_value={
                 "scrapedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "crawlResult": "success",
                 "resultReason": "取得テスト",
                 "extractionMethod": "rule",
                 "totalExtractedMaterials": 1,
                 "extractedDates": [today_str]
             }), \
             patch('sqlite3.connect', side_effect=RuntimeError("skip local db in unit test")), \
             patch('sys.stdout', new_callable=io.StringIO):
            crawler.run_ministry_news_discovery(ministry="TEST", skip_download=True)

        self.assertTrue(saved_snapshots)
        last_cfg = saved_snapshots[-1].get("crawlerConfig", {})
        daily_map = last_cfg.get("dailyCouncilLastCrawlTime", {})
        # Drop 150: 親ページ巡回を伴うピンポイント会議体のみ当日時刻で上書きされ、直接記事抽出は古いタイムスタンプのまま（Weeklyスキップ誤除外を防止）
        self.assertNotIn("test-direct", set(daily_map.keys()) - {"test-direct"} if daily_map["test-direct"].startswith("2026/11/01") else {"test-direct"})
        self.assertTrue(daily_map["test-direct"].startswith("2026/11/01"))
        self.assertIn("test-pinpoint", daily_map)
        self.assertIsInstance(daily_map["test-pinpoint"], str)
        self.assertTrue(daily_map["test-pinpoint"].startswith(today_str))
        c_direct = next(c for c in saved_snapshots[-1]["councils"] if c["id"] == "test-direct")
        self.assertEqual(c_direct.get("crawlStatus", {}).get("extractionMethod"), "ministry_news_direct")
        c_pin = next(c for c in saved_snapshots[-1]["councils"] if c["id"] == "test-pinpoint")
        self.assertEqual(c_pin.get("crawlStatus", {}).get("extractionMethod"), "rule")

    def test_zero_material_recent_meeting_revisited_in_incremental_crawl(self):
        """Drop 150: 直近90日以内の資料0件開催回URLは _build_known_meeting_urls から除外され、再巡回対象になること"""
        now = datetime.now()
        fmt_date = lambda days_ago: (now - timedelta(days=days_ago)).strftime("%Y/%m/%d")
        meetings = [
            {
                "id": "c1-recent-empty",
                "councilId": "c1",
                "date": fmt_date(5),
                "officialUrl": "https://example.go.jp/dai10.html",
                "materials": []
            },
            {
                "id": "c1-future-empty",
                "councilId": "c1",
                "date": (now + timedelta(days=7)).strftime("%Y/%m/%d"),
                "officialUrl": "https://example.go.jp/dai11.html",
                "materials": []
            },
            {
                "id": "c1-done",
                "councilId": "c1",
                "date": fmt_date(30),
                "officialUrl": "https://example.go.jp/dai9.html",
                "materials": [{"name": "資料1", "url": "https://example.go.jp/dai9.pdf"}]
            },
            {
                "id": "c1-ancient-empty",
                "councilId": "c1",
                "date": fmt_date(200),
                "officialUrl": "https://example.go.jp/dai1.html",
                "materials": []
            },
        ]
        known_urls = crawler._build_known_meeting_urls(meetings).get("c1", set())
        self.assertNotIn("https://example.go.jp/dai10.html", known_urls)
        self.assertNotIn("https://example.go.jp/dai11.html", known_urls)
        self.assertIn("https://example.go.jp/dai9.html", known_urls)
        self.assertIn("https://example.go.jp/dai1.html", known_urls)

        candidates = [
            "https://example.go.jp/dai11.html",
            "https://example.go.jp/dai10.html",
            "https://example.go.jp/dai9.html",
            "https://example.go.jp/dai1.html",
        ]
        targets, stats = crawler._filter_incremental_subpages(candidates, known_urls, max_unvisited=50, max_recent=1)
        self.assertIn("https://example.go.jp/dai10.html", targets)
        self.assertIn("https://example.go.jp/dai11.html", targets)
        self.assertEqual(stats["unvisited"], 2)

    def test_roundless_same_day_meeting_upgrades_parent_url_and_sets_updated_ts(self):
        """Drop 150: 回次なし同日会議で個別URLと資料が検出された場合、親URLから自動昇格し lastUpdatedFromCrawl を付与すること"""
        parent_url = "https://example.go.jp/council/index.html"
        sub_url = "https://example.go.jp/council/20261120_shiryou.html"
        data = {
            "councils": [
                {"id": "test-roundless", "ministry": "MOF", "name": "回次なし分科会", "officialUrl": parent_url}
            ],
            "meetings": [
                {
                    "id": "test-roundless-20261120-s01",
                    "councilId": "test-roundless",
                    "name": "回次なし分科会 (2026/11/20)",
                    "date": "2026/11/20",
                    "officialUrl": parent_url,
                    "materials": [],
                    "manualLock": False
                }
            ],
            "scrapingRules": {}
        }
        target = {"id": "test-roundless", "name": "回次なし分科会", "ministry": "MOF", "officialUrl": parent_url}
        scraped_item = {
            "subpageMeetings": [
                {
                    "subpageUrl": sub_url,
                    "name": "回次なし分科会 (令和8年11月20日)",
                    "title": "回次なし分科会 (令和8年11月20日)",
                    "extractedDates": ["2026/11/20"],
                    "materials": [{"name": "配布資料", "url": "https://example.go.jp/council/20261120.pdf", "type": "PDF"}]
                }
            ]
        }
        added = crawler.sync_new_meetings_from_crawl(data, target, scraped_item)
        self.assertEqual(added, 0)
        ex_m = data["meetings"][0]
        self.assertEqual(ex_m["officialUrl"], sub_url)
        self.assertEqual(len(ex_m["materials"]), 1)
        self.assertTrue(ex_m.get("lastUpdatedFromCrawl"))


if __name__ == '__main__':
    unittest.main()
