#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 1回目用情報確認Agent (Agent Initial Verifier)
Webサイトの初回訪問時、DOM構造・サブページ階層・非公開表記・日付パターンを自動確認・解析し、
「2回目用の情報取得ルール (scraping_rules.json)」を自動生成・永続保存する専用Agent
"""

import sys
import os
import json
import urllib.request
import re
import io
from datetime import datetime

# Windows ターミナルログの文字化け防止 (stdout/stderr を UTF-8 に固定)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

RULES_FILE = os.path.join(os.path.dirname(__file__), "scraping_rules.json")

# クロール対象の政府審議会・会議体URLリスト
TARGET_COUNCILS = [
    {
        "id": "cas-zensedai-hosyo",
        "ministry": "CAS",
        "name": "全世代型社会保障構築会議",
        "url": "https://www.cas.go.jp/jp/seisaku/zensedai_hosyo/index.html"
    },
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

def load_rules():
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_rules(rules_data):
    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save rules: {e}", file=sys.stderr)

def fetch_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHubInitialAgent/1.0'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def analyze_and_generate_rule(target, html):
    """【1回目情報確認Agent】DOM構造・階層サブページ・非公開表記を検証し、専用ルールを生成"""
    print(f"   [1回目確認Agent] '{target['name']}' ({target['url']}) のDOM・階層リンク・非公開項目を自動検証中...")
    
    # 2段階階層サブページ（例: dai21/gijisidai.html, dai11/gijisidai.html）の検知
    has_subpages = bool(re.search(r'href=["\']([^"\']*(?:dai\d+|kaisai|gijisidai|gijiroku)[^"\'#]*)["\']', html, re.IGNORECASE))
    has_private_docs = "非公開" in html
    has_wareki = bool(re.search(r'令和\d{1,2}年', html))
    pdf_count = len(re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.IGNORECASE))

    rule = {
        "rule_id": f"rule-{target['id']}-v2",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "verified_by": "Agent_Initial_Verifier_v1",
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
            "resolve_absolute_urls": True,
            "top_page_pdf_count": pdf_count
        }
    }
    return rule

def main():
    print("==========================================================")
    print(" 政策会議ウォッチ (PM-HUB) 1回目用情報確認Agent (Initial Verifier) ")
    print("==========================================================")
    print(f"検証開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"確認対象会議体数: {len(TARGET_COUNCILS)} 件\n")

    rules = load_rules()
    updated = False

    for idx, target in enumerate(TARGET_COUNCILS, 1):
        print(f"[{idx}/{len(TARGET_COUNCILS)}] 情報確認: {target['name']}...")
        html = fetch_url(target["url"])
        if html:
            rule_obj = analyze_and_generate_rule(target, html)
            rules[target["id"]] = rule_obj
            updated = True
            print(f"  [検証完了] 'scraping_rules.json' に '{rule_obj['rule_id']}' を生成・反映しました")
        else:
            print(f"  [SKIP] ネットワーク取得スキップ")
        print("-" * 60)

    if updated:
        save_rules(rules)
        print(f"\n1回目情報確認完了: 生成ルールを {RULES_FILE} に保存しました。")

if __name__ == "__main__":
    main()
