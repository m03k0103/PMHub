#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single-Call Discovery LLM Judge (admin/llm/discovery_judge.py)
==============================================================
Sends the deterministic 1-file discovery digest to LLMClient in a single batched
request (or chunked only if exceeding token threshold), validates returned item IDs
against the input digest (preventing any URL hallucination), and enforces strict
post-filtering for immediate publication safety.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .client import LLMClient

VALID_CATEGORIES = {
    "COUNCIL",
    "COMMITTEE",
    "EXPERT_COMMITTEE",
    "SPECIAL_COMMITTEE",
    "ADVISORY",
    "SUBCOMMITTEE",
    "SECTION",
    "WORKING_GROUP",
    "TASKFORCE",
    "PANEL",
    "ROUNDTABLE",
    "STUDY",
    "LIAISON",
    "HQ",
    "OTHER",
}

CATEGORY_ALIAS_MAP = {
    "STUDY_GROUP": "STUDY",
    "HEADQUARTERS": "HQ",
}


def _is_valid_gov_url(url: str) -> bool:
    """Verify that the URL is a valid HTTP(S) URL on a Japanese government (.go.jp) or official domain."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        host = parsed.netloc.lower().split(":")[0]
        return host.endswith(".go.jp") or host.endswith(".cao.go.jp") or host.endswith(".cas.go.jp")
    except Exception:
        return False


def _build_discovery_prompt(items: List[Dict[str, Any]]) -> str:
    """Build compact structured JSON prompt referencing items strictly by item_id."""
    compact_items = [
        {
            "id": it["id"],
            "ministry": it["ministry"],
            "date": it.get("date", ""),
            "title": it["title"],
            "similar_existing": it.get("similar_existing", []),
        }
        for it in items
    ]
    items_json = json.dumps(compact_items, ensure_ascii=False, indent=2)
    return f"""あなたは日本の官公庁の政策会議（審議会・検討会・有識者会議・ワーキンググループ・分科会・部会・対策本部等）を判定する専門アナリストです。
以下の各府省庁の新着情報リスト（JSON配列）を分析し、まだ登録されていない「新規の政策会議体」に関する記事であるかを判定してください。

【厳守ルール】
1. 出力には必ず入力の `id`（例: "N001"）を指定してください。URLは絶対に出力しないでください。
2. `council_name` には、「第1回」「（第3回）」「の開催について」「議事録」「配付資料」等の回次やイベント表現を除いた**親会議体の正式名称のみ**を記載してください。
3. **新規の会議体（または新設された検討会・ワーキンググループ等の初回会合告知）に該当するもののみ**を `decisions` 配列に出力してください。非会議体ノイズや既存会議体と一致するものは出力に含めないでください（出力件数を最小化するため）。
4. 大臣会見・人事・入札・パブコメ単体・統計公表・国際会議・二国間会談・シンポジウム・セミナー等の非会議体ノイズは絶対に対象外（出力不要）としてください。
5. Markdownコードブロックは含めず、以下のJSONスキーマのみを出力してください。新規会議体がない場合は `{{"decisions": []}}` としてください。

{{
  "decisions": [
    {{
      "item_id": "N001",
      "council_name": "親会議体の正式名称",
      "category": "COUNCIL | STUDY | WORKING_GROUP | SUBCOMMITTEE | HQ | PANEL | COMMITTEE",
      "confidence": 0.92,
      "reason": "判定理由（簡潔に）"
    }}
  ]
}}

