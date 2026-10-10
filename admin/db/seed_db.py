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
    admin_json_path: Path = DEFAULT_ADMIN_JSON
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
        configs_to_store = {
            "ministries": public_data.get("ministries", {}),
            "categories": public_data.get("categories", {}),
            "docTypes": public_data.get("docTypes", {}),
            "scrapingRuleTemplates": admin_data.get("scrapingRuleTemplates") or public_data.get("scrapingRuleTemplates", {}),
            "discoveryKeywords": admin_data.get("discoveryKeywords") or public_data.get("discoveryKeywords", []),
            "crawlerConfig": admin_data.get("crawlerConfig") or public_data.get("crawlerConfig", {}),
            "rejectedCouncils": admin_data.get("rejectedCouncils") or public_data.get("rejectedCouncils", []),
            "initialAlertKeywords": admin_data.get("initialAlertKeywords") or public_data.get("initialAlertKeywords", [])
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
                manual_lock
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
                past_year_count, is_closed, closed_reason, manual_lock
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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

        conn.commit()

        # Stats verification
        c_cnt = cur.execute("SELECT COUNT(*) FROM councils;").fetchone()[0]
        m_cnt = cur.execute("SELECT COUNT(*) FROM meetings;").fetchone()[0]
        mat_cnt = cur.execute("SELECT COUNT(*) FROM materials;").fetchone()[0]
        r_cnt = cur.execute("SELECT COUNT(*) FROM scraping_rules;").fetchone()[0]
        elapsed = time.time() - start_time

        print(f"[SUCCESS] Database seeded successfully in {elapsed:.2f}s!")
        print(f"  Councils: {c_cnt}")
        print(f"  Meetings: {m_cnt}")
        print(f"  Materials: {mat_cnt}")
        print(f"  Scraping Rules: {r_cnt}")
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
    success = seed_db()
    sys.exit(0 if success else 1)
