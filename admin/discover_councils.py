#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 審議会・会議体ディスカバリーエンジン (Council Discovery Engine)
省庁の審議会等一覧ページURL (councilsUrls) を巡回し、新規会議体の名称およびトップページURLを自動抽出・検出する。
"""

import sys
import os
import json
import re
import io
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

# Windows ターミナルログの文字化け防止
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_JS_PATH = os.path.join(PROJECT_ROOT, "docs", "data.js")
KEYWORDS_FILE = os.path.join(BASE_DIR, "discovery_keywords.json")
DISCOVERED_OUTPUT_FILE = os.path.join(BASE_DIR, "discovered_councils.json")

def load_keywords():
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] キーワード設定の読み込みエラー: {e}", file=sys.stderr)
    return {
        "commonKeywords": ["審議会", "検討会", "委員会", "部会", "分科会", "懇談会", "ワーキンググループ", "WG", "研究会", "プロジェクトチーム", "タスクフォース", "円卓会議", "会議"],
        "commonExcludeKeywords": ["過去", "名簿", "委員名簿", "議事録", "議事要旨", "資料一覧", "配付資料", "法令", "設置根拠", "傍聴", "更新履歴", "PDF", "Excel"],
        "ministryAddKeywords": {},
        "ministryExcludeKeywords": {}
    }

def parse_data_js():
    """docs/data.js から MINISTRIES と COUNCILS のデータを抽出する"""
    if not os.path.exists(DATA_JS_PATH):
        print(f"[ERROR] {DATA_JS_PATH} が見つかりません。", file=sys.stderr)
        return {}, []

    with open(DATA_JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # MINISTRIES の抽出 (簡易正規表現)
    ministries = {}
    m_match = re.search(r"const MINISTRIES = (\{[\s\S]*?\n\};)", content)
    if m_match:
        m_str = m_match.group(1).rstrip(";").strip()
        # JSONに近づける置換
        m_json_str = re.sub(r"(\w+):", r'"\1":', m_str)
        m_json_str = m_json_str.replace("'", '"')
        try:
            ministries = json.loads(m_json_str)
        except Exception:
            # フォールバック: 各省庁キーを手動抽出
            for block in re.finditer(r"(\w+):\s*\{([^}]+)\}", content):
                k = block.group(1)
                body = block.group(2)
                name_m = re.search(r"name:\s*'([^']+)'", body)
                official_m = re.search(r"officialUrl:\s*'([^']+)'", body)
                has_m = re.search(r"hasCouncils:\s*(true|false)", body)
                urls_m = re.search(r"councilsUrls:\s*\[([\s\S]*?)\]", body)
                urls = []
                if urls_m:
                    urls = [u.strip().strip("'\"") for u in urls_m.group(1).split(",") if u.strip()]
                ministries[k] = {
                    "name": name_m.group(1) if name_m else k,
                    "officialUrl": official_m.group(1) if official_m else "",
                    "hasCouncils": has_m.group(1) != "false" if has_m else True,
                    "councilsUrls": urls
                }

    # COUNCILS の抽出
    councils = []
    c_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
    if c_match:
        c_str = c_match.group(1).rstrip(";").strip()
        c_json_str = re.sub(r"(\w+):", r'"\1":', c_str)
        c_json_str = c_json_str.replace("'", '"')
        try:
            councils = json.loads(c_json_str)
        except Exception:
            for item in re.finditer(r"\{\s*id:\s*'([^']+)'[\s\S]*?name:\s*'([^']+)'[\s\S]*?ministry:\s*'([^']+)'[\s\S]*?officialUrl:\s*'([^']+)'", content):
                councils.append({
                    "id": item.group(1),
                    "name": item.group(2),
                    "ministry": item.group(3),
                    "officialUrl": item.group(4)
                })

    return ministries, councils

def fetch_html(url):
    """指定URLのHTMLを取得する（User-Agent付与、タイムアウト12秒）"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 PMHubDiscovery/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            charset = res.headers.get_content_charset() or "utf-8"
            html_bytes = res.read()
            try:
                return html_bytes.decode(charset, errors="replace")
            except Exception:
                # cp932/shift_jis フォールバック
                for enc in ["shift_jis", "cp932", "euc-jp"]:
                    try:
                        return html_bytes.decode(enc)
                    except Exception:
                        pass
                return html_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"   [HTTP ERROR] {url}: {e}")
        return None

def normalize_url(url):
    """URLの末尾スラッシュやフラグメントを除去して正規化"""
    if not url:
        return ""
    p = urllib.parse.urlparse(url)
    clean_path = p.path.rstrip("/")
    return f"{p.scheme}://{p.netloc}{clean_path}"

def get_max_seq(councils):
    """既存COUNCILSから最大のID連番を取得する"""
    max_num = 183
    for c in councils:
        cid = c.get("id", "")
        # 末尾の数字を抽出
        num_m = re.search(r"-(\d+)$", cid)
        if num_m:
            try:
                n = int(num_m.group(1))
                if n > max_num:
                    max_num = n
            except ValueError:
                pass
    return max_num

