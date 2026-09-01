#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 2回目用情報取得Engine (2nd-Time Information Retrieval Engine)
1回目用情報確認Agent (agent_initial_verifier.py) が生成した抽出ルール (scraping_rules.json) を読み込み、
高速・高精度な2段階階層クロールおよび資料データ取得を実行する専用Engine
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import re
import io
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import google.generativeai as genai

API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
    try:
        model = genai.GenerativeModel('gemini-3.6-flash')
    except Exception as e:
        print(f"Failed to initialize Gemini model: {e}")
        model = None
else:
    model = None

# Windows ターミナルログの文字化け防止 (chcp 65001 & UTF-8 再構成)
if sys.platform == "win32":
    os.system("chcp 65001 > NUL 2>&1")
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass


DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "backups"))
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "logs"))

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


def save_data_json_with_backup(data, target_file=DATA_JSON_FILE):
    """
    docs/data.json を更新する前に、タイムスタンプ付きで docs/backups/ に自動バックアップを作成し、
    安全に上書き保存する（過去30世代保持）。
    """
    import shutil
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        if os.path.exists(target_file):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(BACKUP_DIR, f"data_{ts}.json")
            shutil.copy2(target_file, backup_path)
            
            # 過去30世代を超える古いバックアップの自動整理
            b_files = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.startswith("data_") and f.endswith(".json")])
            if len(b_files) > 30:
                for old_f in b_files[:-30]:
                    try:
                        os.remove(old_f)
                    except Exception:
                        pass

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save data.json with backup: {e}", file=sys.stderr)
        return False

def load_crawler_config():
    if os.path.exists(DATA_JSON_FILE):
        try:
            with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = data.get("crawlerConfig", {})
                return config.get("llm_mode", False)  # デフォルトは高速・安全な Heuristic モード
        except Exception:
            pass
    return False

def load_councils_from_data_json():
    """docs/data.json から登録済みの全会議体 (COUNCILS) を読み込む（却下済み会議体はクロール対象外）"""
    councils = []
    
    # 却下済みIDセットの読み込み
    rejected_ids = set()
    rejected_file = os.path.join(os.path.dirname(__file__), "rejected_councils.json")
    if os.path.exists(rejected_file):
        try:
            with open(rejected_file, "r", encoding="utf-8") as rf:
                rejected_data = json.load(rf)
                for rc in rejected_data:
                    if rc.get("id"):
                        rejected_ids.add(rc.get("id"))
            print(f"[INFO] 却下済み会議体 {len(rejected_ids)} 件をクロール対象から除外します。")
        except Exception as e:
            print(f"[WARN] failed to load rejected_councils.json: {e}", file=sys.stderr)

    if os.path.exists(DATA_JSON_FILE):
        try:
            with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_councils = data.get("councils", [])
                for item in raw_councils:
                    cid = item.get("id")
                    if cid in rejected_ids:
                        continue
                    if item.get("officialUrl"):
                        councils.append({
                            "id": cid,
                            "ministry": item.get("ministry"),
                            "name": item.get("name"),
                            "url": item.get("officialUrl")
                        })
        except Exception as e:
            print(f"[WARN] data.json 読み込み失敗: {e}", file=sys.stderr)
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
    if os.path.exists(DATA_JSON_FILE):
        try:
            with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                templates = data.get("scrapingRuleTemplates", {})
                raw_rules = data.get("scrapingRules", {})
                
                resolved_rules = {}
                for cid, r in raw_rules.items():
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

