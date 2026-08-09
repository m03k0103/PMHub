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

RULES_FILE = os.path.join(os.path.dirname(__file__), "scraping_rules.json")
DATA_JS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.js"))

def load_councils_from_data_js():
    """docs/data.js から登録済みの全会議体 (COUNCILS) を動的に読み込む"""
    councils = []
    if os.path.exists(DATA_JS_FILE):
        try:
            with open(DATA_JS_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            c_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
            if c_match:
                c_str = c_match.group(1).rstrip(";").strip()
                c_json = re.sub(r"(\w+):", r'"\1":', c_str).replace("'", '"')
                raw_councils = json.loads(c_json)
                for item in raw_councils:
                    if item.get("officialUrl"):
                        councils.append({
                            "id": item.get("id"),
                            "ministry": item.get("ministry"),
                            "name": item.get("name"),
                            "url": item.get("officialUrl")
                        })
        except Exception as e:
            print(f"[WARN] data.js からの会議体動的読み込みにフォールバック: {e}", file=sys.stderr)
            with open(DATA_JS_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            for m in re.finditer(r"\{\s*id:\s*'([^']+)'[\s\S]*?name:\s*'([^']+)'[\s\S]*?ministry:\s*'([^']+)'[\s\S]*?officialUrl:\s*'([^']+)'", content):
                councils.append({
                    "id": m.group(1),
                    "name": m.group(2),
                    "ministry": m.group(3),
                    "url": m.group(4)
                })
    return councils

def load_scraping_rules():
    """2回目用情報取得ルール (scraping_rules.json) を読み込む"""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load scraping_rules.json: {e}", file=sys.stderr)
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

def execute_rule_retrieval(target, html, rule_item):
    """【2回目情報取得Engine】AI考案ルールに基づき2段階階層クロールおよび資料データをフル抽出"""
    rule = rule_item.get("rules", {})
    quirk_note = rule_item.get("ministryQuirk", "標準抽出ルール")
    
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else target["name"]

    pdf_pattern = rule.get("pdf_selector", r'href=["\']([^"\']+\.pdf)["\']')
    top_materials = parse_materials_from_html(html, target["url"], pdf_pattern)

    subpage_meetings = []
    deep_enabled = rule.get("deep_crawl_enabled", True)
    all_extracted_dates = []
    
    if deep_enabled:
        new_meetings, new_materials, new_dates = _crawl_subpages(target["url"], html, rule, quirk_note, pdf_pattern)
        subpage_meetings.extend(new_meetings)
        top_materials.extend(new_materials)
        all_extracted_dates.extend(new_dates)

    unique_materials = []
    seen_keys = set()
    for m in top_materials:
        key = m["url"] if m["url"] != "#" else m["name"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_materials.append(m)

    raw_date_matches = re.findall(rule.get("date_regex", r'(?:令和|平成)\d+年\d+月\d+日|\d{4}年\d+月\d+日|\d{4}[/-]\d+[/-]\d+'), html)
    norm_date_matches = [normalize_japanese_numbers(d) for d in raw_date_matches]
    all_extracted_dates.extend(norm_date_matches)

    past_year_count, has_top_page_dates = calculate_past_year_count(all_extracted_dates)

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

def load_councils_from_data_js():
    import subprocess
    import json
    import os
    project_root = os.path.dirname(os.path.dirname(__file__))
    data_js_path = os.path.join(project_root, "docs", "data.js")
    if not os.path.exists(data_js_path):
        return []
    node_script = f"""
const fs = require('fs');
const vm = require('vm');
try {{
    const dataCode = fs.readFileSync({json.dumps(data_js_path)}, 'utf-8');
    const context = {{}};
    vm.createContext(context);
    vm.runInContext(dataCode, context);
    if (context.COUNCILS) {{
        console.log(JSON.stringify(context.COUNCILS));
    }} else {{
        console.log("[]");
    }}
}} catch (err) {{
    console.error(err);
    process.exit(1);
}}
"""
    try:
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, encoding='utf-8')
        if proc.returncode == 0:
            councils = json.loads(proc.stdout.strip())
            targets = []
            for c in councils:
                targets.append({
                    "id": c.get("id"),
                    "ministry": c.get("ministry"),
                    "name": c.get("name"),
                    "url": c.get("officialUrl")
                })
            return targets
    except Exception as e:
        print(f"[WARN] Failed to load dynamically from data.js: {e}")
    return []

def main():
    global CRAWL_TARGETS
    dynamic_targets = load_councils_from_data_js()
    if dynamic_targets:
        CRAWL_TARGETS = dynamic_targets
        print(f"[INFO] docs/data.js から {len(CRAWL_TARGETS)} 件の会議体を動的に読み込みました。")
    else:
        print(f"[INFO] 静的な CRAWL_TARGETS ({len(CRAWL_TARGETS)} 件) を使用します。")

    print("==========================================================")
    print(" 政策会議ウォッチ (PM-HUB) 2回目用情報取得Engine ")
    print("==========================================================")
    print(f"取得実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"対象会議体数: {len(CRAWL_TARGETS)} 件\n")

    rules = load_scraping_rules()
    if not rules:
        print("[WARN] 'scraping_rules.json' が見つかりません。先に agent_initial_verifier.py を実行してください。", file=sys.stderr)

    results = []

    for idx, target in enumerate(CRAWL_TARGETS, 1):
        print(f"[{idx}/{len(CRAWL_TARGETS)}] HTTP GET: {target['name']} ({target['url']})...")
        html = fetch_url(target["url"])
        
        if html:
            c_id = target["id"]
            rule_obj = rules.get(c_id, {
                "rule_id": "rule-fallback-v1",
                "rules": {
                    "pdf_selector": r'href=["\']([^"\']+\.pdf)["\']',
                    "date_regex": r'令和\d+年\d+月\d+日'
                }
            })
            print(f"   [2回目ルール適用] '{rule_obj.get('rule_id')}' に基づき全自動データ抽出")

            item = execute_rule_retrieval(target, html, rule_obj)
            results.append(item)
            
            print(f"  -> [200 OK] タイトル: {item['pageTitle']}")
            print(f"  -> [データ抽出成功] 総抽出資料数: {item['totalExtractedMaterials']} 件, 検出日付: {item['extractedDates']}")
        else:
            print(f"  -> [SKIP] ネットワーク取得スキップ")
        print("-" * 65)

    output_filename = os.path.join(os.path.dirname(__file__), "scraped_councils_output.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # docs/data.js の LAST_CRAWL_TIME を最新のクロール実行時刻に自動更新
    project_root = os.path.dirname(os.path.dirname(__file__))
    data_js_path = os.path.join(project_root, "docs", "data.js")
    if os.path.exists(data_js_path):
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M")
        with open(data_js_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "const LAST_CRAWL_TIME =" in content:
            updated_content = re.sub(
                r"const LAST_CRAWL_TIME = '[^']*';",
                f"const LAST_CRAWL_TIME = '{now_str}';",
                content
            )
            with open(data_js_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
            print(f"[更新成功] docs/data.js の LAST_CRAWL_TIME を '{now_str}' に更新しました。")

    print(f"\nデータ取得完了: 結果を {output_filename} に保存しました。")

if __name__ == "__main__":
    main()
