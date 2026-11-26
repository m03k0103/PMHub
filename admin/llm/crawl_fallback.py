#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batched LLM Crawl Fallback Engine (admin/llm/crawl_fallback.py)
===============================================================
Track [LLM-Assist] フェーズ2 (Drop 153):
1. 決定論的異常スコア計算 (compute_crawl_anomaly_score):
   抽出0件だけでなく「ページ上部に最新日付があるのに取りこぼし」「資料0件PARTIAL」
   「日付欠落PARTIAL」「汎用タイトル過多」を定量スコア化して補完対象を選別。
2. コンパクトDOMスニペット生成 (build_compact_dom_snippet):
   nav/header/footer/scriptを除外し、実在リンクへ連番ID (L01〜) を割り当てて圧縮。
   LLM には link_id のみ参照させ、URL ハルシネーションを物理遮断する。
3. バッチ LLM 構造補完 (run_batched_llm_crawl_fallback):
   5〜8会議体を1リクエストへ集約し、LLMClient の日次/週次/月次予算上限および
   SQLite llm_cache (SHA-256) の配下で安全に構造抽出を行う。
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .client import LLMClient

_GENERIC_SUBPAGE_TITLES = frozenset({
    "会議資料詳細", "資料詳細", "会議詳細", "開催状況", "トップページ", "ホーム", "目次",
    "会議資料", "資料一覧", "配付資料", "配布資料"
})
_DATE_IN_HTML_RE = re.compile(
    r'(?:令和|平成)\s*(?:\d+|元)\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}[/-]\d{1,2}[/-]\d{1,2}'
)


def _normalize_yyyymmdd(date_str: str) -> str:
    """日付文字列を YYYY/MM/DD 形式へ正規化する。パース不能時は空文字。"""
    if not date_str:
        return ""
    s = str(date_str).strip()
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    s = s.translate(trans)

    m_reiwa = re.match(r'^令和\s*(\d+|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', s)
    if m_reiwa:
        yr = 2018 + (1 if m_reiwa.group(1) == "元" else int(m_reiwa.group(1)))
        return f"{yr:04d}/{int(m_reiwa.group(2)):02d}/{int(m_reiwa.group(3)):02d}"

    m_heisei = re.match(r'^平成\s*(\d+|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', s)
    if m_heisei:
        yr = 1988 + (1 if m_heisei.group(1) == "元" else int(m_heisei.group(1)))
        return f"{yr:04d}/{int(m_heisei.group(2)):02d}/{int(m_heisei.group(3)):02d}"

    m_kanji = re.match(r'^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', s)
    if m_kanji:
        return f"{int(m_kanji.group(1)):04d}/{int(m_kanji.group(2)):02d}/{int(m_kanji.group(3)):02d}"

    m_iso = re.match(r'^(\d{4})[/-](\d{1,2})[/-](\d{1,2})', s)
    if m_iso:
        return f"{int(m_iso.group(1)):04d}/{int(m_iso.group(2)):02d}/{int(m_iso.group(3)):02d}"

    return ""


def compute_crawl_anomaly_score(
    target: Dict[str, Any],
    scraped_item: Dict[str, Any],
    html: str = "",
    existing_latest_date: str = "",
    threshold: int = 45,
) -> Dict[str, Any]:
    """
    Stage 1 ルール抽出結果に対し決定論的異常スコアを算出し、バッチ LLM 補完要否を判定する。
    """
    if not isinstance(scraped_item, dict):
        return {"score": 100, "reasons": ["empty_scraped_item"], "needs_fallback": True}

    cr = (scraped_item.get("crawlResult") or "").lower()
    total_mats = int(scraped_item.get("totalExtractedMaterials") or 0)
    extracted_dates = scraped_item.get("extractedDates") or []
    sub_meetings = scraped_item.get("subpageMeetings") or []

    score = 0
    reasons: List[str] = []

    if cr == "failed" and total_mats == 0 and not sub_meetings:
        score += 100
        reasons.append("zero_extraction")
    elif cr == "partial":
        if sub_meetings and total_mats == 0:
            score += 60
            reasons.append("partial_no_materials")
        elif total_mats > 0 and not extracted_dates:
            score += 50
            reasons.append("partial_no_dates")

    # ページ上位(先頭8000文字)に既存最新開催日より新しい実日付が存在するのに未抽出の場合
    norm_existing = _normalize_yyyymmdd(existing_latest_date)
    if html and norm_existing and norm_existing != "2099/01/01":
        head_text = re.sub(r'<[^>]+>', ' ', html[:8000])
        page_dates = [_normalize_yyyymmdd(m) for m in _DATE_IN_HTML_RE.findall(head_text)]
        page_dates = [d for d in page_dates if d and d != "2099/01/01" and "1990/01/01" <= d <= "2035/12/31"]
        if page_dates:
            newest_in_page = max(page_dates)
            if newest_in_page > norm_existing:
                sub_dates_all = [_normalize_yyyymmdd(d) for d in extracted_dates]
                for sm in sub_meetings:
                    for sd in (sm.get("extractedDates") or []):
                        sub_dates_all.append(_normalize_yyyymmdd(sd))
                sub_dates_valid = [d for d in sub_dates_all if d and d != "2099/01/01"]
                if not sub_dates_valid or max(sub_dates_valid) < newest_in_page:
                    score += 45
                    reasons.append("stale_despite_newer_page_date")

    if sub_meetings:
        generic_cnt = sum(
            1 for sm in sub_meetings
            if (sm.get("name") or sm.get("title") or "").strip() in _GENERIC_SUBPAGE_TITLES
        )
        if generic_cnt * 2 > len(sub_meetings):
            score += 30
            reasons.append("generic_titles_excess")

    return {
        "score": score,
        "reasons": reasons,
        "needs_fallback": score >= threshold,
    }


