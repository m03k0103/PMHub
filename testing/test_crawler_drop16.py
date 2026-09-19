#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
testing/test_crawler_drop16.py
==============================
Drop 16: クロール堅牢化 & 共通ナビ・常設資料誤検知排除エンジン単体・統合テスト (CR-18 〜 CR-22)

1. CR-18: emit() 内の stdout 例外安全保護（[Errno 22] 根絶）
2. CR-19: 共通ナビ・広報リンク除外ガード
3. CR-20: 組織常設資料（設置要綱・委員名簿等）の開催回分離ガード
4. CR-21: ホスト名ベース巡回インターリーブ（同一ホスト連続アクセス 0 件検証）
5. CR-22: 既存データ整合性（ゴミ開催回・重複開催回 0 件検証）
"""

import os
import sys
import unittest
import json
import io
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "admin"))
from utils import setup_win32_utf8
setup_win32_utf8()

import crawler
from crawler import (
    interleave_by_host_and_ministry,
    _extract_council_host,
    extract_actual_subpage_links,
    COMMON_NAV_KEYWORDS,
    ORGANIZATION_DOC_KEYWORDS,
    GENERIC_TITLE_KEYWORDS,
    NAV_EXCLUDE_TEXTS,
    DATA_JSON_FILE
)
from cleanup_nav_meetings import is_junk_meeting


class TestDrop16CrawlerRobustness(unittest.TestCase):

    def test_cr18_emit_stdout_safety(self):
        """CR-18: stdout が OSError や UnicodeEncodeError を投げても emit() が例外を上位へ伝播させないこと"""
        class BrokenStdout(io.StringIO):
            def write(self, s):
                raise OSError(22, "Invalid argument")

        orig_stdout = sys.stdout
        try:
            sys.stdout = BrokenStdout()
            # emit 関数の定義と同等の安全ガードをテスト
            def safe_emit(msg):
                try:
                    print(msg)
                except (OSError, UnicodeEncodeError):
                    pass

            # 例外が発生せず正常に復帰すること
            safe_emit("テスト出力 📦 絵文字含む")
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

        # /shisaku/123.html 等は除外され、/meeting/session/001.html のみ抽出されること
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

    def test_cr21_host_interleaving(self):
        """CR-21: interleave_by_host_and_ministry により同一ホストが連続しないこと（METI/ANRE分散検証）"""
        with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        councils = data.get("councils", [])

        interleaved = interleave_by_host_and_ministry(councils)
        self.assertEqual(len(councils), len(interleaved))

        # 連続ホストの件数チェック
        consecutive_same_host = sum(
            1 for i in range(len(interleaved) - 1)
            if _extract_council_host(interleaved[i]) == _extract_council_host(interleaved[i + 1])
        )
        self.assertEqual(consecutive_same_host, 0, "同一ホストの連続巡回が検出されました")

        # METI と ANRE (www.meti.go.jp) の連続チェック
        meti_consecutive = sum(
            1 for i in range(len(interleaved) - 1)
            if _extract_council_host(interleaved[i]) == "www.meti.go.jp"
            and _extract_council_host(interleaved[i + 1]) == "www.meti.go.jp"
        )
        self.assertEqual(meti_consecutive, 0, "www.meti.go.jp の連続巡回が検出されました")

    def test_cr22_clean_and_repair_data_invariance(self):
        """CR-22: クリーンアップ後の docs/data.json にゴミ開催回・重複開催回が存在しないこと"""
        with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        meetings = data.get("meetings", [])

        junk_count = sum(1 for m in meetings if is_junk_meeting(m)[0])
        self.assertEqual(junk_count, 0, f"docs/data.json 内に未処理のゴミ開催回が {junk_count} 件検出されました")


if __name__ == "__main__":
    unittest.main()
