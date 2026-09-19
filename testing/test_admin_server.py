#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 管理サーバー (admin/server.py) 自動単体・統合テスト
各 API エンドポイントの疎通、レスポンス構造、ステータスコード、エラーハンドリングを検証する。
"""

import os
import sys
import json
import time
import unittest
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

TESTING_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTING_DIR)
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")

if ADMIN_DIR not in sys.path:
    sys.path.insert(0, ADMIN_DIR)

import server


class QuietHandler(server.CustomHandler):
    def log_message(self, format, *args):
        # テスト実行時の HTTP アクセスログ出力を抑制
        pass


class TestAdminServer(unittest.TestCase):
    server = None
    server_thread = None
    base_url = None

    @classmethod
    def setUpClass(cls):
        ThreadingHTTPServer.allow_reuse_address = True
        # ポート 0 で空きポートを自動取得
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.05)  # 起動待機

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()

    def _request(self, path, method="GET", data=None, headers=None):
        url = f"{self.base_url}{path}"
        req_headers = headers or {}
        body = None
        if data is not None:
            if isinstance(data, (dict, list)):
                body = json.dumps(data).encode("utf-8")
                req_headers["Content-Type"] = "application/json"
            elif isinstance(data, (str, bytes)):
                body = data if isinstance(data, bytes) else data.encode("utf-8")

        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                content = res.read().decode("utf-8")
                return res.status, res.headers, content
        except urllib.error.HTTPError as e:
            content = e.read().decode("utf-8") if e.fp else ""
            return e.code, e.headers, content

    def test_cors_options(self):
        """OPTIONS リクエストで CORS ヘッダーが正しく返却されること"""
        status, headers, _ = self._request("/api/discovery-keywords", method="OPTIONS")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))

    def test_get_discovery_keywords(self):
        """GET /api/discovery-keywords が 200 とキーワード構造を返すこと"""
        status, _, body = self._request("/api/discovery-keywords")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict)
        self.assertIn("commonKeywords", data)
        self.assertIsInstance(data["commonKeywords"], list)

    def test_get_crawler_config(self):
        """GET /api/get-crawler-config が 200 と設定オブジェクトを返すこと"""
        status, _, body = self._request("/api/get-crawler-config")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict)

    def test_get_crawler_status(self):
        """GET /api/crawler-status が 200 とステータス構造を返すこと"""
        status, _, body = self._request("/api/crawler-status")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict)
        self.assertIn("running", data)
        self.assertIn("progress", data)
        self.assertIn("logs", data)
        self.assertIn("latest_log_id", data)

    def test_get_discovery_status(self):
        """GET /api/discovery-status が 200 とディスカバリーステータスを返すこと"""
        status, _, body = self._request("/api/discovery-status")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict)
        self.assertIn("running", data)
        self.assertIn("progress", data)
        self.assertIn("logs", data)

    def test_get_rejected_councils(self):
        """GET /api/rejected-councils が 200 と却下リスト配列を返すこと"""
        status, _, body = self._request("/api/rejected-councils")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, list)

    def test_get_new_meetings(self):
        """GET /api/new-meetings が 200 と新着会議カウント構造を返すこと"""
        status, _, body = self._request("/api/new-meetings")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict)
        self.assertIn("count", data)
        self.assertIn("meetings", data)
        self.assertIsInstance(data["meetings"], list)

    def test_get_backups(self):
        """GET /api/backups が 200 とバックアップ配列構造を返すこと"""
        status, _, body = self._request("/api/backups")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict)
        self.assertIn("backups", data)
        self.assertIsInstance(data["backups"], list)

    def test_get_unconfirmed_meetings(self):
        """GET /api/unconfirmed-meetings が 200 OK で count と meetings 配列を返すこと"""
        status, _, body = self._request("/api/unconfirmed-meetings")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict)
        self.assertIn("count", data)
        self.assertIn("meetings", data)
        self.assertIsInstance(data["meetings"], list)

    def test_404_not_found(self):
        """未定義エンドポイントへの GET が 404 を返すこと"""
        status, _, _ = self._request("/api/non-existent-endpoint-xyz-999")
        self.assertEqual(status, 404)

    def test_post_reject_council_missing_id(self):
        """POST /api/reject-council に ID 欠落でリクエストした場合に 500 エラーを返すこと"""
        status, _, body = self._request("/api/reject-council", method="POST", data={})
        self.assertEqual(status, 500)
        data = json.loads(body)
        self.assertEqual(data.get("status"), "error")
        self.assertIn("Council ID is required", data.get("message", ""))

    def test_post_malformed_json_body(self):
        """POST リクエストに不正な JSON 文字列を送信した場合に 500 エラーを返すこと"""
        status, _, body = self._request(
            "/api/save-crawler-config",
            method="POST",
            data="{invalid_json: true",
            headers={"Content-Type": "application/json"}
        )
        self.assertEqual(status, 500)
        data = json.loads(body)
        self.assertEqual(data.get("status"), "error")
        self.assertIn("Invalid JSON payload", data.get("message", ""))


if __name__ == "__main__":
    unittest.main()
