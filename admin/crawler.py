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
CRAWLER_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "crawler_config.json")

def load_crawler_config():
    if os.path.exists(CRAWLER_CONFIG_FILE):
        try:
            with open(CRAWLER_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("llm_mode", True)
        except Exception:
            pass
    return True

def load_councils_from_data_json():
    """docs/data.json から登録済みの全会議体 (COUNCILS) を読み込む"""
    councils = []
    if os.path.exists(DATA_JSON_FILE):
        try:
            with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_councils = data.get("councils", [])
                for item in raw_councils:
                    if item.get("officialUrl"):
                        councils.append({
                            "id": item.get("id"),
                            "ministry": item.get("ministry"),
                            "name": item.get("name"),
                            "url": item.get("officialUrl")
                        })
        except Exception as e:
            print(f"[WARN] data.json 読み込み失敗: {e}", file=sys.stderr)
    return councils

def load_scraping_rules():
    """docs/data.json の scrapingRules キーからスクレイピングルールを読み込む"""
    if os.path.exists(DATA_JSON_FILE):
        try:
            with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("scrapingRules", {})
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
    """HTMLから全配布資料（公開PDFおよび非公開資料）を抽出"""
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
                raw_sub_dates = re.findall(rule.get("date_regex", r'(?:令和|平成)\d+年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'), sub_html)
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

def parse_japanese_date(date_str):
    """和暦・西暦文字列を datetime オブジェクトに変換"""
    if not date_str:
        return None
    date_str = normalize_japanese_numbers(date_str)
    m_reiwa = re.search(r'令和(\d+)年(\d+)月(\d+)日', date_str)
    if m_reiwa:
        try:
            return datetime(2018 + int(m_reiwa.group(1)), int(m_reiwa.group(2)), int(m_reiwa.group(3)))
        except Exception:
            pass
    m_heisei = re.search(r'平成(\d+)年(\d+)月(\d+)日', date_str)
    if m_heisei:
        try:
            return datetime(1988 + int(m_heisei.group(1)), int(m_heisei.group(2)), int(m_heisei.group(3)))
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

def extract_via_llm(url, html, target_name):
    if not model:
        print("[WARN] LLM model not initialized. Skipping LLM extraction.")
        return [], []
        
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup(["script", "style"]):
        script.extract()
    body_text = soup.get_text(separator=' ', strip=True)
    body_text = re.sub(r'\s+', ' ', body_text)[:5000] # Limit tokens
    
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
        
        # fix relative urls
        for m in materials:
            if m.get("url") and not m["url"].startswith("http"):
                m["url"] = urllib.parse.urljoin(url, m["url"])
                
        return materials, data.get("extractedDates", [])
    except Exception as e:
        print(f"[ERROR] LLM Extraction failed: {e}")
        return [], []

def execute_rule_retrieval(target, html, rule_item, use_llm=True):
    """2回目情報取得Engine"""
    rule = rule_item.get("rules", {})
    quirk_note = rule_item.get("ministryQuirk", "標準抽出ルール")
    
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else target["name"]

    unique_materials = []
    norm_date_matches = []
    subpage_meetings = []
    
    if use_llm:
        print("   [LLM Extraction Mode] Extracting data using Gemini API...")
        materials, dates = extract_via_llm(target["url"], html, target["name"])
        unique_materials = materials
        norm_date_matches = dates
    else:
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

        raw_date_matches = re.findall(rule.get("date_regex", r'(?:令和|平成)\d+年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'), html)
        norm_date_matches = [normalize_japanese_numbers(d) for d in raw_date_matches]
        all_extracted_dates.extend(norm_date_matches)

    past_year_count, has_top_page_dates = calculate_past_year_count(norm_date_matches)

    scraped_item = {
        "councilId": target["id"],
        "councilName": target["name"],
        "ministry": target["ministry"],
        "officialUrl": target["url"],
        "scrapedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruleApplied": rule_item.get("rule_id", "rule-default"),
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

def main():
    global CRAWL_TARGETS
    dynamic_targets = load_councils_from_data_json()
    if dynamic_targets:
        CRAWL_TARGETS = dynamic_targets
        print(f"[INFO] docs/data.json から {len(CRAWL_TARGETS)} 件の会議体を動的に読み込みました。")
    else:
        CRAWL_TARGETS = []
        print(f"[INFO] 会議体データが見つかりません。")

    use_llm = load_crawler_config()
    print("==========================================================")
    print(" 政策会議ウォッチ (PM-HUB) クローラー")
    print("==========================================================")
    print(f"抽出モード: {'LLM抽出 (Gemini API)' if use_llm else '既存ルール (Heuristic)'}")
    print(f"取得実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"対象会議体数: {len(CRAWL_TARGETS)} 件\n")

    rules = load_scraping_rules()
    results = []

    for idx, target in enumerate(CRAWL_TARGETS, 1):
        print(f"[{idx}/{len(CRAWL_TARGETS)}] HTTP GET: {target['name']} ({target['url']})...")
        html = fetch_url(target["url"])
        
        if html:
            c_id = target["id"]
            rule_obj = rules.get(c_id, {
                "rule_id": "rule-fallback-v1",
                "rules": {}
            })
            
            item = execute_rule_retrieval(target, html, rule_obj, use_llm=use_llm)
            results.append(item)
            
            print(f"  -> [200 OK] タイトル: {item['pageTitle']}")
            print(f"  -> [データ抽出成功] 総抽出資料数: {item['totalExtractedMaterials']} 件, 検出日付: {item['extractedDates']}")
        else:
            print(f"  -> [SKIP] ネットワーク取得スキップ")
        print("-" * 65)

    output_filename = os.path.join(os.path.dirname(__file__), "scraped_councils_output.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # タイムスタンプのみ更新
    now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
    if os.path.exists(DATA_JSON_FILE):
        try:
            with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["last_crawl_time"] = now_str
            with open(DATA_JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[更新成功] docs/data.json の last_crawl_time を '{now_str}' に更新しました。")
        except Exception as e:
            print(f"[WARN] data.json 更新失敗: {e}")

    print(f"\nデータ取得完了: 結果を {output_filename} に保存しました。")

if __name__ == "__main__":
    main()