def fetch_url(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        print(f"[ERROR] Invalid scheme: {url}", file=sys.stderr)
        return None
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHubRetrievalEngine/2.0'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def parse_materials_from_html(html, base_url, pdf_selector):
    """HTMLから全配布資料（公開PDFおよび非公開資料）を抽出（ポータルや一覧ページ等のノイズは除外）"""
    materials = []
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Base URL consideration
    base_tag = soup.find('base', href=True)
    if base_tag:
        base_url = urllib.parse.urljoin(base_url, base_tag['href'])
    
    # Extract PDF links
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href.lower().endswith('.pdf'):
            link_text = a_tag.get_text(strip=True)
            clean_name = link_text if link_text else os.path.basename(href)
            abs_url = urllib.parse.urljoin(base_url, href)
            
            # ポータルや一覧、一次ソースリンクを除外
            if abs_url == base_url or any(k in clean_name for k in ['公式ポータル', '公式ページ', '公式情報ポータル', '審議会・検討会等一覧', '公式掲載資料・ページ']):
                continue
                
            materials.append({
                "name": clean_name,
                "url": abs_url,
                "type": "PDF",
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

def normalize_japanese_numbers(text):
    """全角英数字・漢数字を半角数値に正規化"""
    tr_map = str.maketrans('０１２３４５６７８９', '0123456789')
    return text.translate(tr_map)

def _crawl_subpages(target_url, html, rule, quirk_note, pdf_pattern):
    """サブページの深掘りクロールロジック"""
    subpage_meetings = []
    additional_materials = []
    all_extracted_dates = []

    soup = BeautifulSoup(html, 'html.parser')
    base_tag = soup.find('base', href=True)
    page_base_url = urllib.parse.urljoin(target_url, base_tag['href']) if base_tag else target_url

    subpage_pattern = rule.get("subpage_discovery_pattern", r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai)[^"\'#]*)["\']')
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

            sub_html = fetch_url(sub_url)
            if sub_html:
                try:
                    sub_soup = BeautifulSoup(sub_html, 'html.parser')
                    sub_title = sub_soup.title.string.strip() if sub_soup.title and sub_soup.title.string else sub_url
                except Exception:
                    sub_title = sub_url

                sub_materials = parse_materials_from_html(sub_html, sub_url, pdf_pattern)
                raw_sub_dates = extract_clean_dates_from_html(sub_html, rule.get("date_regex", r'(?:令和|平成)(?:\d+|元)年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'))
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
            el.decompose()
        for el in soup.find_all(class_=re.compile(r'(side|nav|footer|header|menu|breadcrumb)', re.I)):
            el.decompose()
        main_el = soup.find(id=re.compile(r'(main|content)', re.I)) or soup.find(class_=re.compile(r'(main|content)', re.I)) or soup.body
        return str(main_el) if main_el else str(soup)
    except Exception:
        return html_str

def extract_clean_dates_from_html(html_str, date_regex_pattern=r'(?:令和|平成)(?:\d+|元)年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'):
    """更新日・掲載日などのノイズを除去して会議開催日を抽出"""
    cleaned_html = clean_html_for_dates(html_str)
    raw_dates = re.findall(date_regex_pattern, cleaned_html)
    
    # 「更新日: 2024年X月X日」「掲載日: ...」などの直前ラベル付きの日付を除外
    filtered_dates = []
    for d in raw_dates:
        # 直前20文字に「更新日」「掲載日」「公表日」「作成日」が含まれる場合は除外
        escaped_d = re.escape(d)
        if re.search(r'(?:更新日|最終更新|掲載日|公表日|作成日|ページID|copyright)[\s\:\：\-\.\/]*' + escaped_d, cleaned_html, re.I):
            continue
        filtered_dates.append(d)
        
    return filtered_dates if filtered_dates else raw_dates

def parse_japanese_date(date_str):
    """和暦・西暦文字列を datetime オブジェクトに変換（元年対応）"""
    if not date_str:
        return None
    date_str = normalize_japanese_numbers(date_str)
    m_reiwa = re.search(r'令和(\d+|元)年(\d+)月(\d+)日', date_str)
    if m_reiwa:
        try:
            yr_num = 1 if m_reiwa.group(1) == '元' else int(m_reiwa.group(1))
            return datetime(2018 + yr_num, int(m_reiwa.group(2)), int(m_reiwa.group(3)))
        except Exception:
            pass
    m_heisei = re.search(r'平成(\d+|元)年(\d+)月(\d+)日', date_str)
    if m_heisei:
        try:
            yr_num = 1 if m_heisei.group(1) == '元' else int(m_heisei.group(1))
            return datetime(1988 + yr_num, int(m_heisei.group(2)), int(m_heisei.group(3)))
        except Exception:
            pass
    m_seireki = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
    if m_seireki:
        try:
            return datetime(int(m_seireki.group(1)), int(m_seireki.group(2)), int(m_seireki.group(3)))
        except Exception:
            pass
    m_slash = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', date_str)
    if m_slash:
        try:
            return datetime(int(m_slash.group(1)), int(m_slash.group(2)), int(m_slash.group(3)))
        except Exception:
            pass
    return None

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

    # 会議サブページのパターン (dai1, 1kai, kaisai, gijisidai, etc.)
    subpage_pattern = re.compile(
        r'(?:dai\d+|\d+kai|kaisai|gijisidai|gijiroku|kaigi|meeting|shiryo)',
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
        if abs_url in seen or abs_url == base_url:
            continue
        if subpage_pattern.search(href):
            seen.add(abs_url)
            candidates.append(abs_url)
    
    return candidates[:8]  # 最大8サブページ

def extract_via_llm_single(url, html, target_name):
    """単一ページに対してLLM抽出を実行する"""
    global LLM_QUOTA_BLOCKED
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
    
    deep_enabled = rule.get("deep_crawl_enabled", True)
    all_extracted_dates = []
    
    if deep_enabled:
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

    raw_date_matches = extract_clean_dates_from_html(html, rule.get("date_regex", r'(?:令和|平成)(?:\d+|元)年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'))
    norm_date_matches = [normalize_japanese_numbers(d) for d in raw_date_matches]
    all_extracted_dates.extend(norm_date_matches)
    
    if unique_materials or norm_date_matches or subpage_meetings:
        extraction_method = "rule"
    else:
        # Stage 2: ルールで0件の場合のみ LLM (Gemini API) フォールバックを試行
        if use_llm and not LLM_QUOTA_BLOCKED and model:
            print(f"   [Stage 2 Fallback] ルール未検出 → LLM Extraction (Gemini API) を試行...")
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


def sync_new_meetings_from_crawl(data, target, scraped_item):
    """
    クロール時に検出されたサブページ（個別開催回）から、未登録の新規開催回を自動検知して
    docs/data.json の meetings 配列に正しく追加する。
    ※ 既存の会議レコード（manualLock: true を含む）は完全保護し、上書き・改変しない。
    """
    if not scraped_item:
        return 0

    subpages = scraped_item.get("subpageMeetings", [])
    if not subpages:
        return 0

    council_id = target["id"]
    council_name = target["name"]
    ministry = target["ministry"]
    meetings = data.setdefault("meetings", [])

    existing_c_meets = [m for m in meetings if m.get("councilId") == council_id]
    existing_urls = {m.get("officialUrl", "").rstrip("/"): m for m in existing_c_meets if m.get("officialUrl")}
    existing_titles = {m.get("title", ""): m for m in existing_c_meets if m.get("title")}
    existing_sessions = set()
    for m in existing_c_meets:
        sess_list = extract_session_numbers(m.get("title", "") + " " + m.get("officialUrl", "") + " " + m.get("id", ""))
        for s in sess_list:
            existing_sessions.add(s)

    added_count = 0
    for sub in subpages:
        sub_url = sub.get("subpageUrl", "").rstrip("/")
        sub_title = sub.get("title", "").strip()
        sub_mats = sub.get("materials", [])
        sub_dates = sub.get("extractedDates", [])

        # 開催回番号の抽出
        sess_nums = extract_session_numbers(sub_title + " " + sub_url)
        # 既に該当回次が登録済みの場合はスキップ
        if sess_nums and any(s in existing_sessions for s in sess_nums):
            continue

        # 既にURLまたはタイトルが完全一致している場合はスキップ
        if sub_url and sub_url in existing_urls:
            continue
        if sub_title and sub_title in existing_titles:
            continue

        # 日付の算出および YYYY/MM/DD への正規化
        meet_date = ""
        if sub_dates:
            dt = parse_japanese_date(sub_dates[0])
            if dt:
                meet_date = dt.strftime("%Y/%m/%d")
            else:
                m_iso = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', str(sub_dates[0]))
                if m_iso:
                    meet_date = f"{int(m_iso.group(1)):04d}/{int(m_iso.group(2)):02d}/{int(m_iso.group(3)):02d}"
        
        if not meet_date:
            dt = parse_japanese_date(sub_title)
            if dt:
                meet_date = dt.strftime("%Y/%m/%d")
            else:
                meet_date = datetime.now().strftime("%Y/%m/%d")

        # 会議IDの生成（4セグメント統一形式: {council_id}-{YYYYMMDD}-{回次000またはs00}）
        clean_d = meet_date.replace("/", "").replace("-", "")
        sess_suffix = f"{sorted(sess_nums)[0]:03d}" if sess_nums else f"s{len(existing_c_meets) + added_count + 1:02d}"
        new_meet_id = f"{council_id}-{clean_d}-{sess_suffix}"

        # 重複ID回避
        if any(m.get("id") == new_meet_id for m in meetings):
            new_meet_id = f"{council_id}-{clean_d}-{sess_suffix}_{added_count+1}"

        # タイトルの正規化
        formatted_title = sub_title
        if council_name not in formatted_title and sess_nums:
            formatted_title = f"第{sorted(sess_nums)[0]}回 {council_name}"
        elif not formatted_title or formatted_title.startswith("http"):
            formatted_title = f"{council_name} ({meet_date})"

        # 資料配列の構築
        clean_materials_list = []
        for mat in sub_mats:
            mat_name = mat.get("name", "").strip()
            mat_url = mat.get("url", "").strip()
            mat_type = mat.get("type", "PDF")
            if not mat_url or mat_url == "#" or mat_url == sub_url:
                continue
            clean_materials_list.append({
                "name": mat_name if mat_name else os.path.basename(mat_url),
                "url": mat_url,
                "type": mat_type,
                "isPrivate": mat.get("isPrivate", False)
            })

        new_meeting = {
            "id": new_meet_id,
            "councilId": council_id,
            "title": formatted_title,
            "date": meet_date,
            "officialUrl": sub.get("subpageUrl") or target.get("officialUrl") or target.get("url", ""),
            "category": target.get("category", "COUNCIL"),
            "ministry": ministry,
            "materials": clean_materials_list,
            "isNewlyDiscovered": True,
            "discoveredAt": datetime.now().strftime("%Y/%m/%d %H:%M")
        }

        meetings.append(new_meeting)
        existing_urls[sub_url] = new_meeting
        existing_titles[formatted_title] = new_meeting
        for s in sess_nums:
            existing_sessions.add(s)
        added_count += 1
        print(f"  [✨ 新規開催回自動追加] [{meet_date}] {formatted_title} (ID: {new_meet_id}, 資料: {len(clean_materials_list)}件)")

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
    nums = set()
    matches = re.findall(r'第(\d+)回', text)
    for m in matches:
        nums.add(int(m))
    matches_dai = re.findall(r'dai(\d+)', text, re.IGNORECASE)
    for m in matches_dai:
        nums.add(int(m))
    matches_slash = re.findall(r'[/_](\d{1,3})(?:[_.]|pdf|giji)', text, re.IGNORECASE)
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
        c_url = c_info.get("url", "").strip()

        # 1. ポータル・公式ページ・一覧ページの資料リンクを除外
        for m in m_list:
            clean_mats = []
            for mat in m.get("materials", []):
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
                if m_date and not m_date.startswith("1312") and not m_date.startswith("2026/08/09"):
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
            except Exception:
                pass
        if latest_f:
            try:
                latest_f.write(log_line)
                latest_f.flush()
            except Exception:
                pass
        if progress_callback:
            try:
                progress_callback(msg, payload)
            except Exception as pe:
                print(f"[WARN] progress_callback error: {pe}", file=sys.stderr)

    dynamic_targets = load_councils_from_data_json()
    if dynamic_targets:
        CRAWL_TARGETS = interleave_by_ministry(dynamic_targets)
        emit(f"[INFO] docs/data.json から {len(CRAWL_TARGETS)} 件の会議体を動的に読み込み、同一省庁連続アクセス防止のため省庁分散インターリーブ巡回順に並び替えました。")
    else:
        CRAWL_TARGETS = []
        emit(f"[INFO] 会議体データが見つかりません。")
        if log_f: log_f.close()
        if latest_f: latest_f.close()
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

    # data.json をまるごと読み込み（ステータス更新用）
    data = {}
    if os.path.exists(DATA_JSON_FILE):
        with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

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
                save_data_json_with_backup(data)
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
        emit("-" * 65)

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
    
    if log_f:
        try: log_f.close()
        except Exception: pass
    if latest_f:
        try: latest_f.close()
        except Exception: pass
        
    return stats

def main():
    import threading
    cli_stop_event = threading.Event()
    
    try:
        run_meeting_crawler(stop_event=cli_stop_event)
    except KeyboardInterrupt:
        print("\n\n[INFO] キーボード割り込み (Ctrl+C) を検知しました。停止シグナルを発行します...")
        cli_stop_event.set()

if __name__ == "__main__":
    main()
