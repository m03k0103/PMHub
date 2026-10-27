#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Database Seeder (seed_db.py)
==================================
Seeds SQLite database (admin/pmhub.db) from JSON files:
- docs/data.json (public dataset or legacy combined dataset)
- admin/admin_data.json (admin/crawler configuration, if present)

Fully reversible: Rebuilds pmhub.db from scratch in seconds.
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "admin" / "pmhub.db"
DEFAULT_SCHEMA_PATH = BASE_DIR / "admin" / "db" / "schema.sql"
DEFAULT_PUBLIC_JSON = BASE_DIR / "docs" / "data.json"
DEFAULT_ADMIN_JSON = BASE_DIR / "admin" / "admin_data.json"
DEFAULT_REJECTED_JSON = BASE_DIR / "admin" / "rejected_councils.json"


def init_db(db_path: Path, schema_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with schema DDL."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    return conn


def seed_db(
    db_path: Path = DEFAULT_DB_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    public_json_path: Path = DEFAULT_PUBLIC_JSON,
    admin_json_path: Path = DEFAULT_ADMIN_JSON,
    rejected_json_path: Path = DEFAULT_REJECTED_JSON
) -> bool:
    """Seed pmhub.db from public and admin JSON files."""
    start_time = time.time()
    print(f"[INFO] Seeding database at {db_path}...")

    if not public_json_path.exists():
        print(f"[ERROR] Public JSON file not found: {public_json_path}", file=sys.stderr)
        return False

    with open(public_json_path, "r", encoding="utf-8") as f:
        public_data = json.load(f)

    admin_data = {}
    if admin_json_path.exists():
        print(f"[INFO] Found admin JSON at {admin_json_path}")
        with open(admin_json_path, "r", encoding="utf-8") as f:
            admin_data = json.load(f)
    else:
        print("[INFO] Admin JSON not found; falling back to keys in public JSON (initial migration mode).")

    # Drop 82: Preserve existing local download statuses before re-initializing database
    saved_mats_status = {}
    saved_c_mats_status = {}
    if db_path.exists():
        try:
            old_conn = sqlite3.connect(str(db_path))
            m_cols = [r[1] for r in old_conn.execute("PRAGMA table_info(materials);").fetchall()]
            if "download_status" in m_cols:
                for row in old_conn.execute("SELECT meeting_id, url, local_path, download_status, file_size, downloaded_at FROM materials WHERE download_status != 'pending';"):
                    saved_mats_status[(row[0], row[1])] = (row[2], row[3], row[4], row[5])
            cm_cols = [r[1] for r in old_conn.execute("PRAGMA table_info(council_materials);").fetchall()]
            if "download_status" in cm_cols:
                for row in old_conn.execute("SELECT council_id, url, local_path, download_status, file_size, downloaded_at FROM council_materials WHERE download_status != 'pending';"):
                    saved_c_mats_status[(row[0], row[1])] = (row[2], row[3], row[4], row[5])
            old_conn.close()
            if saved_mats_status or saved_c_mats_status:
                print(f"[INFO] Preserving existing download statuses: {len(saved_mats_status)} materials, {len(saved_c_mats_status)} council materials.")
        except Exception as e_pres:
            print(f"[WARN] Failed to preserve previous download statuses from {db_path}: {e_pres}", file=sys.stderr)

    conn = init_db(db_path, schema_path)
    cur = conn.cursor()

    try:
        # 1. Metadata
        last_crawl_time = public_data.get("lastCrawlTime") or admin_data.get("lastCrawlTime", "")
        if last_crawl_time:
            cur.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('lastCrawlTime', ?);",
                (last_crawl_time,)
            )

        # 2. Master & Admin Configurations
        # We store master lookups (ministries, categories, docTypes) and crawler configs in admin_configs
        # Load rejected_councils from dedicated JSON file (master) or fallback
        rejected_councils_list = []
        if rejected_json_path.exists():
            try:
                with open(rejected_json_path, "r", encoding="utf-8") as rf:
                    rejected_councils_list = json.load(rf)
            except Exception as e_rej:
                print(f"[WARN] Failed to load {rejected_json_path}: {e_rej}", file=sys.stderr)
        if not rejected_councils_list:
            rejected_councils_list = admin_data.get("rejectedCouncils") or public_data.get("rejectedCouncils", [])

        configs_to_store = {
            "ministries": public_data.get("ministries", {}),
            "categories": public_data.get("categories", {}),
            "docTypes": public_data.get("docTypes", {}),
            "scrapingRuleTemplates": admin_data.get("scrapingRuleTemplates") or public_data.get("scrapingRuleTemplates", {}),
            "discoveryKeywords": admin_data.get("discoveryKeywords") or public_data.get("discoveryKeywords", []),
            "crawlerConfig": admin_data.get("crawlerConfig") or public_data.get("crawlerConfig", {}),
            "rejectedCouncils": rejected_councils_list,
            "initialAlertKeywords": admin_data.get("initialAlertKeywords") or public_data.get("initialAlertKeywords", []),
            "initialWatchedCouncilIds": public_data.get("initialWatchedCouncilIds") or admin_data.get("initialWatchedCouncilIds", [])
        }

        for k, v in configs_to_store.items():
            cur.execute(
                "INSERT OR REPLACE INTO admin_configs (key, value_json) VALUES (?, ?);",
                (k, json.dumps(v, ensure_ascii=False))
            )

        # 3. Councils & Council Materials & Crawl Statuses
        councils = public_data.get("councils", [])
        crawl_statuses_from_admin = admin_data.get("crawlStatuses", {})
        c_rows = []
        c_mat_rows = []
        crawl_status_rows = []

        for c in councils:
            cid = c.get("id")
            if not cid:
                continue
            is_closed = 1 if c.get("isClosed") else 0
            manual_lock = 1 if c.get("manualLock") else 0
            is_new_c = 1 if c.get("isNewlyDiscovered") else 0
            c_rows.append((
                cid,
                c.get("ministry", ""),
                c.get("category", ""),
                c.get("name", ""),
                c.get("officialUrl", ""),
                c.get("archiveUrl", ""),
                c.get("description", ""),
                c.get("pastYearCount", 0),
                is_closed,
                c.get("closedReason", ""),
                manual_lock,
                is_new_c,
                c.get("discoveredAt", ""),
                c.get("discoverySource", "")
            ))

            # Council permanent materials
            for mat in c.get("materials", []):
                m_url = mat.get("url")
                if not m_url:
                    continue
                c_mat_rows.append((
                    cid,
                    mat.get("name", ""),
                    m_url,
                    mat.get("type", "PDF"),
                    1 if mat.get("manualLock") else 0
                ))

            # Crawl Status (from admin_data or legacy council record)
            cs = crawl_statuses_from_admin.get(cid) or c.get("crawlStatus")
            if cs:
                crawl_status_rows.append((
                    cid,
                    cs.get("lastAttempt", ""),
                    cs.get("result", ""),
                    cs.get("resultReason", ""),
                    cs.get("extractionMethod", ""),
                    cs.get("materialsCount", 0),
                    cs.get("datesCount", 0),
                    cs.get("failureReason", ""),
                    cs.get("consecutiveFailures", 0),
                    1 if cs.get("manualLockActive") else 0
                ))

        cur.executemany("""
            INSERT OR REPLACE INTO councils (
                id, ministry, category, name, official_url, archive_url, description,
                past_year_count, is_closed, closed_reason, manual_lock,
                is_newly_discovered, discovered_at, discovery_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, c_rows)

        cur.executemany("""
            INSERT OR IGNORE INTO council_materials (
                council_id, name, url, type, manual_lock
            ) VALUES (?, ?, ?, ?, ?);
        """, c_mat_rows)

        cur.executemany("""
            INSERT OR REPLACE INTO crawl_statuses (
                council_id, last_attempt, result, result_reason, extraction_method,
                materials_count, dates_count, failure_reason, consecutive_failures, manual_lock_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, crawl_status_rows)

        # 4. Scraping Rules
        scraping_rules = admin_data.get("scrapingRules") or public_data.get("scrapingRules", {})
        rule_rows = []
        for cid, rule in scraping_rules.items():
            rule_rows.append((cid, json.dumps(rule, ensure_ascii=False)))

        cur.executemany("""
            INSERT OR REPLACE INTO scraping_rules (council_id, rule_json)
            VALUES (?, ?);
        """, rule_rows)

        # 5. Meetings & Materials
        meetings = public_data.get("meetings", [])
        m_rows = []
        mat_rows = []

        for m in meetings:
            mid = m.get("id")
            cid = m.get("councilId")
            if not mid or not cid:
                continue

            tags = m.get("tags")
            tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
            is_unconfirmed = 1 if (m.get("isDateUnconfirmed") or m.get("date") == "2099/01/01") else 0
            is_new = 1 if m.get("isNewlyDiscovered") else 0
            m_lock = 1 if m.get("manualLock") else 0

            m_rows.append((
                mid,
                cid,
                m.get("name", ""),
                m.get("date", ""),
                m.get("round"),
                m.get("officialUrl", ""),
                m.get("summary", ""),
                tags_json,
                is_unconfirmed,
                is_new,
                m.get("discoveredAt", ""),
                m.get("lastUpdatedFromCrawl", ""),
                m_lock
            ))

            for mat in m.get("materials", []):
                mat_url = mat.get("url")
                if not mat_url:
                    continue
                mat_rows.append((
                    mid,
                    mat.get("name", ""),
                    mat_url,
                    mat.get("type", "PDF"),
                    1 if mat.get("isPrivate") else 0,
                    1 if mat.get("manualLock") else 0
                ))

        cur.executemany("""
            INSERT OR REPLACE INTO meetings (
                id, council_id, name, date, round, official_url, summary,
                tags_json, is_date_unconfirmed, is_newly_discovered,
                discovered_at, last_updated_from_crawl, manual_lock
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, m_rows)

        cur.executemany("""
            INSERT OR IGNORE INTO materials (
                meeting_id, name, url, type, is_private, manual_lock
            ) VALUES (?, ?, ?, ?, ?, ?);
        """, mat_rows)

        # 4. Seed rejected_councils table
        rej_rows = []
        for item in rejected_councils_list:
            cid = item.get("id", "").strip()
            if not cid:
                continue
            name = item.get("name", "")
            ministry = item.get("ministry") or (cid.split("-")[0].upper() if "-" in cid else "")
            category = item.get("category") or "COUNCIL"
            url = item.get("officialUrl") or item.get("url") or ""
            rejected_at = item.get("rejectedAt") or ""
            reason = item.get("reason") or ""
            rej_rows.append((cid, name, ministry, category, url, rejected_at, reason))

        cur.executemany("""
            INSERT OR REPLACE INTO rejected_councils (
                id, name, ministry, category, official_url, rejected_at, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, rej_rows)

        # Drop 82: Restore preserved download statuses
        if saved_mats_status:
            cur.executemany("""
                UPDATE materials
                SET local_path = ?, download_status = ?, file_size = ?, downloaded_at = ?
                WHERE meeting_id = ? AND url = ?;
            """, [(v[0], v[1], v[2], v[3], k[0], k[1]) for k, v in saved_mats_status.items()])
            print(f"[INFO] Restored {len(saved_mats_status)} material download statuses from previous database.")

        if saved_c_mats_status:
            cur.executemany("""
                UPDATE council_materials
                SET local_path = ?, download_status = ?, file_size = ?, downloaded_at = ?
                WHERE council_id = ? AND url = ?;
            """, [(v[0], v[1], v[2], v[3], k[0], k[1]) for k, v in saved_c_mats_status.items()])
            print(f"[INFO] Restored {len(saved_c_mats_status)} council material download statuses from previous database.")

        conn.commit()

        # Drop 82: If no statuses were preserved (fresh DB) and local_docs exists on disk, auto-sync
        if not saved_mats_status and not saved_c_mats_status:
            local_docs_dir = BASE_DIR / "local_docs"
            if local_docs_dir.exists() and any(f for f in local_docs_dir.iterdir() if not f.name.startswith(".")):
                conn.close()
                try:
                    from admin.pmm.downloader import sync_local_materials_status
                    print("[INFO] Fresh database seeded and local_docs exists. Synchronizing local material status...", file=sys.stderr)
                    sync_local_materials_status(output_base=local_docs_dir, db_path=db_path)
                except Exception as e_sync:
                    print(f"[WARN] Auto-sync of local materials failed: {e_sync}", file=sys.stderr)
                return True

        # Stats verification
        c_cnt = cur.execute("SELECT COUNT(*) FROM councils;").fetchone()[0]
        m_cnt = cur.execute("SELECT COUNT(*) FROM meetings;").fetchone()[0]
        mat_cnt = cur.execute("SELECT COUNT(*) FROM materials;").fetchone()[0]
        r_cnt = cur.execute("SELECT COUNT(*) FROM scraping_rules;").fetchone()[0]
        rej_cnt = cur.execute("SELECT COUNT(*) FROM rejected_councils;").fetchone()[0]
        elapsed = time.time() - start_time

        print(f"[SUCCESS] Database seeded successfully in {elapsed:.2f}s!")
        print(f"  Councils: {c_cnt}")
        print(f"  Meetings: {m_cnt}")
        print(f"  Materials: {mat_cnt}")
        print(f"  Scraping Rules: {r_cnt}")
        print(f"  Rejected Councils: {rej_cnt}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Seeding failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PMHub Database Seeder")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="Path to schema.sql")
    parser.add_argument("--public-json", type=Path, default=DEFAULT_PUBLIC_JSON, help="Path to docs/data.json")
    parser.add_argument("--admin-json", type=Path, default=DEFAULT_ADMIN_JSON, help="Path to admin/admin_data.json")
    parser.add_argument("--rejected-json", type=Path, default=DEFAULT_REJECTED_JSON, help="Path to admin/rejected_councils.json")
    args = parser.parse_args()

    success = seed_db(
        db_path=args.db,
        schema_path=args.schema,
        public_json_path=args.public_json,
        admin_json_path=args.admin_json,
        rejected_json_path=args.rejected_json
    )
    sys.exit(0 if success else 1)
