#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 審議会・会議体ディスカバリーエンジン (Council Discovery Engine)
省庁の審議会等一覧ページURL (councilsUrls) や新着ポータル (MINISTRY_NEWS_PORTALS) を巡回し、
そこに含まれるすべての会議体（本体、部会、分科会、検討会等）の個別のトップページURLを特定し、
独立した会議体レコードとして自動検出・登録する。
"""

import sys
import os
import json
import re
import io
import urllib.request
import urllib.parse
import time
from datetime import datetime
from bs4 import BeautifulSoup
import concurrent.futures
from urllib.parse import urljoin, urlparse

from utils import (
    setup_win32_utf8, get_browser_headers, save_data_json_with_backup,
    decode_html_bytes, load_rejected_councils, load_data_json, normalize_url_for_matching
)
setup_win32_utf8()

# -------------------------------------------------------------
# Drop 116: モジュール分割（ディスカバリー責務分離 & ファサード互換保証）
# -------------------------------------------------------------
try:
    from admin.discovery_modules import (
        normalize_ministry_code,
        infer_council_category,
        clean_council_name,
        get_core_council_name,
        extract_council_name_from_news_title,
        MINISTRY_CODE_NORMALIZATION,
        NOISE_PERSON_ROLES,
        NOISE_ACTION_PATTERNS,
        NOISE_INTERNATIONAL_AND_ORGS,
        NOISE_INTERNATIONAL_REGEX,
        NOISE_PORTAL_EXACT,
        PRESS_RELEASE_EXCLUSIVE_PATTERNS,
        PRESS_RELEASE_EXCLUSIVE_REGEX,
        is_single_press_or_notice_url,
        is_non_council_noise,
        normalize_url,
        get_url_clean_key,
        get_max_seq,
        is_already_registered_or_rejected,
        fetch_page_and_final_url,
        resolve_parent_url_from_press_release,
    )
except ImportError:
    from discovery_modules import (
        normalize_ministry_code,
        infer_council_category,
        clean_council_name,
        get_core_council_name,
        extract_council_name_from_news_title,
        MINISTRY_CODE_NORMALIZATION,
        NOISE_PERSON_ROLES,
        NOISE_ACTION_PATTERNS,
        NOISE_INTERNATIONAL_AND_ORGS,
        NOISE_INTERNATIONAL_REGEX,
        NOISE_PORTAL_EXACT,
        PRESS_RELEASE_EXCLUSIVE_PATTERNS,
        PRESS_RELEASE_EXCLUSIVE_REGEX,
        is_single_press_or_notice_url,
        is_non_council_noise,
        normalize_url,
        get_url_clean_key,
        get_max_seq,
        is_already_registered_or_rejected,
        fetch_page_and_final_url,
        resolve_parent_url_from_press_release,
    )


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_JSON_PATH = os.path.join(PROJECT_ROOT, "docs", "data.json")
ADMIN_DATA_PATH = os.path.join(BASE_DIR, "admin_data.json")

# 省庁コード正規化マップ (再発防止ガード: ENV -> MOE 等)


# 非会議体ノイズキーワード・パターン定義 (CR-187)




def load_keywords():
    if os.path.exists(ADMIN_DATA_PATH):
        try:
            with open(ADMIN_DATA_PATH, "r", encoding="utf-8") as f:
                adm_data = json.load(f)
            if isinstance(adm_data.get("discoveryKeywords"), dict) and adm_data["discoveryKeywords"]:
                return adm_data["discoveryKeywords"]
        except Exception:
            pass
    data = load_data_json(DATA_JSON_PATH)
    if data and isinstance(data.get("discoveryKeywords"), dict) and data["discoveryKeywords"]:
        return data["discoveryKeywords"]
    return {
        "commonKeywords": ["審議会", "検討会", "委員会", "部会", "分科会", "懇談会", "ワーキンググループ", "ワーキング・グループ", "スタディグループ", "スタディ・グループ", "WG", "SG", "審査会", "研究会", "プロジェクトチーム", "タスクフォース", "有識者会議", "本部", "推進会議", "円卓会議", "会議"],
        "commonExcludeKeywords": ["過去", "名簿", "委員名簿", "議事録", "議事要旨", "資料一覧", "配付資料", "法令", "設置根拠", "傍聴", "更新履歴", "PDF", "Excel", "プライバシーポリシー"],
        "ministryAddKeywords": {},
        "ministryExcludeKeywords": {}
    }

def parse_data_json():
    """docs/data.json および admin/admin_data.json から MINISTRIES, COUNCILS, CATEGORIES, SCRAPING_RULES のデータを抽出する"""
    data = load_data_json(DATA_JSON_PATH)
    if not data:
        print(f"[ERROR] {DATA_JSON_PATH} の読み込みに失敗しました。", file=sys.stderr)
        return {}, [], {}, {}

    ministries = data.get("ministries", {})
    councils = data.get("councils", [])
    categories = data.get("categories", {})
    scraping_rules = data.get("scrapingRules", {})
    if not scraping_rules and os.path.exists(ADMIN_DATA_PATH):
        try:
            with open(ADMIN_DATA_PATH, "r", encoding="utf-8") as f:
                scraping_rules = json.load(f).get("scrapingRules", {})
        except Exception:
            pass
    return ministries, councils, categories, scraping_rules





















def _discover_from_ministry_news(
    emit, target_ministry, ministries, existing_councils,
    categories_def, url_to_slug_map, existing_urls, existing_names,
    rejected_names, rejected_urls, rejected_clean_keys, common_keywords, next_seq,
    used_council_ids, all_portal_urls=None, rejected_ids=None,
    crawler_config=None, mock_llm_responder=None
):
    if all_portal_urls is None:
        all_portal_urls = set()
    if rejected_ids is None:
        rejected_ids = set()
    if crawler_config is None:
        crawler_config = {}
    try:
        from crawler import (
            MINISTRY_NEWS_PORTALS, load_ministry_and_host_configs_from_db,
            resolve_news_portal_urls, extract_news_items_from_html, fetch_url,
            match_council_from_news_item, normalize_text
        )
    except ImportError:
        from admin.crawler import (
            MINISTRY_NEWS_PORTALS, load_ministry_and_host_configs_from_db,
            resolve_news_portal_urls, extract_news_items_from_html, fetch_url,
            match_council_from_news_item, normalize_text
        )

    load_ministry_and_host_configs_from_db(data={"ministries": ministries, "crawlerConfig": crawler_config})
    portals_by_min = {
        normalize_ministry_code(k): (v.get("newsPortals") or MINISTRY_NEWS_PORTALS.get(normalize_ministry_code(k), []))
        for k, v in (ministries or {}).items()
        if isinstance(v, dict) and (v.get("newsPortals") or MINISTRY_NEWS_PORTALS.get(normalize_ministry_code(k)))
    }
    if not portals_by_min:
        portals_by_min = {normalize_ministry_code(k): v for k, v in MINISTRY_NEWS_PORTALS.items()}

    target_mins = [normalize_ministry_code(target_ministry)] if target_ministry else list(dict.fromkeys(portals_by_min.keys()))
    total_ministries = len(target_mins)
    emit(f"走査対象府省庁: {', '.join(target_mins)} (計 {total_ministries} 省庁)")

    councils_by_min = {}
    councils_by_url = {}
    existing_core_names = set()
    for c in existing_councils:
        m = c.get("ministry", "")
        councils_by_min.setdefault(m, []).append(c)
        if c.get("officialUrl"):
            councils_by_url[c.get("officialUrl").rstrip("/")] = c
        if c.get("name"):
            core_k = get_core_council_name(c.get("name"))
            if core_k:
                existing_core_names.add(core_k)

    rejected_core_names = {get_core_council_name(rn) for rn in rejected_names if get_core_council_name(rn)}

    search_kws = common_keywords + ["会議", "有識者会議", "タスクフォース", "プロジェクトチーム", "協議会"]
    discovered_list = []
    seen_in_this_run = set()
    seen_urls_in_this_run = set()
    category_counts = {}
    all_raw_news_items = []
    rule_cand_by_key = {}
    rule_cand_by_url = {}
    now_ts_slash = datetime.now().strftime("%Y/%m/%d %H:%M")

    for current_min_idx, min_code in enumerate(target_mins, start=1):
        portal_defs = portals_by_min.get(min_code, [])
        if not portal_defs:
            continue

        min_name = ministries.get(min_code, {}).get("name", min_code)
        pct = int((current_min_idx / max(total_ministries, 1)) * 90)
        emit(f"\n[{current_min_idx}/{total_ministries}] {min_name} ({min_code}) 新着・報道発表ポータルを走査中...", {
            "type": "ministry_start",
            "progress": pct,
            "current": current_min_idx,
            "total": total_ministries,
            "ministry": min_code,
            "ministryName": min_name
        })

        found_in_min = 0
        for pdef in portal_defs:
            resolved_urls = resolve_news_portal_urls(pdef)
            for rurl in resolved_urls:
                html = fetch_url(rurl, timeout=12)
                if not html:
                    continue
                items = extract_news_items_from_html(html, rurl, min_code, pdef.get("type"))
                for item in items:
                    raw_title = item.get("title", "")
                    all_raw_news_items.append({
                        "title": raw_title,
                        "url": item.get("url", ""),
                        "date": item.get("date", ""),
                        "ministry": min_code
                    })
                    cand_name = extract_council_name_from_news_title(raw_title, search_kws)
                    if not cand_name or len(cand_name) < 4:
                        continue

                    # ノイズ判定 (CR-187)
                    if is_non_council_noise(cand_name, raw_title, item.get("url", "")):
                        continue

                    # 既存・却下判定 (CR-188)
                    if is_already_registered_or_rejected(
                        cand_name, item.get("url", ""), min_code,
                        existing_names, existing_urls, existing_core_names, councils_by_min,
                        rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
                    ):
                        continue

                    key_pair = (min_code, get_core_council_name(cand_name))
                    if key_pair in seen_in_this_run:
                        continue
                    seen_in_this_run.add(key_pair)

                    # 単発プレスリリースからの常設親ページURL自動逆引き (CR-189)
                    resolved_url = resolve_parent_url_from_press_release(item.get("url", ""), cand_name, min_code)
                    orig_item_url = item.get("url", "")

                    # 親ポータルURLや既存URL、重複URLへの誤誘導防止ガード (Check 12対策, Drop 107)
                    norm_resolved = normalize_url(resolved_url)
                    clean_res = get_url_clean_key(resolved_url)

                    # 逆引きURLが単発報道発表URLのまま（親ポータル未解決）の場合は登録を遮断 (Drop 107)
                    if is_single_press_or_notice_url(resolved_url) or (is_single_press_or_notice_url(orig_item_url) and resolved_url == orig_item_url):
                        continue

                    # 逆引きURLが一覧ポータルまたは既に登録/検出済みなら元の単発URLにフォールバックせずスキップ (Drop 107)
                    if (norm_resolved in existing_urls or
                        norm_resolved in all_portal_urls or
                        norm_resolved in seen_urls_in_this_run or
                        (clean_res and clean_res in rejected_clean_keys)):
                        continue

                    # 最終URLが依然として既存または今回重複ならスキップ
                    if norm_resolved in existing_urls or norm_resolved in seen_urls_in_this_run or norm_resolved in all_portal_urls:
                        continue

                    # 最終URLでの既存・却下を再チェック
                    if is_already_registered_or_rejected(
                        cand_name, resolved_url, min_code,
                        existing_names, existing_urls, existing_core_names, councils_by_min,
                        rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
                    ):
                        continue

                    # 今回の検出リスト間でのサフィックス重複排除 (Check 14対策)
                    sub_keywords = ('部会', '分科会', '小委員会', '委員会', 'ワーキンググループ', '検討会', '研究会', '審査会', '専門家会合', 'タスクフォース')
                    n1 = re.sub(r'\s+', '', cand_name)
                    is_dup_with_cand = False
                    for existing_cand in discovered_list:
                        if existing_cand.get("ministry", "").upper() == min_code.upper():
                            n2 = re.sub(r'\s+', '', existing_cand.get("name", ""))
                            if n1 == n2:
                                is_dup_with_cand = True
                                break
                            if len(n1) >= 4 and len(n2) >= 4:
                                if any(k in n1 for k in sub_keywords) and any(k in n2 for k in sub_keywords):
                                    if (n2.endswith(n1) and not n2.startswith(n1)) or (n1.endswith(n2) and not n1.startswith(n2)):
                                        is_dup_with_cand = True
                                        break
                    if is_dup_with_cand:
                        continue

                    seen_urls_in_this_run.add(norm_resolved)

                    category, _ = infer_council_category(f"{cand_name} {raw_title}", categories_def)
                    category_counts[category] = category_counts.get(category, 0) + 1

                    norm_item_url = normalize_url_for_matching(resolved_url)
                    inherited_slug = url_to_slug_map.get(norm_item_url)
                    if inherited_slug and inherited_slug not in used_council_ids:
                        council_id = inherited_slug
                        action_label = "既存スラグID継承"
                    else:
                        council_id = f"{min_code.lower()}-{next_seq}"
                        while council_id in used_council_ids:
                            next_seq += 1
                            council_id = f"{min_code.lower()}-{next_seq}"
                        next_seq += 1
                        action_label = "新規会議体検出"

                    used_council_ids.add(council_id)

                    council_item = {
                        "id": council_id,
                        "name": cand_name,
                        "ministry": min_code,
                        "category": category,
                        "officialUrl": resolved_url,
                        "isNew": True,
                        "isNewlyDiscovered": True,
                        "discoveredAt": now_ts_slash,
                        "discoverySource": "rule"
                    }
                    discovered_list.append(council_item)
                    rule_cand_by_key[key_pair] = council_item
                    rule_cand_by_url[norm_resolved] = council_item
                    rule_cand_by_url[norm_orig] = council_item
                    found_in_min += 1
                    cat_label = categories_def.get(category, category)
                    emit(f"      ✨ [{action_label}] [{cat_label}] {council_id}: {cand_name} -> {resolved_url}", {
                        "type": "council_discovered",
                        "council": council_item
                    })

        emit(f"   -> 検出数: {found_in_min} 件")

    # Drop 81: 決定論的 1ファイル 新着ダイジェスト生成 & 単一リクエスト LLM 判定
    try:
        try:
            from llm.digest import build_discovery_digest
            from llm.client import LLMClient
            from llm.discovery_judge import judge_discovery_digest
        except ImportError:
            from admin.llm.digest import build_discovery_digest
            from admin.llm.client import LLMClient
            from admin.llm.discovery_judge import judge_discovery_digest

        digest_doc = build_discovery_digest(
            raw_items=all_raw_news_items,
            existing_councils=existing_councils,
            rejected_ids=rejected_ids,
            rejected_names=rejected_names,
            rejected_urls=rejected_urls,
            rejected_clean_keys=rejected_clean_keys,
            save_file=True
        )
        d_stats = digest_doc.get("stats", {})
        emit(
            f"\n[Digest] 省庁新着ダイジェスト生成完了: 原データ {d_stats.get('raw_count', 0)} 件 -> "
            f"候補 {d_stats.get('candidate_count', 0)} 件 (hash={digest_doc.get('digest_hash', '')[:12]})"
        )

        llm_enabled = bool(
            crawler_config.get("discovery_llm_mode", crawler_config.get("llm_mode", False))
        ) or (mock_llm_responder is not None)

        if llm_enabled and digest_doc.get("items"):
            emit("[LLM-Assist] ダイジェスト1ファイル一括LLM判定を実行中...")
            llm_client = LLMClient(
                schedule_tier=crawler_config.get("schedule_tier", "daily"),
                budget_config=crawler_config.get("llm_budget"),
                mock_responder=mock_llm_responder
            )
            judge_res = judge_discovery_digest(
                digest_doc=digest_doc,
                llm_client=llm_client,
                min_confidence=0.80
            )
            j_stats = judge_res.get("stats", {})
            emit(
                f"[LLM-Assist] 判定完了 (status={judge_res.get('status')}): "
                f"API呼出 {j_stats.get('llm_calls', 0)} 回 (キャッシュ {j_stats.get('cache_hits', 0)} 回), "
                f"新規会議体候補 {j_stats.get('accepted_count', 0)} 件"
            )

            sub_keywords = ('部会', '分科会', '小委員会', '委員会', 'ワーキンググループ', '検討会', '研究会', '審査会', '専門家会合', 'タスクフォース')
            for llm_cand in judge_res.get("candidates", []):
                min_code = normalize_ministry_code(llm_cand.get("ministry", ""))
                cand_name = llm_cand.get("name", "").strip()
                orig_item_url = llm_cand.get("url", "").strip()
                raw_title = llm_cand.get("raw_title", "")
                if not min_code or not cand_name or not orig_item_url:
                    continue

                key_pair = (min_code, get_core_council_name(cand_name))
                norm_orig = normalize_url(orig_item_url)

                matched_rule_cand = rule_cand_by_key.get(key_pair) or rule_cand_by_url.get(norm_orig)
                if matched_rule_cand is not None:
                    matched_rule_cand["discoverySource"] = "both"
                    continue

                if key_pair in seen_in_this_run:
                    continue

                if is_already_registered_or_rejected(
                    cand_name, orig_item_url, min_code,
                    existing_names, existing_urls, existing_core_names, councils_by_min,
                    rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
                ):
                    continue

                resolved_url = resolve_parent_url_from_press_release(orig_item_url, cand_name, min_code)
                norm_resolved = normalize_url(resolved_url)
                clean_res = get_url_clean_key(resolved_url)

                # 逆引きURLが単発報道発表URLのまま（親ポータル未解決）の場合は登録を遮断 (Drop 107)
                if is_single_press_or_notice_url(resolved_url) or (is_single_press_or_notice_url(orig_item_url) and resolved_url == orig_item_url):
                    continue

                # 逆引きURLが一覧ポータルまたは既に登録/検出済みなら元の単発URLにフォールバックせずスキップ (Drop 107)
                if (norm_resolved in existing_urls or
                    norm_resolved in all_portal_urls or
                    norm_resolved in seen_urls_in_this_run or
                    (clean_res and clean_res in rejected_clean_keys)):
                    continue

                if norm_resolved in existing_urls or norm_resolved in seen_urls_in_this_run or norm_resolved in all_portal_urls:
                    continue

                if is_already_registered_or_rejected(
                    cand_name, resolved_url, min_code,
                    existing_names, existing_urls, existing_core_names, councils_by_min,
                    rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
                ):
                    continue

                n1 = re.sub(r'\s+', '', cand_name)
                is_dup_with_cand = False
                for existing_cand in discovered_list:
                    if existing_cand.get("ministry", "").upper() == min_code.upper():
                        n2 = re.sub(r'\s+', '', existing_cand.get("name", ""))
                        if n1 == n2:
                            is_dup_with_cand = True
                            break
                        if len(n1) >= 4 and len(n2) >= 4:
                            if any(k in n1 for k in sub_keywords) and any(k in n2 for k in sub_keywords):
                                if (n2.endswith(n1) and not n2.startswith(n1)) or (n1.endswith(n2) and not n1.startswith(n2)):
                                    is_dup_with_cand = True
                                    break
                if is_dup_with_cand:
                    continue

                seen_in_this_run.add(key_pair)
                seen_urls_in_this_run.add(norm_resolved)

                category, is_def_cat = infer_council_category(f"{cand_name} {raw_title}", categories_def)
                if is_def_cat and llm_cand.get("category") in categories_def:
                    category = llm_cand["category"]
                category_counts[category] = category_counts.get(category, 0) + 1

                norm_item_url = normalize_url_for_matching(resolved_url)
                inherited_slug = url_to_slug_map.get(norm_item_url)
                if inherited_slug and inherited_slug not in used_council_ids:
                    council_id = inherited_slug
                    action_label = "LLMスラグID継承"
                else:
                    council_id = f"{min_code.lower()}-{next_seq}"
                    while council_id in used_council_ids:
                        next_seq += 1
                        council_id = f"{min_code.lower()}-{next_seq}"
                    next_seq += 1
                    action_label = "LLM新規会議体検出"

                used_council_ids.add(council_id)

                council_item = {
                    "id": council_id,
                    "name": cand_name,
                    "ministry": min_code,
                    "category": category,
                    "officialUrl": resolved_url,
                    "isNew": True,
                    "isNewlyDiscovered": True,
                    "discoveredAt": now_ts_slash,
                    "discoverySource": "llm"
                }
                discovered_list.append(council_item)
                cat_label = categories_def.get(category, category)
                emit(f"      🤖 [{action_label}] [{cat_label}] {council_id}: {cand_name} -> {resolved_url}", {
                    "type": "council_discovered",
                    "council": council_item
                })
    except Exception as e:
        emit(f"[WARN] ダイジェスト生成・LLM判定中に警告が発生しました: {e}")

    return discovered_list, category_counts


def _discover_normal_for_single_ministry(
    min_code, min_info, add_kw, exc_kw, common_keywords,
    categories_def, url_to_slug_map, existing_urls, existing_names, existing_core_names, councils_by_min,
    rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys,
    resolved_url_cache
):
    """
    1省庁分の通常審議会一覧巡回タスク (並列ワーカー対応・同一省庁内は直列かつディレイ遵守) (CR-190)
    """
    councils_urls = min_info.get("councilsUrls", [])
    target_kw = common_keywords + add_kw
    discovered_in_min = []
    seen_in_min = set()

    for page_url in councils_urls:
        page_url = page_url.strip()
        if not page_url or not page_url.startswith("http") or "abolition_list.html" in page_url:
            continue

        html, final_page_url = fetch_page_and_final_url(page_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Drop 113: 内閣府(CAO) council.html の終了会議体(#done01)セクション除外ガード
        done_nodes = set()
        if "cao.go.jp" in final_page_url or "council.html" in final_page_url:
            h2_done = soup.find(id="done01")
            if h2_done:
                done_nodes = set(h2_done.find_all_next())

        links = soup.find_all("a", href=True)

        for a in links:
            if done_nodes and a in done_nodes:
                continue

            href = a["href"].strip()
            # Drop 113: 内閣官房(CAS)等の廃止一覧ページ(abolition_list.html)リンクの除外ガード
            if "abolition_list.html" in href:
                continue
            raw_text = a.get_text(separator=" ", strip=True)
            title_attr = a.get("title", "").strip()
            link_text = raw_text or title_attr

            if not link_text or len(link_text) < 3 or len(link_text) > 100:
                continue

            if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                continue

            # キーワード照合
            if not any(kw in link_text for kw in target_kw):
                continue
            # 除外キーワード照合
            if any(ex in link_text for ex in exc_kw):
                continue

            # 絶対URLに変換
            abs_url = urllib.parse.urljoin(final_page_url, href)

            # ノイズ・ドキュメント直リンク・単発報道発表URL判定 (CR-187, Drop 107)
            if is_non_council_noise(link_text, "", abs_url) or is_single_press_or_notice_url(abs_url):
                continue

            # 会議体名のクレンジング (CR-186)
            is_meet_pat = bool(re.search(r'[(（]?第\s*[0-9０-９一-九]+\s*回[)）]?', link_text))
            cand_name = clean_council_name(link_text) if is_meet_pat else link_text.strip()
            if not cand_name or len(cand_name) < 4:
                continue

            if is_non_council_noise(cand_name, link_text, abs_url):
                continue

            # HTTPアクセス前の事前フィルタ (CR-190)
            if is_already_registered_or_rejected(
                cand_name, abs_url, min_code,
                existing_names, existing_urls, existing_core_names, councils_by_min,
                rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
            ):
                continue

            core_k = get_core_council_name(cand_name)
            if core_k in seen_in_min:
                continue

            # HTTPアクセスして最終正規URLを取得（キャッシュ活用）
            if abs_url in resolved_url_cache:
                final_council_url = resolved_url_cache[abs_url]
            else:
                _, final_council_url = fetch_page_and_final_url(abs_url)
                if not final_council_url:
                    final_council_url = abs_url
                resolved_url_cache[abs_url] = final_council_url

            # 最終URLでの既存・却下判定
            if is_already_registered_or_rejected(
                cand_name, final_council_url, min_code,
                existing_names, existing_urls, existing_core_names, councils_by_min,
                rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys
            ):
                continue

            seen_in_min.add(core_k)

            category, is_default = infer_council_category(f"{cand_name} {link_text}", categories_def)

            # target_url_cand の決定 (CR-191: 一覧URL強制上書きバグを廃止)
            target_url_cand = final_council_url

            discovered_in_min.append({
                "cand_name": cand_name,
                "link_text": link_text,
                "target_url_cand": target_url_cand,
                "category": category,
                "is_default": is_default,
                "min_code": min_code
            })

    return min_code, discovered_in_min


def run_discovery(progress_callback=None, target_ministry=None, dry_run=False, mode="normal", mock_llm_responder=None, enable_llm=None):
    def emit(msg, data=None):
        print(msg)
        if progress_callback:
            try:
                progress_callback(msg, data)
            except Exception:
                pass

    emit("=" * 70)
    emit(f"【PM-HUB】省庁 審議会・会議体ディスカバリー巡回 開始 (モード: {'省庁新着検知' if mode == 'ministry_news' else '通常一覧巡回'})")
    if mode == "ministry_news":
        emit("（各府省庁トップページ・報道発表ポータルから新設された検討会・会議体を検知します）")
    else:
        emit("（審議会等ページにアクセスし、全会議体を個別の正規URLで独立検出します）")
    if target_ministry:
        emit(f"巡回対象省庁フィルター: {target_ministry.upper()}")
    if dry_run:
        emit("動作モード: DRY RUN（data.json への書き込みなし）")
    emit(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    emit("=" * 70)

    keywords_cfg = load_keywords()
    common_keywords = keywords_cfg.get("commonKeywords", [])
    common_excludes = keywords_cfg.get("commonExcludeKeywords", [])
    min_add_kw = keywords_cfg.get("ministryAddKeywords", {})
    min_exc_kw = keywords_cfg.get("ministryExcludeKeywords", {})

    ministries, existing_councils, categories_def, scraping_rules = parse_data_json()
    emit(f"登録済み省庁数: {len(ministries)} 組織, 既存会議体数: {len(existing_councils)} 件, カテゴリー定義数: {len(categories_def)} 種類\n")

    # 全省庁の審議会一覧トップURL（councilsUrls）のセット (CR-191: スラグ継承汚染防止)
    all_portal_urls = set()
    for min_info in ministries.values():
        for u in min_info.get("councilsUrls", []):
            if u:
                all_portal_urls.add(normalize_url_for_matching(u))
                all_portal_urls.add(normalize_url(u))

    # CR-92 / CR-191: 既存URL -> スラグIDマップの構築（審議会一覧ポータルURLは除外）
    url_to_slug_map = {}
    for c in existing_councils:
        cid = c.get("id")
        if not cid:
            continue
        for u in (c.get("officialUrl"), c.get("url"), c.get("archiveUrl")):
            if u and isinstance(u, str):
                nu = normalize_url_for_matching(u)
                if nu and nu not in url_to_slug_map and nu not in all_portal_urls:
                    url_to_slug_map[nu] = cid

    for cid, r in scraping_rules.items():
        if not isinstance(r, dict):
            continue
        for u in (r.get("officialUrl"), r.get("target_url"), r.get("url"), r.get("archiveUrl")):
            if u and isinstance(u, str):
                nu = normalize_url_for_matching(u)
                if nu and nu not in url_to_slug_map and nu not in all_portal_urls:
                    url_to_slug_map[nu] = cid
    emit(f"既存スラグID照合用URLインデックス: {len(url_to_slug_map)} 件を構築しました（スラグID自動継承）")

    # 却下済み会議体データの読み込み（再検出・再登録をブロック）
    rejected_data = load_rejected_councils()
    rejected_ids = set()
    rejected_urls = set()
    rejected_clean_keys = set()
    rejected_names = set()
    rejected_core_names = set()
    for rc in rejected_data:
        if rc.get("id"):
            rejected_ids.add(rc.get("id").strip())
        if rc.get("officialUrl"):
            rejected_urls.add(normalize_url(rc.get("officialUrl")))
            clean_k = get_url_clean_key(rc.get("officialUrl"))
            if clean_k:
                rejected_clean_keys.add(clean_k)
        if rc.get("name"):
            n_raw = rc.get("name").strip()
            rejected_names.add(n_raw)
            n_clean = clean_council_name(n_raw)
            if n_clean:
                rejected_names.add(n_clean)
            c_core = get_core_council_name(n_raw)
            if c_core:
                rejected_core_names.add(c_core)
    emit(f"却下済み会議体除外リスト: {len(rejected_data)} 件をロードしました（巡回検出対象外として完全除外）")

    # 既存の会議体URLと名前のセット（重複判定用）
    existing_urls = {normalize_url(c.get("officialUrl", "")) for c in existing_councils if c.get("officialUrl")}
    existing_names = {c.get("name", "").strip() for c in existing_councils if c.get("name")}
    existing_core_names = {get_core_council_name(c.get("name")) for c in existing_councils if c.get("name") and get_core_council_name(c.get("name"))}
    councils_by_min = {}
    for c in existing_councils:
        councils_by_min.setdefault(c.get("ministry", "").upper(), []).append(c)

    next_seq = get_max_seq(existing_councils) + 1
    used_council_ids = {c.get("id") for c in existing_councils if c.get("id")}
    discovered_list = []
    category_counts = {}
    unmatched_category_councils = []

    admin_data_cfg = load_data_json(ADMIN_DATA_PATH) or {}
    crawler_config = admin_data_cfg.get("crawlerConfig") or (load_data_json(DATA_JSON_PATH) or {}).get("crawlerConfig", {})
    if enable_llm is not None:
        crawler_config["discovery_llm_mode"] = bool(enable_llm)

    if mode == "ministry_news":
        discovered_list, category_counts = _discover_from_ministry_news(
            emit, target_ministry, ministries, existing_councils,
            categories_def, url_to_slug_map, existing_urls, existing_names,
            rejected_names, rejected_urls, rejected_clean_keys, common_keywords, next_seq,
            used_council_ids, all_portal_urls=all_portal_urls,
            rejected_ids=rejected_ids, crawler_config=crawler_config,
            mock_llm_responder=mock_llm_responder
        )
    else:
        active_ministries = [m for code, m in ministries.items() if m.get("hasCouncils", True) and m.get("councilsUrls") and (not target_ministry or code.upper() == target_ministry.upper())]
        total_ministries = len(active_ministries)
        emit(f"走査対象府省庁: {total_ministries} 省庁 (省庁間並列ワーカー + 事前フィルタ高速化)")

        resolved_url_cache = {}
        tasks = []

        for min_code, min_info in sorted(ministries.items()):
            if target_ministry and min_code.upper() != target_ministry.upper():
                continue
            has_councils = min_info.get("hasCouncils", True)
            councils_urls = min_info.get("councilsUrls", [])
            if not has_councils or not councils_urls:
                continue

            add_kw = min_add_kw.get(min_code, [])
            exc_kw = min_exc_kw.get(min_code, []) + common_excludes
            tasks.append((min_code, min_info, add_kw, exc_kw))

        # 省庁間並列ワーカーで実行 (CR-190)
        max_workers = min(6, len(tasks)) if tasks else 1
        emit(f"並列スレッド数: {max_workers} ワーカーで巡回開始...")

        results_by_min = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_min = {
                executor.submit(
                    _discover_normal_for_single_ministry,
                    t[0], t[1], t[2], t[3], common_keywords,
                    categories_def, url_to_slug_map, existing_urls, existing_names, existing_core_names, councils_by_min,
                    rejected_names, rejected_urls, rejected_core_names, rejected_clean_keys,
                    resolved_url_cache
                ): t[0] for t in tasks
            }
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_min):
                m_code = future_to_min[future]
                completed_count += 1
                try:
                    m_code_ret, disc_items = future.result()
                    results_by_min[m_code_ret] = disc_items
                    m_name = ministries.get(m_code_ret, {}).get("name", m_code_ret)
                    pct = int((completed_count / max(total_ministries, 1)) * 90)
                    emit(f"   [{completed_count}/{total_ministries}] [{m_code_ret}] {m_name} 完了 (候補 {len(disc_items)} 件)", {
                        "type": "ministry_done",
                        "ministry": m_code_ret,
                        "progress": pct
                    })
                except Exception as e:
                    emit(f"   [ERROR] [{m_code}] 巡回中にエラー発生: {e}")

        # 結果の統合とID採番 (CR-191, Check 12/14重複排除)
        seen_urls_in_normal = set()
        sub_keywords = ('部会', '分科会', '小委員会', '委員会', 'ワーキンググループ', '検討会', '研究会', '審査会', '専門家会合', 'タスクフォース')

        for min_code, min_info in sorted(ministries.items()):
            disc_items = results_by_min.get(min_code, [])
            for item in disc_items:
                cand_name = item["cand_name"]
                link_text = item["link_text"]
                target_url_cand = item["target_url_cand"]
                category = item["category"]
                is_default = item["is_default"]

                norm_cand_url = normalize_url(target_url_cand)
                # 単発報道発表URL除外 & URL重複防止 (Drop 107, Check 12)
                if is_single_press_or_notice_url(target_url_cand) or norm_cand_url in existing_urls or norm_cand_url in seen_urls_in_normal or norm_cand_url in all_portal_urls:
                    continue

                # 同一省庁内での新規候補間サフィックス重複防止 (Check 14)
                n1 = re.sub(r'\s+', '', cand_name)
                is_suffix_dup = False
                for ex_cand in discovered_list:
                    if ex_cand.get("ministry", "").upper() == min_code.upper():
                        n2 = re.sub(r'\s+', '', ex_cand.get("name", ""))
                        if n1 == n2:
                            is_suffix_dup = True
                            break
                        if len(n1) >= 4 and len(n2) >= 4:
                            if any(k in n1 for k in sub_keywords) and any(k in n2 for k in sub_keywords):
                                if (n2.endswith(n1) and not n2.startswith(n1)) or (n1.endswith(n2) and not n1.startswith(n2)):
                                    is_suffix_dup = True
                                    break
                if is_suffix_dup:
                    continue

                seen_urls_in_normal.add(norm_cand_url)
                category_counts[category] = category_counts.get(category, 0) + 1
                if is_default:
                    unmatched_category_councils.append({
                        "id": None,
                        "name": cand_name,
                        "url": target_url_cand,
                        "ministry": min_code,
                        "appliedCategory": category
                    })

                norm_final_url = normalize_url_for_matching(target_url_cand)
                inherited_slug = url_to_slug_map.get(norm_final_url)

                if inherited_slug and inherited_slug not in used_council_ids:
                    council_id = inherited_slug
                    is_inherited = True
                else:
                    council_id = f"{min_code.lower()}-{next_seq}"
                    while council_id in used_council_ids:
                        next_seq += 1
                        council_id = f"{min_code.lower()}-{next_seq}"
                    next_seq += 1
                    is_inherited = False

                used_council_ids.add(council_id)

                if is_default and unmatched_category_councils:
                    unmatched_category_councils[-1]["id"] = council_id

                now_ts_slash = datetime.now().strftime("%Y/%m/%d %H:%M")
                council_item = {
                    "id": council_id,
                    "name": cand_name,
                    "ministry": min_code,
                    "category": category,
                    "officialUrl": target_url_cand,
                    "isNew": True,
                    "isNewlyDiscovered": True,
                    "discoveredAt": now_ts_slash,
                    "discoverySource": "rule"
                }

                discovered_list.append(council_item)
                cat_label = categories_def.get(category, category)
                action_label = "既存スラグID継承" if is_inherited else "新規会議体検出"
                emit(f"      ✨ [{action_label}] [{cat_label}] {council_id}: {cand_name} -> {target_url_cand}", {
                    "type": "council_discovered",
                    "council": council_item
                })

    emit("\n" + "=" * 70)
    emit(f"ディスカバリー巡回完了: 合計 {len(discovered_list)} 件の新規会議体レコードを作成しました。")
    emit("-" * 70)
    emit("【新規検出会議体のカテゴリー内訳】")
    if category_counts:
        for cat_id, cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            label = categories_def.get(cat_id, cat_id)
            emit(f"  - {label} ({cat_id}): {cnt} 件")
    else:
        emit("  - 新規検出なし")

    if unmatched_category_councils:
        emit("-" * 70)
        emit(f"⚠️ 【特定カテゴリーに該当せずデフォルト（COUNCIL/審議会）が適用された会議体: {len(unmatched_category_councils)}件】")
        for u in unmatched_category_councils:
            emit(f"  ・ [{u['ministry']}] {u['id']}: {u['name']} -> {u['url']}")
    elif discovered_list:
        emit("-" * 70)
        emit("  ✨ すべての新規会議体が特定の定義済みカテゴリーに分類されました。")
    emit("=" * 70)

    # 結果JSONの保存 (data.json の councils を更新、却下済みを完全パージ)
    if dry_run:
        emit("\n[DRY RUN] dry-run モードのため、data.json への保存はスキップされました。")
        return discovered_list

    data = load_data_json(DATA_JSON_PATH)
    if data:
        try:
            existing_councils = data.get("councils", [])
            existing_dict = {c.get("id"): c for c in existing_councils if c.get("id")}
            
            filtered_existing_dict = {}
            for cid, c in existing_dict.items():
                c_url = normalize_url(c.get("officialUrl", ""))
                c_clean_k = get_url_clean_key(c.get("officialUrl", ""))
                c_name = c.get("name", "").strip()
                c_clean_name = clean_council_name(c_name)

                if (cid in rejected_ids or
                    c_url in rejected_urls or
                    (c_clean_k and c_clean_k in rejected_clean_keys) or
                    c_name in rejected_names or
                    (c_clean_name and c_clean_name in rejected_names)):
                    continue
                filtered_existing_dict[cid] = c

            # 重複防止用セット (Check 12 & Check 14 厳格ガード)
            saved_urls = {normalize_url(c.get("officialUrl", "")) for c in filtered_existing_dict.values() if c.get("officialUrl")}
            saved_names_by_min = {}
            for c in filtered_existing_dict.values():
                saved_names_by_min.setdefault(c.get("ministry", "").upper(), []).append(c)

            sub_keywords = ('部会', '分科会', '小委員会', '委員会', 'ワーキンググループ', '検討会', '研究会', '審査会', '専門家会合', 'タスクフォース')

            added_count = 0
            for new_c in discovered_list:
                cid = new_c.get("id")
                norm_u = normalize_url(new_c.get("officialUrl", ""))
                clean_k = get_url_clean_key(new_c.get("officialUrl", ""))
                raw_n = new_c.get("name", "").strip()
                clean_n = clean_council_name(raw_n)
                m_code = new_c.get("ministry", "").upper()

                # 却下判定
                if (cid in rejected_ids or
                    norm_u in rejected_urls or
                    (clean_k and clean_k in rejected_clean_keys) or
                    raw_n in rejected_names or
                    (clean_n and clean_n in rejected_names)):
                    continue

                if cid in filtered_existing_dict:
                    # 既存の会議体は既存の新着状態・ロック状態・件数を維持
                    ex_rec = filtered_existing_dict[cid]
                    new_c.pop("status", None)
                    new_c["isNewlyDiscovered"] = bool(ex_rec.get("isNewlyDiscovered", False))
                    if ex_rec.get("discoveredAt"):
                        new_c["discoveredAt"] = ex_rec["discoveredAt"]
                    else:
                        new_c.pop("discoveredAt", None)
                    if ex_rec.get("discoverySource"):
                        new_c["discoverySource"] = ex_rec["discoverySource"]
                    else:
                        new_c.pop("discoverySource", None)
                    new_c["manualLock"] = ex_rec.get("manualLock", False)
                    new_c["pastYearCount"] = ex_rec.get("pastYearCount", 0)
                    filtered_existing_dict[cid] = new_c
                    continue

                # 1. URL重複チェック (Check 12)
                if norm_u in saved_urls or norm_u in all_portal_urls:
                    continue

                # 2. 同一省庁内の短縮サフィックス重複チェック (Check 14)
                n1 = re.sub(r'\s+', '', raw_n)
                n1_clean = re.sub(r'\s+', '', clean_n)
                is_suffix_dup = False
                for ex_c in saved_names_by_min.get(m_code, []):
                    ex_name = ex_c.get("name", "")
                    n2 = re.sub(r'\s+', '', ex_name)
                    if n1 == n2 or n1_clean == n2:
                        is_suffix_dup = True
                        break
                    for cand_cand in (n1, n1_clean):
                        if len(cand_cand) >= 4 and len(n2) >= 4:
                            if any(k in cand_cand for k in sub_keywords) and any(k in n2 for k in sub_keywords):
                                if (n2.endswith(cand_cand) and not n2.startswith(cand_cand)) or (cand_cand.endswith(n2) and not cand_cand.startswith(n2)):
                                    is_suffix_dup = True
                                    break
                    if is_suffix_dup:
                        break
                if is_suffix_dup:
                    continue

                new_c.pop("status", None)
                new_c["isNewlyDiscovered"] = True
                new_c["discoveredAt"] = new_c.get("discoveredAt") or datetime.now().strftime("%Y/%m/%d %H:%M")
                new_c["discoverySource"] = new_c.get("discoverySource") or "rule"
                filtered_existing_dict[cid] = new_c
                saved_urls.add(norm_u)
                saved_names_by_min.setdefault(m_code, []).append(new_c)
                added_count += 1
            
            data["councils"] = list(filtered_existing_dict.values())
            if "discoveredCouncils" in data:
                del data["discoveredCouncils"]

            # CR-92: 新規登録された会議体の scrapingRules 自動連動登録 (Case 11 & Case 15)
            # 必ず filtered_existing_dict (councilsマスター) に存在する会議体のみを対象とする
            scraping_rules_in_data = data.setdefault("scrapingRules", {})
            new_rules_count = 0
            for cid, c_obj in filtered_existing_dict.items():
                if cid and cid not in scraping_rules_in_data:
                    scraping_rules_in_data[cid] = {
                        "template": "tpl-cas-gijisidai-nested",
                        "manualLock": True,
                        "officialUrl": c_obj.get("officialUrl", ""),
                        "extract_from_parent_table": True
                    }
                    new_rules_count += 1

            # 孤立ルールを完全にパージ (FK制約保護)
            orphan_count = 0
            for r_cid in list(scraping_rules_in_data.keys()):
                if r_cid not in filtered_existing_dict:
                    del scraping_rules_in_data[r_cid]
                    orphan_count += 1

            if new_rules_count > 0:
                print(f"新規会議体 {new_rules_count} 件に scrapingRules を自動連動登録しました。")
            if orphan_count > 0:
                print(f"孤立 scrapingRules {orphan_count} 件をパージしました。")
            
            if save_data_json_with_backup(data):
                print(f"結果を data.json の councils に保存しました（新規追加: {added_count} 件）。")

                # SQLite マスターDBへの同期シード ＆ 2系統エクスポート
                try:
                    from db.seed_db import seed_db
                    from db.export_data import export_data
                except ImportError:
                    from admin.db.seed_db import seed_db
                    from admin.db.export_data import export_data

                print("[DB SYNC] SQLite マスターDB (admin/pmhub.db) への同期シードを実行中...")
                if seed_db():
                    print("[DB SYNC] 2系統 JSON への決定論的エクスポートを実行中...")
                    export_data()
                    print("[DB SYNC] SQLite マスターDB & 2系統 JSON の完全同期が完了しました。")
                else:
                    print("[WARN] SQLite マスターDBへのシードに失敗しました。")
            else:
                print(f"[WARN] data.json の保存に失敗しました。")
        except Exception as e:
            print(f"[ERROR] data.json の更新に失敗しました: {e}")
            import traceback
            traceback.print_exc()
    return discovered_list
    return discovered_list

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PMHub 審議会・会議体ディスカバリーエンジン")
    parser.add_argument("--ministry", type=str, default=None, help="巡回対象の省庁コード（例: FSA, MOF, METI）")
    parser.add_argument("--dry-run", action="store_true", help="data.json を更新せず、検出結果の表示のみを行う")
    parser.add_argument("--mode", choices=["normal", "ministry_news"], default="normal", help="探索モード (normal: 審議会等一覧巡回, ministry_news: 省庁新着情報検知)")
    parser.add_argument("--from-ministry-news", dest="from_news", action="store_true", help="省庁新着情報・報道発表から新規会議体を検知")
    parser.add_argument("--llm", action="store_true", help="LLM判定モードを強制ON")
    parser.add_argument("--no-llm", action="store_true", help="LLM判定モードをOFF")
    args = parser.parse_args()
    mode = "ministry_news" if args.from_news or args.mode == "ministry_news" else "normal"
    enable_llm = True if args.llm else (False if args.no_llm else None)
    run_discovery(target_ministry=args.ministry, dry_run=args.dry_run, mode=mode, enable_llm=enable_llm)
