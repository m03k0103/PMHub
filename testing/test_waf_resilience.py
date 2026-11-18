#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WAF耐性 & 動的レートリミット・省庁ドメイン設定 単体テストスイート (test_waf_resilience.py)
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'admin'))
import crawler


class TestWafResilience(unittest.TestCase):

    def setUp(self):
        crawler.reset_waf_blocked_ministries()
        crawler._thread_local.current_ministry = None

    def tearDown(self):
        crawler.reset_waf_blocked_ministries()
        crawler._thread_local.current_ministry = None

    def test_dynamic_host_interval(self):
        """CR-49: ドメイン別動的レートリミットが正しく解決されるか検証"""
        self.assertEqual(crawler._get_host_interval("www.meti.go.jp"), 1.5)
        self.assertEqual(crawler._get_host_interval("meti.go.jp"), 1.5)
        self.assertEqual(crawler._get_host_interval("sub.meti.go.jp"), 1.5)
        self.assertEqual(crawler._get_host_interval("www.mhlw.go.jp"), 0.5)
        self.assertEqual(crawler._get_host_interval("www.cao.go.jp"), 0.5)
        self.assertEqual(crawler._get_host_interval(""), 0.5)

    def test_ministry_and_host_configs_db_unification(self):
        """省庁ドメイン・新着ポータル・ホスト設定のDB一元化とENV残存バグ根絶検証"""
        crawler.load_ministry_and_host_configs_from_db()
        self.assertNotIn("ENV", crawler.MINISTRY_DOMAINS, "Legacy 'ENV' key must not exist in MINISTRY_DOMAINS")
        self.assertIn("MOE", crawler.MINISTRY_DOMAINS)
        self.assertIn("env.go.jp", crawler.MINISTRY_DOMAINS["MOE"])
        self.assertGreaterEqual(len(crawler.MINISTRY_DOMAINS), 45, "All ministries in DB should have domains loaded")
        self.assertIn("MOE", crawler.MINISTRY_NEWS_PORTALS)
        self.assertNotIn("ENV", crawler.MINISTRY_NEWS_PORTALS)
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
        resp_202 = MagicMock()
        resp_202.status = 202
        resp_202.headers.get.return_value = 'text/html'
        resp_202.read.return_value = b'<html>challenge</html>'
        resp_202.__enter__.return_value = resp_202

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

    def test_is_s3_or_cdn_not_found(self):
        """Drop 137: Amazon S3 / CloudFront 擬似403 (Not Found) の検知判定を検証"""
        # 403 かつ S3 ページ不在メッセージ
        s3_body = "<html><head><title>指定されたページまたはファイルは存在しません</title></head></html>".encode('utf-8')
        self.assertTrue(crawler.is_s3_or_cdn_not_found(403, body_bytes=s3_body))
        self.assertTrue(crawler.is_s3_or_cdn_not_found(403, body_text="指定されたページは見つかりませんでした"))
        self.assertTrue(crawler.is_s3_or_cdn_not_found(403, body_text="<Code>NoSuchKey</Code>"))
        self.assertTrue(crawler.is_s3_or_cdn_not_found(404, body_text="404 Not Found"))
        # 通常の403（アクセス遮断・WAF）
        self.assertFalse(crawler.is_s3_or_cdn_not_found(403, body_text="Forbidden. Request blocked by administrative rule."))
        self.assertFalse(crawler.is_s3_or_cdn_not_found(200, body_text="指定されたページまたはファイルは存在しません"))

    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_fetch_url_s3_pseudo_403_fast_fail(self, mock_urlopen, mock_sleep):
        """Drop 137: S3 擬似403 発生時に待機リトライやcurlをバイパスして即座にNoneを返すか検証"""
        import urllib.error
        import io
        s3_html = "<html><title>指定されたページまたはファイルは存在しません</title></html>".encode('utf-8')
        fp = io.BytesIO(s3_html)
        http_err = urllib.error.HTTPError(
            url="https://example.go.jp/notfound",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=fp
        )
        mock_urlopen.side_effect = http_err

        res = crawler.fetch_url("https://example.go.jp/notfound")
        self.assertIsNone(res)
        self.assertEqual(mock_urlopen.call_count, 1)
        # リトライ待機（time.sleep）が呼ばれていないこと
        mock_sleep.assert_not_called()
        # last_fetch_error に S3 403 Not Found が記録されていること
        last_err = getattr(crawler._thread_local, 'last_fetch_error', '')
        self.assertIn("S3 403 Not Found", last_err)

    def test_safe_emit_log_transparency_to_registered_files(self):
        """Drop 137: safe_emit_log が登録されたログファイルハンドルへ透過的に追記するか検証"""
        import io
        buf = io.StringIO()
        crawler.register_crawler_logfile(buf)
        try:
            crawler.safe_emit_log("Drop 137 transparency test message")
            content = buf.getvalue()
            self.assertIn("Drop 137 transparency test message", content)
            self.assertRegex(content, r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")
        finally:
            crawler.unregister_crawler_logfile(buf)

        # 登録解除後は書き込まれないこと
        prev_len = len(buf.getvalue())
        crawler.safe_emit_log("After unregister message")
        self.assertEqual(len(buf.getvalue()), prev_len)

    @patch('crawler._fetch_with_curl', return_value=None)
    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_waf_challenge_blocked_blocks_subsequent_ministry_access(self, mock_urlopen, mock_sleep, mock_curl):
        """WAF CHALLENGE BLOCKED 発生後、同じ省庁への以降の fetch_url アクセスが完全にスキップされることを検証"""
        resp_waf = MagicMock()
        resp_waf.status = 200
        resp_waf.headers.get.return_value = 'text/html; charset=utf-8'
        resp_waf.read.return_value = b'<html><script>awsWafCookieDomainList=[]</script></html>'
        resp_waf.__enter__.return_value = resp_waf

        resp_ok = MagicMock()
        resp_ok.status = 200
        resp_ok.headers.get.return_value = 'text/html; charset=utf-8'
        resp_ok.read.return_value = '<html><title>内閣府会議</title></html>'.encode('utf-8')
        resp_ok.__enter__.return_value = resp_ok

        mock_urlopen.side_effect = [resp_waf, resp_ok]

        # 1回目: METI で WAF CHALLENGE BLOCKED が発生
        res1 = crawler.fetch_url("https://www.meti.go.jp/shingikai/c1.html", ministry="METI")
        self.assertIsNone(res1)
        self.assertTrue(crawler.is_ministry_waf_blocked("METI"))
        self.assertEqual(mock_urlopen.call_count, 1)

        # 2回目: 同じ METI へのアクセスはネットワーク通信を行わずスキップ
        res2 = crawler.fetch_url("https://www.meti.go.jp/shingikai/c2.html", ministry="METI")
        self.assertIsNone(res2)
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertIn("WAF Blocked Skip", getattr(crawler._thread_local, 'last_fetch_error', ''))

        # 3回目: 別省庁（CAO）は通常通りアクセスされる
        res3 = crawler.fetch_url("https://www.cao.go.jp/council/c1.html", ministry="CAO")
        self.assertIsNotNone(res3)
        self.assertIn("内閣府会議", res3)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch('crawler.save_data_json_with_backup', return_value=True)
    @patch('crawler.load_scraping_rules', return_value={})
    @patch('crawler.load_data_json')
    @patch('crawler._fetch_with_curl', return_value=None)
    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_run_meeting_crawler_skips_same_ministry_after_waf_blocked(
        self, mock_urlopen, mock_sleep, mock_curl, mock_load_data, mock_load_rules, mock_save
    ):
        """run_meeting_crawler 実行中に WAF CHALLENGE BLOCKED になった省庁の後続会議体がスキップされることを検証"""
        mock_data = {
            "councils": [
                {"id": "meti-c1", "name": "経産省会議1", "ministry": "METI", "officialUrl": "https://www.meti.go.jp/c1.html", "isActive": True},
                {"id": "meti-c2", "name": "経産省会議2", "ministry": "METI", "officialUrl": "https://www.meti.go.jp/c2.html", "isActive": True},
                {"id": "cao-c1", "name": "内閣府会議1", "ministry": "CAO", "officialUrl": "https://www.cao.go.jp/c1.html", "isActive": True},
            ],
            "meetings": [
                {"id": "meti-c1-20261001-001", "councilId": "meti-c1", "date": "2026/10/01", "name": "第1回"},
                {"id": "meti-c2-20261001-001", "councilId": "meti-c2", "date": "2026/10/01", "name": "第1回"},
                {"id": "cao-c1-20261001-001", "councilId": "cao-c1", "date": "2026/10/01", "name": "第1回"},
            ],
            "scrapingRules": {},
            "rejectedCouncils": [],
        }
        mock_load_data.return_value = mock_data

        called_urls = []
        def fake_urlopen(req, timeout=12, context=None):
            u = req.full_url if hasattr(req, 'full_url') else str(req)
            called_urls.append(u)
            resp = MagicMock()
            resp.headers.get.return_value = 'text/html; charset=utf-8'
            resp.__enter__.return_value = resp
            if "meti.go.jp" in u:
                resp.status = 200
                resp.read.return_value = b'<html><script>awsWafCookieDomainList=[]</script></html>'
            else:
                resp.status = 200
                resp.read.return_value = '<html><title>内閣府会議1</title><body><p>2026年10月1日</p></body></html>'.encode('utf-8')
            return resp

        mock_urlopen.side_effect = fake_urlopen

        with patch('crawler.interleave_by_host_and_ministry', side_effect=lambda x: x), \
             patch('sqlite3.connect'):
            stats = crawler.run_meeting_crawler(workers=1, skip_download=True)

        self.assertIn("https://www.meti.go.jp/c1.html", called_urls)
        self.assertNotIn("https://www.meti.go.jp/c2.html", called_urls)
        self.assertIn("https://www.cao.go.jp/c1.html", called_urls)
        self.assertEqual(stats.get("waf_skipped"), 1)
        self.assertEqual(stats.get("waf_blocked_ministries"), ["METI"])


if __name__ == '__main__':
    unittest.main()
