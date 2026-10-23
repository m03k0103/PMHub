#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 審議会・会議体ディスカバリーエンジン (Council Discovery Engine)
省庁の審議会等一覧ページURL (councilsUrls) や新着ポータル (MINISTRY_NEWS_PORTALS) を巡回し、
そこに含まれるすべての会議体（本体、部会、分科会、検討会等）の個別のトップページURLを特定し、
独立した会議体レコードとして自動検出・登録する。
"""

import sys
import os
import json
import re
import io
import urllib.request
import urllib.parse
import time
from datetime import datetime
from bs4 import BeautifulSoup
import concurrent.futures
from urllib.parse import urljoin, urlparse

from utils import (
    setup_win32_utf8, get_browser_headers, save_data_json_with_backup,
    decode_html_bytes, load_rejected_councils, load_data_json, normalize_url_for_matching
)
setup_win32_utf8()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "docs", "data.json")

# 非会議体ノイズキーワード・パターン定義 (CR-187)
NOISE_PERSON_ROLES = r"(?:大臣|副大臣|政務官|長官|総理|知事|教授|名誉教授|代表|委員)"
NOISE_ACTION_PATTERNS = [
    re.compile(rf"{NOISE_PERSON_ROLES}が"),
    re.compile(rf"{NOISE_PERSON_ROLES}と.*(?:会談|面会|意見交換|表敬)"),
    re.compile(r"大臣発言"),
    re.compile(r"(?:意見交換|研究課題発表)を(?:実施|行い)"),
    re.compile(r"日本人初】"),
]

NOISE_INTERNATIONAL_AND_ORGS = [
    # 国際機関・国際会議・条約会合
    "世銀", "IMF", "FATF", "金融活動作業部会", "国際通貨金融委員会", "WTO", "CITES", "ワシントン条約",
    "生物多様性条約", "気候変動枠組条約", "締約国会議", "国連総会", "国連犯罪防止", "国連国際商取引",
    "国際かんがい排水", "日米合同委員会", "日米政府の戦略的投資", "日米サイバー", "日米加", "日・ベトナム",
    "日ロ漁業", "北太平洋漁業", "アジア・アフリカ法律", "アジア矯正", "海運先進国", "ウクライナ汚職",
    "世界保護司", "欧州委員会", "大韓民国", "フィンランド", "豪州政府", "プレCOP",
    # 国会・政党・一般法人
    "参議院", "衆議院", "自由民主党", "一般社団法人", "公益社団法人", "公益財団法人", "独立行政法人", "株式会社"
]
NOISE_INTERNATIONAL_REGEX = re.compile(
    r"(?:COP\d+|" + "|".join(re.escape(k) for k in NOISE_INTERNATIONAL_AND_ORGS) + r")"
)

NOISE_PORTAL_EXACT = {
    "政策・審議会", "省議・審議会", "審議会・委員会", "審議会等", "政策・審議会等", "省議・審議会等",
    "政策・審議会等トップへ", "各種本部・会議等の活動情報", "本審議会 トップページ", "公害等調整委員会",
    "中央環境審議会", "法制審議会会議", "審議会情報", "度"
}


def load_keywords():
    data = load_data_json(DATA_JSON_PATH)
    if data and "discoveryKeywords" in data:
        return data["discoveryKeywords"]
    return {
        "commonKeywords": ["審議会", "検討会", "委員会", "部会", "分科会", "懇談会", "ワーキンググループ", "ワーキング・グループ", "スタディグループ", "スタディ・グループ", "WG", "SG", "審査会", "研究会", "プロジェクトチーム", "タスクフォース", "有識者会議", "本部", "推進会議", "円卓会議", "会議"],
        "commonExcludeKeywords": ["過去", "名簿", "委員名簿", "議事録", "議事要旨", "資料一覧", "配付資料", "法令", "設置根拠", "傍聴", "更新履歴", "PDF", "Excel", "プライバシーポリシー"],
        "ministryAddKeywords": {},
        "ministryExcludeKeywords": {}
    }

def parse_data_json():
    """docs/data.json から MINISTRIES, COUNCILS, CATEGORIES, SCRAPING_RULES のデータを抽出する"""
    data = load_data_json(DATA_JSON_PATH)
    if not data:
        print(f"[ERROR] {DATA_JSON_PATH} の読み込みに失敗しました。", file=sys.stderr)
        return {}, [], {}, {}

    ministries = data.get("ministries", {})
    councils = data.get("councils", [])
    categories = data.get("categories", {})
    scraping_rules = data.get("scrapingRules", {})
    return ministries, councils, categories, scraping_rules

def infer_council_category(name_or_text, defined_categories=None):
    """
    会議体名称またはリンクテキストから、定義済み categories に合致するカテゴリIDを判定。
    戻り値: (category_id, is_default_fallback)
    """
    text = name_or_text or ""
    # 優先度の高い特定キーワードから順に判定
    if "専門調査会" in text or "専門委員会" in text or "専門審査会" in text:
        cat = "EXPERT_COMMITTEE"
    elif "特別委員会" in text:
        cat = "SPECIAL_COMMITTEE"
    elif "タスクフォース" in text or "TF" in text:
        cat = "TASKFORCE"
    elif "分科会" in text:
        cat = "SUBCOMMITTEE"
    elif "部会" in text:
        cat = "SECTION"
    elif "ワーキンググループ" in text or "ワーキング・グループ" in text or "作業部会" in text or "作業班" in text or "WG" in text:
        cat = "WORKING_GROUP"
    elif "有識者会議" in text:
        cat = "PANEL"
    elif "懇談会" in text:
        cat = "ROUNDTABLE"
    elif "スタディグループ" in text or "スタディ・グループ" in text or "SG" in text or "検討会" in text or "研究会" in text or "検討会議" in text or "協議会" in text:
        cat = "STUDY"
    elif "関係閣僚会議" in text or "連絡会議" in text:
        cat = "LIAISON"
    elif "推進本部" in text or "本部" in text or "推進会議" in text:
        cat = "HQ"
    elif "諮問会議" in text:
        cat = "ADVISORY"
    elif "審査会" in text or "委員会" in text:
        cat = "COMMITTEE"
    elif "審議会" in text or "会合" in text:
        cat = "COUNCIL"
    else:
        cat = "COUNCIL"
        return (cat, True)
    
    if defined_categories and cat not in defined_categories:
        return ("COUNCIL", True)
    return (cat, False)

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

def clean_council_name(name):
    """
    「第X回」や日付プレフィックス、末尾の「配布資料」「議事概要」などを除去して
    親会議体名（1つの会議体レコード）を抽出する。(CR-186)
    """
    if not name:
        return ""
    try:
        from crawler import normalize_text
    except ImportError:
        from admin.crawler import normalize_text
    n = normalize_text(name).strip()
    
    # 0. 省庁カテゴリ・ラベルプレフィックスの除去 (CR-186)
    n = re.sub(r'^(?:審議会等|報道発表|会議等|その他|国際政策|財総研|お知らせ|新着情報|トピックス|プレスリリース)[\s　:：]+', '', n)
    
    # 1. 日付・更新ラベル・年度・期数プレフィックスの除去 (CR-186)
    n = re.sub(r'^(?:〈[^〉]+〉|＜[^＞]+＞|【[^】]+】|\[[^\]]+\])(?:\s*[(（]更新[)）])?\s*', '', n)
    n = re.sub(r'^(?:令和|平成)\s*[0-9０-９一-九元]+\s*年\s*[0-9０-９一-九]+\s*月\s*[0-9０-９一-九]+\s*日(?:開催)?\s*', '', n)
    n = re.sub(r'^(?:令和|平成)\s*[0-9０-９一-九元]+\s*年度\s*', '', n)
    n = re.sub(r'^\b\d{4}\s*年度\s*', '', n)
    n = re.sub(r'^第\s*[0-9０-９一-九]+\s*期\s*', '', n)
    n = re.sub(r'^(?:第[0-9０-９一-九]+回|第[0-9０-９一-九]+回\s*)\s*', '', n)
    
    # 2. 括弧付き回数・開催案内の除去
    n = re.sub(r'[（(]第[0-9０-９一-九]+回.*?[）)]', '', n)
    n = re.sub(r'【\d+月\d+日開催】', '', n)
    n = re.sub(r'【\d{4}/\d{1,2}/\d{1,2}開催】', '', n)
    
    # 3. 中間・末尾の回数・議事概要の除去
    n = re.sub(r'\s*第[0-9０-９一-九]+回.*', '', n)
    n = re.sub(r'\s*(?:の開催について|開催について|の開催案内|開催案内).*', '', n)
    n = re.sub(r'\s*(?:報告書について|報告書).*', '', n)
    n = re.sub(r'\s*(?:配布資料|配付資料|取りまとめ.*|について|開催概要|議事要旨|議事録|議事次第|議事概要)$', '', n)

    # 4. 前後の孤立括弧・空白の補正
    # ※末尾の閉じていない括弧（例: "恩給審査会（平成21年度廃止前"）も除去できるように配慮
    n = re.sub(r'^[「『【\[\(（\s]+', '', n)
    n = re.sub(r'[」』】\]\)）\s]+$', '', n)
    
    return n.strip()

def get_core_council_name(name: str) -> str:
    """
    表記揺れ（空白、全角半角、年度、期数、「について」、括弧補足）を除去した
    正規化コア名称を生成する (CR-188)。
    """
    if not name:
        return ""
    try:
        from crawler import normalize_text
    except ImportError:
        from admin.crawler import normalize_text
    c = normalize_text(name).strip()
    # 括弧内の補足を除去 (例: （令和8年～）, (平成21年度廃止前), （京都コングレス）)
    c = re.sub(r'[（(][^）)]*[）)]?', '', c)
    c = clean_council_name(c)
    # 先頭の年度・期数
    c = re.sub(r'^(?:令和|平成|\d{4})\S*年度?\s*', '', c)
    c = re.sub(r'^第\s*\d+\s*期\s*', '', c)
    # 末尾の「について」
    c = re.sub(r'について$', '', c)
    # 空白、中黒、記号を除去
    c = re.sub(r'[\s　・~～―－\-_:：/／()（）]', '', c)
    return c.strip().lower()

def is_non_council_noise(name: str, raw_text: str = "", url: str = "") -> bool:
    """
    非会議体ノイズ（大臣動静・国際会議・条約会合・国会・一般法人・ナビ要素・PDF直リンク）を判定 (CR-187)
    """
    text_check = f"{name} {raw_text}".strip()
    clean_name = clean_council_name(name)

    # 1. 最小文字数ガード (4文字未満は除外, 例: '度')
    if len(clean_name) < 4:
        return True

    # 2. 完全一致ポータル・ナビ名称
    if clean_name in NOISE_PORTAL_EXACT or name.strip() in NOISE_PORTAL_EXACT:
        return True

    # 3. ナビゲーション・個別ヒアリング末尾・パターン
    if re.search(r"(?:トップページ|トップへ|活動情報|主査ヒアリング|公聴会|意見募集)$", clean_name):
        return True
    if re.search(r"^(?:政策・審議会|省議・審議会|審議会・委員会|審議会等)", clean_name):
        return True

    # 4. 人物・大臣動静・イベントアクション判定
    for pat in NOISE_ACTION_PATTERNS:
        if pat.search(text_check):
            return True

    # 5. 国際会議・条約会合・国会・一般法人判定
    if NOISE_INTERNATIONAL_REGEX.search(text_check):
        return True

    # 6. PDF/ドキュメント直リンクURLの除外
    if url and re.search(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip)$", url, re.I):
        return True

    return False


def normalize_url(url):
    """URLの末尾スラッシュやフラグメント(#)を除去して正規化"""
    if not url:
        return ""
    p = urllib.parse.urlparse(url)
    clean_path = p.path.rstrip("/")
    return f"{p.scheme}://{p.netloc}{clean_path}"

def get_url_clean_key(url):
    """http/https や末尾スラッシュ、クエリ、フラグメントを除去したURLの比較キーを生成"""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return f"{netloc}{path}"
    except Exception:
        return url.strip().lower()

def get_max_seq(councils):
    """既存COUNCILSから最大のID連番を取得する (例: cao-184 -> 184)"""
    max_num = 183
    for c in councils:
        cid = c.get("id", "")
        num_m = re.search(r"-(\d+)$", cid)
        if num_m:
            try:
                n = int(num_m.group(1))
                if n > max_num:
                    max_num = n
            except ValueError:
                pass
    return max_num

def extract_council_name_from_news_title(title: str, keywords: list) -> str:
    """ニュース記事タイトルから会議体名称を抽出・クレンジング (CR-186)"""
    try:
        from crawler import normalize_text
    except ImportError:
        from admin.crawler import normalize_text
    t = normalize_text(title).strip()

    # 0. 省庁カテゴリラベルの除去 (CR-186)
    t = re.sub(r'^(?:審議会等|報道発表|会議等|その他|国際政策|財総研|お知らせ|新着情報|トピックス|プレスリリース)[\s　:：]+', '', t)

    # 0.5 サブタイトル・キャッチコピー区切りの分割 (CR-186)
    # 例: 「上下水道政策の基本的な方向性を議論します~上下水道政策の基本的なあり方検討会」 -> 後半を優先
    sub_delim_m = re.search(r'[~～―－](?=[^~～―－]+(?:' + '|'.join(re.escape(k) for k in keywords) + r'))', t)
    if sub_delim_m:
        t = t[sub_delim_m.end():].strip()

    # 1. 鉤括弧「」『』【】内の会議体名を優先抽出
    brackets = re.findall(r'[「『【]([^」』】]+)[」』】]', t)
    for b in brackets:
        b_clean = clean_council_name(b)
        if any(kw in b_clean for kw in keywords) and len(b_clean) >= 4:
            return b_clean

    # 2. 接尾辞や開催案内語句の除去
    t_clean = clean_council_name(t)

    # 3. 会議体キーワードを含む部分の切り出し (末尾までの探索)
    for kw in sorted(keywords, key=len, reverse=True):
        pos = t_clean.find(kw)
        if pos != -1:
            cand = t_clean[:pos + len(kw)].strip()
            cand = clean_council_name(cand)
            if len(cand) >= 4 and any(k in cand for k in keywords):
                return cand

    return ""


def resolve_parent_url_from_press_release(press_url: str, cand_name: str, min_code: str) -> str:
    """
    単発プレスリリースHTML内の関連リンクから、常設親ページURLを1ホップ自動逆引き探索する (CR-189)
    親ページが見つかった場合はそのURL、見つからない場合は元の press_url を返す。
    """
    # 単発プレスリリースURLパターンの判定
    is_press_release = bool(re.search(
        r'(?:/stf/newpage_\d+\.html|/report/press/|/press/|/menu_news/s-news/|/news/|/hisho/kouhou/)',
        press_url
    ))
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
        if abs_u == press_url or re.search(r'(?:/stf/newpage_\d+|/report/press/|/press/|/menu_news/s-news/)', abs_u):
            continue

        link_text = a.get_text(separator=" ", strip=True)
        link_title = a.get("title", "").strip()
        combined_text = f"{link_text} {link_title}"

        score = 0
        # 会議体名そのものを含むリンク
        if clean_cand and clean_cand in combined_text:
            score += 10
        # 常設ディレクトリパターンを含む
        if re.search(r'/(?:shingikai|seisakunitsuite|council|singi|policy|councils|b_menu/shingi)/', abs_u):
            score += 5
        # リンク文言に親ページ示唆語句を含む
        if any(w in combined_text for w in ["開催状況", "過去の開催", "審議会等", "検討会はこちら", "ホームページはこちら", "会議資料"]):
            score += 3

        if score > best_score and score >= 5:
            best_score = score
            best_url = abs_u

    return best_url or press_url


def is_already_registered_or_rejected(
    cand_name: str, cand_url: str, min_code: str,
    existing_names: set, existing_urls: set, existing_core_names: set, existing_councils_by_min: dict,
    rejected_names: set, rejected_urls: set, rejected_core_names: set, rejected_clean_keys: set
) -> bool:
    """
    完全一致に加え、正規化コア名称および同一省庁内の部会サフィックス一致で既存・却下判定 (CR-188)
    """
    clean_name = clean_council_name(cand_name)
    core_name = get_core_council_name(cand_name)
    norm_url = normalize_url(cand_url)
    clean_key = get_url_clean_key(cand_url)

    # 1. URLによる突合
    if norm_url in existing_urls or (clean_key and clean_key in rejected_clean_keys):
        return True
    if norm_url in rejected_urls:
        return True

    # 2. 完全一致名称による突合
    if cand_name in existing_names or clean_name in existing_names:
        return True
    if cand_name in rejected_names or clean_name in rejected_names:
        return True

    # 3. 正規化コア名称（Core Name）による突合
    if core_name:
        if core_name in existing_core_names:
            return True
        if core_name in rejected_core_names:
            return True

    # 4. 同一省庁内の「親審議会名＋部会・分科会・委員会名」サフィックス一致判定 (CR-188)
    # 例: cand_name = '電波利用環境委員会' -> 既存 '情報通信審議会 情報通信技術分科会 電波利用環境委員会'
    if min_code and len(clean_name) >= 5:
        min_existing = existing_councils_by_min.get(min_code.upper(), [])
        for c in min_existing:
            ex_name = c.get("name", "")
            if ex_name.endswith(clean_name) or clean_name.endswith(ex_name):
                return True

    return False


def _discover_from_ministry_news(
    emit, target_ministry, ministries, existing_councils,
    categories_def, url_to_slug_map, existing_urls, existing_names,
    rejected_names, rejected_urls, rejected_clean_keys, common_keywords, next_seq,
    used_council_ids
):
    try:
        from crawler import (
            MINISTRY_NEWS_PORTALS, resolve_news_portal_urls,
            extract_news_items_from_html, fetch_url,
            match_council_from_news_item, normalize_text
        )
    except ImportError:
        from admin.crawler import (
            MINISTRY_NEWS_PORTALS, resolve_news_portal_urls,
            extract_news_items_from_html, fetch_url,
            match_council_from_news_item, normalize_text
        )

    target_mins = [target_ministry.upper()] if target_ministry else list(MINISTRY_NEWS_PORTALS.keys())
    total_ministries = len(target_mins)
    emit(f"走査対象府省庁: {', '.join(target_mins)} (計 {total_ministries} 省庁)")

    councils_by_min = {}
    councils_by_url = {}
    existing_core_names = set()
    for c in existing_councils:
        m = c.get("ministry", "")
        councils_by_min.setdefault(m, []).append(c)
        if c.get("officialUrl"):
            councils_by_url[c.get("officialUrl").rstrip("/")] = c
        if c.get("name"):
            core_k = get_core_council_name(c.get("name"))
            if core_k:
                existing_core_names.add(core_k)

    rejected_core_names = {get_core_council_name(rn) for rn in rejected_names if get_core_council_name(rn)}

    search_kws = common_keywords + ["会議", "有識者会議", "タスクフォース", "プロジェクトチーム", "協議会"]
    discovered_list = []
    seen_in_this_run = set()
    category_counts = {}

    for current_min_idx, min_code in enumerate(target_mins, start=1):
        portal_defs = MINISTRY_NEWS_PORTALS.get(min_code, [])
        if not portal_defs:
            continue

        min_name = ministries.get(min_code, {}).get("name", min_code)
        pct = int((current_min_idx / max(total_ministries, 1)) * 90)
        emit(f"\n[{current_min_idx}/{total_ministries}] {min_name} ({min_code}) 新着・報道発表ポータルを走査中...", {
            "type": "ministry_start",
            "progress": pct,
            "current": current_min_idx,
            "total": total_ministries,
            "ministry": min_code,
            "ministryName": min_name
        })

        found_in_min = 0
        for pdef in portal_defs:
            resolved_urls = resolve_news_portal_urls(pdef)
            for rurl in resolved_urls:
                html = fetch_url(rurl, timeout=12)
                if not html:
                    continue
                items = extract_news_items_from_html(html, rurl, min_code, pdef.get("type"))
                for item in items:
                    raw_title = item.get("title", "")
                    cand_name = extract_council_name_from_news_title(raw_title, search_kws)
                    if not cand_name or len(cand_name) < 4:
                        continue

                    # ノイズ判定 (CR-187)
                    if is_non_council_noise(cand_name, raw_title, item.get("url", "")):
                        continue

                    # 既存・却下判定 (CR-188)
                    if is_already_registered_or_rejected(
                        cand_name, item.get("url", ""), min_code,
                        existing_names, existing_urls, existing_core_names, councils_by_min,
                        rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
                    ):
                        continue

                    key_pair = (min_code, get_core_council_name(cand_name))
                    if key_pair in seen_in_this_run:
                        continue
                    seen_in_this_run.add(key_pair)

                    # 単発プレスリリースからの常設親ページURL自動逆引き (CR-189)
                    resolved_url = resolve_parent_url_from_press_release(item.get("url", ""), cand_name, min_code)
                    if resolved_url != item.get("url", ""):
                        # 逆引き後のURLで既存・却下を再チェック
                        if is_already_registered_or_rejected(
                            cand_name, resolved_url, min_code,
                            existing_names, existing_urls, existing_core_names, councils_by_min,
                            rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
                        ):
                            continue

                    category, _ = infer_council_category(f"{cand_name} {raw_title}", categories_def)
                    category_counts[category] = category_counts.get(category, 0) + 1

                    norm_item_url = normalize_url_for_matching(resolved_url)
                    inherited_slug = url_to_slug_map.get(norm_item_url)
                    if inherited_slug and inherited_slug not in used_council_ids:
                        council_id = inherited_slug
                        action_label = "既存スラグID継承"
                    else:
                        council_id = f"{min_code.lower()}-{next_seq}"
                        while council_id in used_council_ids:
                            next_seq += 1
                            council_id = f"{min_code.lower()}-{next_seq}"
                        next_seq += 1
                        action_label = "新規会議体検出"

                    used_council_ids.add(council_id)

                    council_item = {
                        "id": council_id,
                        "name": cand_name,
                        "ministry": min_code,
                        "category": category,
                        "officialUrl": resolved_url,
                        "isNew": True
                    }
                    discovered_list.append(council_item)
                    found_in_min += 1
                    cat_label = categories_def.get(category, category)
                    emit(f"      ✨ [{action_label}] [{cat_label}] {council_id}: {cand_name} -> {resolved_url}", {
                        "type": "council_discovered",
                        "council": council_item
                    })

        emit(f"   -> 検出数: {found_in_min} 件")

    return discovered_list, category_counts


def _discover_normal_for_single_ministry(
    min_code, min_info, add_kw, exc_kw, common_keywords,
    categories_def, url_to_slug_map, existing_urls, existing_names, existing_core_names, councils_by_min,
    rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys,
    resolved_url_cache
):
    """
    1省庁分の通常審議会一覧巡回タスク (並列ワーカー対応・同一省庁内は直列かつディレイ遵守) (CR-190)
    """
    councils_urls = min_info.get("councilsUrls", [])
    target_kw = common_keywords + add_kw
    discovered_in_min = []
    seen_in_min = set()

    for page_url in councils_urls:
        page_url = page_url.strip()
        if not page_url or not page_url.startswith("http"):
            continue

        html, final_page_url = fetch_page_and_final_url(page_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=True)

        for a in links:
            href = a["href"].strip()
            raw_text = a.get_text(separator=" ", strip=True)
            title_attr = a.get("title", "").strip()
            link_text = raw_text or title_attr

            if not link_text or len(link_text) < 3 or len(link_text) > 100:
                continue

            if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                continue

            # キーワード照合
            if not any(kw in link_text for kw in target_kw):
                continue
            # 除外キーワード照合
            if any(ex in link_text for ex in exc_kw):
                continue

            # 絶対URLに変換
            abs_url = urllib.parse.urljoin(final_page_url, href)

            # ノイズ・ドキュメント直リンク判定 (CR-187)
            if is_non_council_noise(link_text, "", abs_url):
                continue

            # 会議体名のクレンジング (CR-186)
            is_meet_pat = bool(re.search(r'[(（]?第\s*[0-9０-９一-九]+\s*回[)）]?', link_text))
            cand_name = clean_council_name(link_text) if is_meet_pat else link_text.strip()
            if not cand_name or len(cand_name) < 4:
                continue

            if is_non_council_noise(cand_name, link_text, abs_url):
                continue

            # HTTPアクセス前の事前フィルタ (CR-190)
            if is_already_registered_or_rejected(
                cand_name, abs_url, min_code,
                existing_names, existing_urls, existing_core_names, councils_by_min,
                rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
            ):
                continue

            core_k = get_core_council_name(cand_name)
            if core_k in seen_in_min:
                continue

            # HTTPアクセスして最終正規URLを取得（キャッシュ活用）
            if abs_url in resolved_url_cache:
                final_council_url = resolved_url_cache[abs_url]
            else:
                _, final_council_url = fetch_page_and_final_url(abs_url)
                if not final_council_url:
                    final_council_url = abs_url
                resolved_url_cache[abs_url] = final_council_url

            # 最終URLでの既存・却下判定
            if is_already_registered_or_rejected(
                cand_name, final_council_url, min_code,
                existing_names, existing_urls, existing_core_names, councils_by_min,
                rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
            ):
                continue

            seen_in_min.add(core_k)

            category, is_default = infer_council_category(f"{cand_name} {link_text}", categories_def)

            # target_url_cand の決定 (CR-191: 一覧URL強制上書きバグを廃止)
            target_url_cand = final_council_url

            discovered_in_min.append({
                "cand_name": cand_name,
                "link_text": link_text,
                "target_url_cand": target_url_cand,
                "category": category,
                "is_default": is_default,
                "min_code": min_code
            })

    return min_code, discovered_in_min


def run_discovery(progress_callback=None, target_ministry=None, dry_run=False, mode="normal"):
    def emit(msg, data=None):
        print(msg)
        if progress_callback:
            try:
                progress_callback(msg, data)
            except Exception:
                pass

    emit("=" * 70)
    emit(f"【PM-HUB】省庁 審議会・会議体ディスカバリー巡回 開始 (モード: {'省庁新着検知' if mode == 'ministry_news' else '通常一覧巡回'})")
    if mode == "ministry_news":
        emit("（各府省庁トップページ・報道発表ポータルから新設された検討会・会議体を検知します）")
    else:
        emit("（審議会等ページにアクセスし、全会議体を個別の正規URLで独立検出します）")
    if target_ministry:
        emit(f"巡回対象省庁フィルター: {target_ministry.upper()}")
    if dry_run:
        emit("動作モード: DRY RUN（data.json への書き込みなし）")
    emit(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit("=" * 70)

    keywords_cfg = load_keywords()
    common_keywords = keywords_cfg.get("commonKeywords", [])
    common_excludes = keywords_cfg.get("commonExcludeKeywords", [])
    min_add_kw = keywords_cfg.get("ministryAddKeywords", {})
    min_exc_kw = keywords_cfg.get("ministryExcludeKeywords", {})

    ministries, existing_councils, categories_def, scraping_rules = parse_data_json()
    emit(f"登録済み省庁数: {len(ministries)} 組織, 既存会議体数: {len(existing_councils)} 件, カテゴリー定義数: {len(categories_def)} 種類\n")

    # 全省庁の審議会一覧トップURL（councilsUrls）のセット (CR-191: スラグ継承汚染防止)
    all_portal_urls = set()
    for min_info in ministries.values():
        for u in min_info.get("councilsUrls", []):
            if u:
                all_portal_urls.add(normalize_url_for_matching(u))
                all_portal_urls.add(normalize_url(u))

    # CR-92 / CR-191: 既存URL -> スラグIDマップの構築（審議会一覧ポータルURLは除外）
    url_to_slug_map = {}
    for c in existing_councils:
        cid = c.get("id")
        if not cid:
            continue
        for u in (c.get("officialUrl"), c.get("url"), c.get("archiveUrl")):
            if u and isinstance(u, str):
                nu = normalize_url_for_matching(u)
                if nu and nu not in url_to_slug_map and nu not in all_portal_urls:
                    url_to_slug_map[nu] = cid

    for cid, r in scraping_rules.items():
        if not isinstance(r, dict):
            continue
        for u in (r.get("officialUrl"), r.get("target_url"), r.get("url"), r.get("archiveUrl")):
            if u and isinstance(u, str):
                nu = normalize_url_for_matching(u)
                if nu and nu not in url_to_slug_map and nu not in all_portal_urls:
                    url_to_slug_map[nu] = cid
    emit(f"既存スラグID照合用URLインデックス: {len(url_to_slug_map)} 件を構築しました（スラグID自動継承）")

    # 却下済み会議体データの読み込み（再検出・再登録をブロック）
    rejected_data = load_rejected_councils()
    rejected_ids = set()
    rejected_urls = set()
    rejected_clean_keys = set()
    rejected_names = set()
    rejected_core_names = set()
    for rc in rejected_data:
        if rc.get("id"):
            rejected_ids.add(rc.get("id").strip())
        if rc.get("officialUrl"):
            rejected_urls.add(normalize_url(rc.get("officialUrl")))
            clean_k = get_url_clean_key(rc.get("officialUrl"))
            if clean_k:
                rejected_clean_keys.add(clean_k)
        if rc.get("name"):
            n_raw = rc.get("name").strip()
            rejected_names.add(n_raw)
            n_clean = clean_council_name(n_raw)
            if n_clean:
                rejected_names.add(n_clean)
            c_core = get_core_council_name(n_raw)
            if c_core:
                rejected_core_names.add(c_core)
    emit(f"却下済み会議体除外リスト: {len(rejected_data)} 件をロードしました（巡回検出対象外として完全除外）")

    # 既存の会議体URLと名前のセット（重複判定用）
    existing_urls = {normalize_url(c.get("officialUrl", "")) for c in existing_councils if c.get("officialUrl")}
    existing_names = {c.get("name", "").strip() for c in existing_councils if c.get("name")}
    existing_core_names = {get_core_council_name(c.get("name")) for c in existing_councils if c.get("name") and get_core_council_name(c.get("name"))}
    councils_by_min = {}
    for c in existing_councils:
        councils_by_min.setdefault(c.get("ministry", "").upper(), []).append(c)

    next_seq = get_max_seq(existing_councils) + 1
    used_council_ids = {c.get("id") for c in existing_councils if c.get("id")}
    discovered_list = []
    category_counts = {}
    unmatched_category_councils = []

    if mode == "ministry_news":
        discovered_list, category_counts = _discover_from_ministry_news(
            emit, target_ministry, ministries, existing_councils,
            categories_def, url_to_slug_map, existing_urls, existing_names,
            rejected_names, rejected_urls, rejected_clean_keys, common_keywords, next_seq,
            used_council_ids
        )
    else:
        active_ministries = [m for code, m in ministries.items() if m.get("hasCouncils", True) and m.get("councilsUrls") and (not target_ministry or code.upper() == target_ministry.upper())]
        total_ministries = len(active_ministries)
        emit(f"走査対象府省庁: {total_ministries} 省庁 (省庁間並列ワーカー + 事前フィルタ高速化)")

        resolved_url_cache = {}
        tasks = []

        for min_code, min_info in sorted(ministries.items()):
            if target_ministry and min_code.upper() != target_ministry.upper():
                continue
            has_councils = min_info.get("hasCouncils", True)
            councils_urls = min_info.get("councilsUrls", [])
            if not has_councils or not councils_urls:
                continue

            add_kw = min_add_kw.get(min_code, [])
            exc_kw = min_exc_kw.get(min_code, []) + common_excludes
            tasks.append((min_code, min_info, add_kw, exc_kw))

        # 省庁間並列ワーカーで実行 (CR-190)
        max_workers = min(6, len(tasks)) if tasks else 1
        emit(f"並列スレッド数: {max_workers} ワーカーで巡回開始...")

        results_by_min = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_min = {
                executor.submit(
                    _discover_normal_for_single_ministry,
                    t[0], t[1], t[2], t[3], common_keywords,
                    categories_def, url_to_slug_map, existing_urls, existing_names, existing_core_names, councils_by_min,
                    rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys,
                    resolved_url_cache
                ): t[0] for t in tasks
            }
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_min):
                m_code = future_to_min[future]
                completed_count += 1
                try:
                    m_code_ret, disc_items = future.result()
                    results_by_min[m_code_ret] = disc_items
                    m_name = ministries.get(m_code_ret, {}).get("name", m_code_ret)
                    pct = int((completed_count / max(total_ministries, 1)) * 90)
                    emit(f"   [{completed_count}/{total_ministries}] [{m_code_ret}] {m_name} 完了 (候補 {len(disc_items)} 件)", {
                        "type": "ministry_done",
                        "ministry": m_code_ret,
                        "progress": pct
                    })
                except Exception as e:
                    emit(f"   [ERROR] [{m_code}] 巡回中にエラー発生: {e}")

        # 結果の統合とID採番 (CR-191)
        for min_code, min_info in sorted(ministries.items()):
            disc_items = results_by_min.get(min_code, [])
            for item in disc_items:
                cand_name = item["cand_name"]
                link_text = item["link_text"]
                target_url_cand = item["target_url_cand"]
                category = item["category"]
                is_default = item["is_default"]

                category_counts[category] = category_counts.get(category, 0) + 1
                if is_default:
                    unmatched_category_councils.append({
                        "id": None,
                        "name": cand_name,
                        "url": target_url_cand,
                        "ministry": min_code,
                        "appliedCategory": category
                    })

                norm_final_url = normalize_url_for_matching(target_url_cand)
                inherited_slug = url_to_slug_map.get(norm_final_url)

                if inherited_slug and inherited_slug not in used_council_ids:
                    council_id = inherited_slug
                    is_inherited = True
                else:
                    council_id = f"{min_code.lower()}-{next_seq}"
                    while council_id in used_council_ids:
                        next_seq += 1
                        council_id = f"{min_code.lower()}-{next_seq}"
                    next_seq += 1
                    is_inherited = False

                used_council_ids.add(council_id)

                if is_default and unmatched_category_councils:
                    unmatched_category_councils[-1]["id"] = council_id

                council_item = {
                    "id": council_id,
                    "name": cand_name,
                    "ministry": min_code,
                    "category": category,
                    "officialUrl": target_url_cand,
                    "isNew": True
                }

                discovered_list.append(council_item)
                cat_label = categories_def.get(category, category)
                action_label = "既存スラグID継承" if is_inherited else "新規会議体検出"
                emit(f"      ✨ [{action_label}] [{cat_label}] {council_id}: {cand_name} -> {target_url_cand}", {
                    "type": "council_discovered",
                    "council": council_item
                })

    emit("\n" + "=" * 70)
    emit(f"ディスカバリー巡回完了: 合計 {len(discovered_list)} 件の新規会議体レコードを作成しました。")
    emit("-" * 70)
    emit("【新規検出会議体のカテゴリー内訳】")
    if category_counts:
        for cat_id, cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            label = categories_def.get(cat_id, cat_id)
            emit(f"  - {label} ({cat_id}): {cnt} 件")
    else:
        emit("  - 新規検出なし")

    if unmatched_category_councils:
        emit("-" * 70)
        emit(f"⚠️ 【特定カテゴリーに該当せずデフォルト（COUNCIL/審議会）が適用された会議体: {len(unmatched_category_councils)}件】")
        for u in unmatched_category_councils:
            emit(f"  ・ [{u['ministry']}] {u['id']}: {u['name']} -> {u['url']}")
    elif discovered_list:
        emit("-" * 70)
        emit("  ✨ すべての新規会議体が特定の定義済みカテゴリーに分類されました。")
    emit("=" * 70)

    # 結果JSONの保存 (data.json の councils を更新、却下済みを完全パージ)
    if dry_run:
        emit("\n[DRY RUN] dry-run モードのため、data.json への保存はスキップされました。")
        return discovered_list

    data = load_data_json(DATA_JSON_PATH)
    if data:
        try:
            existing_councils = data.get("councils", [])
            existing_dict = {c.get("id"): c for c in existing_councils if c.get("id")}
            
            filtered_existing_dict = {}
            for cid, c in existing_dict.items():
                c_url = normalize_url(c.get("officialUrl", ""))
                c_clean_k = get_url_clean_key(c.get("officialUrl", ""))
                c_name = c.get("name", "").strip()
                c_clean_name = clean_council_name(c_name)

                if (cid in rejected_ids or
                    c_url in rejected_urls or
                    (c_clean_k and c_clean_k in rejected_clean_keys) or
                    c_name in rejected_names or
                    (c_clean_name and c_clean_name in rejected_names)):
                    continue
                filtered_existing_dict[cid] = c

            for new_c in discovered_list:
                cid = new_c.get("id")
                if (cid in rejected_ids or
                    normalize_url(new_c.get("officialUrl", "")) in rejected_urls or
                    get_url_clean_key(new_c.get("officialUrl", "")) in rejected_clean_keys or
                    new_c.get("name", "").strip() in rejected_names):
                    continue

                if cid in filtered_existing_dict:
                    # 既存の会議体はステータスを維持
                    new_c["status"] = filtered_existing_dict[cid].get("status", "approved")
                    new_c["manualLock"] = filtered_existing_dict[cid].get("manualLock", False)
                    new_c["pastYearCount"] = filtered_existing_dict[cid].get("pastYearCount", 0)
                else:
                    new_c["status"] = "pending"
                filtered_existing_dict[cid] = new_c
            
            data["councils"] = list(filtered_existing_dict.values())
            if "discoveredCouncils" in data:
                del data["discoveredCouncils"]

            # CR-92: 新規登録された会議体の scrapingRules 自動連動登録 (AGENTS.md 第5条)
            scraping_rules_in_data = data.setdefault("scrapingRules", {})
            new_rules_count = 0
            for new_c in discovered_list:
                cid = new_c.get("id")
                if cid and cid not in scraping_rules_in_data:
                    scraping_rules_in_data[cid] = {
                        "template": "tpl-cas-gijisidai-nested",
                        "manualLock": True,
                        "officialUrl": new_c.get("officialUrl", ""),
                        "extract_from_parent_table": True
                    }
                    new_rules_count += 1
            if new_rules_count > 0:
                print(f"新規会議体 {new_rules_count} 件に scrapingRules を自動連動登録しました。")
            
            if save_data_json_with_backup(data):
                print(f"結果を data.json の councils に保存しました（自動バックアップ作成完了）。")
            else:
                print(f"[WARN] data.json の保存に失敗しました。")
        except Exception as e:
            print(f"[ERROR] data.json の更新に失敗しました: {e}")
    return discovered_list

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PMHub 審議会・会議体ディスカバリーエンジン")
    parser.add_argument("--ministry", type=str, default=None, help="巡回対象の省庁コード（例: FSA, MOF, METI）")
    parser.add_argument("--dry-run", action="store_true", help="data.json を更新せず、検出結果の表示のみを行う")
    parser.add_argument("--mode", choices=["normal", "ministry_news"], default="normal", help="探索モード (normal: 審議会等一覧巡回, ministry_news: 省庁新着情報検知)")
    parser.add_argument("--from-ministry-news", dest="from_news", action="store_true", help="省庁新着情報・報道発表から新規会議体を検知")
    args = parser.parse_args()
    mode = "ministry_news" if args.from_news or args.mode == "ministry_news" else "normal"
    run_discovery(target_ministry=args.ministry, dry_run=args.dry_run, mode=mode)
