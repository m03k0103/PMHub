# -*- coding: utf-8 -*-
"""
http_client.py:
PMHub 共通HTTP通信クライアント (Drop 116)
クローラー (crawler.py) およびディスカバリー (discover_councils.py) で共通利用可能な
標準ブラウザヘッダー、同一ホスト直列化レートリミット、文字コード自動判定付きHTTP取得層。
"""

import sys
import os
import time
import threading
import urllib.request
import urllib.parse
import ssl
from typing import Optional, Tuple, Dict, Any

try:
    from admin.utils import get_browser_headers, decode_html_bytes
except ImportError:
    from utils import get_browser_headers, decode_html_bytes

# レートリミット管理用グローバルロック・ホスト別最終リクエスト時刻
_HTTP_LOCK = threading.Lock()
_HOST_LAST_ACCESS: Dict[str, float] = {}
DEFAULT_HOST_INTERVAL = 0.5  # 秒（AGENTS.md 規約: 最低0.35秒以上厳守）


def extract_host(url: str) -> str:
    """URLからホスト名 (netloc) を抽出"""
    if not url:
        return ""
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""


def apply_host_rate_limit(host: str, interval: float = DEFAULT_HOST_INTERVAL):
    """
    同一ホストに対する直列化スロットリング。
    前回アクセスから interval 秒経過するまでスリープする。
    """
    if not host:
        return
    effective_interval = max(0.35, interval)
    with _HTTP_LOCK:
        now = time.time()
        last = _HOST_LAST_ACCESS.get(host, 0.0)
        elapsed = now - last
        if elapsed < effective_interval:
            sleep_sec = effective_interval - elapsed
            time.sleep(sleep_sec)
        _HOST_LAST_ACCESS[host] = time.time()


def fetch_raw_response(
    url: str,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
    enforce_rate_limit: bool = True,
    interval: float = DEFAULT_HOST_INTERVAL,
) -> Tuple[bytes, str, int]:
    """
    指定URLからバイト列レスポンスと最終URL、ステータスコードを取得する。
    Returns: (raw_bytes, final_url, status_code)
    """
    if not url:
        return b"", "", 0

    host = extract_host(url)
    if enforce_rate_limit and host:
        apply_host_rate_limit(host, interval=interval)

    req_headers = get_browser_headers()
    if headers:
        req_headers.update(headers)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        final_url = resp.geturl()
        status_code = resp.status if hasattr(resp, "status") else 200
        raw_bytes = resp.read()
        return raw_bytes, final_url, status_code


def fetch_html_page(
    url: str,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
    enforce_rate_limit: bool = True,
    interval: float = DEFAULT_HOST_INTERVAL,
) -> Tuple[str, str]:
    """
    指定URLからHTMLテキストおよび最終URLを取得する。
    自動でエンコーディング判定・デコードを行い、文字化けを防止する。
    Returns: (html_text, final_url)
    """
    try:
        raw_bytes, final_url, status_code = fetch_raw_response(
            url,
            timeout=timeout,
            headers=headers,
            enforce_rate_limit=enforce_rate_limit,
            interval=interval,
        )
        if not raw_bytes:
            return "", final_url
        html_text = decode_html_bytes(raw_bytes)
        return html_text, final_url
    except Exception as e:
        return "", url
