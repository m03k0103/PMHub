#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - AI Adaptive Multi-Stage Crawler Engine
日本政府各省庁・内閣官房・内閣府の審議会・会議ウェブサイトから最新配布資料・議事要旨を自動収集・解析・構造化するPythonクローラー

【ユーザー指示事項の高度反映】
1. 【1回目情報確認Agent】:
   - 初回訪問時、ページのDOM構造（サブページ遷移リンク有無、非公開資料の記載有無、和暦/西暦形式）を高度解析。
   - 「2段階階層クロールルール」および「非公開資料検知フラグ」を含む AIルール (scraping_rules.json) を自動生成・永続保存。
2. 【2回目情報取得Engine】:
   - 初回に生成・保存されたルールに基づき、TOPページ ➔ 各個別回ページ (dai11/gijisidai.html 等) へ2段階アクセス。
   - 資料1〜12などの全配布資料を省略なくフル抽出（非公開資料は isPrivate: true として識別）。
   - 全相対URLを絶対パスに自動正規化。
"""

import sys
import os
import json
import urllib.request
import urllib.parse
import re
from datetime import datetime

RULES_FILE = os.path.join(os.path.dirname(__file__), "scraping_rules.json")

# クロール対象の政府審議会・会議体URLリスト
CRAWL_TARGETS = [
    {
        "id": "cas-chutou-jyousei",
        "ministry": "CAS",
        "name": "中東情勢に関する関係閣僚会議",
        "url": "https://www.cas.go.jp/jp/seisaku/chyutoujyousei/index.html"
    },
    {
        "id": "cao-ai-strategy",
        "ministry": "CAO",
        "name": "AI戦略会議",
        "url": "https://www8.cao.go.jp/cstp/ai/"
    },
    {
        "id": "cao-kisei-kaikaku",
        "ministry": "CAO",
        "name": "規制改革推進会議",
        "url": "https://www8.cao.go.jp/kisei-kaikaku/index.html"
    },
    {
        "id": "ra-fukko-suishin",
        "ministry": "RA",
        "name": "復興推進委員会",
        "url": "https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-155/cat-156/000813/"
    },
    {
        "id": "cas-zensedai-hosyo",
        "ministry": "CAS",
        "name": "全世代型社会保障構築会議",
        "url": "https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/index.html"
    },
    {
        "id": "cas-kokumin-kaigi",
        "ministry": "CAS",
        "name": "社会保障国民会議",
        "url": "https://www.cas.go.jp/jp/seisaku/kokuminkaigi/index.html"
    },
    {
        "id": "cao-ai-hq",
        "ministry": "CAO",
        "name": "人工知能戦略本部",
        "url": "https://www8.cao.go.jp/cstp/ai/ai_hq/kaisai.html"
    },
    {
        "id": "digital-suishin",
        "ministry": "DIGITAL",
        "name": "デジタル社会推進会議",
        "url": "https://www.digital.go.jp/councils/social-promotion"
    }
]

def load_scraping_rules():
    """AIが過去生成した抽出ルールファイルを読み込む"""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to load scraping rules: {e}", file=sys.stderr)
    return {}

def save_scraping_rules(rules_data):
    """生成したAIルールを永続保存する"""
    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save scraping rules: {e}", file=sys.stderr)

def fetch_url(url):
    """指定URLのHTMLを取得"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 PMHubCrawler/2.0'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            return html
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def generate_ai_rule(target, html):
    """【1回目: 情報確認Agent】Webページ構造を自動確認・解析し、2段階深掘りクロールルールを自動生成"""
    print(f"   [1回目: AI情報確認Agent起動] '{target['name']}' のDOM・個別回構造・非公開表記を自動解析中...")
    
    has_subpages = bool(re.search(r'href=["\']([^"\']*(?:dai\d+|kaisai|gijisidai|gijiroku)[^"\'#]*)["\']', html, re.IGNORECASE))
    has_private_docs = "非公開" in html
    has_wareki = bool(re.search(r'令和\d{1,2}年', html))
    
    rule = {
        "rule_id": f"rule-{target['id']}-v2",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generator": "AI_Adaptive_Rule_Engine_v2",
        "councilName": target["name"],
        "targetUrl": target["url"],
        "rules": {
            "encoding": "utf-8",
            "deep_crawl_enabled": has_subpages,
            "subpage_discovery_pattern": "href=[\"']([^\"']*(?:dai\\d+|kaisai|gijisidai|gijiroku)[^\"']*)[\"']" if has_subpages else None,
            "date_regex": "(?:令和[0-9０-９一-九]+年[0-9０-９一-十二]+月[0-9０-９一-三十一]+日|20[2-9][0-9]年[0-1]?[0-9]月[0-3]?[0-9]日)" if has_wareki else "20[2-9][0-9]年[0-1]?[0-9]月[0-3]?[0-9]日",
            "pdf_selector": "href=[\"']([^\"']+\\.pdf)[\"']",
            "private_doc_keyword": "非公開",
            "detect_private_materials": has_private_docs,
            "extract_all_materials": True,
            "resolve_absolute_urls": True
        }
    }
    return rule

