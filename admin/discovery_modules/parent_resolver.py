# -*- coding: utf-8 -*-
"""
parent_resolver.py:
プレスリリース・報道発表ページから常設親ページURLへの逆引き (Drop 116)
"""

import re
import urllib.request
import urllib.parse
import ssl
from typing import Optional, Tuple
from bs4 import BeautifulSoup

try:
    from admin.crawler_modules.http_client import fetch_html_page
except ImportError:
    from crawler_modules.http_client import fetch_html_page

try:
    from admin.discovery_modules.name_cleaner import get_core_council_name
    from admin.discovery_modules.noise_filters import (
        is_single_press_or_notice_url,
        is_non_council_noise,
        normalize_url,
    )
except ImportError:
    from discovery_modules.name_cleaner import get_core_council_name
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


def resolve_parent_url_from_press_release(press_url: str, cand_name: str, min_code: str) -> str:
    """
    単発プレスリリースHTML内の関連リンクから、常設親ページURLを1ホップ自動逆引き探索する (CR-189)
    親ページが見つかった場合はそのURL、見つからない場合は元の press_url を返す。
    """
    # 単発プレスリリースURLパターンの判定 (Drop 107)
    is_press_release = bool(
        is_single_press_or_notice_url(press_url) or
        re.search(r'(?:/stf/newpage_\d+\.html|/report/press/|/press/|/menu_news/s-news/|/news/|/hisho/kouhou/)', press_url)
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

    best_url = None
    best_score = -1

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        abs_u = urljoin(press_url, href)
        parsed_target = urlparse(abs_u)

        # 同一省庁ドメインのみ対象
        if parsed_target.netloc.lower() != parsed_base.netloc.lower():
            continue
        # ドキュメント直リンクや別プレスリリースは除外
        if re.search(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip)$", abs_u, re.I):
            continue
        if abs_u == press_url or is_single_press_or_notice_url(abs_u) or re.search(r'(?:/stf/newpage_\d+|/report/press/|/press/|/menu_news/s-news/)', abs_u):
            continue

        link_text = a.get_text(separator=" ", strip=True)
        link_title = a.get("title", "").strip()
        combined_text = f"{link_text} {link_title}"

        score = 0
        # 会議体名そのものを含むリンク
        if clean_cand and clean_cand in combined_text:
            score += 10
        # 常設ディレクトリパターンを含む (Drop 107: 主要省庁常設パス拡充)
        if re.search(r'/(?:shingikai|seisakunitsuite|council|singi|policy|councils|b_menu/shingi|koku|maritime|road|jutakukentiku|toshi|mizukokudo|sogoseisaku|tetudo|jidosha|port|tochi_fudousan_kensetsugyo|nature)/', abs_u):
            score += 5
        # リンク文言に親ページ示唆語句を含む
        if any(w in combined_text for w in ["開催状況", "過去の開催", "審議会等", "検討会はこちら", "ホームページはこちら", "会議資料"]):
            score += 3

        if score > best_score and score >= 5:
            best_score = score
            best_url = abs_u

    return best_url or press_url

