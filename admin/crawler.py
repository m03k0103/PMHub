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
from datetime import datetime

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

# クロール対象の政府審議会・会議体URLリスト
CRAWL_TARGETS = [
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
        "url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html"
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
    },
    {
        "id": "fsa-kinyu-shingi",
        "ministry": "FSA",
        "name": "金融審議会",
        "url": "https://www.fsa.go.jp/singi/singi_kinyu/base_gijiroku.html"
    },
    {
        "id": "moj-hosei-shingi",
        "ministry": "MOJ",
        "name": "法制審議会",
        "url": "https://www.moj.go.jp/shingi1/shingikai_soukai.html"
    },
    {
        "id": "mod-cho-shin",
        "ministry": "MOD",
        "name": "防衛調達審議会",
        "url": "https://www.mod.go.jp/j/policy/agenda/meeting/cho-shin/index.html"
    },
    {
        "id": "mod-drastic-reinforcement",
        "ministry": "MOD",
        "name": "防衛力の抜本的強化に関する有識者会議",
        "url": "https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/index.html"
    },
    {
        "id": "mod-defense-industry-wg",
        "ministry": "MOD",
        "name": "防衛産業ワーキンググループ",
        "url": "https://www.mod.go.jp/j/policy/agenda/meeting/defense_industry_wg/index.html"
    },
    {
        "id": "maff-shokuryo-nogyo",
        "ministry": "MAFF",
        "name": "食料・農業・農村政策審議会",
        "url": "https://www.maff.go.jp/j/council/seisaku/"
    },
    {
        "id": "mlit-shakai-sihon-soukai",
        "ministry": "MLIT",
        "name": "社会資本整備審議会",
        "url": "https://www.mlit.go.jp/policy/shingikai/s201_shakai01.html"
    },
    {
        "id": "mlit-energy-anzenhosho-wg",
        "ministry": "MLIT",
        "name": "エネルギー・経済安全保障小委員会",
        "url": "https://www.mlit.go.jp/policy/shingikai/s404_anzenhosho.html"
    },
    {
        "id": "mlit-infra-management-wg",
        "ministry": "MLIT",
        "name": "インフラマネジメント戦略小委員会",
        "url": "https://www.mlit.go.jp/policy/shingikai/s204_management02.html"
    },
    {
        "id": "npa-seisaku-hyoka-kenkyukai",
        "ministry": "NPA",
        "name": "警察庁政策評価研究会",
        "url": "https://www.npa.go.jp/policies/council/index.html"
    },
    {
        "id": "nra-teireikai",
        "ministry": "NRA",
        "name": "原子力規制委員会",
        "url": "https://www.nra.go.jp/index.html"
    },
    {
        "id": "cao-space-anpo",
        "ministry": "CAO",
        "name": "宇宙政策委員会 宇宙安全保障部会",
        "url": "https://www8.cao.go.jp/space/comittee/anpo.html"
    }
]

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

    subpage_pattern = rule.get("subpage_discovery_pattern", r'href=["\']([^"\']*(?:dai\d+|\d+kai|kaisai|gijisidai)[^"\'#]*)["\']')
    subpage_links = re.findall(subpage_pattern, html, re.IGNORECASE)

    if subpage_links:
        unique_subpages = list(dict.fromkeys([urllib.parse.urljoin(target_url, l) for l in subpage_links]))[:6]
        print(f"   [2回目情報取得Engine ({quirk_note})] サブページ {len(unique_subpages)} 件を深掘り巡回中...")

        for sub_url in unique_subpages:
            parsed_url = urllib.parse.urlparse(sub_url)
            if parsed_url.scheme not in ('http', 'https'):
                continue

            sub_html = fetch_url(sub_url)
            if sub_html:
                sub_title_match = re.search(r'<title>(.*?)</title>', sub_html, re.IGNORECASE | re.DOTALL)
                sub_title = sub_title_match.group(1).strip() if sub_title_match else sub_url

                sub_materials = parse_materials_from_html(sub_html, sub_url, pdf_pattern)
                raw_sub_dates = re.findall(rule.get("date_regex", r'令和\d+年\d+月\d+日'), sub_html)
                norm_sub_dates = [normalize_japanese_numbers(d) for d in raw_sub_dates]

                subpage_meetings.append({
                    "subpageUrl": sub_url,
                    "title": sub_title,
                    "extractedMaterialsCount": len(sub_materials),
                    "materials": sub_materials,
                    "extractedDates": list(set(norm_sub_dates))[:2]
                })
                additional_materials.extend(sub_materials)

    return subpage_meetings, additional_materials


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
    
    if deep_enabled:
        new_meetings, new_materials = _crawl_subpages(target["url"], html, rule, quirk_note, pdf_pattern)
        subpage_meetings.extend(new_meetings)
        top_materials.extend(new_materials)

    unique_materials = []
    seen_keys = set()
    for m in top_materials:
        key = m["url"] if m["url"] != "#" else m["name"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique_materials.append(m)

    raw_date_matches = re.findall(rule.get("date_regex", r'令和\d+年\d+月\d+日'), html)
    norm_date_matches = [normalize_japanese_numbers(d) for d in raw_date_matches]

    scraped_item = {
        "councilId": target["id"],
        "councilName": target["name"],
        "ministry": target["ministry"],
        "officialUrl": target["url"],
        "scrapedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ruleApplied": rule_item.get("rule_id", "rule-default"),
        "ministryQuirk": quirk_note,
        "pageTitle": page_title,
        "totalExtractedMaterials": len(unique_materials),
        "materials": unique_materials,
        "extractedDates": list(set(norm_date_matches))[:3],
        "subpageMeetings": subpage_meetings
    }
    return scraped_item

def main():
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

    print(f"\nデータ取得完了: 結果を {output_filename} に保存しました。")

if __name__ == "__main__":
    main()
