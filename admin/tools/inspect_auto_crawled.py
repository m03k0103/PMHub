#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Auto-Crawled Data Inspector & AI Correction Helper (inspect_auto_crawled.py)
==================================================================================
Allows AI agents and administrators to inspect meetings, materials, and councils
that were automatically added or updated by the crawler (GitHub Actions scheduled
crawl or local crawl), identify candidates requiring AI correction, and mark
verified records with `manualLock = true`.

Usage Examples:
  # List auto-crawled meetings in the last 7 days (unverified / manual_lock=0 only)
  python admin/tools/inspect_auto_crawled.py --days 7

  # Focus on meetings held within the last 60 days that were auto-crawled in the last 7 days
  python admin/tools/inspect_auto_crawled.py --days 7 --meeting-days 60 --format detail

  # List only items with potential anomalies needing AI correction (e.g. missing round, 0 materials)
  python admin/tools/inspect_auto_crawled.py --days 7 --anomaly-only --format detail

  # Output JSON for AI batch inspection
  python admin/tools/inspect_auto_crawled.py --days 7 --limit 30 --format json

  # Mark specific meeting/council IDs as verified (sets manual_lock=1 and syncs JSONs)
  python admin/tools/inspect_auto_crawled.py --mark-verified cas-zensedai_shakaihosho_kochiku-20261105-013
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows CP932
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "admin" / "pmhub.db"

GENERIC_TITLE_PATTERNS = [
    r"^(会議|配付|配布)?資料(一覧|詳細)?$",
    r"^議事(次第|録|要旨)(一覧|詳細)?$",
    r"^(トップ|ホーム|目次|インデックス|index|詳細|一覧)$",
    r"^開催(について|案内|結果|概要)$",
]


