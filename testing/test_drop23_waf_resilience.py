#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 23 テストスイート: METI/ANRE AWS WAF耐性 & 動的レートリミット検証 (CR-48, CR-49)
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'admin'))
import crawler

class TestDrop23WafResilience(unittest.TestCase):

    def test_dynamic_host_interval(self):
        """CR-49: ドメイン別動的レートリミットが正しく解決されるか検証"""
        self.assertEqual(crawler._get_host_interval("www.meti.go.jp"), 1.5)
        self.assertEqual(crawler._get_host_interval("meti.go.jp"), 1.5)
        self.assertEqual(crawler._get_host_interval("sub.meti.go.jp"), 1.5)
        self.assertEqual(crawler._get_host_interval("www.mhlw.go.jp"), 0.5)
        self.assertEqual(crawler._get_host_interval("www.cao.go.jp"), 0.5)
        self.assertEqual(crawler._get_host_interval(""), 0.5)

    def test_ministry_and_host_configs_db_unification(self):
        """Drop 92: 省庁ドメイン・新着ポータル・ホスト設定のDB一元化とENV残存バグ根絶検証"""
        crawler.load_ministry_and_host_configs_from_db()
        self.assertNotIn("ENV", crawler.MINISTRY_DOMAINS, "Legacy 'ENV' key must not exist in MINISTRY_DOMAINS")
        self.assertIn("MOE", crawler.MINISTRY_DOMAINS)
        self.assertIn("env.go.jp", crawler.MINISTRY_DOMAINS["MOE"])
        self.assertGreaterEqual(len(crawler.MINISTRY_DOMAINS), 45, "All ministries in DB should have domains loaded")
        self.assertIn("MOE", crawler.MINISTRY_NEWS_PORTALS)
        self.assertNotIn("ENV", crawler.MINISTRY_NEWS_PORTALS)
        # 外局と本省の共有ドメイン（ANRE / METI 等）が他省庁ドメインとして誤遮断されないことを検証
        self.assertNotIn("meti.go.jp", crawler._OTHER_MINISTRY_DOMAINS_MAP.get("ANRE", ()))
        self.assertNotIn("env.go.jp", crawler._OTHER_MINISTRY_DOMAINS_MAP.get("MOE", ()))
        self.assertIn("mhlw.go.jp", crawler._OTHER_MINISTRY_DOMAINS_MAP.get("METI", ()))

    def test_is_waf_challenge(self):
        """CR-43 / CR-48: AWS WAF / Cloudflare チャレンジ画面の検知検証"""
        self.assertTrue(crawler.is_waf_challenge(b"anything", status_code=202))
        self.assertTrue(crawler.is_waf_challenge("anything", status_code=202))
        self.assertTrue(crawler.is_waf_challenge(b"<script>awsWafCookieDomainList=[]</script>", status_code=200))
        self.assertTrue(crawler.is_waf_challenge("<div id='challenge-running'></div>", status_code=200))
        self.assertFalse(crawler.is_waf_challenge("<html><head><title>正常なページ</title></head></html>", status_code=200))

    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_fetch_url_retry_on_202(self, mock_urlopen, mock_sleep):
        """CR-48: HTTP 202 発生時にクールダウン待機して自動リトライが実行されるか検証"""
        # 1回目の呼び出し: 202 チャレンジ
        resp_202 = MagicMock()
        resp_202.status = 202
        resp_202.headers.get.return_value = 'text/html'
        resp_202.read.return_value = b'<html>challenge</html>'
        resp_202.__enter__.return_value = resp_202

        # 2回目の呼び出し: 200 OK 正常HTML
        resp_200 = MagicMock()
        resp_200.status = 200
        resp_200.headers.get.return_value = 'text/html; charset=utf-8'
        resp_200.read.return_value = '<html><head><title>正常審議会</title></head><body><h1>第1回</h1></body></html>'.encode('utf-8')
        resp_200.__enter__.return_value = resp_200

        mock_urlopen.side_effect = [resp_202, resp_200]

        html = crawler.fetch_url("https://www.meti.go.jp/shingikai/sample/index.html")
        self.assertIsNotNone(html)
        self.assertIn("正常審議会", html)
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_any_call(2.5)

if __name__ == '__main__':
    unittest.main()
