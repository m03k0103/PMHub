#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 審議会・会議体ディスカバリーエンジン (Council Discovery Engine)
省庁の審議会等一覧ページURL (councilsUrls) を巡回し、そこに含まれるすべての会議体（本体、部会、分科会、検討会等）の
実際の個別のトップページURLへHTTPアクセスして「最終的な正規URL」を特定し、独立した会議体レコードとして自動検出・登録する。
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
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "docs", "data.json")
KEYWORDS_FILE = os.path.join(BASE_DIR, "discovery_keywords.json")

def load_keywords():
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] キーワード設定の読み込みエラー: {e}", file=sys.stderr)
    return {
        "commonKeywords": ["審議会", "検討会", "委員会", "部会", "分科会", "懇談会", "ワーキンググループ", "WG", "研究会", "プロジェクトチーム", "タスクフォース", "有識者会議", "本部", "推進会議", "円卓会議", "会議"],
        "commonExcludeKeywords": ["過去", "名簿", "委員名簿", "議事録", "議事要旨", "資料一覧", "配付資料", "法令", "設置根拠", "傍聴", "更新履歴", "PDF", "Excel", "プライバシーポリシー"],
        "ministryAddKeywords": {},
        "ministryExcludeKeywords": {}
    }

def parse_data_json():
    """docs/data.json から MINISTRIES と COUNCILS のデータを抽出する"""
    if not os.path.exists(DATA_JSON_PATH):
        print(f"[ERROR] {DATA_JSON_PATH} が見つかりません。", file=sys.stderr)
        return {}, []

    try:
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            ministries = data.get("ministries", {})
            councils = data.get("councils", [])
            return ministries, councils
    except Exception as e:
        print(f"[ERROR] failed to parse data.json: {e}", file=sys.stderr)
        return {}, []

