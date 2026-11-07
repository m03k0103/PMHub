#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Database Synchronizer (sync_from_json.py)
==============================================
Synchronizes local SQLite master DB (admin/pmhub.db) with updated JSON files:
- docs/data.json
- docs/data_archive.json
- admin/admin_data.json

Key Protections (PMM & ManualLock Integrity):
1. Never resets or overwrites downloaded PMM assets:
   If materials.download_status == 'downloaded', local_path, file_size,
   downloaded_at, and download_status are preserved unconditionally.
2. Never overwrites manualLock = 1 records (councils, meetings, materials).
3. Safely inserts new councils, meetings, and materials discovered by CI crawls.
4. Synchronizes auto-crawl discovery metadata (councilCrawlMeta, meetingCrawlMeta,
   isNewlyDiscovered, discoveredAt, lastUpdatedFromCrawl, discoverySource) so that
   newly crawled items from remote CI can be inspected and corrected by AI/humans.
5. Updates non-destructive metadata (crawlerConfig, scrapingRules, crawlStatuses).
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure UTF-8 output on Windows CP932
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "admin" / "pmhub.db"
DEFAULT_PUBLIC_JSON = BASE_DIR / "docs" / "data.json"
DEFAULT_ARCHIVE_JSON = BASE_DIR / "docs" / "data_archive.json"
DEFAULT_ADMIN_JSON = BASE_DIR / "admin" / "admin_data.json"


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file safely."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ [WARNING] Failed to load {path}: {e}", file=sys.stderr)
        return None