def run_discovery():
    print("=" * 70)
    print("【PM-HUB】省庁 審議会・会議体ディスカバリー巡回 開始")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    keywords_cfg = load_keywords()
    common_keywords = keywords_cfg.get("commonKeywords", [])
    common_excludes = keywords_cfg.get("commonExcludeKeywords", [])
    min_add_kw = keywords_cfg.get("ministryAddKeywords", {})
    min_exc_kw = keywords_cfg.get("ministryExcludeKeywords", {})

    ministries, existing_councils = parse_data_js()
    print(f"登録済み省庁数: {len(ministries)} 組織, 既存会議体数: {len(existing_councils)} 件\n")

    # 既存の会議体URLと名前のセット（重複判定用）
    existing_urls = {normalize_url(c.get("officialUrl", "")) for c in existing_councils if c.get("officialUrl")}
    existing_names = {c.get("name", "").strip() for c in existing_councils if c.get("name")}

    next_seq = get_max_seq(existing_councils) + 1
    discovered_list = []
    seen_in_this_run = set()

    for min_code, min_info in sorted(ministries.items()):
        min_name = min_info.get("name", min_code)
        has_councils = min_info.get("hasCouncils", True)
        councils_urls = min_info.get("councilsUrls", [])

        if not has_councils or not councils_urls:
            continue

        add_kw = min_add_kw.get(min_code, [])
        exc_kw = min_exc_kw.get(min_code, []) + common_excludes
        target_kw = common_keywords + add_kw

        print(f"▶ [{min_code}] {min_name} (審議会ページURL: {len(councils_urls)} 件)")

        for page_url in councils_urls:
            page_url = page_url.strip()
            if not page_url or not page_url.startswith("http"):
                continue

            print(f"   [GET] 巡回: {page_url}")
            html = fetch_html(page_url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            links = soup.find_all("a", href=True)

            found_count_in_page = 0
            for a in links:
                href = a["href"].strip()
                raw_text = a.get_text(separator=" ", strip=True)
                title_attr = a.get("title", "").strip()
                link_text = raw_text or title_attr

                if not link_text or len(link_text) < 3 or len(link_text) > 100:
                    continue

                # アンカーリンクやjavascriptの除外
                if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                    continue

                # キーワード照合（追加・共通キーワードのいずれかを含む）
                has_match = any(kw in link_text for kw in target_kw)
                if not has_match:
                    continue

                # 除外キーワード照合
                is_excluded = any(ex in link_text for ex in exc_kw)
                if is_excluded:
                    continue

                # 絶対URLへ変換
                abs_url = urllib.parse.urljoin(page_url, href)
                norm_abs_url = normalize_url(abs_url)

                # PDF/Excel/画像などのファイル直リンクは会議体トップURLではないため除外
                if re.search(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip)$", abs_url, re.I):
                    continue

                # 既に登録済みのURLまたは名前かチェック
                if norm_abs_url in existing_urls or link_text in existing_names:
                    continue

                # 今回のクロール内での重複チェック
                key_pair = (min_code, link_text, norm_abs_url)
                if key_pair in seen_in_this_run:
                    continue
                seen_in_this_run.add(key_pair)

                # カテゴリの自動推定
                category = "COUNCIL"
                if "部会" in link_text:
                    category = "SECTION"
                elif "分科会" in link_text:
                    category = "SUBCOMMITTEE"
                elif "ワーキンググループ" in link_text or "WG" in link_text:
                    category = "WORKING_GROUP"
                elif "検討会" in link_text or "研究会" in link_text or "懇談会" in link_text:
                    category = "STUDY"
                elif "委員会" in link_text:
                    category = "COMMITTEE"
                elif "本部" in link_text or "推進会議" in link_text:
                    category = "HQ"

                # 採番: {ministry_lower}-{seq} (例: cao-184)
                council_id = f"{min_code.lower()}-{next_seq}"
                next_seq += 1

                council_item = {
                    "id": council_id,
                    "name": link_text,
                    "ministry": min_code,
                    "category": category,
                    "officialUrl": abs_url,
                    "isNew": True,
                    "trackedSince": datetime.now().strftime("%Y-%m-%d"),
                    "sourcePageUrl": page_url
                }

                discovered_list.append(council_item)
                found_count_in_page += 1
                print(f"      ✨ [新規検出] {council_id}: {link_text}")
                print(f"         URL: {abs_url}")

            print(f"   -> 検出数: {found_count_in_page} 件")

    print("\n" + "=" * 70)
    print(f"ディスカバリー巡回完了: 合計 {len(discovered_list)} 件の新規会議体を検出しました。")
    print("=" * 70)

    # 結果JSONの保存
    with open(DISCOVERED_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "crawledAt": datetime.now().isoformat(),
            "totalDiscovered": len(discovered_list),
            "councils": discovered_list
        }, f, ensure_ascii=False, indent=2)

    print(f"結果を {DISCOVERED_OUTPUT_FILE} に保存しました。")
    return discovered_list

if __name__ == "__main__":
    run_discovery()
