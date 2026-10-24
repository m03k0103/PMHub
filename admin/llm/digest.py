#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deterministic Ministry News Digest Builder (admin/llm/digest.py)
================================================================
Aggregates raw ministry news items across ministries, applies deterministic
pre-filters (date cutoff, URL deduplication, existing council session exclusion,
rejected council exclusion, and strong non-council noise filters), assigns
sequential short IDs (N001, N002, ...), attaches top-3 similar existing councils
per ministry, and writes a single canonical JSON digest file with SHA-256 hash.
"""

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from utils import normalize_text, normalize_url_for_matching
except ImportError:
    from admin.utils import normalize_text, normalize_url_for_matching

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DIGEST_DIR = BASE_DIR / "discovery"

# Obvious non-council press release / announcement patterns that never represent a policy council
STRONG_NON_COUNCIL_PATTERNS = [
    re.compile(r"(?:大臣|副大臣|政務官|長官|総理).*?(?:記者会見|会見|動静|出張|談話|挨拶|コメント)"),
    re.compile(r"(?:人事異動|幹部名簿|採用情報|職員採用|公募結果|入札公告|一般競争入札|調達情報|落札者)"),
    re.compile(r"(?:パブリックコメント|意見公募手続).*?(?:開始|結果|募集)"),
    re.compile(r"(?:統計|調査結果|月例経済報告|白書|年次報告)(?:の公表|について)?$"),
    re.compile(r"(?:行政処分|業務改善命令|課徴金納付命令|指名停止)"),
    re.compile(r"(?:表敬訪問|表敬|会談|電話会談|首脳会談|外相会談)を(?:実施|行い)"),
]


def _normalize_iso_date(date_str: str) -> str:
    """Normalize YYYY/MM/DD or YYYY-MM-DD to YYYY-MM-DD for lexicographical comparison."""
    if not date_str:
        return ""
    s = str(date_str).strip().replace("/", "-").replace(".", "-")
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _is_obvious_non_council_news(title: str, url: str) -> bool:
    """Return True if the news title/URL is unmistakably not a domestic policy council."""
    if not title or len(title.strip()) < 4:
        return True
    u_low = (url or "").lower()
    if any(u_low.endswith(ext) for ext in (".zip", ".xlsx", ".xls", ".csv", ".doc", ".docx", ".ppt", ".pptx")):
        return True
    for pat in STRONG_NON_COUNCIL_PATTERNS:
        if pat.search(title):
            return True
    return False


def _char_bigrams(text: str) -> Set[str]:
    """Compute character bigrams for lightweight deterministic similarity scoring."""
    s = re.sub(r"[\s　・、。()（）「」『』【】第回0-9０-９]+", "", text or "")
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _find_top_similar_councils(
    title: str,
    ministry_councils: List[Dict[str, Any]],
    top_k: int = 3
) -> List[Dict[str, str]]:
    """
    Find up to top_k existing councils in the same ministry with highest character bigram overlap.
    Avoids sending all 1,546 councils in the LLM prompt while enabling duplicate/alias detection.
    """
    if not ministry_councils:
        return []
    t_bg = _char_bigrams(title)
    if not t_bg:
        return []

    scored = []
    for c in ministry_councils:
        cid = c.get("id", "")
        cname = c.get("name", "")
        if not cid or not cname:
            continue
        c_bg = _char_bigrams(cname)
        if not c_bg:
            continue
        overlap = len(t_bg & c_bg)
        if overlap > 0:
            score = overlap / max(len(c_bg), 1)
            scored.append((score, overlap, cid, cname))

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [{"id": cid, "name": cname} for _, _, cid, cname in scored[:top_k]]


def build_discovery_digest(
    raw_items: List[Dict[str, Any]],
    existing_councils: List[Dict[str, Any]],
    rejected_ids: Optional[Set[str]] = None,
    rejected_names: Optional[Set[str]] = None,
    rejected_urls: Optional[Set[str]] = None,
    rejected_clean_keys: Optional[Set[str]] = None,
    cutoff_date: Optional[str] = None,
    output_path: Optional[Path] = None,
    save_file: bool = True
) -> Dict[str, Any]:
    """
    Build a deterministic 1-file discovery digest from raw ministry news items.

    Returns a dictionary containing:
      - digest_hash: SHA-256 hex digest of canonical candidate items
      - generated_at: timestamp
      - stats: counts of raw, filtered_by_date, filtered_by_dup, filtered_by_existing,
               filtered_by_rejected, filtered_by_noise, candidate_count
      - items: list of candidate items [{id, ministry, date, title, url, similar_existing}]
      - items_by_id: dict mapping item_id (e.g. 'N001') -> item dict
      - file_path: saved file path string (if save_file=True)
    """
    try:
        from crawler import match_council_from_news_item
    except ImportError:
        from admin.crawler import match_council_from_news_item

    try:
        from discover_councils import get_url_clean_key, clean_council_name
    except ImportError:
        from admin.discover_councils import get_url_clean_key, clean_council_name

    rejected_ids = rejected_ids or set()
    rejected_names = rejected_names or set()
    rejected_urls = rejected_urls or set()
    rejected_clean_keys = rejected_clean_keys or set()

    norm_cutoff = _normalize_iso_date(cutoff_date) if cutoff_date else ""

    councils_by_min: Dict[str, List[Dict[str, Any]]] = {}
    councils_by_url: Dict[str, Dict[str, Any]] = {}
    existing_norm_urls: Set[str] = set()
    existing_clean_names: Set[str] = set()

    for c in existing_councils:
        m_code = (c.get("ministry") or "").upper()
        councils_by_min.setdefault(m_code, []).append(c)
        off_url = (c.get("officialUrl") or "").strip()
        if off_url:
            councils_by_url[off_url.rstrip("/")] = c
            existing_norm_urls.add(normalize_url_for_matching(off_url))
        cname = (c.get("name") or "").strip()
        if cname:
            existing_clean_names.add(cname)
            existing_clean_names.add(clean_council_name(cname))

    norm_rejected_urls = {normalize_url_for_matching(u) for u in rejected_urls if u}

    stats = {
        "raw_count": len(raw_items),
        "filtered_by_date": 0,
        "filtered_by_dup": 0,
        "filtered_by_existing": 0,
        "filtered_by_rejected": 0,
        "filtered_by_noise": 0,
        "candidate_count": 0,
    }

    seen_keys: Set[str] = set()
    pre_candidates: List[Dict[str, Any]] = []

    for raw in raw_items:
        title = normalize_text(raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()
        ministry = (raw.get("ministry") or "").strip().upper()
        item_date = _normalize_iso_date(raw.get("date") or "")

        if not title or not url or not url.startswith("http"):
            stats["filtered_by_noise"] += 1
            continue

        # 1. Date cutoff filter
        if norm_cutoff and item_date and item_date < norm_cutoff:
            stats["filtered_by_date"] += 1
            continue

        # 2. URL & title deduplication
        norm_url = normalize_url_for_matching(url)
        dedup_key = f"{ministry}|{norm_url}|{title}"
        if dedup_key in seen_keys:
            stats["filtered_by_dup"] += 1
            continue
        seen_keys.add(dedup_key)

        # 3. Rejected councils filter
        clean_k = get_url_clean_key(url)
        if (
            norm_url in norm_rejected_urls
            or url.rstrip("/") in rejected_urls
            or (clean_k and clean_k in rejected_clean_keys)
            or title in rejected_names
        ):
            stats["filtered_by_rejected"] += 1
            continue

        # 4. Registered council session announcement filter
        if norm_url in existing_norm_urls:
            stats["filtered_by_existing"] += 1
            continue

        matched_c, _ = match_council_from_news_item(
            {"title": title, "url": url, "ministry": ministry},
            councils_by_url,
            councils_by_min
        )
        if matched_c is not None:
            stats["filtered_by_existing"] += 1
            continue

        # 5. Obvious non-council noise filter
        if _is_obvious_non_council_news(title, url):
            stats["filtered_by_noise"] += 1
            continue

        pre_candidates.append({
            "ministry": ministry,
            "date": item_date,
            "title": title,
            "url": url,
            "norm_url": norm_url,
        })

    # Deterministic sort by (ministry, date, norm_url, title)
    pre_candidates.sort(key=lambda x: (x["ministry"], x["date"], x["norm_url"], x["title"]))

    items: List[Dict[str, Any]] = []
    items_by_id: Dict[str, Dict[str, Any]] = {}

    for idx, cand in enumerate(pre_candidates, start=1):
        item_id = f"N{idx:03d}"
        min_code = cand["ministry"]
        similar = _find_top_similar_councils(
            cand["title"],
            councils_by_min.get(min_code, []),
            top_k=3
        )
        entry = {
            "id": item_id,
            "ministry": min_code,
            "date": cand["date"],
            "title": cand["title"],
            "url": cand["url"],
            "similar_existing": similar,
        }
        items.append(entry)
        items_by_id[item_id] = entry

    stats["candidate_count"] = len(items)

    # Canonical hash calculation (depends purely on sorted deterministic items)
    canonical_payload = [
        {
            "id": it["id"],
            "ministry": it["ministry"],
            "date": it["date"],
            "title": it["title"],
            "url": it["url"],
            "similar_existing": it["similar_existing"],
        }
        for it in items
    ]
    canonical_str = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    digest_doc = {
        "digest_hash": digest_hash,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": stats,
        "items": items,
        "items_by_id": items_by_id,
    }

    saved_path_str = ""
    if save_file:
        if output_path is None:
            DEFAULT_DIGEST_DIR.mkdir(parents=True, exist_ok=True)
            date_tag = datetime.now().strftime("%Y%m%d")
            output_path = DEFAULT_DIGEST_DIR / f"digest_{date_tag}.json"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        file_payload = {
            "digest_hash": digest_hash,
            "generated_at": digest_doc["generated_at"],
            "stats": stats,
            "items": items,
        }
        tmp_path = output_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(file_payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, output_path)
        saved_path_str = str(output_path)

    digest_doc["file_path"] = saved_path_str
    return digest_doc