def sync_database(
    db_path: Path = DEFAULT_DB_PATH,
    public_json_path: Path = DEFAULT_PUBLIC_JSON,
    archive_json_path: Path = DEFAULT_ARCHIVE_JSON,
    admin_json_path: Path = DEFAULT_ADMIN_JSON,
    dry_run: bool = False,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Sync SQLite database with JSON data while protecting PMM files and manualLock records.
    Returns sync summary statistics.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}. Please run seed_db.py first.")

    public_data = load_json(public_json_path)
    if not public_data:
        raise ValueError(f"Public data JSON not found or invalid: {public_json_path}")

    archive_data = load_json(archive_json_path) or {}
    admin_data = load_json(admin_json_path) or {}

    stats = {
        "councils_inserted": 0,
        "councils_updated": 0,
        "councils_skipped_lock": 0,
        "meetings_inserted": 0,
        "meetings_updated": 0,
        "meetings_skipped_lock": 0,
        "materials_inserted": 0,
        "materials_updated": 0,
        "materials_pmm_preserved": 0,
        "materials_skipped_lock": 0,
        "rules_synced": 0,
        "statuses_synced": 0,
        "configs_synced": 0,
    }

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row

    try:
        if not dry_run:
            conn.execute("BEGIN IMMEDIATE;")

        cur = conn.cursor()

        # -------------------------------------------------------------
        # 0. Sync lastCrawlTime metadata & Prepare Crawl Meta maps
        # -------------------------------------------------------------
        last_crawl_time = public_data.get("lastCrawlTime") or admin_data.get("lastCrawlTime", "")
        if last_crawl_time and not dry_run:
            cur.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('lastCrawlTime', ?);",
                (last_crawl_time,)
            )

        council_crawl_meta = admin_data.get("councilCrawlMeta", {}) if admin_data else {}
        meeting_crawl_meta = admin_data.get("meetingCrawlMeta", {}) if admin_data else {}
        manual_locks = admin_data.get("manualLocks", {}) if admin_data else {}
        locked_councils = set(manual_locks.get("councils", [])) if isinstance(manual_locks, dict) else set()
        locked_meetings = set(manual_locks.get("meetings", [])) if isinstance(manual_locks, dict) else set()
        locked_materials = set(manual_locks.get("materials", [])) if isinstance(manual_locks, dict) else set()

        # -------------------------------------------------------------
        # 1. Sync Councils
        # -------------------------------------------------------------
        councils = public_data.get("councils", [])
        for c in councils:
            cid = c.get("id") or c.get("councilId")
            if not cid:
                continue

            c_meta = council_crawl_meta.get(cid, {}) if isinstance(council_crawl_meta, dict) else {}
            c_discovered_at = c_meta.get("discoveredAt") or c.get("discoveredAt") or ""
            c_discovery_source = c_meta.get("discoverySource") or c.get("discoverySource") or ""
            c_is_new = 1 if c.get("isNewlyDiscovered") else 0
            c_manual_lock = 1 if (cid in locked_councils or c.get("manualLock")) else 0

            cur.execute("SELECT id, manual_lock FROM councils WHERE id = ?", (cid,))
            existing = cur.fetchone()

            if not existing:
                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO councils (
                            id, ministry, category, name, official_url, archive_url,
                            description, past_year_count, is_closed, closed_reason,
                            manual_lock, is_newly_discovered, discovered_at, discovery_source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cid,
                            c.get("ministry", ""),
                            c.get("category", "COUNCIL"),
                            c.get("name", ""),
                            c.get("officialUrl", ""),
                            c.get("archiveUrl", ""),
                            c.get("description", ""),
                            c.get("pastYearCount", 0),
                            1 if c.get("isClosed") else 0,
                            c.get("closedReason", ""),
                            c_manual_lock,
                            c_is_new,
                            c_discovered_at,
                            c_discovery_source
                        )
                    )
                stats["councils_inserted"] += 1
            else:
                if existing["manual_lock"] == 1:
                    stats["councils_skipped_lock"] += 1
                else:
                    if not dry_run:
                        cur.execute(
                            """
                            UPDATE councils SET
                                ministry = ?, category = ?, name = ?, official_url = ?,
                                archive_url = ?, description = ?, past_year_count = ?,
                                is_closed = ?, closed_reason = ?,
                                is_newly_discovered = ?,
                                discovered_at = COALESCE(NULLIF(?, ''), discovered_at),
                                discovery_source = COALESCE(NULLIF(?, ''), discovery_source),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (
                                c.get("ministry", ""),
                                c.get("category", "COUNCIL"),
                                c.get("name", ""),
                                c.get("officialUrl", ""),
                                c.get("archiveUrl", ""),
                                c.get("description", ""),
                                c.get("pastYearCount", 0),
                                1 if c.get("isClosed") else 0,
                                c.get("closedReason", ""),
                                c_is_new,
                                c_discovered_at,
                                c_discovery_source,
                                cid
                            )
                        )
                    stats["councils_updated"] += 1

        # -------------------------------------------------------------
        # 2. Sync Meetings & Materials (Public + Archive)
        # -------------------------------------------------------------
        all_meetings = list(public_data.get("meetings", []))
        if archive_data.get("meetings"):
            all_meetings.extend(archive_data["meetings"])

        for m in all_meetings:
            mid = m.get("id")
            cid = m.get("councilId")
            if not mid or not cid:
                continue

            m_meta = meeting_crawl_meta.get(mid, {}) if isinstance(meeting_crawl_meta, dict) else {}
            m_discovered_at = m_meta.get("discoveredAt") or m.get("discoveredAt") or ""
            m_last_updated = m_meta.get("lastUpdatedFromCrawl") or m.get("lastUpdatedFromCrawl") or ""
            m_is_new = 1 if m.get("isNewlyDiscovered") else 0
            m_manual_lock = 1 if (mid in locked_meetings or m.get("manualLock")) else 0

            # Check meeting in DB
            cur.execute("SELECT id, manual_lock FROM meetings WHERE id = ?", (mid,))
            existing_m = cur.fetchone()

            tags_json = json.dumps(m.get("tags", []), ensure_ascii=False) if m.get("tags") else None

            if not existing_m:
                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO meetings (
                            id, council_id, name, date, round, official_url,
                            summary, tags_json, is_date_unconfirmed, is_newly_discovered,
                            discovered_at, last_updated_from_crawl, manual_lock
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            mid,
                            cid,
                            m.get("name", ""),
                            m.get("date", ""),
                            m.get("round"),
                            m.get("officialUrl", ""),
                            m.get("summary", ""),
                            tags_json,
                            1 if m.get("isDateUnconfirmed") else 0,
                            m_is_new,
                            m_discovered_at,
                            m_last_updated,
                            m_manual_lock
                        )
                    )
                stats["meetings_inserted"] += 1
            else:
                if existing_m["manual_lock"] == 1:
                    stats["meetings_skipped_lock"] += 1
                else:
                    if not dry_run:
                        cur.execute(
                            """
                            UPDATE meetings SET
                                name = ?, date = ?, round = ?, official_url = ?,
                                summary = ?, tags_json = ?, is_date_unconfirmed = ?,
                                is_newly_discovered = ?,
                                discovered_at = COALESCE(NULLIF(?, ''), discovered_at),
                                last_updated_from_crawl = COALESCE(NULLIF(?, ''), last_updated_from_crawl),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                            """,
                            (
                                m.get("name", ""),
                                m.get("date", ""),
                                m.get("round"),
                                m.get("officialUrl", ""),
                                m.get("summary", ""),
                                tags_json,
                                1 if m.get("isDateUnconfirmed") else 0,
                                m_is_new,
                                m_discovered_at,
                                m_last_updated,
                                mid
                            )
                        )
                    stats["meetings_updated"] += 1

            # Sync Materials of this meeting
            materials = m.get("materials", [])
            for mat in materials:
                m_url = mat.get("url", "").strip()
                m_name = mat.get("name", "").strip()
                if not m_url or not m_name:
                    continue

                mat_manual_lock = 1 if (f"{mid}:{m_url}" in locked_materials or mat.get("manualLock")) else 0

                cur.execute(
                    "SELECT id, download_status, local_path, file_size, downloaded_at, manual_lock "
                    "FROM materials WHERE meeting_id = ? AND url = ?",
                    (mid, m_url)
                )
                existing_mat = cur.fetchone()

                if not existing_mat:
                    if not dry_run:
                        cur.execute(
                            """
                            INSERT INTO materials (
                                meeting_id, name, url, type, is_private, manual_lock,
                                download_status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                mid,
                                m_name,
                                m_url,
                                mat.get("type", "PDF"),
                                1 if mat.get("isPrivate") else 0,
                                mat_manual_lock,
                                "pending"
                            )
                        )
                    stats["materials_inserted"] += 1
                else:
                    if existing_mat["manual_lock"] == 1:
                        stats["materials_skipped_lock"] += 1
                        continue

                    # PMM Protection Rule:
                    # If already downloaded, preserve download_status, local_path, file_size, downloaded_at
                    if existing_mat["download_status"] == "downloaded":
                        stats["materials_pmm_preserved"] += 1
                        if not dry_run:
                            cur.execute(
                                """
                                UPDATE materials SET
                                    name = ?, type = ?, is_private = ?
                                WHERE id = ?
                                """,
                                (
                                    m_name,
                                    mat.get("type", "PDF"),
                                    1 if mat.get("isPrivate") else 0,
                                    existing_mat["id"]
                                )
                            )
                    else:
                        if not dry_run:
                            cur.execute(
                                """
                                UPDATE materials SET
                                    name = ?, type = ?, is_private = ?
                                WHERE id = ?
                                """,
                                (
                                    m_name,
                                    mat.get("type", "PDF"),
                                    1 if mat.get("isPrivate") else 0,
                                    existing_mat["id"]
                                )
                            )
                    stats["materials_updated"] += 1

        # -------------------------------------------------------------
        # 3. Sync Admin Data (scrapingRules, crawlStatuses, crawlerConfig)
        # -------------------------------------------------------------
        if admin_data:
            # scrapingRules
            rules = admin_data.get("scrapingRules", {})
            for cid, r_def in rules.items():
                if not cid or not r_def:
                    continue
                r_json = json.dumps(r_def, ensure_ascii=False)
                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO scraping_rules (council_id, rule_json, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(council_id) DO UPDATE SET
                            rule_json = excluded.rule_json,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (cid, r_json)
                    )
                stats["rules_synced"] += 1

            # crawlStatuses
            statuses = admin_data.get("crawlStatuses", {})
            for cid, s_info in statuses.items():
                if not cid or not isinstance(s_info, dict):
                    continue
                if not dry_run:
                    cur.execute(
                        """
                        INSERT INTO crawl_statuses (
                            council_id, last_attempt, result, result_reason,
                            extraction_method, materials_count, dates_count,
                            failure_reason, consecutive_failures, manual_lock_active,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(council_id) DO UPDATE SET
                            last_attempt = excluded.last_attempt,
                            result = excluded.result,
                            result_reason = excluded.result_reason,
                            extraction_method = excluded.extraction_method,
                            materials_count = excluded.materials_count,
                            dates_count = excluded.dates_count,
                            failure_reason = excluded.failure_reason,
                            consecutive_failures = excluded.consecutive_failures,
                            manual_lock_active = excluded.manual_lock_active,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            cid,
                            s_info.get("lastAttempt", ""),
                            s_info.get("result", ""),
                            s_info.get("resultReason", ""),
                            s_info.get("extractionMethod", ""),
                            s_info.get("materialsCount", 0),
                            s_info.get("datesCount", 0),
                            s_info.get("failureReason", ""),
                            s_info.get("consecutiveFailures", 0),
                            1 if s_info.get("manualLockActive") else 0
                        )
                    )
                stats["statuses_synced"] += 1

            # crawlerConfig & configs
            for cfg_key in ["crawlerConfig", "discoveryKeywords", "initialAlertKeywords"]:
                val = admin_data.get(cfg_key)
                if val is not None:
                    val_json = json.dumps(val, ensure_ascii=False)
                    if not dry_run:
                        cur.execute(
                            """
                            INSERT INTO admin_configs (key, value_json, updated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(key) DO UPDATE SET
                                value_json = excluded.value_json,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (cfg_key, val_json)
                        )
                    stats["configs_synced"] += 1

        if not dry_run:
            conn.commit()
            if verbose:
                print(f"✅ [SUCCESS] Master database ({db_path.name}) synchronized successfully!")
        else:
            if verbose:
                print(f"🔍 [DRY-RUN] No changes committed to {db_path.name}.")

    except Exception as e:
        if not dry_run:
            conn.rollback()
        raise e
    finally:
        conn.close()

    if verbose:
        print("--------------------------------------------------")
        print(" PMHub DB 差分同期サマリー")
        print("--------------------------------------------------")
        print(f"  ・会議体: 新規追加 {stats['councils_inserted']} 件 / 更新 {stats['councils_updated']} 件 (ロック保護 {stats['councils_skipped_lock']} 件)")
        print(f"  ・開催回: 新規追加 {stats['meetings_inserted']} 件 / 更新 {stats['meetings_updated']} 件 (ロック保護 {stats['meetings_skipped_lock']} 件)")
        print(f"  ・配付資料: 新規追加 {stats['materials_inserted']} 件 / 更新 {stats['materials_updated']} 件")
        print(f"      (PMMダウンロード資産保護: {stats['materials_pmm_preserved']} 件 / ロック保護 {stats['materials_skipped_lock']} 件)")
        print(f"  ・スクレイピングルール同期: {stats['rules_synced']} 件")
        print(f"  ・クロールステータス同期: {stats['statuses_synced']} 件")
        print(f"  ・管理設定同期: {stats['configs_synced']} 件")
        print("--------------------------------------------------")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize local SQLite master DB with updated JSON files (PMM & manualLock protected)."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite master DB")
    parser.add_argument("--public-json", type=Path, default=DEFAULT_PUBLIC_JSON, help="Path to docs/data.json")
    parser.add_argument("--archive-json", type=Path, default=DEFAULT_ARCHIVE_JSON, help="Path to docs/data_archive.json")
    parser.add_argument("--admin-json", type=Path, default=DEFAULT_ADMIN_JSON, help="Path to admin/admin_data.json")
    parser.add_argument("--dry-run", action="store_true", help="Simulate synchronization without modifying DB")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    try:
        sync_database(
            db_path=args.db,
            public_json_path=args.public_json,
            archive_json_path=args.archive_json,
            admin_json_path=args.admin_json,
            dry_run=args.dry_run,
            verbose=not args.quiet
        )
    except Exception as e:
        print(f"❌ [ERROR] Synchronization failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
