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


if __name__ == '__main__':
    unittest.main()