def fetch_page_and_final_url(url):
    """
    指定URLへ実際にHTTPアクセスし、転送（リダイレクト）を追跡して
    「最終的な正規URL」およびHTMLテキストを取得する。
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 PMHubDiscovery/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            final_url = res.geturl()  # リダイレクト後の最終正規URL
            charset = res.headers.get_content_charset() or "utf-8"
            html_bytes = res.read()
            html_text = ""
            try:
                html_text = html_bytes.decode(charset, errors="replace")
            except Exception:
                for enc in ["shift_jis", "cp932", "euc-jp"]:
                    try:
                        html_text = html_bytes.decode(enc)
                        break
                    except Exception:
                        pass
                if not html_text:
                    html_text = html_bytes.decode("utf-8", errors="ignore")
            return html_text, final_url
    except Exception as e:
        print(f"   [HTTP ERROR] {url}: {e}")
        return None, url

def clean_council_name(name):
    """「第X回」や日付プレフィックス、末尾の「配布資料」などを除去して親会議体名を抽出"""
    name = re.sub(r'^(令和\d+年\d+月\d+日開催|令和\d+年\d+月\d+日|令和\d+年|平成\d+年|\b\d{4}年\d+月\d+日開催?)\s*', '', name)
    name = re.sub(r'^(第[0-9０-９一-九]+回|第[0-9０-９一-九]+回\s*)\s*', '', name)
    name = re.sub(r'^(令和\d+年\s*第[0-9０-９一-九]+回|平成\d+年\s*第[0-9０-９一-九]+回)\s*', '', name)
    name = re.sub(r'\s*(配布資料|取りまとめ.*|について|開催概要|議事要旨|議事録)$', '', name)
    return name.strip()

def normalize_url(url):
    """URLの末尾スラッシュやフラグメント(#)を除去して正規化"""
    if not url:
        return ""
    p = urllib.parse.urlparse(url)
    clean_path = p.path.rstrip("/")
    return f"{p.scheme}://{p.netloc}{clean_path}"

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

def run_discovery(progress_callback=None):
    def emit(msg, data=None):
        print(msg)
        if progress_callback:
            try:
                progress_callback(msg, data)
            except Exception:
                pass

    emit("=" * 70)
    emit("【PM-HUB】省庁 審議会・会議体ディスカバリー巡回 開始")
    emit("（審議会等ページにアクセスし、全会議体を個別の正規URLで独立検出します）")
    emit(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit("=" * 70)

    keywords_cfg = load_keywords()
    common_keywords = keywords_cfg.get("commonKeywords", [])
    common_excludes = keywords_cfg.get("commonExcludeKeywords", [])
    min_add_kw = keywords_cfg.get("ministryAddKeywords", {})
    min_exc_kw = keywords_cfg.get("ministryExcludeKeywords", {})

    ministries, existing_councils = parse_data_json()
    emit(f"登録済み省庁数: {len(ministries)} 組織, 既存会議体数: {len(existing_councils)} 件\n")

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
    total_ministries = len([m for m in ministries.values() if m.get("hasCouncils", True) and m.get("councilsUrls")])
    current_min_idx = 0

    for min_code, min_info in sorted(ministries.items()):
        min_name = min_info.get("name", min_code)
        has_councils = min_info.get("hasCouncils", True)
        councils_urls = min_info.get("councilsUrls", [])

        if not has_councils or not councils_urls:
            continue

        current_min_idx += 1
        pct = int((current_min_idx / max(total_ministries, 1)) * 90)

        add_kw = min_add_kw.get(min_code, [])
        exc_kw = min_exc_kw.get(min_code, []) + common_excludes
        target_kw = common_keywords + add_kw

        emit(f"▶ [{current_min_idx}/{total_ministries}] [{min_code}] {min_name} (審議会一覧: {len(councils_urls)} 件)", {
            "type": "ministry_start",
            "ministry": min_code,
            "ministryName": min_name,
            "progress": pct,
            "current": current_min_idx,
            "total": total_ministries
        })

        for page_url in councils_urls:
            page_url = page_url.strip()
            if not page_url or not page_url.startswith("http"):
                continue

            emit(f"   [GET] 審議会等一覧ページ巡回: {page_url}", {
                "type": "page_fetch",
                "url": page_url,
                "ministry": min_code
            })
            html, final_page_url = fetch_page_and_final_url(page_url)
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

                if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                    continue

                # キーワード照合（「審議会」「分科会」「部会」「検討会」などを検知）
                has_match = any(kw in link_text for kw in target_kw)
                if not has_match:
                    continue

                # 除外キーワード照合
                is_excluded = any(ex in link_text for ex in exc_kw)
                if is_excluded:
                    continue

                # 絶対URLに変換
                abs_url = urllib.parse.urljoin(final_page_url, href)

                # PDF/Excel/画像などのドキュメント直リンクは除外
                if re.search(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip)$", abs_url, re.I):
                    continue

                # 会議体ページへ実際にアクセスして最終的な正規URL（リダイレクト後）を特定
                _, final_council_url = fetch_page_and_final_url(abs_url)
                if not final_council_url:
                    final_council_url = abs_url

                norm_final_url = normalize_url(final_council_url)

                # 会議体名の正規化（「第X回」などの個別の開催回名が含まれる場合は親会議体名を抽出）
                is_meeting_pattern = bool(re.search(r'(第[0-9０-９一-九]+回|令和\d+年|\d{4}年\d+月\d+日)', link_text))
                target_council_name = clean_council_name(link_text) if is_meeting_pattern else link_text
                if not target_council_name:
                    target_council_name = link_text

                # 重複判定: 既に登録済みの正規URLまたは同名かチェック
                if norm_final_url in existing_urls:
                    continue
                if target_council_name in existing_names:
                    continue

                # 今回のクロール内での重複チェック
                key_pair = (min_code, target_council_name)
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

                # 採番規則: 省庁コード小文字 + 連番 (例: cao-184, mhlw-185)
                council_id = f"{min_code.lower()}-{next_seq}"
                next_seq += 1

                council_item = {
                    "id": council_id,
                    "name": target_council_name,
                    "ministry": min_code,
                    "category": category,
                    "officialUrl": final_council_url if not is_meeting_pattern else page_url,
                    "isNew": True,
                    "trackedSince": datetime.now().strftime("%Y-%m-%d"),
                    "sourcePageUrl": page_url
                }

                discovered_list.append(council_item)
                found_count_in_page += 1
                emit(f"      ✨ [新規会議体検出] {council_id}: {link_text} -> {final_council_url}", {
                    "type": "council_discovered",
                    "council": council_item
                })

            emit(f"   -> 検出数: {found_count_in_page} 件")

    emit("\n" + "=" * 70)
    emit(f"ディスカバリー巡回完了: 合計 {len(discovered_list)} 件の新規会議体レコードを作成しました。")
    emit("=" * 70)

    # 結果JSONの保存 (data.jsonのdiscoveredCouncilsを更新)
    if os.path.exists(DATA_JSON_PATH):
        try:
            with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            existing_discovered = data.get("discoveredCouncils", [])
            existing_dict = {c.get("id"): c for c in existing_discovered if c.get("id")}
            
            for new_c in discovered_list:
                cid = new_c.get("id")
                if cid in existing_dict:
                    new_c["status"] = existing_dict[cid].get("status", "pending")
                else:
                    new_c["status"] = "pending"
                existing_dict[cid] = new_c
            
            data["discoveredCouncils"] = list(existing_dict.values())
            
            with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            print(f"結果を data.json の discoveredCouncils に保存しました。")
        except Exception as e:
            print(f"[ERROR] data.json の更新に失敗しました: {e}")
    return discovered_list

if __name__ == "__main__":
    run_discovery()