def build_compact_dom_snippet(html: str, base_url: str, max_chars: int = 2500) -> Dict[str, Any]:
    """
    HTML から不要UIを除去し、見出し・リンク一覧（L01, L02, ...）・本文抜粋を圧縮生成する。
    """
    if not html:
        return {"title": "", "headings": [], "links": [], "links_by_id": {}, "text_excerpt": ""}

    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""

    for tag in soup.find_all(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    headings: List[str] = []
    for h in soup.find_all(["h1", "h2", "h3"]):
        txt = re.sub(r'\s+', ' ', h.get_text(" ", strip=True)).strip()
        if txt and txt not in headings:
            headings.append(txt[:80])
        if len(headings) >= 8:
            break

    links: List[Dict[str, Any]] = []
    links_by_id: Dict[str, Dict[str, Any]] = {}
    seen_urls = set()
    seq = 1
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        abs_url = urljoin(base_url, href)
        if abs_url in seen_urls:
            continue
        seen_urls.add(abs_url)
        ltext = re.sub(r'\s+', ' ', a.get_text(" ", strip=True)).strip()
        if not ltext or len(ltext) < 2:
            continue
        link_id = f"L{seq:02d}"
        seq += 1
        is_pdf = bool(urlparse(abs_url).path.lower().endswith(".pdf"))
        entry = {"id": link_id, "text": ltext[:80], "url": abs_url, "is_pdf": is_pdf}
        links.append({"id": link_id, "text": entry["text"], "is_pdf": is_pdf})
        links_by_id[link_id] = entry
        if len(links) >= 40:
            break

    raw_text = re.sub(r'\s+', ' ', soup.get_text(" ", strip=True)).strip()
    overhead = len(page_title) + sum(len(h) for h in headings) + len(json.dumps(links, ensure_ascii=False))
    text_budget = max(300, int(max_chars) - overhead)

    return {
        "title": page_title[:100],
        "headings": headings,
        "links": links,
        "links_by_id": links_by_id,
        "text_excerpt": raw_text[:text_budget],
    }


def _build_batch_prompt(batch_payload: List[Dict[str, Any]]) -> str:
    compact_json = json.dumps(batch_payload, ensure_ascii=False, indent=2)
    return f"""あなたは日本の官公庁の審議会・検討会Webページから開催回情報と配付資料リンクを構造抽出する専門アナリストです。
以下の各会議体スニペットを解析し、取得できている開催回・日付・配付資料リンクIDを抽出してください。

【厳守ルール】
1. 出力は必ず入力の `council_id` と、入力 `links` 配列内の `id`（例: "L01"）のみを参照してください。URL文字列は絶対に出力しないでください。
2. `date` は必ず `YYYY/MM/DD`（例: "2026/11/10"）形式に正規化してください（和暦令和8年→2026年）。特定不能な開催回は出力しないでください。
3. 確認できた開催回のみ `meetings` に出力し、不明な会議体は空配列 `"meetings": []` にしてください。
4. Markdownコードブロックは出力せず、純粋な JSON オブジェクトのみ返却してください。

{{
  "results": [
    {{
      "council_id": "会議体ID",
      "meetings": [
        {{
          "date": "2026/11/10",
          "title": "第X回 〇〇検討会",
          "subpage_link_id": "L01 または空文字",
          "material_link_ids": ["L02", "L03"]
        }}
      ]
    }}
  ]
}}

【入力会議体バッチ】
{compact_json}
"""


def run_batched_llm_crawl_fallback(
    anomaly_entries: List[Dict[str, Any]],
    llm_client: Optional[LLMClient] = None,
    batch_size: int = 5,
) -> Dict[str, Any]:
    """
    異常スコア基準を満たした会議体群を 5〜8 件ずつバッチ化して LLMClient へ問い合わせ、
    実在 link_id 照合済み (ハルシネーション遮断) の抽出結果を返す。
    """
    stats = {
        "total_candidates": len(anomaly_entries or []),
        "batches": 0,
        "llm_calls": 0,
        "cache_hits": 0,
        "resolved_councils": 0,
        "status": "no_candidates",
    }
    if not anomaly_entries:
        return {"stats": stats, "results_by_council": {}}

    client = llm_client or LLMClient(schedule_tier="weekly")
    eff_batch_size = max(1, min(8, int(batch_size)))
    ordered = sorted(anomaly_entries, key=lambda x: (-int(x.get("score", 0)), str(x.get("council_id", ""))))

    results_by_council: Dict[str, Dict[str, Any]] = {}
    last_status = "ok"

    for start in range(0, len(ordered), eff_batch_size):
        chunk = ordered[start:start + eff_batch_size]
        batch_prompt_items = []
        links_map_by_cid: Dict[str, Dict[str, Dict[str, Any]]] = {}
        council_url_by_cid: Dict[str, str] = {}

        for entry in chunk:
            cid = entry["council_id"]
            snippet = entry.get("snippet") or build_compact_dom_snippet(entry.get("html", ""), entry.get("url", ""))
            links_map_by_cid[cid] = snippet.get("links_by_id") or {}
            council_url_by_cid[cid] = entry.get("url", "")
            batch_prompt_items.append({
                "council_id": cid,
                "name": entry.get("name", ""),
                "existing_latest_date": entry.get("existing_latest_date", ""),
                "anomaly_reasons": entry.get("reasons", []),
                "title": snippet.get("title", ""),
                "headings": snippet.get("headings", []),
                "links": snippet.get("links", []),
                "text_excerpt": snippet.get("text_excerpt", ""),
            })

        canonical = json.dumps(batch_prompt_items, ensure_ascii=False, sort_keys=True)
        digest_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        prompt = _build_batch_prompt(batch_prompt_items)

        calls_before = client.calls_made
        cache_before = client.cache_hits
        resp = client.generate_structured_json(
            prompt=prompt,
            digest_hash=digest_hash,
            purpose="crawl_fallback",
            context_meta={"councils": batch_prompt_items},
        )
        stats["batches"] += 1
        stats["llm_calls"] += max(0, client.calls_made - calls_before)
        stats["cache_hits"] += max(0, client.cache_hits - cache_before)
        last_status = resp.get("status", "error")

        if last_status in ("budget_exceeded", "quota_blocked", "unavailable"):
            break

        raw_results = (resp.get("data") or {}).get("results") or []
        if not isinstance(raw_results, list):
            continue

        for r_item in raw_results:
            if not isinstance(r_item, dict):
                continue
            cid = r_item.get("council_id", "")
            if cid not in links_map_by_cid:
                continue
            links_by_id = links_map_by_cid[cid]
            parent_url = council_url_by_cid[cid]

            subpage_meetings = []
            extracted_dates = []
            all_mats = []

            for raw_m in (r_item.get("meetings") or []):
                if not isinstance(raw_m, dict):
                    continue
                norm_date = _normalize_yyyymmdd(raw_m.get("date", ""))
                if not norm_date or norm_date == "2099/01/01":
                    continue
                m_title = (raw_m.get("title") or "").strip()
                if not m_title:
                    continue

                sub_lid = (raw_m.get("subpage_link_id") or "").strip()
                if sub_lid and sub_lid in links_by_id:
                    sub_url = links_by_id[sub_lid]["url"]
                else:
                    sub_url = parent_url

                mats = []
                for mat_lid in (raw_m.get("material_link_ids") or []):
                    lid_s = str(mat_lid).strip()
                    if lid_s in links_by_id:
                        linfo = links_by_id[lid_s]
                        mats.append({
                            "name": linfo["text"],
                            "url": linfo["url"],
                            "type": "PDF" if linfo.get("is_pdf") else "HTML",
                            "isPrivate": False,
                        })
                if not mats and not (sub_lid and sub_lid in links_by_id):
                    continue

                extracted_dates.append(norm_date)
                all_mats.extend(mats)
                subpage_meetings.append({
                    "subpageUrl": sub_url,
                    "name": m_title,
                    "title": m_title,
                    "extractedDates": [norm_date],
                    "materials": mats,
                })

            if subpage_meetings:
                results_by_council[cid] = {
                    "scrapedAt": "",
                    "crawlResult": "success" if all_mats else "partial",
                    "resultReason": f"Track [LLM-Assist] バッチ構造補完 ({len(subpage_meetings)}回 / 資料{len(all_mats)}件)",
                    "extractionMethod": "llm_batch",
                    "totalExtractedMaterials": len(all_mats),
                    "extractedDates": list(dict.fromkeys(extracted_dates))[:5],
                    "subpageMeetings": subpage_meetings,
                    "materials": all_mats,
                }
                stats["resolved_councils"] += 1

    stats["status"] = last_status
    return {"stats": stats, "results_by_council": results_by_council}
