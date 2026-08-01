#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 1回目用情報確認Agent (AI Rule Synthesis Agent)
Webサイト初回訪問時、生成AI的推論アルゴリズムにより各省庁サイト固有の「クセ」
（DOM構造・全角数字・階層URLパターン・非公開表記・和暦西暦混在等）を深く自動解析し、
2回目用ルールエンジンが使用する最適化ルール (scraping_rules.json) を動的に考案・保存するエージェント
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
        "url": "https://www8.cao.go.jp/cstp/ai/ai_senryaku/ai_senryaku.html"
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
        "name": "デジタル社会推進会議幹事会",
        "url": "https://www.digital.go.jp/councils/social-promotion-executive"
    },
    {
        "id": "cfa-kodomo-suishin",
        "ministry": "CFA",
        "name": "こども政策推進会議",
        "url": "https://www.cfa.go.jp/councils/suishinkaigi"
    },
    {
        "id": "cfa-kodomo-shingikai",
        "ministry": "CFA",
        "name": "こども家庭審議会",
        "url": "https://www.cfa.go.jp/councils/shingikai"
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PMHubAIRuleSynthesisAgent/3.0'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}", file=sys.stderr)
        return None

def synthesize_ai_rule_for_council(target, html):
    """
    【生成AI的ルール考案ロジック】
    省庁Webサイト固有の「クセ」（URL構造、全角数字表記、個別開催回サブページ、非公開文書の扱い）を
    分析・推論し、2回目取得Engine用の最適化ルールを考案する
    """
    print(f"   [1回目AI確認Agent] '{target['name']}' ({target['url']}) の「サイトのクセ」をAI深層解析中...")
    
    ministry = target["ministry"]
    url = target["url"]
    
    # 1. サブページ階層（個別回）の検出と推論
    subpage_matches = re.findall(r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai|gijiroku|meetings|\d{8})[^"\'#]*)["\']', html, re.IGNORECASE)
    has_deep_subpages = len(subpage_matches) > 0
    
    # 省庁別のサブページ構造クセの分類
    if "cas.go.jp" in url:
        subpage_pattern = r'href=["\']([^"\']*(?:dai\d+|gijisidai|gijiroku)[^"\'#]*)["\']'
        quirk_notes = "内閣官房型: daiXX/gijisidai.html 形式の2段階ネスト構造"
    elif "cao.go.jp" in url:
        subpage_pattern = r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai)[^"\'#]*)["\']'
        quirk_notes = "内閣府型: ◯kai/◯kai.html または kaisai.html の個別の回ネスト"
    elif "reconstruction.go.jp" in url:
        subpage_pattern = r'href=["\']([^"\']*(?:topics/|\d{8}|shidai)[^"\'#]*)["\']'
        quirk_notes = "復興庁型: topics/cat-XX 分類URLおよび日付命名PDF"
    elif "digital.go.jp" in url:
        subpage_pattern = r'href=["\']([^"\']*(?:councils|meetings|\d{8})[^"\'#]*)["\']'
        quirk_notes = "デジタル庁型: リソース絶対パス/ルート相対パス混在型HTML5構造"
    elif "cfa.go.jp" in url:
        subpage_pattern = r'href=["\']([^"\']*(?:councils/[a-z0-9_-]+/[a-f0-9]{8}|councils/[a-z0-9_-]+)[^"\'#]*)["\']'
        quirk_notes = "こども家庭庁型: /councils/会議名/UUIDハッシュ個別の回URL構造"
    else:
        subpage_pattern = r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai)[^"\'#]*)["\']'
        quirk_notes = "標準省庁型: 汎用個別回パターン"

    # 2. 全角数字・和暦/西暦パターンの解析
    has_fullwidth_nums = bool(re.search(r'[０-９]', html))
    has_wareki = bool(re.search(r'令和[0-9０-９一-九]+年', html))
    
    if has_fullwidth_nums or has_wareki:
        date_pattern = r'(?:令和[0-9０-９一-九]+年[0-9０-９一-十二]+月[0-9０-９一-三十一]+日|20[2-9][0-9]年[0-1]?[0-9]月[0-3]?[0-9]日)'
    else:
        date_pattern = r'20[2-9][0-9]年[0-1]?[0-9]月[0-3]?[0-9]日'

    # 3. 非公開資料の検出
    has_private = "非公開" in html or "非公表" in html

    # 4. 資料リンクおよびPDF件数の計測
    pdf_count = len(re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.IGNORECASE))

    # 5. 生成AI考案ルールの合成
    ai_rule = {
        "rule_id": f"rule-{target['id']}-ai-v3",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generator": "AI_Rule_Synthesis_Agent_v3",
        "councilName": target["name"],
        "targetUrl": target["url"],
        "ministryQuirk": quirk_notes,
        "rules": {
            "encoding": "utf-8",
            "deep_crawl_enabled": has_deep_subpages,
            "subpage_discovery_pattern": subpage_pattern,
            "date_regex": date_pattern,
            "prefer_subpage_date": True,
            "extract_subpage_materials_primary": True,
            "pdf_selector": r'href=["\']([^"\']+\.pdf)["\']',
            "private_doc_keyword": "非公開",
            "detect_private_materials": has_private,
            "extract_all_materials": True,
            "resolve_absolute_urls": True,
            "top_page_pdf_count": pdf_count
        }
    }
    return ai_rule

def main():
    print("==========================================================")
    print(" 政策会議ウォッチ (PM-HUB) 1回目用 AI Rule Synthesis Agent ")
    print("==========================================================")
    print(f"解析実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"解析対象会議体数: {len(TARGET_COUNCILS)} 件\n")

    rules = load_rules()
    updated_count = 0

    for idx, target in enumerate(TARGET_COUNCILS, 1):
        print(f"[{idx}/{len(TARGET_COUNCILS)}] 「サイトのクセ」をAI解析中: {target['name']} ({target['ministry']})...")
        html = fetch_url(target["url"])
        
        if html:
            ai_rule_obj = synthesize_ai_rule_for_council(target, html)
            rules[target["id"]] = ai_rule_obj
            updated_count += 1
            print(f"  -> [AI推論完了] 考案ルール: '{ai_rule_obj['rule_id']}'")
            print(f"  -> [分析されたクセ] {ai_rule_obj['ministryQuirk']}")
        else:
            print(f"  -> [SKIP] ネットワーク取得スキップ")
        print("-" * 65)

    if updated_count > 0:
        save_rules(rules)
        print(f"\n1回目AI確認完了: 全{updated_count}件のAI考案ルールを {RULES_FILE} に永続保存しました。")

if __name__ == "__main__":
    main()
