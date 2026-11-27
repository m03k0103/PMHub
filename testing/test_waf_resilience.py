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
        for agency_code in ("ACA", "ANRE", "JSA", "SMEA", "NPA", "ISA", "RA"):
            self.assertIn(agency_code, crawler.MINISTRY_NEWS_PORTALS, f"{agency_code} should have newsPortals")
            self.assertTrue(len(crawler.MINISTRY_NEWS_PORTALS[agency_code]) >= 1)
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

    @patch('crawler._fetch_with_curl')
    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_fetch_url_immediate_circuit_breaker_on_202(self, mock_urlopen, mock_sleep, mock_curl):
        """対策5: HTTP 202 検知時に2.5秒リトライやcurlフォールバックを行わず即時サーキットブレーカー停止・ホスト遮断されるか検証"""
        resp_202 = MagicMock()
        resp_202.status = 202
        resp_202.headers.get.return_value = 'text/html'
        resp_202.read.return_value = b'<html>challenge</html>'
        resp_202.__enter__.return_value = resp_202

        mock_urlopen.return_value = resp_202

        host = "waf202-test.meti.go.jp"
        res1 = crawler.fetch_url(f"https://{host}/shingikai/sample/index.html")
        self.assertIsNone(res1)
        self.assertEqual(mock_urlopen.call_count, 1)
        mock_curl.assert_not_called()
        for call in mock_sleep.call_args_list:
            self.assertNotAlmostEqual(call.args[0], 2.5, places=3)
        self.assertTrue(crawler.is_host_waf_blocked(host))
        self.assertIn("WAF 202 Challenge", getattr(crawler._thread_local, 'last_fetch_error', ''))

        # 後続の同一ホストアクセスはネットワーク通信を行わず即時スキップ
        res2 = crawler.fetch_url(f"https://{host}/shingikai/sample/other.html")
        self.assertIsNone(res2)
        self.assertEqual(mock_urlopen.call_count, 1)

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
    def test_waf_challenge_blocked_blocks_subsequent_host_access(self, mock_urlopen, mock_sleep, mock_curl):
        """Drop 150: 同一ホストで連続3回 WAF CHALLENGE BLOCKED 発生後、同一ホストのみ遮断され他ホストは継続すること"""
        resp_waf = MagicMock()
        resp_waf.status = 200
        resp_waf.headers.get.return_value = 'text/html; charset=utf-8'
        resp_waf.read.return_value = b'<html><script>awsWafCookieDomainList=[]</script></html>'
        resp_waf.__enter__.return_value = resp_waf

        resp_ok_sub = MagicMock()
        resp_ok_sub.status = 200
        resp_ok_sub.headers.get.return_value = 'text/html; charset=utf-8'
        resp_ok_sub.read.return_value = '<html><title>中小企業庁会議</title></html>'.encode('utf-8')
        resp_ok_sub.__enter__.return_value = resp_ok_sub

        resp_ok_cao = MagicMock()
        resp_ok_cao.status = 200
        resp_ok_cao.headers.get.return_value = 'text/html; charset=utf-8'
        resp_ok_cao.read.return_value = '<html><title>内閣府会議</title></html>'.encode('utf-8')
        resp_ok_cao.__enter__.return_value = resp_ok_cao

        # METI (www.meti.go.jp) で連続3回 WAF 検知後に遮断、同一 METI 配下の別ホストや他省庁は正常通過
        mock_urlopen.side_effect = [resp_waf, resp_waf, resp_waf, resp_ok_sub, resp_ok_cao]

        for i in range(3):
            res = crawler.fetch_url(f"https://www.meti.go.jp/shingikai/c{i+1}.html", ministry="METI")
            self.assertIsNone(res)
            if i < 2:
                self.assertFalse(crawler.is_host_waf_blocked("www.meti.go.jp"))

        self.assertTrue(crawler.is_host_waf_blocked("www.meti.go.jp"))
        self.assertFalse(crawler.is_ministry_waf_blocked("METI"))
        self.assertEqual(mock_urlopen.call_count, 3)

        # 4回目: 同一ホスト www.meti.go.jp へのアクセスはネットワーク通信を行わずスキップ
        res_skip = crawler.fetch_url("https://www.meti.go.jp/shingikai/c4.html", ministry="METI")
        self.assertIsNone(res_skip)
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertIn("WAF Blocked Skip (Host www.meti.go.jp)", getattr(crawler._thread_local, 'last_fetch_error', ''))

        # 5回目: 同じ METI/SMEA 系でも別ホスト (www.chusho.meti.go.jp) には影響せずアクセス成功
        res_sub = crawler.fetch_url("https://www.chusho.meti.go.jp/c1.html", ministry="METI")
        self.assertIsNotNone(res_sub)
        self.assertIn("中小企業庁会議", res_sub)

        # 6回目: 別省庁（CAO）は通常通りアクセスされる
        res_cao = crawler.fetch_url("https://www.cao.go.jp/council/c1.html", ministry="CAO")
        self.assertIsNotNone(res_cao)
        self.assertIn("内閣府会議", res_cao)
        self.assertEqual(mock_urlopen.call_count, 5)

    @patch('crawler._fetch_with_curl', return_value=None)
    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_waf_host_isolation_warp_and_success_reset(self, mock_urlopen, mock_sleep, mock_curl):
        """Drop 150: warp.ndl.go.jp のWAF遮断が www.meti.go.jp に波及せず、成功時に連続失敗カウントがリセットされること"""
        resp_waf = MagicMock()
        resp_waf.status = 200
        resp_waf.headers.get.return_value = 'text/html; charset=utf-8'
        resp_waf.read.return_value = b'<html><script>awsWafCookieDomainList=[]</script></html>'
        resp_waf.__enter__.return_value = resp_waf

        resp_ok = MagicMock()
        resp_ok.status = 200
        resp_ok.headers.get.return_value = 'text/html; charset=utf-8'
        resp_ok.read.return_value = '<html><title>正常ページ</title></html>'.encode('utf-8')
        resp_ok.__enter__.return_value = resp_ok

        # METI で 2回WAF -> 1回200成功(リセット) -> 再び2回WAF でも遮断されないこと
        mock_urlopen.side_effect = [resp_waf, resp_waf, resp_ok, resp_waf, resp_waf]
        for idx in range(5):
            r = crawler.fetch_url(f"https://www.meti.go.jp/shingi/p{idx}.html", ministry="METI")
            if idx == 2:
                self.assertIsNotNone(r)
            else:
                self.assertIsNone(r)
        self.assertFalse(crawler.is_host_waf_blocked("www.meti.go.jp"))

        # warp.ndl.go.jp は ministry="METI" で3回WAFしても www.meti.go.jp を遮断しない
        mock_urlopen.side_effect = [resp_waf, resp_waf, resp_waf, resp_ok]
        for idx in range(3):
            self.assertIsNone(crawler.fetch_url(f"https://warp.ndl.go.jp/web/{idx}.html", ministry="METI"))
        self.assertTrue(crawler.is_host_waf_blocked("warp.ndl.go.jp"))
        self.assertFalse(crawler.is_host_waf_blocked("www.meti.go.jp"))
        res_meti = crawler.fetch_url("https://www.meti.go.jp/shingi/ok.html", ministry="METI")
        self.assertIsNotNone(res_meti)

    def test_warp_archive_url_excluded_from_active_crawl(self):
        """Drop 150: 国立国会図書館 WARP アーカイブURLの会議体が通常巡回対象から除外されること"""
        self.assertTrue(crawler.is_warp_archive_url("https://warp.ndl.go.jp/web/20180913000000/www.meti.go.jp/shingikai/"))
        self.assertTrue(crawler.is_warp_archive_url("https://warp.da.ndl.go.jp/info:ndljp/pid/283990/www.mofa.go.jp/"))
        self.assertFalse(crawler.is_warp_archive_url("https://www.meti.go.jp/shingikai/sample/index.html"))

        mock_data = {
            "councils": [
                {"id": "meti-warp", "ministry": "METI", "name": "過去WARP", "officialUrl": "https://warp.ndl.go.jp/web/1/index.html"},
                {"id": "meti-normal", "ministry": "METI", "name": "通常会議", "officialUrl": "https://www.meti.go.jp/shingi/1.html"},
            ],
            "meetings": [],
            "scrapingRules": {},
        }
        with patch('crawler.load_data_json', return_value=mock_data), \
             patch('crawler.get_rejected_identifiers', return_value=(set(), set(), set())), \
             patch('builtins.print'):
            normal_targets = crawler.load_councils_from_data_json(recent_years="all", include_closed=False)
            with_closed_targets = crawler.load_councils_from_data_json(recent_years="all", include_closed=True)
        self.assertEqual([c["id"] for c in normal_targets], ["meti-normal"])
        self.assertEqual({c["id"] for c in with_closed_targets}, {"meti-warp", "meti-normal"})

    @patch('crawler.save_data_json_with_backup', return_value=True)
    @patch('crawler.load_scraping_rules', return_value={})
    @patch('crawler.load_data_json')
    @patch('crawler._fetch_with_curl', return_value=None)
    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_run_meeting_crawler_skips_same_host_after_waf_blocked(
        self, mock_urlopen, mock_sleep, mock_curl, mock_load_data, mock_load_rules, mock_save
    ):
        """Drop 150: run_meeting_crawler 実行中にホスト単位で連続3回WAF検知した場合、後続の同一ホストのみスキップし他ホストは継続すること"""
        mock_data = {
            "councils": [
                {"id": "meti-c1", "name": "経産省会議1", "ministry": "METI", "officialUrl": "https://www.meti.go.jp/c1.html", "isActive": True},
                {"id": "meti-c2", "name": "経産省会議2", "ministry": "METI", "officialUrl": "https://www.meti.go.jp/c2.html", "isActive": True},
                {"id": "meti-c3", "name": "経産省会議3", "ministry": "METI", "officialUrl": "https://www.meti.go.jp/c3.html", "isActive": True},
                {"id": "meti-c4", "name": "経産省会議4", "ministry": "METI", "officialUrl": "https://www.meti.go.jp/c4.html", "isActive": True},
                {"id": "smea-c1", "name": "中小企業庁会議1", "ministry": "METI", "officialUrl": "https://www.chusho.meti.go.jp/c1.html", "isActive": True},
                {"id": "cao-c1", "name": "内閣府会議1", "ministry": "CAO", "officialUrl": "https://www.cao.go.jp/c1.html", "isActive": True},
            ],
            "meetings": [
                {"id": "meti-c1-20261001-001", "councilId": "meti-c1", "date": "2026/10/01", "name": "第1回"},
                {"id": "meti-c2-20261001-001", "councilId": "meti-c2", "date": "2026/10/01", "name": "第1回"},
                {"id": "meti-c3-20261001-001", "councilId": "meti-c3", "date": "2026/10/01", "name": "第1回"},
                {"id": "meti-c4-20261001-001", "councilId": "meti-c4", "date": "2026/10/01", "name": "第1回"},
                {"id": "smea-c1-20261001-001", "councilId": "smea-c1", "date": "2026/10/01", "name": "第1回"},
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
            if "www.meti.go.jp" in u:
                resp.status = 200
                resp.read.return_value = b'<html><script>awsWafCookieDomainList=[]</script></html>'
            else:
                resp.status = 200
                resp.read.return_value = '<html><title>正常会議</title><body><p>2026年10月1日</p></body></html>'.encode('utf-8')
            return resp

        mock_urlopen.side_effect = fake_urlopen

        with patch('crawler.interleave_by_host_and_ministry', side_effect=lambda x: x), \
             patch('sqlite3.connect'):
            stats = crawler.run_meeting_crawler(workers=1, skip_download=True)

        self.assertIn("https://www.meti.go.jp/c1.html", called_urls)
        self.assertIn("https://www.meti.go.jp/c2.html", called_urls)
        self.assertIn("https://www.meti.go.jp/c3.html", called_urls)
        self.assertNotIn("https://www.meti.go.jp/c4.html", called_urls)
        self.assertIn("https://www.chusho.meti.go.jp/c1.html", called_urls)
        self.assertIn("https://www.cao.go.jp/c1.html", called_urls)
        self.assertEqual(stats.get("waf_skipped"), 1)
        self.assertEqual(stats.get("waf_blocked_hosts"), ["www.meti.go.jp"])
        self.assertEqual(stats.get("waf_blocked_ministries"), [])

    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_fetch_url_in_run_html_cache_strips_anchor(self, mock_urlopen, mock_sleep):
        """対策1: 同一巡回内で #anchor のみ異なる親ページURLは1回だけ通信しキャッシュを再利用すること"""
        resp = MagicMock()
        resp.status = 200
        resp.headers.get.return_value = 'text/html; charset=utf-8'
        resp.read.return_value = '<html><title>研究会一覧</title><body><h2 id="a">A</h2><h2 id="b">B</h2></body></html>'.encode('utf-8')
        resp.__enter__.return_value = resp
        mock_urlopen.return_value = resp

        base_url = "https://www.chusho.meti.go.jp/koukai/kenkyukai/index.html"
        html1 = crawler.fetch_url(f"{base_url}#council_a")
        html2 = crawler.fetch_url(f"{base_url}#council_b")
        self.assertIsNotNone(html1)
        self.assertEqual(html1, html2)
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_fetch_url_conditional_get_304_uses_cached_html(self, mock_urlopen, mock_sleep):
        """対策2: ETag / Last-Modified を記憶し、次回 HTTP 304 応答時にキャッシュ済みHTMLを返すこと"""
        import http.client
        import io
        import urllib.error

        hdrs = http.client.HTTPMessage()
        hdrs.add_header('Content-Type', 'text/html; charset=utf-8')
        hdrs.add_header('ETag', '"smea-v1"')
        hdrs.add_header('Last-Modified', 'Thu, 26 Nov 2026 09:00:00 GMT')

        resp_200 = MagicMock()
        resp_200.status = 200
        resp_200.headers = hdrs
        resp_200.info.return_value = hdrs
        resp_200.read.return_value = '<html><title>条件付きGET会議</title></html>'.encode('utf-8')
        resp_200.__enter__.return_value = resp_200

        url = "https://www.chusho.meti.go.jp/koukai/shingikai/index.html"
        err_304 = urllib.error.HTTPError(url=url, code=304, msg="Not Modified", hdrs={}, fp=io.BytesIO(b""))
        mock_urlopen.side_effect = [resp_200, err_304]

        html1 = crawler.fetch_url(url)
        self.assertIn("条件付きGET会議", html1)

        # 次回クロール相当として巡回内キャッシュのみクリアし、条件付きGETキャッシュを残す
        with crawler._RUN_HTML_CACHE_LOCK:
            crawler._RUN_HTML_CACHE.clear()

        html2 = crawler.fetch_url(url)
        self.assertEqual(html2, html1)
        self.assertEqual(mock_urlopen.call_count, 2)

        req2 = mock_urlopen.call_args_list[1].args[0]
        req2_hdrs = {k.lower(): v for k, v in req2.header_items()}
        self.assertEqual(req2_hdrs.get('if-none-match'), '"smea-v1"')
        self.assertEqual(req2_hdrs.get('if-modified-since'), 'Thu, 26 Nov 2026 09:00:00 GMT')

    def test_rate_limit_host_applies_bounded_jitter(self):
        """対策3: ホスト間レートリミットに既定基準間隔以上のランダムゆらぎ（ジッター）が付与されること"""
        from crawler_modules import http_client

        host = "jitter-check.meti.go.jp"
        crawler._LAST_REQUEST_TIME_BY_HOST.pop(host, None)
        crawler._LAST_REQUEST_TIME_BY_HOST[host] = 100.0
        try:
            with patch('crawler.time.time', return_value=100.2), \
                 patch('crawler.time.sleep') as mock_sleep, \
                 patch('crawler.random.uniform', return_value=0.35) as mock_uniform, \
                 patch('crawler._get_host_interval', return_value=2.0):
                crawler._rate_limit_host(host)
                mock_uniform.assert_called_once()
                low, high = mock_uniform.call_args.args
                self.assertEqual(low, 0.0)
                self.assertAlmostEqual(high, 0.7, places=4)
                # interval = 2.0 + 0.35 = 2.35, elapsed = 0.2 -> sleep 2.15
                mock_sleep.assert_called_once()
                self.assertAlmostEqual(mock_sleep.call_args.args[0], 2.15, places=3)
        finally:
            crawler._LAST_REQUEST_TIME_BY_HOST.pop(host, None)

        with http_client._HTTP_LOCK:
            http_client._HOST_LAST_ACCESS[host] = 200.0
        try:
            with patch('crawler_modules.http_client.time.time', side_effect=[200.1, 202.35]), \
                 patch('crawler_modules.http_client.time.sleep') as mock_hc_sleep, \
                 patch('crawler_modules.http_client.random.uniform', return_value=0.25) as mock_hc_uniform:
                http_client.apply_host_rate_limit(host, interval=2.0, jitter_ratio=0.35, max_jitter=1.5)
                mock_hc_uniform.assert_called_once()
                mock_hc_sleep.assert_called_once()
                self.assertAlmostEqual(mock_hc_sleep.call_args.args[0], 2.15, places=3)
        finally:
            with http_client._HTTP_LOCK:
                http_client._HOST_LAST_ACCESS.pop(host, None)

    @patch('time.sleep')
    @patch('urllib.request.urlopen')
    def test_fetch_url_cookie_session_and_referer_headers(self, mock_urlopen, mock_sleep):
        """対策4: 同一ホスト内のCookie維持およびReferer / Sec-Fetch-Siteヘッダー付与を検証"""
        import http.client

        hdrs1 = http.client.HTTPMessage()
        hdrs1.add_header('Content-Type', 'text/html; charset=utf-8')
        hdrs1.add_header('Set-Cookie', 'pmhub_sess=tok123; Path=/; Secure')

        resp1 = MagicMock()
        resp1.status = 200
        resp1.headers = hdrs1
        resp1.info.return_value = hdrs1
        resp1.read.return_value = '<html><title>親ページ</title></html>'.encode('utf-8')
        resp1.__enter__.return_value = resp1

        hdrs2 = http.client.HTTPMessage()
        hdrs2.add_header('Content-Type', 'text/html; charset=utf-8')
        resp2 = MagicMock()
        resp2.status = 200
        resp2.headers = hdrs2
        resp2.info.return_value = hdrs2
        resp2.read.return_value = '<html><title>サブページ</title></html>'.encode('utf-8')
        resp2.__enter__.return_value = resp2

        hdrs3 = http.client.HTTPMessage()
        hdrs3.add_header('Content-Type', 'text/html; charset=utf-8')
        resp3 = MagicMock()
        resp3.status = 200
        resp3.headers = hdrs3
        resp3.info.return_value = hdrs3
        resp3.read.return_value = '<html><title>外部</title></html>'.encode('utf-8')
        resp3.__enter__.return_value = resp3

        mock_urlopen.side_effect = [resp1, resp2, resp3]

        parent_url = "https://www.chusho.meti.go.jp/koukai/kenkyukai/index.html"
        sub_url = "https://www.chusho.meti.go.jp/koukai/kenkyukai/sub1.html"
        ext_url = "https://www.meti.go.jp/shingikai/other.html"

        crawler.fetch_url(parent_url)
        crawler.fetch_url(sub_url, referer=f"{parent_url}#sec1")
        crawler.fetch_url(ext_url, referer=parent_url)

        req2 = mock_urlopen.call_args_list[1].args[0]
        req2_hdrs = {k.lower(): v for k, v in req2.header_items()}
        self.assertIn('pmhub_sess=tok123', req2_hdrs.get('cookie', ''))
        self.assertEqual(req2_hdrs.get('referer'), parent_url)
        self.assertEqual(req2_hdrs.get('sec-fetch-site'), 'same-origin')
        self.assertEqual(req2_hdrs.get('connection'), 'keep-alive')

        req3 = mock_urlopen.call_args_list[2].args[0]
        req3_hdrs = {k.lower(): v for k, v in req3.header_items()}
        self.assertEqual(req3_hdrs.get('sec-fetch-site'), 'cross-site')


if __name__ == '__main__':
    unittest.main()
