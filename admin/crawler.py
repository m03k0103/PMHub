#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 審議会・会議体情報取得Engine (Information Retrieval Engine)
docs/data.json の会議体マスター (councils) およびスクレイピングルール (scrapingRules) を読み込み、
高速・高精度な階層クロールおよび資料データ取得を実行する専用Engine
"""

import sys
import os
import json
import shutil
import urllib.request
import urllib.parse
import re
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils import (
    setup_win32_utf8, get_browser_headers, save_data_json_with_backup,
    decode_html_bytes, get_rejected_identifiers, normalize_japanese_numbers, load_data_json,
    parse_japanese_date
)
setup_win32_utf8()

# LLM (Gemini API) の遅延初期化キャッシュ
_gemini_model = None

def get_gemini_model():
    """
    LLMフォールバックが必要な場合にのみ初期化する（遅延ロード）。
    通常運用（Heuristicモード）時の起動時間を短縮し、依存警告を抑制する。
    """
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            import google.generativeai as genai
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('gemini-3.8-flash')
        return _gemini_model
    except Exception as e:
        print(f"[WARN] Failed to initialize Gemini model (gemini-3.8-flash): {e}")
        return None


DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "backups"))
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "logs"))

# 無効な日付プレフィックス（旧クローラー残骸などスコアリング対象外の日付パターン）
INVALID_DATE_PREFIXES = ("1312",)

# ジェネリックタイトル・ポータル見出しキーワード（会議名として不適切な汎用文字列）
GENERIC_TITLE_KEYWORDS = frozenset({
    '会議資料詳細', '資料詳細', '会議詳細', 'トップページ', '目次', 'ホーム', '配付資料一覧',
    '政策について', '総務省の紹介', '国立国会図書館インターネット資料収集保存事業（WARP）',
    '国立国会図書館インターネット資料収集保存事業', '議事次第', '配付資料', '配布資料',
    '議題', '資料', '議事', '日時', 'メンバー', '会議資料一覧', '審議会・検討会・研究会等',
    '審議会、検討会、研究会等', '令和３年改正個人情報保護法について', '原子力規制委員会',
    'サイトマップ', '開催案内', '開催について', '１開催日時', '１．日', '●日時', 'お知らせ',
    '新着情報', '１．日時', '１　開催日時', '議事要旨等', 'Interim Report', '共同主催国際会議',
    '議事次第・資料一覧', '配布資料一覧', '配付資料一覧'
})

# 配付資料として不適切な汎用ナビゲーション・UIテキスト（事前除外用定数）
EXCLUDE_MATERIAL_NAMES = frozenset({
    '本文へ移動します', 'フッターへ移動します', '閉じる', 'メニューを閉じる',
    'メニューを開く', 'このページの先頭へ', '前のページへ戻る', '前のページへ',
    '先頭へ戻る', 'ページトップへ', 'ページ先頭へ', 'PAGE TOP', 'Page Top',
    'pagetop', 'トップへ', 'トップ', 'HOME', 'Home', '戻る', '印刷', '印刷する',
    '別ウィンドウで開く', '新しいウィンドウで開く', '（別ウィンドウで開く）',
    'JavaScriptが無効です', 'JavaScriptを有効にしてください'
})

# デフォルトの日付抽出正規表現
DEFAULT_DATE_REGEX = r'(?:令和|平成)(?:\d+|元)年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'

# 汎用インデックス・ポータルURL除外用の事前コンパイル正規表現
_GENERIC_INDEX_URL_PATTERNS = re.compile(
    r'houdou/index\.html|'
    r'houdou/houdou\.html|'
    r'press/index\.html|'
    r'topics/index\.html|'
    r'news/index\.html|'
    r'shingi/index\.html|'
    r'/pressrelease/?$|'
    r'/houdou_topics/?$|'
    r'/houdou/?$|'
    r'comittee/kaisai\.html|'
    r'space/comittee/about\.html|'
    r'/kaisai\.html$|'
    r'indexshingi\.html|'
    r'newpage_19921\.html|'
    r'cas\.go\.jp/jp/s(?:i|hi)ryou?(?:/index\.html)?$|'
    r'cas\.go\.jp/jp/s(?:i|hi)ryou?/|'
    r'cyber/what-we-do/csmeeting\.html|'
    r'/int/kaisai/kako\.html|'
    r'study/dai3sya/index\.html|'
    r'policymeeting/(?:index\.html)?$|'
    r'gijiroku/zeicho/\d{4}/(?:index\.html)?$|'
    r'fsc\.go\.jp/senmon/(?:[^/]+/)?$|'
    r'kanbou_library_library\d+_\d+\.html|'
    r'14th_congress_index\.html|'
    r'menu_sosiki/singi/index\.html|'
    r'sonota_index\.html|'
    r'topics/bukyoku/syakai/soren/|'
    r'bousai\.go\.jp/kohou/oshirase/|'
    r'iinkaisai/iinkaisai\.html|'
    r'bunkakaisai/bunkakaisai\.html|'
    r'yusei_kaisai\.html|'
    r'/kaisai/yusei/|'
    r'menu_news/s-news|'
    r'b_menu/houdou|'
    r'da\.nra\.go\.jp/search\?.*f\.gi=.*f\.gi=|'
    r'digital\.go\.jp/(?:en/)?councils/[^/]+/?$|'
    r'digital\.go\.jp/en/|'
    r'digital\.go\.jp/councils/procurement-agile-opensource/(?:agile|opensource)-review-meeting/?$|'
    r'sitemap(?:\.html|\.xml|/)?$|'
    r'/sitemap/|'
    r'member(?:\.html|/)?$|'
    r'meibo(?:\.html|/)?$',
    re.IGNORECASE
)

# 汎用インデックス判定用の除外タイトルキーワード
_GENERIC_INDEX_TITLE_KEYWORDS = frozenset({
    "その他情報", "覚書等", "覚書", "有識者会議｜警察庁", "過去の国際会議",
    "研究会等一覧へのリンク", "会議資料詳細", "資料詳細", "会議詳細",
    "食の安全、を科学する", "審議会等", "｜デジタル庁", "｜Digital Agency", "Digital Agency"
})


# 省庁コードと公式ドメインのマッピング（他省庁URLの誤混入ガード用）
MINISTRY_DOMAINS = {
    "MHLW": ["mhlw.go.jp"],
    "METI": ["meti.go.jp"],
    "MAFF": ["maff.go.jp"],
    "MOJ": ["moj.go.jp"],
    "CAO": ["cao.go.jp", "scj.go.jp"],
    "CAS": ["cas.go.jp"],
    "NPA": ["npa.go.jp"],
    "FSA": ["fsa.go.jp"],
    "MIC": ["soumu.go.jp"],
    "MOF": ["mof.go.jp"],
    "MEXT": ["mext.go.jp"],
    "MLIT": ["mlit.go.jp"],
    "ENV": ["env.go.jp"],
    "MOD": ["mod.go.jp"],
    "DIGITAL": ["digital.go.jp"],
    "CFA": ["cfa.go.jp"]
}
_OTHER_MINISTRY_DOMAINS_MAP = {
    m: tuple(d for om, dlist in MINISTRY_DOMAINS.items() if om != m for d in dlist)
    for m in MINISTRY_DOMAINS
}

# 429 Quota Exceeded 回避用のサーキットブレーカーフラグ
LLM_QUOTA_BLOCKED = False

def init_crawler_logfile():
    """admin/logs/ ディレクトリに日時付きログファイルと latest ログファイルを初期化してファイルオブジェクトを返す"""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"crawler_{ts}.log"
        log_filepath = os.path.join(LOGS_DIR, log_filename)
        latest_filepath = os.path.join(LOGS_DIR, "crawler_latest.log")
        
        log_f = open(log_filepath, "a", encoding="utf-8")
        latest_f = open(latest_filepath, "w", encoding="utf-8")
        return log_f, latest_f, log_filepath, latest_filepath
    except Exception as e:
        print(f"[WARN] Failed to initialize log file: {e}", file=sys.stderr)
        return None, None, "", ""

def load_crawler_config():
    data = load_data_json(DATA_JSON_FILE)
    config = data.get("crawlerConfig", {})
    return config.get("llm_mode", False)  # デフォルトは高速・安全な Heuristic モード

def load_councils_from_data_json():
    """docs/data.json から登録済みの全会議体 (COUNCILS) を読み込む（却下済み会議体・非アクティブ会議体はクロール対象外）"""
    councils = []
    
    # 却下済みIDセットの読み込み
    rejected_ids, _, _ = get_rejected_identifiers()
    print(f"[INFO] 却下済み会議体 {len(rejected_ids)} 件をクロール対象から除外します。")

    data = load_data_json(DATA_JSON_FILE)
    raw_councils = data.get("councils", [])
    scraping_rules = data.get("scrapingRules", {})
    inactive_count = 0
    for item in raw_councils:
        cid = item.get("id")
        if cid in rejected_ids:
            continue
        # 会議体マスターまたはスクレイピングルールで非アクティブ指定されている場合はスキップ
        rule = scraping_rules.get(cid, {}) if isinstance(scraping_rules, dict) else {}
        if (
            item.get("is_active") is False
            or item.get("isActive") is False
            or (isinstance(rule, dict) and (rule.get("is_active") is False or rule.get("isActive") is False))
        ):
            inactive_count += 1
            continue
        if item.get("officialUrl"):
            councils.append({
                "id": cid,
                "ministry": item.get("ministry"),
                "name": item.get("name"),
                "url": item.get("officialUrl")
            })
    if inactive_count > 0:
        print(f"[INFO] 終了済み/非アクティブ会議体 {inactive_count} 件をクロール対象から除外します。")
    return councils

def interleave_by_ministry(councils):
    """
    同一省庁への連続アクセスを極力防止するため、省庁ごとに均等間隔（インターリーブ）で
    巡回順序を並び替える。
    """
    if not councils:
        return []
    from collections import defaultdict, deque
    buckets = defaultdict(deque)
    for c in councils:
        m = c.get("ministry") or "OTHER"
        buckets[m].append(c)
    
    # 件数が多い順にソートした省庁リスト
    sorted_ministries = sorted(buckets.keys(), key=lambda k: len(buckets[k]), reverse=True)
    
    # ラウンドロビン抽出
    interleaved = []
    while buckets:
        for k in sorted_ministries:
            if k in buckets and buckets[k]:
                interleaved.append(buckets[k].popleft())
                if not buckets[k]:
                    del buckets[k]
                    
    # 末尾に同一省庁が連続して残る場合、先頭側の別の省庁の間に挿入して分散
    final_list = []
    for item in interleaved:
        if not final_list or final_list[-1].get("ministry") != item.get("ministry"):
            final_list.append(item)
        else:
            # 連続してしまう場合は、直前と異なる省庁の隙間に遡って挿入
            inserted = False
            for idx in range(len(final_list) - 1, 0, -1):
                prev_m = final_list[idx - 1].get("ministry")
                curr_m = final_list[idx].get("ministry")
                this_m = item.get("ministry")
                if prev_m != this_m and curr_m != this_m:
                    final_list.insert(idx, item)
                    inserted = True
                    break
            if not inserted:
                final_list.append(item)
                
    return final_list

def load_scraping_rules():
    """docs/data.json の scrapingRules キーからスクレイピングルールを読み込み、必要に応じて scrapingRuleTemplates を展開・マージする"""
    data = load_data_json(DATA_JSON_FILE)
    if data:
        try:
            templates = data.get("scrapingRuleTemplates", {})
            raw_rules = data.get("scrapingRules", {})
            resolved_rules = {}
            for cid, r in raw_rules.items():
                # is_active / isActive が明示的に False の場合はスキップ
                if isinstance(r, dict) and (r.get("is_active") is False or r.get("isActive") is False):
                    continue
                if isinstance(r, dict) and "template" in r and r["template"] in templates:
                    tpl_name = r["template"]
                    # テンプレートをベースに個別オーバーライドをマージ
                    merged = dict(templates[tpl_name])
                    merged.update(r)
                    merged.pop("template", None)
                    resolved_rules[cid] = merged
                else:
                    resolved_rules[cid] = r
            return resolved_rules
        except Exception as e:
            print(f"[WARN] Failed to load scrapingRules from data.json: {e}", file=sys.stderr)
    return {}

def fetch_url(url, timeout=12):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        print(f"[ERROR] Invalid scheme: {url}", file=sys.stderr)
        return None
    headers = get_browser_headers()
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            raw_bytes = response.read()
            return decode_html_bytes(raw_bytes, content_type)
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def parse_materials_from_html(html, base_url, pdf_selector=None):
    """HTMLから全配布資料（公開PDF、HTML議事録、および非公開資料）を抽出（ポータルやヘッダー・ナビノイズは事前除外）"""
    materials = []
    if not html:
        return materials
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Base URL consideration
    base_tag = soup.find('base', href=True)
    if base_tag:
        base_url = urllib.parse.urljoin(base_url, base_tag['href'])
    
    # 2. 共通ヘッダー・フッター・ナビゲーション領域の事前完全除去（スキップリンク・UIノイズの根本遮断）
    for noise_tag in soup(['header', 'footer', 'nav', 'aside', 'script', 'style']):
        noise_tag.extract()
    for noise_id in ['header_navskip', 'js_drawer', 'header', 'footer', 'local_nav', 'gnavi', 'topic_path_head', 'sub_contents']:
        el = soup.find(id=noise_id)
        if el:
            el.extract()

    seen_urls = set()

    # 3. リンク抽出 (PDF文書およびHTML議事録・要旨)
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href'].strip()
        if not href or href.startswith('#') or href.startswith('javascript:'):
            continue
            
        # ハッシュアンカー付きURLのアンカー部分を正規化・判定
        if '#' in href and any(h in href.lower() for h in ['#contents', '#block_', '#header', '#footer', '#skip', '#main', '#page']):
            continue

        abs_url = urllib.parse.urljoin(base_url, href)
        if abs_url == base_url or abs_url in seen_urls:
            continue
        if any(k in abs_url.lower() for k in ['cas.go.jp/jp/siryou', 'cas.go.jp/jp/shiryo']) or is_generic_index_url(abs_url):
            continue

        raw_text = a_tag.get_text(" ", strip=True)
        clean_name = re.sub(r'[\（\(]PDF[／/形式\:\s\d\.\,KBMB]+\s*[\）\)]', '', raw_text).strip()
        clean_name = re.sub(r'［PDF形式：\d+.*?］', '', clean_name).strip()
        
        parsed_path = urllib.parse.urlparse(abs_url).path
        filename = os.path.basename(parsed_path)
        if not clean_name:
            clean_name = filename if filename else "配付資料"

        if clean_name in EXCLUDE_MATERIAL_NAMES or any(k in clean_name for k in ['移動します', '公式ポータル', '公式ページ', '公式情報ポータル', '審議会・検討会等一覧', '公式掲載資料・ページ']):
            continue

        # A. PDFおよび各種文書ファイル
        if href.lower().endswith(('.pdf', '.docx', '.xlsx', '.doc', '.xls')) or '/pdf/' in href.lower():
            seen_urls.add(abs_url)
            materials.append({
                "name": clean_name,
                "url": abs_url,
                "type": "PDF",
                "isPrivate": False
            })
        # B. HTML形式の議事録・議事要旨
        elif any(k in href.lower() for k in ['gijiroku', 'gijiyoshi', 'giji_yoshi', 'proceedings']) or any(k in clean_name for k in ['議事録', '議事要旨', '議事次第・配布資料']):
            seen_urls.add(abs_url)
            doc_name = clean_name
            if 'gijiroku' in href.lower() and ('議事録' not in doc_name):
                doc_name = "議事録"
            elif 'gijiyoshi' in href.lower() and ('議事要旨' not in doc_name):
                doc_name = "議事要旨"
            materials.append({
                "name": doc_name,
                "url": abs_url,
                "type": "HTML",
                "isPrivate": False
            })
            
    private_lines = re.findall(r'(資料\d+[\s\:\：]*[^\n<]+(?:非公開)[^\n<]*)', html)
    for p_text in private_lines:
        clean_p_text = re.sub(r'<[^>]+>', '', p_text).strip()
        materials.append({
            "name": clean_p_text,
            "url": "#",
            "type": "非公開",
            "isPrivate": True
        })
        
    return materials

def extract_page_title(soup, rule=None, fallback_url=""):
    """
    HTML soupから会議名・ページタイトルを抽出する。
    title_selector -> 見出しタグ (h2, h1, h3) -> <title> タグの順に探索し、ジェネリックタイトルを除外する。
    """
    try:
        title = ""
        if rule:
            title_sel = rule.get("title_selector")
            if title_sel:
                sel_el = soup.select_one(title_sel)
                if sel_el:
                    title = sel_el.get_text(" ", strip=True)

        # title_selector で取れなかった場合、またはジェネリックタイトルの場合
        if not title or any(kw in title for kw in GENERIC_TITLE_KEYWORDS):
            for tag_name in ['h2', 'h1', 'h3']:
                found_tag = soup.find(tag_name)
                if found_tag:
                    t_cand = found_tag.get_text(" ", strip=True)
                    if t_cand and not any(kw in t_cand for kw in GENERIC_TITLE_KEYWORDS):
                        title = t_cand
                        break

        # それでもなければ <title> タグ
        if not title and soup.title and soup.title.string:
            cand_title = soup.title.string.strip()
            # サフィックス・余分な空白の除去
            cand_title = re.sub(r'｜.*$', '', cand_title).strip()
            cand_title = re.sub(r' - .*$', '', cand_title).strip()
            cand_title = re.sub(r'\s+', ' ', cand_title).strip()
            if cand_title and not any(kw in cand_title for kw in GENERIC_TITLE_KEYWORDS):
                title = cand_title

        if title:
            title = re.sub(r'｜.*$', '', title).strip()
            title = re.sub(r' - .*$', '', title).strip()
            title = re.sub(r'\s+', ' ', title).strip()
            if any(kw == title for kw in GENERIC_TITLE_KEYWORDS):
                title = ""

        return title if title else fallback_url
    except Exception:
        # パース失敗やネットワーク異常時はフォールバックURLを安全に返却
        return fallback_url


def _crawl_subpages(target_url, html, rule, quirk_note, pdf_pattern):
    """サブページの深掘りクロールロジック"""
    subpage_meetings = []
    additional_materials = []
    all_extracted_dates = []

    soup = BeautifulSoup(html, 'html.parser')
    base_tag = soup.find('base', href=True)
    page_base_url = urllib.parse.urljoin(target_url, base_tag['href']) if base_tag else target_url

    subpage_pattern = rule.get("subpage_discovery_pattern", r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai|gijiroku|newpage_\d+|shingi2|session|meeting|siryou|bunkakai)[^"\'#]*)["\']')
    subpage_links = re.findall(subpage_pattern, html, re.IGNORECASE)

    if subpage_links:
        unique_subpages = list(dict.fromkeys([urllib.parse.urljoin(page_base_url, l) for l in subpage_links]))[:6]
        print(f"   [2回目情報取得Engine ({quirk_note})] サブページ {len(unique_subpages)} 件を深掘り巡回中...")

        for sub_url in unique_subpages:
            parsed_url = urllib.parse.urlparse(sub_url)
            if parsed_url.scheme not in ('http', 'https'):
                continue
            if sub_url.lower().endswith('.pdf'):
                continue
            if any(k in sub_url.lower() for k in ['cas.go.jp/jp/siryou', 'cas.go.jp/jp/shiryo']) or is_generic_index_url(sub_url):
                continue

            sub_html = fetch_url(sub_url)
            if sub_html:
                sub_soup = BeautifulSoup(sub_html, 'html.parser')
                sub_title = extract_page_title(sub_soup, rule, fallback_url=sub_url)

                sub_materials = parse_materials_from_html(sub_html, sub_url, pdf_pattern)
                
                # 2段階配付資料自動探索: もしPDF資料が0件（または議事録のみ）の場合、同一ディレクトリの随伴資料ページ（gijishidai.html等）を自動探索
                has_pdf = any(m.get("type") == "PDF" for m in sub_materials)
                if not has_pdf:
                    folder_url = sub_url if sub_url.endswith('/') else urllib.parse.urljoin(sub_url, './')
                    # 随伴資料ページの候補探索（同階層のgijishidai.htmlまたはページ内リンク）
                    companion_candidates = []
                    for a in sub_soup.find_all('a', href=True):
                        h_lower = a['href'].lower()
                        if any(k in h_lower for k in ['gijishidai', 'shiryo', 'siryou', 'haifu']) and not h_lower.endswith('.pdf'):
                            companion_candidates.append(urllib.parse.urljoin(sub_url, a['href']))
                    companion_candidates.append(urllib.parse.urljoin(folder_url, 'gijishidai.html'))
                    companion_candidates.append(urllib.parse.urljoin(folder_url, 'index.html'))
                    
                    for comp_url in list(dict.fromkeys(companion_candidates)):
                        if comp_url == sub_url:
                            continue
                        comp_html = fetch_url(comp_url)
                        if comp_html:
                            comp_mats = parse_materials_from_html(comp_html, comp_url, pdf_pattern)
                            comp_pdfs = [cm for cm in comp_mats if cm.get("type") == "PDF"]
                            if comp_pdfs:
                                for cp in comp_pdfs:
                                    if not any(m.get("url") == cp.get("url") for m in sub_materials):
                                        sub_materials.append(cp)
                                # 自身が議事録ページであれば議事録としても保持
                                if 'gijiroku' in sub_url.lower() and not any(m.get("url") == sub_url for m in sub_materials):
                                    sub_materials.append({
                                        "name": "議事録",
                                        "url": sub_url,
                                        "type": "HTML",
                                        "isPrivate": False
                                    })
                                break

                # 3段階配付資料自動展開: 抽出された資料リストに「会議資料」「資料」等のHTMLページがある場合、そのリンク先を取得して内部の末端PDF資料を展開
                html_materials = [m for m in sub_materials if (m.get('url', '').endswith('.html') or m.get('url', '').endswith('.htm'))]
                for hm in html_materials:
                    hm_url = hm.get('url')
                    hm_name = hm.get('name', '')
                    if any(k in hm_name for k in ['会議資料', '配付資料', '配布資料', '資料一覧', '資料']) or re.search(r'\d+kai\.html$', hm_url):
                        hm_html = fetch_url(hm_url)
                        if hm_html:
                            expanded_mats = parse_materials_from_html(hm_html, hm_url, pdf_pattern)
                            for em in expanded_mats:
                                if em.get('type') == 'PDF' and not any(m.get('url') == em.get('url') for m in sub_materials):
                                    sub_materials.append(em)

                raw_sub_dates = extract_clean_dates_from_html(sub_html, rule.get("date_regex", DEFAULT_DATE_REGEX))
                norm_sub_dates = [normalize_japanese_numbers(d) for d in raw_sub_dates]
                all_extracted_dates.extend(norm_sub_dates)

                subpage_meetings.append({
                    "subpageUrl": sub_url,
                    "title": sub_title,
                    "extractedMaterialsCount": len(sub_materials),
                    "materials": sub_materials,
                    "extractedDates": list(set(norm_sub_dates))[:2]
                })
                additional_materials.extend(sub_materials)

    return subpage_meetings, additional_materials, all_extracted_dates

def clean_html_for_dates(html_str):
    """ヘッダー・フッター・サイドバー・パンくず等のノイズを除去して本文ブロックを抽出"""
    if not html_str:
        return ""
    try:
        soup = BeautifulSoup(html_str, 'html.parser')
        for tag in soup(['nav', 'aside', 'footer', 'script', 'style', 'header']):
            tag.decompose()
        for el in soup.find_all(id=re.compile(r'(side|nav|footer|header|menu|breadcrumb)', re.I)):
            if el.name not in ('body', 'html'):
                el.decompose()
        for el in soup.find_all(class_=re.compile(r'(side|nav|footer|header|menu|breadcrumb)', re.I)):
            if el.name not in ('body', 'html'):
                el.decompose()
        main_el = soup.find(id=re.compile(r'(main|content)', re.I)) or soup.find(class_=re.compile(r'(main|content)', re.I)) or soup.body
        return str(main_el) if main_el else str(soup)
    except Exception:
        return html_str

def validate_and_normalize_date(date_str):
    """
    抽出された日付文字列が実在する妥当な日付（1990年〜2035年、月1〜12、日1〜31）であるかを検証し、
    正規化された文字列または None を返す。
    """
    if not date_str or not isinstance(date_str, str):
        return None
    dt = parse_japanese_date(date_str)
    if not dt:
        return None
    max_year = datetime.now().year + 2
    if 1990 <= dt.year <= max_year and 1 <= dt.month <= 12 and 1 <= dt.day <= 31:
        return date_str.strip()
    return None

def extract_clean_dates_from_html(html_str, date_regex_pattern=r'(?<![\d\w\/\-])(?:(?:令和|平成)(?:\d+|元)年\d{1,2}月\d{1,2}日|\d{4}年\d{1,2}月\d{1,2}日|\d{4}[/-]\d{1,2}[/-]\d{1,2})(?![\d\w\/\-])'):
    """更新日・掲載日などのノイズや不正パターンを除去して会議開催日を抽出"""
    cleaned_html = clean_html_for_dates(html_str)
    # 全角数字を半角に正規化
    cleaned_html = normalize_japanese_numbers(cleaned_html)
    # 年号併記の括弧を除去 (例: 2026年（令和8年）3月24日 -> 2026年3月24日)
    cleaned_html = re.sub(r'(\d{4}年)[（\(][^）\)\n]+[）\)]\s*(\d{1,2}月\d{1,2}日)', r'\1\2', cleaned_html)
    cleaned_html = re.sub(r'((?:令和|平成)(?:\d+|元)年)[（\(][^）\)\n]+[）\)]\s*(\d{1,2}月\d{1,2}日)', r'\1\2', cleaned_html)
    raw_dates = re.findall(date_regex_pattern, cleaned_html)
    
    # 「更新日: 2024年X月X日」「掲載日: ...」などの直前ラベル付きの日付を除外
    filtered_dates = []
    for d in raw_dates:
        # 直前ラベルに「更新日」「掲載日」「公表日」「作成日」「施行期日」「適用期日」等が含まれる場合は除外
        escaped_d = re.escape(d)
        if re.search(r'(?:更新日|最終更新|掲載日|公表日|作成日|ページID|copyright|施行期日|施行日|施行|適用期日|適用日|公布の日|公布日|施行予定|適用予定)[^。\n]{0,30}' + escaped_d, cleaned_html, re.I):
            continue
        valid_d = validate_and_normalize_date(d)
        if valid_d:
            filtered_dates.append(valid_d)
        
    return filtered_dates


def calculate_past_year_count(extracted_dates, ref_date=None):
    """抽出された日付から過去1年間の開催数を算出。トップページ等に日付がなければ ('-', False) を返す"""
    if ref_date is None:
        ref_date = datetime.now()
    if not extracted_dates:
        return "-", False
    
    parsed_dates = []
    for d_str in extracted_dates:
        dt = parse_japanese_date(d_str)
        if dt:
            parsed_dates.append(dt)
            
    if not parsed_dates:
        return "-", False
        
    one_year_ago = ref_date - timedelta(days=365)
    unique_past_year_dates = set([dt.strftime('%Y-%m-%d') for dt in parsed_dates if one_year_ago <= dt <= ref_date])
    return len(unique_past_year_dates), True

def discover_subpage_links(html, base_url):
    """トップページHTMLから会議の個別ページへのリンクを発見する"""
    soup = BeautifulSoup(html, 'html.parser')
    base_tag = soup.find('base', href=True)
    if base_tag:
        base_url = urllib.parse.urljoin(base_url, base_tag['href'])

    # 会議サブページのパターン (dai1, 1kai, kaisai, gijisidai, newpage_XXX, shingi2, etc.)
    subpage_pattern = re.compile(
        r'(?:dai\d+|\d+kai|kaisai|gijisidai|gijiroku|kaigi|meeting|shiryo|siryou|newpage_\d+|shingi2|session|bunkakai)',
        re.IGNORECASE
    )
    
    candidates = []
    seen = set()
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href.startswith('#') or href.startswith('javascript:'):
            continue
        if href.lower().endswith('.pdf'):
            continue
        abs_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(abs_url)
        if parsed.scheme not in ('http', 'https'):
            continue
        # 同一ドメインのみ
        base_domain = urllib.parse.urlparse(base_url).netloc
        if parsed.netloc != base_domain:
            continue
        if abs_url in seen or abs_url == base_url or any(k in abs_url.lower() for k in ['cas.go.jp/jp/siryou', 'cas.go.jp/jp/shiryo']) or is_generic_index_url(abs_url):
            continue
        if subpage_pattern.search(href):
            seen.add(abs_url)
            candidates.append(abs_url)
    
    # 優先度ソート: 議事次第（gijishidai）、配付資料（shiryo）、ディレクトリトップ（index.html/末尾スラッシュ）を議事録単体より優先
    def subpage_priority(url):
        u_low = url.lower()
        if any(k in u_low for k in ['gijishidai', 'shiryo', 'siryou', 'haifu']):
            return 3
        if u_low.endswith('/') or u_low.endswith('/index.html') or 'dai' in u_low or 'kai' in u_low:
            return 2
        if 'gijiroku' in u_low:
            return 1
        return 0

    candidates.sort(key=subpage_priority, reverse=True)
    return candidates[:12]  # 最大12サブページを優先巡回

def extract_via_llm_single(url, html, target_name):
    """単一ページに対してLLM抽出を実行する"""
    global LLM_QUOTA_BLOCKED
    model = get_gemini_model()
    if not model or LLM_QUOTA_BLOCKED:
        return [], []
        
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style"]):
        script.extract()
    body_text = soup.get_text(separator=' ', strip=True)
    body_text = re.sub(r'\s+', ' ', body_text)[:5000]
    
    prompt = f"""