def parse_materials_from_html(html, base_url, pdf_selector):
    """HTMLから全配布資料（公開PDFおよび非公開資料）を抽出"""
    materials = []
    
    # 1. リンク付きPDF資料の抽出
    pdf_matches = re.findall(r'<a[^>]*href=["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    for pdf_url, link_text in pdf_matches:
        clean_name = re.sub(r'<[^>]+>', '', link_text).strip()
        if not clean_name:
            clean_name = os.path.basename(pdf_url)
        abs_url = urllib.parse.urljoin(base_url, pdf_url)
        materials.append({
            "name": clean_name,
            "url": abs_url,
            "type": "PDF",
            "isPrivate": False
        })
        
    # 2. 非公開資料表記の抽出 (例: 資料5 外務省提出資料（非公開）)
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

def extract_with_rule(target, html, rule_item):
    """【2回目: 情報取得Engine】保存済みAIルールに基づき、2段階深掘り＆全資料フル抽出"""
    rule = rule_item.get("rules", {})
    
    # ページタイトル
    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else target["name"]

    # Step 1: TOPページ資料の抽出
    pdf_pattern = rule.get("pdf_selector", r'href=["\']([^"\']+\.pdf)["\']')
    top_materials = parse_materials_from_html(html, target["url"], pdf_pattern)

    # Step 2: 2段階階層クロール (Subpage Deep Crawling)
    subpage_meetings = []
    deep_enabled = rule.get("deep_crawl_enabled", True)
    
    if deep_enabled:
        subpage_pattern = rule.get("subpage_discovery_pattern", r'href=["\']([^"\']*(?:dai\d+|kaisai|gijisidai)[^"\'#]*)["\']')
        subpage_links = re.findall(subpage_pattern, html, re.IGNORECASE)
        
        if subpage_links:
            unique_subpages = list(dict.fromkeys([urllib.parse.urljoin(target["url"], l) for l in subpage_links]))[:6]
            print(f"   [2段階目: 情報取得Engine] 個別回サブページ {len(unique_subpages)} 件を深掘り巡回中...")

            for sub_url in unique_subpages:
                sub_html = fetch_url(sub_url)
                if sub_html:
                    sub_title_match = re.search(r'<title>(.*?)</title>', sub_html, re.IGNORECASE | re.DOTALL)
                    sub_title = sub_title_match.group(1).strip() if sub_title_match else sub_url
                    
                    sub_materials = parse_materials_from_html(sub_html, sub_url, pdf_pattern)
                    sub_dates = re.findall(rule.get("date_regex", r'令和\d+年\d+月\d+日'), sub_html)

                    subpage_meetings.append({
                        "subpageUrl": sub_url,
                        "title": sub_title,
                        "extractedMaterialsCount": len(sub_materials),
                        "materials": sub_materials,
                        "extractedDates": list(set(sub_dates))[:2]
                    })
                    top_materials.extend(sub_materials)

    # 重複排除
    unique_materials = []
    seen_urls = set()
    for m in top_materials:
        key = m["url"] if m["url"] != "#" else m["name"]
        if key not in seen_urls:
            seen_urls.add(key)
            unique_materials.append(m)

    # 日付の抽出
    date_matches = re.findall(rule.get("date_regex", r'令和\d+年\d+月\d+日'), html)

    scraped_item = {
        "councilId": target["id"],
        "councilName": target["name"],
        "ministry": target["ministry"],
        "officialUrl": target["url"],
        "scrapedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruleApplied": rule_item.get("rule_id", "rule-default"),
        "pageTitle": page_title,
        "totalExtractedMaterials": len(unique_materials),
        "materials": unique_materials,
        "extractedDates": list(set(date_matches))[:3],
        "subpageMeetings": subpage_meetings
    }
    return scraped_item

def main():
    print("==========================================================")
    print(" 政策会議ウォッチ (PM-HUB) AI適応型2段階クローラー ")
    print("==========================================================")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"対象会議体数: {len(CRAWL_TARGETS)} 件\n")

    existing_rules = load_scraping_rules()
    results = []

    for idx, target in enumerate(CRAWL_TARGETS, 1):
        print(f"[{idx}/{len(CRAWL_TARGETS)}] HTTP GET: {target['name']} ({target['url']})...")
        html = fetch_url(target["url"])
        
        if html:
            c_id = target["id"]
            if c_id not in existing_rules:
                # 1回目: AI情報確認Agentによりルールを自動合成
                new_rule = generate_ai_rule(target, html)
                existing_rules[c_id] = new_rule
                save_scraping_rules(existing_rules)
                print(f"   [1回目完了] '{new_rule['rule_id']}' を scraping_rules.json に生成・反映しました")
            else:
                print(f"   [2回目ルール適用] 保存済みルール '{existing_rules[c_id]['rule_id']}' に基づき2段階情報取得を実行")

            # 2回目: ルールに基づく情報取得
            item = extract_with_rule(target, html, existing_rules[c_id])
            results.append(item)
            
            print(f"  -> [200 OK] タイトル: {item['pageTitle']}")
            print(f"  -> [全資料抽出結果] 総抽出資料数: {item['totalExtractedMaterials']} 件 (非公開含む), 検出日付: {item['extractedDates']}")
        else:
            print(f"  -> [SKIP] ネットワーク取得スキップ")
        print("-" * 65)

    output_filename = os.path.join(os.path.dirname(__file__), "scraped_councils_output.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nクローリング完了: 全データを {output_filename} に保存しました。")

if __name__ == "__main__":
    main()