def evaluate_meeting_anomalies(
    meeting: Dict[str, Any],
    council_name: str = "",
    council_url: str = "",
    today_str: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Evaluate an auto-crawled meeting record and return a list of potential
    anomalies that may benefit from AI review/correction.
    """
    if not today_str:
        today_str = datetime.now().strftime("%Y/%m/%d")

    anomalies: List[Dict[str, str]] = []
    m_id = str(meeting.get("id") or "")
    m_name = str(meeting.get("name") or "").strip()
    m_date = str(meeting.get("date") or "").strip().replace("-", "/")
    m_round = meeting.get("round")
    m_url = str(meeting.get("officialUrl") or "").strip()
    materials = meeting.get("materials") or []
    is_future = bool(m_date and m_date != "2099/01/01" and m_date > today_str)

    # 1. Unconfirmed / dummy date
    if meeting.get("isDateUnconfirmed") or m_date == "2099/01/01" or not m_date:
        anomalies.append({"code": "unconfirmed_date", "label": "日付未確定"})

    # 2. Missing round number (special suffix -s01 etc. or null round)
    if m_round is None or re.search(r"-s\d+$", m_id):
        if not re.search(r"第\s*\d+\s*回", m_name):
            anomalies.append({"code": "missing_round", "label": "回次未特定"})

    # 3. Zero materials (only flag if the meeting date is today or in the past)
    if len(materials) == 0 and not is_future:
        anomalies.append({"code": "no_materials", "label": "配付資料0件"})

    # 4. Title identical to council name without round or date differentiation
    if council_name and m_name == council_name.strip():
        anomalies.append({"code": "identical_to_council", "label": "親会議体名と同一タイトル"})

    # 5. Generic title pattern
    for pat in GENERIC_TITLE_PATTERNS:
        if re.search(pat, m_name, re.IGNORECASE):
            anomalies.append({"code": "generic_title", "label": "汎用タイトル疑い"})
            break

    # 6. Official URL identical to parent council URL (when materials are 0 and not future)
    if council_url and m_url and m_url.rstrip("/") == council_url.strip().rstrip("/") and len(materials) == 0 and not is_future:
        anomalies.append({"code": "same_as_council_url", "label": "個別ページ未特定(親URL同一)"})

    return anomalies


def fetch_auto_crawled_data(
    db_path: Path = DEFAULT_DB_PATH,
    days: int = 7,
    all_dates: bool = False,
    meeting_days: Optional[int] = None,
    unverified_only: bool = True,
    anomaly_only: bool = False,
    ministry: Optional[str] = None,
    council_id: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Query SQLite master DB for auto-crawled meetings and councils.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    today_str = datetime.now().strftime("%Y/%m/%d")
    cutoff_str = ""
    if not all_dates and days > 0:
        cutoff_dt = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_dt.strftime("%Y/%m/%d")

    meeting_date_cutoff = ""
    if meeting_days is not None and meeting_days > 0:
        m_cutoff_dt = datetime.now() - timedelta(days=meeting_days)
        meeting_date_cutoff = m_cutoff_dt.strftime("%Y/%m/%d")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        # Build query for meetings
        where_clauses = [
            "(m.is_newly_discovered = 1 OR length(COALESCE(m.discovered_at, '')) > 0 OR length(COALESCE(m.last_updated_from_crawl, '')) > 0)"
        ]
        params: List[Any] = []

        if cutoff_str:
            where_clauses.append(
                "(m.is_newly_discovered = 1 "
                "OR substr(REPLACE(COALESCE(m.discovered_at, ''), '-', '/'), 1, 10) >= ? "
                "OR substr(REPLACE(COALESCE(m.last_updated_from_crawl, ''), '-', '/'), 1, 10) >= ?)"
            )
            params.extend([cutoff_str, cutoff_str])

        if meeting_date_cutoff:
            where_clauses.append("REPLACE(COALESCE(m.date, ''), '-', '/') >= ?")
            params.append(meeting_date_cutoff)

        if unverified_only:
            where_clauses.append("m.manual_lock = 0")

        if ministry:
            mins = [x.strip().upper() for x in ministry.split(",") if x.strip()]
            if mins:
                placeholders = ",".join("?" for _ in mins)
                where_clauses.append(f"UPPER(c.ministry) IN ({placeholders})")
                params.extend(mins)

        if council_id:
            where_clauses.append("m.council_id = ?")
            params.append(council_id.strip())

        where_sql = " AND ".join(where_clauses)
        query = f"""
            SELECT
                m.id, m.council_id, m.name, m.date, m.round, m.official_url,
                m.is_date_unconfirmed, m.is_newly_discovered,
                m.discovered_at, m.last_updated_from_crawl, m.manual_lock,
                c.name AS council_name, c.ministry, c.official_url AS council_url
            FROM meetings m
            JOIN councils c ON m.council_id = c.id
            WHERE {where_sql}
            ORDER BY
                m.date DESC,
                COALESCE(NULLIF(m.last_updated_from_crawl, ''), NULLIF(m.discovered_at, ''), m.date) DESC,
                m.id DESC
        """
        rows = cur.execute(query, params).fetchall()

        # Fetch materials for matching meetings in batch
        m_ids = [r["id"] for r in rows]
        mats_by_mid: Dict[str, List[Dict[str, Any]]] = {}
        if m_ids:
            chunk_size = 500
            for i in range(0, len(m_ids), chunk_size):
                chunk = m_ids[i:i + chunk_size]
                ph = ",".join("?" for _ in chunk)
                mat_rows = cur.execute(
                    f"SELECT meeting_id, name, url, type, manual_lock FROM materials WHERE meeting_id IN ({ph}) ORDER BY id ASC",
                    chunk
                ).fetchall()
                for mr in mat_rows:
                    mats_by_mid.setdefault(mr["meeting_id"], []).append({
                        "name": mr["name"],
                        "url": mr["url"],
                        "type": mr["type"],
                        "manualLock": bool(mr["manual_lock"])
                    })

        meetings_result: List[Dict[str, Any]] = []
        total_matching = 0
        anomaly_count = 0

        for r in rows:
            mid = r["id"]
            mats = mats_by_mid.get(mid, [])
            m_obj: Dict[str, Any] = {
                "id": mid,
                "councilId": r["council_id"],
                "councilName": r["council_name"],
                "ministry": r["ministry"],
                "name": r["name"],
                "date": r["date"],
                "round": r["round"],
                "officialUrl": r["official_url"],
                "councilUrl": r["council_url"],
                "isDateUnconfirmed": bool(r["is_date_unconfirmed"]),
                "isNewlyDiscovered": bool(r["is_newly_discovered"]),
                "discoveredAt": r["discovered_at"] or "",
                "lastUpdatedFromCrawl": r["last_updated_from_crawl"] or "",
                "manualLock": bool(r["manual_lock"]),
                "materialsCount": len(mats),
                "materials": mats,
            }
            anomalies = evaluate_meeting_anomalies(
                m_obj,
                council_name=r["council_name"] or "",
                council_url=r["council_url"] or "",
                today_str=today_str
            )
            m_obj["anomalies"] = anomalies
            if anomalies:
                anomaly_count += 1

            if anomaly_only and not anomalies:
                continue

            total_matching += 1
            if limit <= 0 or len(meetings_result) < limit:
                meetings_result.append(m_obj)

        # Also query newly discovered councils
        c_where = [
            "(is_newly_discovered = 1 OR length(COALESCE(discovered_at, '')) > 0)"
        ]
        c_params: List[Any] = []
        if cutoff_str:
            c_where.append(
                "(is_newly_discovered = 1 OR substr(REPLACE(COALESCE(discovered_at, ''), '-', '/'), 1, 10) >= ?)"
            )
            c_params.append(cutoff_str)
        if unverified_only:
            c_where.append("manual_lock = 0")
        if ministry:
            mins = [x.strip().upper() for x in ministry.split(",") if x.strip()]
            if mins:
                ph = ",".join("?" for _ in mins)
                c_where.append(f"UPPER(ministry) IN ({ph})")
                c_params.extend(mins)
        if council_id:
            c_where.append("id = ?")
            c_params.append(council_id.strip())

        c_rows = cur.execute(
            f"""
            SELECT id, ministry, category, name, official_url, is_newly_discovered,
                   discovered_at, discovery_source, manual_lock
            FROM councils
            WHERE {' AND '.join(c_where)}
            ORDER BY COALESCE(NULLIF(discovered_at, ''), id) DESC
            """,
            c_params
        ).fetchall()

        councils_result = [
            {
                "id": cr["id"],
                "ministry": cr["ministry"],
                "category": cr["category"],
                "name": cr["name"],
                "officialUrl": cr["official_url"],
                "isNewlyDiscovered": bool(cr["is_newly_discovered"]),
                "discoveredAt": cr["discovered_at"] or "",
                "discoverySource": cr["discovery_source"] or "",
                "manualLock": bool(cr["manual_lock"]),
            }
            for cr in c_rows
        ]

        return {
            "cutoffDate": cutoff_str or "ALL",
            "meetingDateCutoff": meeting_date_cutoff or "ALL",
            "unverifiedOnly": unverified_only,
            "anomalyOnly": anomaly_only,
            "totalMeetingsMatching": total_matching,
            "totalMeetingsWithAnomalies": anomaly_count,
            "returnedMeetingsCount": len(meetings_result),
            "totalCouncilsMatching": len(councils_result),
            "meetings": meetings_result,
            "councils": councils_result[:limit] if limit > 0 else councils_result,
        }
    finally:
        conn.close()


def mark_records_verified(
    target_ids: List[str],
    db_path: Path = DEFAULT_DB_PATH,
    export: bool = True
) -> Dict[str, int]:
    """
    Mark specified meeting IDs or council IDs as verified by setting
    manual_lock = 1 and is_newly_discovered = 0, then exporting to JSONs.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    updated_meetings = 0
    updated_councils = 0
    try:
        with conn:
            cur = conn.cursor()
            for tid in target_ids:
                tid = tid.strip()
                if not tid:
                    continue
                # Try meeting first (3 hyphens)
                cur.execute(
                    "UPDATE meetings SET manual_lock = 1, is_newly_discovered = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (tid,)
                )
                if cur.rowcount > 0:
                    updated_meetings += cur.rowcount
                    cur.execute(
                        "UPDATE materials SET manual_lock = 1 WHERE meeting_id = ?",
                        (tid,)
                    )
                    continue

                # Try council
                cur.execute(
                    "UPDATE councils SET manual_lock = 1, is_newly_discovered = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (tid,)
                )
                if cur.rowcount > 0:
                    updated_councils += cur.rowcount
    finally:
        conn.close()

    if export and (updated_meetings > 0 or updated_councils > 0):
        sys.path.insert(0, str(BASE_DIR))
        from admin.db.export_data import export_data
        export_data(db_path=db_path)

    return {
        "updated_meetings": updated_meetings,
        "updated_councils": updated_councils
    }


def print_report(result: Dict[str, Any], fmt: str = "table") -> None:
    """Format and print inspection result."""
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 95)
    print(" 🤖 PMHub 自動クロール追加・更新データ確認レポート (AI補正インスペクタ)")
    print("=" * 95)
    print(f"  ・クロール検知期間: {result['cutoffDate']} 以降"
          + (f" (開催日フィルタ: {result['meetingDateCutoff']} 以降)" if result.get("meetingDateCutoff") != "ALL" else ""))
    print(f"  ・抽出フィルタ    : {'未補正のみ (manualLock=OFF)' if result['unverifiedOnly'] else '全件 (ロック済含む)'}"
          f"{' / 要AI補正候補のみ (--anomaly-only)' if result['anomalyOnly'] else ''}")
    print(f"  ・該当開催回総数  : {result['totalMeetingsMatching']} 件 (表示: {result['returnedMeetingsCount']} 件 / 要補正ヒントあり: {result['totalMeetingsWithAnomalies']} 件)")
    print(f"  ・該当新規会議体数: {result['totalCouncilsMatching']} 件")
    print("-" * 95)

    if result["councils"]:
        print("\n【1. 自動クロール新規検出会議体 (Councils)】")
        for c in result["councils"]:
            lock_str = "🔒保護済" if c["manualLock"] else "⏳未補正"
            print(f"  - [{c['ministry']}] {c['id']} | {c['name']} ({lock_str}, 検知: {c['discoveredAt'] or 'N/A'})")
            print(f"    URL: {c['officialUrl']}")

    print("\n【2. 自動クロール追加・更新開催回 (Meetings)】")
    meetings = result["meetings"]
    if not meetings:
        print("  該当する開催回はありません。")
        return

    for idx, m in enumerate(meetings, 1):
        lock_str = "🔒保護済" if m["manualLock"] else "⏳未補正"
        stamp = m["lastUpdatedFromCrawl"] or m["discoveredAt"] or "日時未記録"
        stamp_type = "資料更新" if m["lastUpdatedFromCrawl"] else "新規検知"
        anom_str = ""
        if m["anomalies"]:
            labels = ", ".join(a["label"] for a in m["anomalies"])
            anom_str = f" ⚠️[{labels}]"

        print(f"{idx:3d}. [{m['ministry']}] {m['id']} ({m['date']}) | 資料:{m['materialsCount']}件 | {stamp_type}:{stamp} | {lock_str}{anom_str}")
        print(f"     会議体: {m['councilName']} ({m['councilId']})")
        print(f"     開催回: {m['name']}  [URL: {m['officialUrl']}]")

        if fmt == "detail" and m["materials"]:
            for mat_idx, mat in enumerate(m["materials"][:10], 1):
                print(f"       📄 ({mat_idx}) {mat['name']} -> {mat['url']}")
            if len(m["materials"]) > 10:
                print(f"       ... 他 {len(m['materials']) - 10} 件の配付資料")
    print("=" * 95)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect auto-crawled meetings and councils for AI review and correction."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite master DB")
    parser.add_argument("--days", type=int, default=7, help="Lookback days for discovered_at / last_updated_from_crawl (default: 7)")
    parser.add_argument("--all-dates", action="store_true", help="Ignore crawl date cutoff and inspect all auto-crawled records")
    parser.add_argument("--meeting-days", type=int, default=None, help="Filter by meeting held date within the last N days (e.g. 60)")
    parser.add_argument("--include-locked", action="store_true", help="Include records that already have manual_lock = 1")
    parser.add_argument("--anomaly-only", action="store_true", help="Only show meetings with potential anomalies needing AI correction")
    parser.add_argument("--ministry", type=str, default=None, help="Filter by ministry code(s), comma-separated (e.g. METI,CAO)")
    parser.add_argument("--council-id", type=str, default=None, help="Filter by specific councilId")
    parser.add_argument("--limit", type=int, default=50, help="Maximum number of meetings to output (0 for unlimited, default: 50)")
    parser.add_argument("--format", choices=["table", "detail", "json"], default="table", help="Output format (table, detail, json)")
    parser.add_argument("--mark-verified", nargs="+", metavar="ID", help="Mark specified meeting/council IDs as verified (manual_lock=1) and export JSONs")
    parser.add_argument("--no-export", action="store_true", help="Skip automatic JSON export when using --mark-verified")

    args = parser.parse_args()

    if args.mark_verified:
        res = mark_records_verified(
            target_ids=args.mark_verified,
            db_path=args.db,
            export=not args.no_export
        )
        print(f"✅ 確認済ロック (manual_lock=1) を付与しました: 開催回 {res['updated_meetings']} 件 / 会議体 {res['updated_councils']} 件")
        return

    result = fetch_auto_crawled_data(
        db_path=args.db,
        days=args.days,
        all_dates=args.all_dates,
        meeting_days=args.meeting_days,
        unverified_only=not args.include_locked,
        anomaly_only=args.anomaly_only,
        ministry=args.ministry,
        council_id=args.council_id,
        limit=args.limit
    )
    print_report(result, fmt=args.format)


if __name__ == "__main__":
    main()
