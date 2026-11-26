# -*- coding: utf-8 -*-
"""
parent_resolver.py:
プレスリリース・報道発表ページから常設親ページURLへの逆引き (Drop 116)
"""

import re
import time
import urllib.request
import urllib.parse
from urllib.parse import urlparse, urljoin
import ssl
from typing import Optional, Tuple
from bs4 import BeautifulSoup

try:
    from admin.utils import get_browser_headers, decode_html_bytes
except ImportError:
    from utils import get_browser_headers, decode_html_bytes

try:
    from admin.crawler_modules.http_client import fetch_html_page
except ImportError:
    from crawler_modules.http_client import fetch_html_page

try:
    from admin.discovery_modules.name_cleaner import get_core_council_name, clean_council_name
    from admin.discovery_modules.noise_filters import (
        is_single_press_or_notice_url,
        is_non_council_noise,
        normalize_url,
    )
except ImportError:
    from discovery_modules.name_cleaner import get_core_council_name, clean_council_name
    from discovery_modules.noise_filters import (
        is_single_press_or_notice_url,
        is_non_council_noise,
        normalize_url,
    )

def fetch_page_and_final_url(url):
    """
    指定URLへ実際にHTTPアクセスし、転送（リダイレクト）を追跡して
    「最終的な正規URL」およびHTMLテキストを取得する。
    """
    time.sleep(0.35)  # 0.35s rate limit to prevent overloading target servers
    req = urllib.request.Request(
        url,
        headers=get_browser_headers()
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            final_url = res.geturl()  # リダイレクト後の最終正規URL
            content_type = res.headers.get("Content-Type", "")
            html_bytes = res.read()
            html_text = decode_html_bytes(html_bytes, content_type)
            return html_text, final_url
    except Exception as e:
        return None, url


_MINISTRY_COUNCIL_PATH_MARKERS = (
    "/council/", "/councils/", "/shingi/", "/singi/", "/shingikai/",
    "/kaigi/", "/seisaku/", "/stf/shingi", "/shingi2/", "/singi_kento/",
    "/bunkashingikai/", "/iinkai/", "/kentoukai/", "/kondankai/"
)
_PRESS_ONLY_PATH_RE = re.compile(
    r'(?:/report/press/|/press/|/menu_news/s-news/|/news/|/hisho/kouhou/|/houdou/|/koho_hodo_oshirase/|/pressrelease/|/topics/)',
    re.IGNORECASE
)


def _score_candidate_link(abs_u: str, link_text: str, clean_cand: str, cand_kws: tuple, in_breadcrumb: bool = False) -> int:
    """逆引き候補リンクの適合スコアを算出する (CR-189 / Drop 152)"""
    score = 0
    if clean_cand and clean_cand in link_text:
        score += 10
    if any(k in link_text for k in ("開催状況", "議事要旨", "配付資料", "議事録", "検討会", "審議会", "委員会", "会議")):
        score += 5
    if any(marker in abs_u.lower() for marker in _MINISTRY_COUNCIL_PATH_MARKERS):
        score += 3
    if in_breadcrumb and (
        (clean_cand and clean_cand in link_text)
        or any(kw in link_text for kw in cand_kws)
    ):
        score += 4
    return score


def resolve_parent_url_from_press_release(press_url: str, cand_name: str, min_code: str) -> str:
    """
    単発プレスリリースHTML内の関連リンク・パンくずリスト・上位ディレクトリから、
    常設親ページURLを多段自動逆引き探索する (CR-189 / Drop 152)
    親ページが見つかった場合はそのURL、見つからない場合は元の press_url を返す。
    """
    # 単発プレスリリースURL・個別回URLパターンの判定 (Drop 107 / Drop 152)
    is_press_release = bool(
        is_single_press_or_notice_url(press_url) or
        re.search(r'(?:/stf/newpage_\d+\.html|/report/press/|/press/|/menu_news/s-news/|/news/|/hisho/kouhou/|/dai\d+/)', press_url)
    )
    if not is_press_release:
        return press_url

    try:
        from crawler import fetch_url
    except ImportError:
        from admin.crawler import fetch_url

    html = fetch_url(press_url, timeout=10)
    if not html:
        return press_url

    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urlparse(press_url)
    clean_cand = clean_council_name(cand_name)
    cand_kws = ("審議会", "検討会", "委員会", "部会", "分科会", "研究会", "会議", "ワーキンググループ", "タスクフォース")

    # パンくずリスト内の<a>要素を事前収集 (Drop 152)
    breadcrumb_anchors = set()
    for bc in soup.select('nav[aria-label*="breadcrumb"], nav[aria-label*="パンくず"], .breadcrumb, .breadcrumbs, #topicPath, .topicpath, .pankuzu'):
        for a in bc.find_all("a", href=True):
            breadcrumb_anchors.add(id(a))

    best_url = None
    best_score = -1

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        abs_u = urljoin(press_url, href)
        parsed_target = urlparse(abs_u)

        # 同一ホスト限定 (外部ドメインやSNS等は除外)
        if parsed_target.netloc.lower() != parsed_base.netloc.lower():
            continue

        # PDF・Office文書等のバイナリ/添付ファイル直リンクは親ページ候補から除外
        if re.search(r'\.(?:pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip|csv)$', parsed_target.path or '', re.IGNORECASE):
            continue

        # プレスリリース自体の再リンクやアーカイブ除外
        if is_single_press_or_notice_url(abs_u):
            continue

        link_text = a.get_text(strip=True)
        # ノイズ文字列の除外
        if is_non_council_noise(link_text, url=abs_u):
            continue

        score = _score_candidate_link(
            abs_u, link_text, clean_cand, cand_kws, in_breadcrumb=(id(a) in breadcrumb_anchors)
        )
        if score > best_score and score >= 5:
            best_score = score
            best_url = abs_u

    if best_url:
        return best_url

    # フォールバック (Drop 152): 報道発表専用パス以外の個別ページなら1階層上のディレクトリ index.html を実在確認
    if not _PRESS_ONLY_PATH_RE.search(parsed_base.path or ""):
        path_parts = [p for p in (parsed_base.path or "").split("/") if p]
        if len(path_parts) >= 2:
            parent_dir = "/" + "/".join(path_parts[:-1]) + "/"
            if len(path_parts) >= 3 and re.match(r'^(?:dai\d+|kai\d+|\d+|r\d+_\d+)$', path_parts[-2], re.I) and path_parts[-1].endswith((".html", ".htm")):
                parent_dir = "/" + "/".join(path_parts[:-2]) + "/"
            parent_cand_url = f"{parsed_base.scheme}://{parsed_base.netloc}{parent_dir}index.html"
            if parent_cand_url.rstrip("/") != press_url.rstrip("/") and not is_single_press_or_notice_url(parent_cand_url):
                p_html = fetch_url(parent_cand_url, timeout=8)
                if p_html:
                    p_soup = BeautifulSoup(p_html, "html.parser")
                    title_parts = []
                    if p_soup.title and p_soup.title.string:
                        title_parts.append(p_soup.title.string)
                    for h in p_soup.find_all(["h1", "h2"], limit=3):
                        title_parts.append(h.get_text(" ", strip=True))
                    combined_h = " ".join(title_parts)
                    if (clean_cand and clean_cand in combined_h) or any(kw in combined_h for kw in cand_kws):
                        return parent_cand_url

    return press_url