【入力新着リスト】
{items_json}
"""


def judge_discovery_digest(
    digest_doc: Dict[str, Any],
    llm_client: Optional[LLMClient] = None,
    min_confidence: float = 0.80,
    max_items_per_chunk: int = 350,
) -> Dict[str, Any]:
    """
    Judge candidate news items in digest_doc using LLMClient.
    Enforces strict ID-only lookup and 3-stage post-validation.

    Returns dict:
      - status: 'ok' | 'cached' | 'empty' | 'budget_exceeded' | 'quota_blocked' | 'unavailable' | 'error'
      - candidates: list of validated new council candidate dicts
      - stats: {total_items, llm_calls, cache_hits, raw_decisions, accepted_count,
                rejected_low_confidence, rejected_existing_match, rejected_noise,
                ignored_unknown_id}
    """
    try:
        from discover_councils import clean_council_name, is_non_council_noise
    except ImportError:
        from admin.discover_councils import clean_council_name, is_non_council_noise

    items = digest_doc.get("items", [])
    items_by_id = digest_doc.get("items_by_id") or {it["id"]: it for it in items if "id" in it}
    base_hash = digest_doc.get("digest_hash", "")

    stats = {
        "total_items": len(items),
        "llm_calls": 0,
        "cache_hits": 0,
        "raw_decisions": 0,
        "accepted_count": 0,
        "rejected_low_confidence": 0,
        "rejected_existing_match": 0,
        "rejected_noise": 0,
        "ignored_unknown_id": 0,
    }

    if not items:
        return {"status": "empty", "candidates": [], "stats": stats}

    if llm_client is None:
        llm_client = LLMClient(schedule_tier="daily")

    # Split into chunks only if exceeding max_items_per_chunk (safety for >150k tokens)
    chunks = [items[i:i + max_items_per_chunk] for i in range(0, len(items), max_items_per_chunk)]
    all_decisions: List[Dict[str, Any]] = []
    last_status = "ok"

    for c_idx, chunk in enumerate(chunks):
        chunk_hash = (
            base_hash
            if len(chunks) == 1
            else hashlib.sha256(f"{base_hash}:chunk{c_idx}".encode("utf-8")).hexdigest()
        )
        prompt = _build_discovery_prompt(chunk)
        res = llm_client.generate_structured_json(
            prompt=prompt,
            digest_hash=chunk_hash,
            purpose="discovery_digest",
            context_meta={"items": chunk, "chunk_index": c_idx},
        )
        last_status = res.get("status", "error")
        if last_status in ("budget_exceeded", "quota_blocked", "unavailable", "error"):
            break
        data = res.get("data", {})
        decisions = data.get("decisions", [])
        if isinstance(decisions, list):
            all_decisions.extend(decisions)

    stats["llm_calls"] = llm_client.calls_made
    stats["cache_hits"] = llm_client.cache_hits
    stats["raw_decisions"] = len(all_decisions)

    accepted_candidates: List[Dict[str, Any]] = []

    for dec in all_decisions:
        if not isinstance(dec, dict):
            continue
        item_id = str(dec.get("item_id") or "").strip()
        if not item_id or item_id not in items_by_id:
            # Anti-hallucination guard: never accept any item not in the input digest
            stats["ignored_unknown_id"] += 1
            continue

        if "is_new_council" in dec and not dec.get("is_new_council"):
            continue

        if dec.get("matches_existing_id"):
            stats["rejected_existing_match"] += 1
            continue

        try:
            conf = float(dec.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0

        if conf < min_confidence:
            stats["rejected_low_confidence"] += 1
            continue

        orig_item = items_by_id[item_id]
        orig_url = orig_item["url"]
        orig_title = orig_item["title"]
        min_code = orig_item["ministry"]

        raw_name = str(dec.get("council_name") or "").strip()
        cleaned_name = clean_council_name(raw_name)
        if not cleaned_name or len(cleaned_name) < 4:
            stats["rejected_noise"] += 1
            continue

        # Deterministic noise & gov domain verification
        if is_non_council_noise(cleaned_name, orig_title, orig_url) or not _is_valid_gov_url(orig_url):
            stats["rejected_noise"] += 1
            continue

        cat = str(dec.get("category") or "COUNCIL").strip().upper()
        cat = CATEGORY_ALIAS_MAP.get(cat, cat)
        if cat not in VALID_CATEGORIES:
            cat = "COUNCIL"

        accepted_candidates.append({
            "item_id": item_id,
            "ministry": min_code,
            "name": cleaned_name,
            "raw_title": orig_title,
            "url": orig_url,
            "date": orig_item.get("date", ""),
            "category": cat,
            "confidence": conf,
            "reason": str(dec.get("reason") or "").strip(),
            "discoverySource": "llm",
        })

    stats["accepted_count"] = len(accepted_candidates)
    return {
        "status": last_status,
        "candidates": accepted_candidates,
        "stats": stats,
    }