以下の官公庁会議（{target_name}）のウェブページの内容から、配付資料のリストと開催日を抽出してください。
URL: {url}

必ず以下のJSONスキーマに従って出力してください。Markdownコードブロックは含めないでください。
{{
  "materials": [
    {{"name": "資料名", "url": "資料のURL"}}
  ],
  "extractedDates": [
    "2023-12-01", "2024-01-15" (日付の配列、YYYY-MM-DD形式、和暦は西暦に変換)
  ]
}}

本文:
{body_text}
"""
    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        if result_text.startswith("```json"): result_text = result_text[7:]
        if result_text.startswith("```"): result_text = result_text[3:]
        if result_text.endswith("```"): result_text = result_text[:-3]
        
        data = json.loads(result_text.strip())
        materials = data.get("materials", [])
        
        for m in materials:
            if m.get("url") and not m["url"].startswith("http"):
                m["url"] = urllib.parse.urljoin(url, m["url"])
                
        return materials, data.get("extractedDates", [])
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower():
            LLM_QUOTA_BLOCKED = True
            print(f"[WARN] Gemini API クォータ制限 (429) を検知しました。以降の巡回は高速 Heuristic ルール抽出モードで安全に継続します。")
        else:
            print(f"[WARN] LLM Extraction failed for {url}: {e}")
        return [], []

def extract_via_llm(target_url, html, target_name):
    """LLM抽出（トップページ + サブページ巡回）"""
    global LLM_QUOTA_BLOCKED
    model = get_gemini_model()
    if not model or LLM_QUOTA_BLOCKED:
        return [], []
    
    # Step 1: トップページ抽出
    all_materials, all_dates = extract_via_llm_single(target_url, html, target_name)
    
    # Step 2: サブページ発見・巡回
    if not LLM_QUOTA_BLOCKED:
        subpage_urls = discover_subpage_links(html, target_url)
        if subpage_urls:
            print(f"   [LLM Subpage Crawl] {len(subpage_urls)} 件のサブページを巡回中...")
            for sub_url in subpage_urls:
                if LLM_QUOTA_BLOCKED:
                    break
                sub_html = fetch_url(sub_url)
                if sub_html:
                    sub_materials, sub_dates = extract_via_llm_single(sub_url, sub_html, target_name)
                    all_materials.extend(sub_materials)
                    all_dates.extend(sub_dates)
    
    # 重複排除
    seen_urls = set()
    unique_materials = []
    for m in all_materials:
        key = m.get("url", m.get("name", ""))
        if key not in seen_urls:
            seen_urls.add(key)
            unique_materials.append(m)
    
    unique_dates = list(set(all_dates))
    return unique_materials, unique_dates

def execute_rule_retrieval(target, html, rule_item, use_llm=False):
    """多段情報取得Engine (高速Heuristicルール優先 → 未抽出時LLMフォールバック)"""
    global LLM_QUOTA_BLOCKED
    rule = rule_item.get("rules", {})
    quirk_note = rule_item.get("ministryQuirk", "標準抽出ルール")
    
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else target["name"]

    unique_materials = []
    norm_date_matches = []
    subpage_meetings = []
    extraction_method = "none"
    
    # Stage 1: 高速・網羅的な Heuristic ルール抽出 (scrapingRules 準拠)
    pdf_pattern = rule.get("pdf_selector", r'href=["\']([^"\']+\.pdf)["\']')
    top_materials = parse_materials_from_html(html, target["url"], pdf_pattern)
    
    # ディープクロールは常に実行（サブページを深掘りして配付資料を収集）
    all_extracted_dates = []
    new_meetings, new_materials, new_dates = _crawl_subpages(target["url"], html, rule, quirk_note, pdf_pattern)
    subpage_meetings.extend(new_meetings)
    top_materials.extend(new_materials)
    all_extracted_dates.extend(new_dates)

    seen_keys = set()
    for m in top_materials:
        key = m["url"] if m["url"] != "#" else m["name"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_materials.append(m)

    raw_date_matches = extract_clean_dates_from_html(html, rule.get("date_regex", DEFAULT_DATE_REGEX))
    top_norm_dates = [normalize_japanese_numbers(d) for d in raw_date_matches]
    all_extracted_dates.extend(top_norm_dates)
    norm_date_matches = list(dict.fromkeys(all_extracted_dates))
    
    if unique_materials or norm_date_matches or subpage_meetings:
        extraction_method = "rule"
    else:
        # Stage 2: ルールで0件の場合のみ LLM (Gemini API) フォールバックを試行
        if use_llm and not LLM_QUOTA_BLOCKED and get_gemini_model():
            print(f"   [Stage 2 Fallback] ルール未検出 → LLM Extraction (Gemini API: gemini-3.8-flash) を試行...")
            materials, dates = extract_via_llm(target["url"], html, target["name"])
            if materials or dates:
                unique_materials = materials
                norm_date_matches = dates
                extraction_method = "llm"
                print(f"   [Stage 2 OK] LLMフォールバック抽出成功: 資料 {len(materials)} 件, 日付 {len(dates)} 件")
            else:
                extraction_method = "none"

    past_year_count, has_top_page_dates = calculate_past_year_count(norm_date_matches)

    # 抽出結果の判定
    if unique_materials and norm_date_matches:
        crawl_result = "success"
    elif unique_materials or norm_date_matches:
        crawl_result = "partial"
    else:
        crawl_result = "failed"

    scraped_item = {
        "councilId": target["id"],
        "councilName": target["name"],
        "ministry": target["ministry"],
        "officialUrl": target["url"],
        "scrapedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruleApplied": rule_item.get("rule_id", "rule-default"),
        "extractionMethod": extraction_method,
        "crawlResult": crawl_result,
        "ministryQuirk": quirk_note,
        "pageTitle": page_title,
        "pastYearCount": past_year_count,
        "hasTopPageDates": has_top_page_dates,
        "totalExtractedMaterials": len(unique_materials),
        "materials": unique_materials,
        "extractedDates": list(set(norm_date_matches))[:5],
        "subpageMeetings": subpage_meetings
    }
    return scraped_item


def is_generic_index_url(url, title=""):
    """報道発表インデックスやポータルトップ・開催状況一覧・「その他情報」等の汎用インデックスURLかどうかを判定する"""
    if not url:
        return True
    if _GENERIC_INDEX_URL_PATTERNS.search(url.lower()):
        return True
    if title and any(k in title for k in _GENERIC_INDEX_TITLE_KEYWORDS):
        return True
    return False

def is_preliminary_notice_page(url, title=""):
    """
    開催案内・事前告知ページ（例: .../kaisai/index.html, .../kaisaiannai/..., 〜の開催について）や資料未添付の議事要旨・議事録単体ページであるかを判定。
    これらは資料が掲載される会議ページではないため、独立した会議として追加しない。
    """
    if not url and not title:
        return False
    u_lower = (url or "").lower()
    # URLに /kaisai/ や /kaisaiannai/ や /online_kaisai 等が含まれる場合
    if re.search(r'/(?:kaisai|kaisaiannai|online_kaisai)/', u_lower) or u_lower.endswith('/kaisai.html') or 'kaisaiannai' in u_lower:
        return True
    # タイトルから末尾の省庁名サフィックスを除去して判定
    t_clean = (title or "").strip()
    t_clean = re.sub(r'[\s｜\|].*?(?:厚生労働省|内閣府|内閣官房|財務省|金融庁|法務省|経済産業省|文部科学省|総務省|外務省|農林水産省|国土交通省|環境省|防衛省|デジタル庁|こども家庭庁).*$', '', t_clean).strip()
    if re.search(r'(?:の開催について|の開催案内|の開催のお知らせ|開催のお知らせ|開催案内|傍聴の案内|傍聴について|の開催概要について|議事要旨|議事録)$', t_clean):
        return True
    return False


def _resolve_meeting_date(sub_dates, sub_title, sub_url):
    """
    サブページの抽出日付、タイトル、URLから開催日を特定し、
    YYYY/MM/DD 形式の日付文字列と is_date_unconfirmed (未特定ダミー 2099/01/01 フラグ) を返す。
    """
    meet_date = ""
    is_date_unconfirmed = False
    if sub_dates:
        dt = parse_japanese_date(sub_dates[0])
        if dt:
            meet_date = dt.strftime("%Y/%m/%d")
        else:
            m_iso = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', str(sub_dates[0]))
            if m_iso:
                meet_date = f"{int(m_iso.group(1)):04d}/{int(m_iso.group(2)):02d}/{int(m_iso.group(3)):02d}"

    if not meet_date and sub_title:
        dt = parse_japanese_date(sub_title)
        if dt:
            meet_date = dt.strftime("%Y/%m/%d")

    if not meet_date and sub_url:
        # URL内の日付パターン (例: 20240820, 2024-08-20, 2024_08_20)
        m_url = re.search(r'(?:^|[/_-])(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?:$|[._/-])', sub_url)
        if m_url:
            meet_date = f"{m_url.group(1)}/{m_url.group(2)}/{m_url.group(3)}"

    # 開催日が特定できない場合は当日日付ではなくダミー日付(2099/01/01)を設定（管理画面で要確認対象とする）
    if not meet_date:
        meet_date = "2099/01/01"
        is_date_unconfirmed = True

    return meet_date, is_date_unconfirmed


def _build_new_meeting(target, sub, clean_materials_list, sess_nums, meet_date, is_date_unconfirmed, existing_c_meets, added_count, existing_meeting_ids, council_parent_url):
    """
    新規開催回（meeting）オブジェクトを生成して返す。
    4セグメントID生成、重複ID回避、タイトル正規化、公式URL解決を実施。
    """
    council_id = target["id"]
    council_name = target["name"]
    ministry = target.get("ministry", "")
    sub_title = sub.get("title", "").strip()

    # 会議IDの生成（4セグメント統一形式: {council_id}-{YYYYMMDD}-{回次000またはs00}）
    clean_d = meet_date.replace("/", "").replace("-", "")
    sess_suffix = f"{sorted(sess_nums)[0]:03d}" if sess_nums else f"s{len(existing_c_meets) + added_count + 1:02d}"
    new_meet_id = f"{council_id}-{clean_d}-{sess_suffix}"

    # 重複ID回避
    if new_meet_id in existing_meeting_ids:
        new_meet_id = f"{council_id}-{clean_d}-{sess_suffix}_{added_count+1}"

    # タイトルの正規化
    formatted_title = sub_title
    # 開催案内プレフィックス/サフィックスのクリーンアップ
    if formatted_title:
        formatted_title = re.sub(r'「(.*?)」を開催します.*$', r'\1', formatted_title)
        formatted_title = re.sub(r'を開催します.*$', '', formatted_title)
        formatted_title = re.sub(r'（開催案内）$', '', formatted_title)
        formatted_title = re.sub(r'\(開催案内\)$', '', formatted_title)
        formatted_title = re.sub(r'の開催について$', '', formatted_title)
        formatted_title = re.sub(r'[（\(](?:令和|平成)(?:\d+|元)年度.*?[）\)]$', '', formatted_title)
        formatted_title = formatted_title.strip()

    is_generic = not formatted_title or formatted_title.startswith("http") or any(kw == formatted_title for kw in GENERIC_TITLE_KEYWORDS)
    if is_generic:
        if sess_nums:
            formatted_title = f"第{sorted(sess_nums)[0]}回 {council_name}"
        else:
            date_label = "開催日不明" if is_date_unconfirmed else meet_date
            formatted_title = f"{council_name} ({date_label})"
    elif council_name not in formatted_title and sess_nums:
        formatted_title = f"第{sorted(sess_nums)[0]}回 {council_name}"

    if is_date_unconfirmed and "開催日不明" not in formatted_title:
        formatted_title = f"{formatted_title} (開催日不明)"

    # 汎用報道URLや資料未掲載の場合は親の会議体URLを設定
    resolved_meet_url = sub.get("subpageUrl")
    if not resolved_meet_url or is_generic_index_url(resolved_meet_url, sub_title):
        resolved_meet_url = council_parent_url

    new_meeting_obj = {
        "id": new_meet_id,
        "councilId": council_id,
        "name": formatted_title,
        "title": formatted_title,
        "date": meet_date,
        "officialUrl": resolved_meet_url,
        "materials": clean_materials_list,
        "isNewlyDiscovered": True,
        "discoveredAt": datetime.now().strftime("%Y/%m/%d %H:%M")
    }
    if is_date_unconfirmed:
        new_meeting_obj["isDateUnconfirmed"] = True

    return new_meeting_obj


def sync_new_meetings_from_crawl(data, target, scraped_item):
    """
    クロール時に検出されたサブページ（個別開催回）から、
    1. 未登録の新規開催回を自動検知して docs/data.json の meetings 配列に追加する。
    2. 開催前・未掲載で親URLのままだった既存会議に、新たに個別資料ページが公開された場合は officialUrl と資料を自動昇格・更新する。
    ※ 既存の手動作成済み会議（manualLock: true かつ個別資料登録済み）は保護する。
    """
    if not scraped_item:
        return 0

    subpages = scraped_item.get("subpageMeetings", [])
    if not subpages:
        return 0

    council_id = target["id"]
    council_name = target["name"]
    council_parent_url = target.get("officialUrl") or target.get("url", "")
    ministry = target["ministry"]
    meetings = data.setdefault("meetings", [])

    existing_c_meets = [m for m in meetings if m.get("councilId") == council_id]
    existing_urls = {m.get("officialUrl", "").rstrip("/"): m for m in existing_c_meets if m.get("officialUrl")}
    existing_titles = {m.get("title", ""): m for m in existing_c_meets if m.get("title")}
    existing_meeting_ids = {m.get("id") for m in meetings if m.get("id")}
    existing_sessions = set()
    for m in existing_c_meets:
        sess = extract_session_numbers(m.get("title", "") + " " + m.get("officialUrl", "") + " " + m.get("id", ""))
        existing_sessions.update(sess)

    added_count = 0
    for sub in subpages:
        sub_url = sub.get("subpageUrl", "").rstrip("/")
        sub_title = sub.get("title", "").strip()
        sub_mats = sub.get("materials", [])
        sub_dates = sub.get("extractedDates", [])

        # 汎用インデックスURLや内閣官房「その他情報」等は会議ページとして登録しない
        if is_generic_index_url(sub_url, sub_title):
            continue

        # 事前開催案内ページ（資料なしの事前告知）は会議ページとして登録しない
        if is_preliminary_notice_page(sub_url, sub_title) and not sub_mats:
            continue

        # ジェネリックタイトルおよびポータルサイト名の登録遮断ガード
        if any(kw == sub_title for kw in GENERIC_TITLE_KEYWORDS) or '食の安全、を科学する' in sub_title:
            continue

        # 親会議体への下部組織・専門家会合の誤混入ガード（例: 税制調査会(cao-zei_cho)にEBPM等の専門家会合が混入するのを防止）
        if council_id == "cao-zei_cho":
            if any(k in sub_url.lower() for k in ['/ebpm/', '/life/', '/digital-noukan/', '/noukan/', '/sozoku-zoyo/', '/renketsu/', '/rougo/', '/koku-han/', '/discussion']) or "専門家会合" in sub_title or "ディスカッショングループ" in sub_title:
                continue
        if council_id == "cao-cstp":
            if any(k in sub_url.lower() for k in ['kaisaiannai', 'bridge', 'brige_wg']) or any(k in sub_title for k in ['ワーキンググループ', 'WG', 'BRIDGE', '中間評価']):
                continue

        # 他省庁URLの誤混入ガード（例: MHLW会議体にMETIのURLが混入するのを防止）
        ministry_code = (ministry or "").upper()
        if ministry_code:
            parsed_sub = urllib.parse.urlparse(sub_url)
            sub_host = parsed_sub.netloc.lower()
            if "example.com" not in sub_host and "localhost" not in sub_host:
                other_ministry_domains = _OTHER_MINISTRY_DOMAINS_MAP.get(ministry_code, ())
                if any(other_d in sub_host for other_d in other_ministry_domains):
                    continue

        # 開催回番号の抽出
        sess_nums = extract_session_numbers(sub_title + " " + sub_url)

        # 資料配列の構築（配付資料の名称属性は 'name' で厳格統一）
        clean_materials_list = []
        for mat in sub_mats:
            mat_name = (mat.get("name") or mat.get("title") or "").strip()
            mat_url = mat.get("url", "").strip()
            mat_type = mat.get("type", "PDF")
            if not mat_url or mat_url == "#" or mat_url == sub_url:
                continue
            mat_item = {
                "name": mat_name if mat_name else os.path.basename(mat_url),
                "url": mat_url
            }
            if mat_type and mat_type not in ("PDF", "pdf"):
                mat_item["type"] = mat_type
            if mat.get("isPrivate"):
                mat_item["isPrivate"] = True
            clean_materials_list.append(mat_item)

        # --- A. 既存会議の自動昇格・更新（資料未掲載・親URLだった会議が開催日後に個別資料ページを検出した場合） ---
        if sess_nums and any(s in existing_sessions for s in sess_nums):
            matched_existing = []
            for m in existing_c_meets:
                m_sess = extract_session_numbers(m.get("title", "") + " " + m.get("officialUrl", "") + " " + m.get("id", ""))
                if any(s in m_sess for s in sess_nums):
                    matched_existing.append(m)

            for ex_m in matched_existing:
                curr_url = ex_m.get("officialUrl", "").rstrip("/")
                curr_mats = ex_m.get("materials", [])
                
                is_parent_or_generic = (curr_url == council_parent_url.rstrip("/") or is_generic_index_url(curr_url))
                has_no_mats = len(curr_mats) == 0
                has_new_valid_subpage = sub_url and not is_generic_index_url(sub_url, sub_title)

                if (is_parent_or_generic or has_no_mats) and has_new_valid_subpage and clean_materials_list:
                    ex_m["officialUrl"] = sub.get("subpageUrl")
                    ex_m["materials"] = clean_materials_list
                    ex_m["lastUpdatedFromCrawl"] = datetime.now().strftime("%Y/%m/%d %H:%M")
                    print(f"  [✨ 資料ページ自動更新] [{ex_m.get('date')}] {ex_m.get('title')} (URL: {sub_url}, 資料: {len(clean_materials_list)}件)")
                    added_count += 1
            continue

        # 既にURLまたはタイトルが完全一致している場合はスキップ
        if sub_url and sub_url in existing_urls:
            continue
        if sub_title and sub_title in existing_titles:
            continue

        # --- B. 新規開催回の追加 ---
        meet_date, is_date_unconfirmed = _resolve_meeting_date(sub_dates, sub_title, sub_url)

        # 開催日未確認（2099/01/01）の場合の厳格ガード（資料0件またはジェネリックタイトルは登録禁止）
        if is_date_unconfirmed:
            if not clean_materials_list:
                continue
            if any(kw in sub_title for kw in GENERIC_TITLE_KEYWORDS):
                continue

        # 同一会議体・同一日付の重複チェック（同日重複の自動防止および資料マージ）
        if not is_date_unconfirmed:
            same_date_meets = [m for m in existing_c_meets if m.get("date") == meet_date]
            if same_date_meets:
                # 既に同一日付の会議が存在する場合、資料のみを既存会議にマージして新規追加はスキップ
                for ex_m in same_date_meets:
                    ex_mats = ex_m.setdefault("materials", [])
                    ex_mat_urls = {mat.get("url") for mat in ex_mats if mat.get("url")}
                    for new_mat in clean_materials_list:
                        if new_mat.get("url") not in ex_mat_urls:
                            ex_mats.append(new_mat)
                            ex_mat_urls.add(new_mat.get("url"))
                continue
        new_meeting = _build_new_meeting(
            target=target,
            sub=sub,
            clean_materials_list=clean_materials_list,
            sess_nums=sess_nums,
            meet_date=meet_date,
            is_date_unconfirmed=is_date_unconfirmed,
            existing_c_meets=existing_c_meets,
            added_count=added_count,
            existing_meeting_ids=existing_meeting_ids,
            council_parent_url=council_parent_url
        )

        meetings.append(new_meeting)
        existing_meeting_ids.add(new_meeting["id"])
        existing_urls[sub_url] = new_meeting
        meet_title = new_meeting.get("title") or new_meeting.get("name") or ""
        existing_titles[meet_title] = new_meeting
        for s in sess_nums:
            existing_sessions.add(s)
        added_count += 1
        log_prefix = "⚠️ [開催日不明(2099/01/01)]" if is_date_unconfirmed else "✨ [新規開催回自動追加]"
        print(f"  {log_prefix} [{meet_date}] {meet_title} (ID: {new_meeting['id']}, 資料: {len(clean_materials_list)}件)")

    if added_count > 0:
        # 日付降順に再ソート
        meetings.sort(key=lambda x: x.get("date", ""), reverse=True)
        # 会議体の pastYearCount を更新
        for c in data.get("councils", []):
            if c.get("id") == council_id:
                c_meets = [m for m in meetings if m.get("councilId") == council_id]
                c["pastYearCount"] = len(c_meets)
                break

    return added_count


def update_crawl_status(data, council_id, scraped_item, failure_reason=None):
    """data.json の councils 配列内の該当会議体に crawlStatus を記録する。
    manualLock: true が設定された会議体はクロールステータスのみ更新し、
    officialUrl / name / description 等のコアフィールドを上書きしない。"""
    for council in data.get("councils", []):
        if council.get("id") == council_id:
            is_locked = council.get("manualLock", False)
            if is_locked:
                print(f"  [\U0001F512 LOCKED] {council_id}: manualLock が設定されています。crawlStatus のみ更新します（コアフィールドは保護済み）。")

            prev_status = council.get("crawlStatus", {})
            prev_failures = prev_status.get("consecutiveFailures", 0)

            if scraped_item is None:
                # fetch自体が失敗
                council["crawlStatus"] = {
                    "lastAttempt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "result": "failed",
                    "extractionMethod": "none",
                    "materialsCount": 0,
                    "datesCount": 0,
                    "failureReason": failure_reason or "Fetch failed",
                    "consecutiveFailures": prev_failures + 1,
                    "manualLockActive": is_locked
                }
            else:
                result = scraped_item.get("crawlResult", "failed")
                council["crawlStatus"] = {
                    "lastAttempt": scraped_item.get("scrapedAt", ""),
                    "result": result,
                    "extractionMethod": scraped_item.get("extractionMethod", "none"),
                    "materialsCount": scraped_item.get("totalExtractedMaterials", 0),
                    "datesCount": len(scraped_item.get("extractedDates", [])),
                    "failureReason": "" if result != "failed" else "Both LLM and rule extraction returned 0 results",
                    "consecutiveFailures": 0 if result != "failed" else prev_failures + 1,
                    "manualLockActive": is_locked
                }
            break

def extract_session_numbers(text):
    if not text:
        return set()
    t_norm = normalize_japanese_numbers(str(text))
    nums = set()
    matches = re.findall(r'第\s*(\d+)\s*回', t_norm)
    for m in matches:
        nums.add(int(m))
    matches_dai = re.findall(r'dai\s*(\d+)', t_norm, re.IGNORECASE)
    for m in matches_dai:
        nums.add(int(m))
    matches_slash = re.findall(r'[/_](\d{1,3})(?:[_.]|pdf|giji)', t_norm, re.IGNORECASE)
    for m in matches_slash:
        nums.add(int(m))
    return nums

def extract_years(text):
    if not text:
        return set()
    years = set()
    reiwa = re.findall(r'令和([元\d]+)年', text)
    for r in reiwa:
        val = 1 if r == '元' else int(r)
        years.add(2018 + val)
    heisei = re.findall(r'平成([元\d]+)年', text)
    for h in heisei:
        val = 1 if h == '元' else int(h)
        years.add(1988 + val)
    western = re.findall(r'20\d\d', text)
    for w in western:
        years.add(int(w))
    r_file = re.findall(r'[/_]r0?(\d+)', text, re.IGNORECASE)
    for rf in r_file:
        years.add(2018 + int(rf))
    h_file = re.findall(r'[/_]h0?(\d+)', text, re.IGNORECASE)
    for hf in h_file:
        years.add(1988 + int(hf))
    return years

def deduplicate_data_materials(data):
    """docs/data.json の会議（MEETINGS）に紐づく資料リンクの重複を排除し、正確な回へ一意に再配分する"""
    from collections import defaultdict
    meetings = data.get("meetings", [])
    councils = {c["id"]: c for c in data.get("councils", [])}

    council_meetings = defaultdict(list)
    for m in meetings:
        c_id = m.get("councilId")
        if c_id:
            council_meetings[c_id].append(m)

    removed_cross_dup = 0
    removed_portal = 0

    for c_id, m_list in council_meetings.items():
        c_info = councils.get(c_id, {})
        c_url = (c_info.get("officialUrl") or c_info.get("url", "")).strip()

        # 1. ポータル・公式ページ・一覧ページの資料リンクを除外
        for m in m_list:
            # manualLock: true の会議はそのまま保護（重複排除・移動対象外）
            if m.get("manualLock", False):
                continue
            clean_mats = []
            for mat in m.get("materials", []):
                # manualLock: true の個別資料も保護
                if mat.get("manualLock", False):
                    clean_mats.append(mat)
                    continue
                url = mat.get("url", "").strip()
                name = mat.get("name", "").strip()
                if (c_url and url == c_url) or any(k in name for k in ["公式ポータル", "公式ページ", "公式情報ポータル", "審議会・検討会等一覧", "公式掲載資料・ページ"]):
                    removed_portal += 1
                    continue
                clean_mats.append(mat)
            m["materials"] = clean_mats

        # 2. 会議体内の複数開催回に重複して紐づいている同一資料URLの解消
        url_to_instances = defaultdict(list)
        for m in m_list:
            # manualLock: true の会議はそのまま保護（重複排除・移動対象外）
            if m.get("manualLock", False):
                continue
            for mat in m.get("materials", []):
                url = mat.get("url", "").strip()
                if url and url != "#":
                    # manualLock: true の個別資料も除外
                    if mat.get("manualLock", False):
                        continue
                    url_to_instances[url].append((m, mat))

        for url, insts in url_to_instances.items():
            if len(insts) <= 1:
                continue

            scored_candidates = []
            for m, mat in insts:
                score = 0
                m_title = m.get("title", "")
                m_id = m.get("id", "")
                mat_name = mat.get("name", "")

                m_sessions = extract_session_numbers(m_title + " " + m_id)
                mat_sessions = extract_session_numbers(mat_name + " " + url)

                common_sessions = m_sessions.intersection(mat_sessions)
                if common_sessions:
                    score += 100 * len(common_sessions)

                m_years = extract_years(m.get("date", "") + " " + m_title)
                mat_years = extract_years(mat_name + " " + url)
                common_years = m_years.intersection(mat_years)
                if common_years:
                    score += 10 * len(common_years)

                if re.search(r'第\d+回', m_title):
                    score += 5

                m_date = m.get("date", "")
                if m_date and not m_date.startswith(INVALID_DATE_PREFIXES):
                    score += 2

                scored_candidates.append((score, m, mat))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            best_m = scored_candidates[0][1]

            for score, m, mat in scored_candidates:
                if m["id"] != best_m["id"]:
                    m["materials"] = [x for x in m["materials"] if x.get("url") != url]
                    removed_cross_dup += 1

    if removed_cross_dup > 0 or removed_portal > 0:
        print(f"[重複排除] 会議間重複資料 {removed_cross_dup} 件、ポータルリンク {removed_portal} 件を自動整理しました。")

def run_meeting_crawler(progress_callback=None, stop_event=None):
    global CRAWL_TARGETS
    
    log_f, latest_f, log_filepath, latest_filepath = init_crawler_logfile()

    def emit(msg, payload=None):
        print(msg)
        now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{now_ts}] {msg}\n"
        if log_f:
            try:
                log_f.write(log_line)
                log_f.flush()
            except OSError:
                pass
        if latest_f:
            try:
                latest_f.write(log_line)
                latest_f.flush()
            except OSError:
                pass
        if progress_callback:
            try:
                progress_callback(msg, payload)
            except Exception as pe:
                print(f"[WARN] progress_callback error: {pe}", file=sys.stderr)

    try:
        dynamic_targets = load_councils_from_data_json()
        if dynamic_targets:
            CRAWL_TARGETS = interleave_by_ministry(dynamic_targets)
            emit(f"[INFO] docs/data.json から {len(CRAWL_TARGETS)} 件の会議体を動的に読み込み、同一省庁連続アクセス防止のため省庁分散インターリーブ巡回順に並び替えました。")
        else:
            CRAWL_TARGETS = []
            emit(f"[INFO] 会議体データが見つかりません。")
            return {"success": 0, "partial": 0, "failed": 0, "fetch_error": 0, "new_meetings": 0, "log_file": log_filepath}

        use_llm = load_crawler_config()
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        emit("=" * 60)
        emit(" 政策会議ウォッチ (PM-HUB) クローラー")
        emit("=" * 60)
        emit(f"抽出モード: {'LLM抽出 (Gemini API) + フォールバック' if use_llm else '既存ルール (Heuristic)'}")
        emit(f"取得実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        emit(f"対象会議体数: {len(CRAWL_TARGETS)} 件")
        if log_filepath:
            emit(f"ログファイル出力先: {log_filepath}\n")

        # data.json を読み込み（ステータス更新用）
        data = load_data_json(DATA_JSON_FILE)

        # クロール開始時に lastCrawlTime を即時更新・バックアップ保存
        data["lastCrawlTime"] = now_str
        save_data_json_with_backup(data)

        rules = load_scraping_rules()
        results = []
        stats = {
            "success": 0,
            "partial": 0,
            "failed": 0,
            "fetch_error": 0,
            "new_meetings": 0,
            "stopped": False,
            "processed_councils": 0,
            "newly_added_list": [],
            "log_file": log_filepath
        }
        total_councils = len(CRAWL_TARGETS)

        for idx, target in enumerate(CRAWL_TARGETS, 1):
            # 途中停止チェック
            if stop_event and stop_event.is_set():
                emit(f"\n🛑 [STOP] ユーザーまたはシステムによる停止要求を受信しました。処理を安全に中断します（処理済み: {idx-1}/{total_councils} 件）。")
                stats["stopped"] = True
                break

            pct = int((idx / max(total_councils, 1)) * 90)
            c_name = target.get("name", target.get("id"))
            c_min = target.get("ministry", "")
            
            emit(f"▶ [{idx}/{total_councils}] [{c_min}] HTTP GET: {c_name} ({target['url']})...", {
                "type": "council_start",
                "council_id": target["id"],
                "council_name": c_name,
                "ministry": c_min,
                "progress": pct,
                "current": idx,
                "total": total_councils,
                "log_file": log_filepath
            })
            
            try:
                html = fetch_url(target["url"])
                stats["processed_councils"] += 1
                
                if html:
                    c_id = target["id"]
                    rule_obj = rules.get(c_id, {
                        "rule_id": "rule-fallback-v1",
                        "rules": {}
                    })
                    
                    item = execute_rule_retrieval(target, html, rule_obj, use_llm=use_llm)
                    results.append(item)
                    
                    cr = item.get("crawlResult", "failed")
                    stats[cr] = stats.get(cr, 0) + 1
                    
                    status_icon = {"success": "🟢", "partial": "🟡", "failed": "🔴"}.get(cr, "⚪")
                    emit(f"  -> {status_icon} [{cr.upper()}] タイトル: {item['pageTitle']}")
                    emit(f"  -> 資料: {item['totalExtractedMaterials']} 件, 日付: {item['extractedDates']}, 抽出方法: {item['extractionMethod']}")
                    
                    update_crawl_status(data, target["id"], item)
                    new_added = sync_new_meetings_from_crawl(data, target, item)
                    if new_added > 0:
                        stats["new_meetings"] += new_added
                        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
                        data["lastCrawlTime"] = now_str
                        save_data_json_with_backup(data, create_backup=False)
                        emit(f"  -> 📦 新規会議 {new_added} 件を data.json の meetings に自動追加・同期しました。", {
                            "type": "new_meeting_added",
                            "council_id": target["id"],
                            "council_name": c_name,
                            "new_added": new_added
                        })
                else:
                    stats["fetch_error"] += 1
                    emit(f"  -> 🔴 [FETCH ERROR] ネットワーク取得失敗")
                    update_crawl_status(data, target["id"], None, "Network fetch failed")
            except Exception as council_err:
                stats["failed"] += 1
                emit(f"  -> 🔴 [UNEXPECTED ERROR] 会議体巡回中に予期せぬ例外が発生しました: {council_err}")
                try:
                    update_crawl_status(data, target["id"], None, f"Unexpected error: {council_err}")
                except Exception as status_err:
                    emit(f"  -> [WARN] update_crawl_status 記録失敗: {status_err}")
            emit("-" * 65)

            # レートリミット（スロットリング: 行政サーバー負荷軽減 & WAFブロック回避）
            if idx < total_councils and not (stop_event and stop_event.is_set()):
                time.sleep(0.35)

        # サマリー表示
        emit(f"\n{'='*60}")
        if stats.get("stopped"):
            emit(f" 🛑 クロール中断サマリー (途中停止)")
        else:
            emit(f" クロール結果サマリー (完了)")
        emit(f"{'='*60}")
        emit(f"  処理会議体数:          {stats['processed_councils']} / {total_councils} 件")
        emit(f"  🟢 成功 (success):     {stats['success']} 件")
        emit(f"  🟡 部分成功 (partial):    {stats['partial']} 件")
        emit(f"  🔴 失敗 (failed):      {stats['failed']} 件")
        emit(f"  🔴 取得エラー:         {stats['fetch_error']} 件")
        emit(f"  📦 新規追加会議:       {stats['new_meetings']} 件")
        if log_filepath:
            emit(f"  📄 ログファイル:       {log_filepath}")
        emit(f"{'='*60}")

        # 全体データに対して資料リンクの重複排除・正規化を実施
        deduplicate_data_materials(data)

        # data.json にクロールステータスと最終タイムスタンプを保存（バックアップ付き）
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        data["lastCrawlTime"] = now_str
        if save_data_json_with_backup(data):
            emit(f"[更新成功] docs/data.json にクロール結果・ステータスと lastCrawlTime ({now_str}) を保存しました（自動バックアップ作成完了）。")
        else:
            emit(f"[WARN] data.json 更新失敗")

        # 新規追加された会議リストを抽出してイベントに添付
        newly_added = [m for m in data.get("meetings", []) if m.get("isNewlyDiscovered")]
        stats["newly_added_list"] = newly_added[:20]

        finish_type = "crawl_stopped" if stats.get("stopped") else "crawl_completed"
        emit(f"処理終了: docs/data.json を更新しました。", {
            "type": finish_type,
            "progress": 100,
            "stats": stats,
            "newly_added_count": len(newly_added),
            "lastCrawlTime": now_str,
            "log_file": log_filepath,
            "stopped": stats.get("stopped", False)
        })
        
        return stats
    finally:
        if log_f:
            try: log_f.close()
            except OSError: pass
        if latest_f:
            try: latest_f.close()
            except OSError: pass

def main():
    import threading
    import traceback
    cli_stop_event = threading.Event()
    
    try:
        run_meeting_crawler(stop_event=cli_stop_event)
    except KeyboardInterrupt:
        print("\n\n[INFO] キーボード割り込み (Ctrl+C) を検知しました。停止シグナルを発行します...")
        cli_stop_event.set()
    except Exception as e:
        print(f"\n\n[FATAL CRASH] クローラー実行中に未処理の例外が発生しました: {e}", file=sys.stderr)
        traceback.print_exc()
        try:
            with open("admin/logs/crawler_crash.log", "a", encoding="utf-8") as cf:
                cf.write(f"[{datetime.now()}] FATAL CRASH: {e}\n")
                traceback.print_exc(file=cf)
        except OSError:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
