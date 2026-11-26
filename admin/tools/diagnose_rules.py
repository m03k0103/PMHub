#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Deterministic Scraping Rule Diagnostics Tool (admin/tools/diagnose_rules.py)
====================================================================================
Drop 153 (フェーズ3):
SQLite マスターDB (admin/pmhub.db) 上の partial / failed アクティブ会議体を走査し、
失敗・部分成功要因の分類および最適テンプレート診断を決定論的に行う。
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

TOOLS_DIR = Path(__file__).resolve().parent
ADMIN_DIR = TOOLS_DIR.parent
ROOT_DIR = ADMIN_DIR.parent
for p in (str(ADMIN_DIR), str(ROOT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULT_DB_PATH = ADMIN_DIR / "pmhub.db"

try:
    from utils import setup_win32_utf8
    from discover_councils import infer_scraping_rule_for_council
    from crawler import is_warp_archive_url
except ImportError:
    from admin.utils import setup_win32_utf8
    from admin.discover_councils import infer_scraping_rule_for_council
    from admin.crawler import is_warp_archive_url


def classify_council_issue(
    council_row: Dict[str, Any],
    status_row: Dict[str, Any],
    rule_dict: Optional[Dict[str, Any]] = None,
    html: Optional[str] = None,
) -> Dict[str, Any]:
    """
    1会議体の巡回ステータス・公式URL・現行ルールから障害カテゴリと推奨テンプレートを診断する。
    """
    rule_dict = rule_dict or {}
    cid = council_row.get("id", "")
    ministry = council_row.get("ministry", "")
    name = council_row.get("name", "")
    official_url = (council_row.get("official_url") or council_row.get("officialUrl") or "").strip()

    result = (status_row.get("result") or "").strip().lower()
    failure_reason = (status_row.get("failure_reason") or status_row.get("failureReason") or "").strip()
    result_reason = (status_row.get("result_reason") or status_row.get("resultReason") or "").strip()
    reason_text = failure_reason or result_reason

    current_template = (rule_dict.get("template") or "").strip()
    inferred = infer_scraping_rule_for_council(official_url, html=html)
    recommended_template = inferred.get("template", "tpl-ministry-hybrid-kaisai")

    category = "other_error"
    recommendation = "個別ページのHTML構造を確認してください"

    if is_warp_archive_url(official_url):
        category = "warp_archive"
        recommendation = "国立国会図書館WARP凍結アーカイブのためDrop 150により通常巡回から除外済み"
    elif "WAF Blocked Skip" in reason_text or "WAF 202" in reason_text or "WAF Challenge" in reason_text:
        category = "waf_legacy_skip"
        recommendation = "Drop 150 ホスト単位WAF分離後の次回Weekly/Monthly巡回で自動解消予定"
    elif (
        recommended_template
        and recommended_template != current_template
        and (recommended_template != "tpl-ministry-hybrid-kaisai" or not current_template)
    ):
        category = "template_mismatch"
        recommendation = f"テンプレートを '{current_template or '(none)'}' から '{recommended_template}' へ更新推奨"
    elif result == "partial" and ("資料が0件" in reason_text or "資料0件" in reason_text):
        category = "zero_material_partial"
        recommendation = "サブページ/pdf_selector再調整またはバッチLLM構造補完対象"
    elif result == "partial" and "開催日未取得" in reason_text:
        category = "date_missing_partial"
        recommendation = "date_regex調整またはバッチLLM構造補完対象"
    elif result == "failed" and "検出できませんでした" in reason_text:
        category = "zero_extraction_failed"
        recommendation = "ルール未適合ページのためバッチLLM構造補完(--llm)または個別ルール整備が必要"

    return {
        "council_id": cid,
        "ministry": ministry,
        "name": name,
        "official_url": official_url,
        "result": result,
        "reason": reason_text,
        "category": category,
        "current_template": current_template,
        "recommended_template": recommended_template,
        "rule_manual_lock": bool(rule_dict.get("manualLock")),
        "recommendation": recommendation,
    }


def diagnose_councils(
    db_path: Path = DEFAULT_DB_PATH,
    ministry: Optional[str] = None,
    status_filter: str = "all",
    limit: int = 50,
    fetch_live: bool = False,
) -> Dict[str, Any]:
    """
    SQLite マスターDB内の partial / failed アクティブ会議体を一括診断する。
    """
    db_p = Path(db_path)
    if not db_p.exists():
        raise FileNotFoundError(f"Database not found: {db_p}")

    target_results = ("partial", "failed") if status_filter == "all" else (status_filter,)
    placeholders = ",".join("?" for _ in target_results)

    sql = f"""
        SELECT c.id, c.ministry, c.name, c.official_url,
               cs.result, cs.result_reason, cs.failure_reason, cs.extraction_method,
               sr.rule_json
        FROM councils c
        JOIN crawl_statuses cs ON c.id = cs.council_id
        LEFT JOIN scraping_rules sr ON c.id = sr.council_id
        WHERE c.is_closed = 0
          AND cs.result IN ({placeholders})
    """
    params: List[Any] = list(target_results)
    if ministry:
        sql += " AND UPPER(c.ministry) = ?"
        params.append(ministry.strip().upper())
    sql += " ORDER BY CASE cs.result WHEN 'failed' THEN 0 ELSE 1 END, c.ministry, c.id"

    conn = sqlite3.connect(str(db_p))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    fetcher = None
    if fetch_live:
        try:
            from crawler import fetch_url
        except ImportError:
            from admin.crawler import fetch_url
        fetcher = fetch_url

    all_items: List[Dict[str, Any]] = []
    counts = Counter()

    for idx, r in enumerate(rows):
        rule_dict: Dict[str, Any] = {}
        if r["rule_json"]:
            try:
                rule_dict = json.loads(r["rule_json"])
            except Exception:
                rule_dict = {}

        html = None
        if fetcher is not None and idx < limit:
            html = fetcher(r["official_url"], timeout=10, ministry=r["ministry"])

        diag = classify_council_issue(dict(r), dict(r), rule_dict, html=html)
        counts[diag["category"]] += 1
        all_items.append(diag)

    return {
        "total_issues": len(all_items),
        "counts_by_category": dict(counts),
        "items": all_items[: max(1, int(limit))],
        "all_items": all_items,
    }


def apply_recommended_templates(
    db_path: Path = DEFAULT_DB_PATH,
    items: Optional[List[Dict[str, Any]]] = None,
    force_locked: bool = False,
    export_after: bool = True,
) -> int:
    """
    template_mismatch と診断された会議体の scraping_rules.template を更新する。
    """
    if not items:
        return 0
    targets = [
        it for it in items
        if it.get("category") == "template_mismatch"
        and it.get("recommended_template")
        and (force_locked or not it.get("rule_manual_lock"))
    ]
    if not targets:
        return 0

    conn = sqlite3.connect(str(db_path))
    updated = 0
    try:
        with conn:
            for it in targets:
                cid = it["council_id"]
                row = conn.execute("SELECT rule_json FROM scraping_rules WHERE council_id = ?", (cid,)).fetchone()
                rule_obj: Dict[str, Any] = {}
                if row and row[0]:
                    try:
                        rule_obj = json.loads(row[0])
                    except Exception:
                        rule_obj = {}
                rule_obj["template"] = it["recommended_template"]
                conn.execute(
                    """
                    INSERT INTO scraping_rules (council_id, rule_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(council_id) DO UPDATE SET
                        rule_json = excluded.rule_json,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (cid, json.dumps(rule_obj, ensure_ascii=False)),
                )
                updated += 1
    finally:
        conn.close()

    if updated > 0 and export_after:
        try:
            from db.export_data import export_data
        except ImportError:
            from admin.db.export_data import export_data
        export_data()

    return updated


def main():
    setup_win32_utf8()
    parser = argparse.ArgumentParser(description="PMHub スクレイピングルール自動診断ツール [Drop 153]")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite マスターDBパス")
    parser.add_argument("--ministry", default=None, help="絞り込み省庁コード（例: METI, MHLW）")
    parser.add_argument("--status", choices=["all", "partial", "failed"], default="all", help="対象ステータス")
    parser.add_argument("--limit", type=int, default=50, help="一覧表示件数上限")
    parser.add_argument("--fetch", action="store_true", help="実HTMLを取得してDOMベース診断を行う")
    parser.add_argument("--apply", action="store_true", help="template_mismatch の推奨テンプレートをDBへ自動適用")
    parser.add_argument("--force-locked", action="store_true", help="--apply 時に manualLock ルールも更新対象にする")
    parser.add_argument("--format", choices=["table", "json"], default="table", help="出力形式")
    args = parser.parse_args()

    res = diagnose_councils(
        db_path=Path(args.db),
        ministry=args.ministry,
        status_filter=args.status,
        limit=args.limit,
        fetch_live=args.fetch,
    )

    applied_count = 0
    if args.apply:
        applied_count = apply_recommended_templates(
            db_path=Path(args.db),
            items=res["all_items"],
            force_locked=args.force_locked,
            export_after=True,
        )

    if args.format == "json":
        payload = {
            "total_issues": res["total_issues"],
            "counts_by_category": res["counts_by_category"],
            "applied_templates": applied_count,
            "items": res["items"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("=" * 90)
    print(" 🔧 PMHub スクレイピングルール自己診断レポート (Drop 153)")
    print("=" * 90)
    print(f"  ・診断対象合計 (partial/failed): {res['total_issues']} 件")
    print(f"  ・カテゴリ内訳:")
    for cat, cnt in sorted(res["counts_by_category"].items(), key=lambda x: -x[1]):
        print(f"      - {cat}: {cnt} 件")
    if args.apply:
        print(f"  ・テンプレート自動適用数: {applied_count} 件")
    print("-" * 90)
    for i, it in enumerate(res["items"], start=1):
        tpl_info = f"{it['current_template'] or '(none)'} -> {it['recommended_template']}"
        print(f"{i:3d}. [{it['ministry']}] {it['council_id']} | {it['result'].upper()} | {it['category']} | {tpl_info}")
        print(f"     {it['name']} ({it['official_url']})")
        if it["reason"]:
            print(f"     理由: {it['reason']}")
    print("=" * 90)


if __name__ == "__main__":
    main()
