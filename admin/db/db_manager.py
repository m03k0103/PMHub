#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Database Manager & Synchronization Pipeline (admin/db/db_manager.py)
========================================================================
Handles direct read/write operations with SQLite database (admin/pmhub.db),
and triggers deterministic export pipeline (export_data.py) to keep docs/data.json
and admin/admin_data.json continuously synchronized.
"""

from datetime import datetime
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .export_data import export_data
from .seed_db import seed_db

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "admin" / "pmhub.db"
DEFAULT_PUBLIC_JSON = BASE_DIR / "docs" / "data.json"
DEFAULT_ADMIN_JSON = BASE_DIR / "admin" / "admin_data.json"
SCHEMA_PATH = BASE_DIR / "admin" / "db" / "schema.sql"


def ensure_database(
    db_path: Path = DEFAULT_DB_PATH,
    public_json_path: Path = DEFAULT_PUBLIC_JSON,
    admin_json_path: Path = DEFAULT_ADMIN_JSON,
    schema_path: Path = SCHEMA_PATH
) -> bool:
    """Ensure pmhub.db exists and is seeded; if not, initialize and seed automatically."""
    if not db_path.exists():
        print(f"[INFO] Database {db_path} not found. Auto-seeding from JSON files...", file=sys.stderr)
        return seed_db(
            db_path=db_path,
            public_json_path=public_json_path,
            admin_json_path=admin_json_path,
            schema_path=schema_path
        )

    # Check and apply schema migrations for local materials management if needed
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        mat_cols = [r[1] for r in cur.execute("PRAGMA table_info(materials);").fetchall()]
        cols_to_add = [
            ("local_path", "TEXT", "NULL"),
            ("download_status", "TEXT", "'pending'"),
            ("file_size", "INTEGER", "NULL"),
            ("downloaded_at", "TEXT", "NULL")
        ]
        for col, typ, dflt in cols_to_add:
            if col not in mat_cols:
                cur.execute(f"ALTER TABLE materials ADD COLUMN {col} {typ} DEFAULT {dflt};")

        c_mat_cols = [r[1] for r in cur.execute("PRAGMA table_info(council_materials);").fetchall()]
        for col, typ, dflt in cols_to_add:
            if col not in c_mat_cols:
                cur.execute(f"ALTER TABLE council_materials ADD COLUMN {col} {typ} DEFAULT {dflt};")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_materials_status ON materials(download_status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_council_materials_status ON council_materials(download_status);")

        # Drop 80 schema migration: Ensure rejected_councils table and indexes exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rejected_councils (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ministry TEXT,
                category TEXT DEFAULT 'COUNCIL',
                official_url TEXT,
                rejected_at TEXT,
                reason TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rejected_councils_ministry ON rejected_councils(ministry);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rejected_councils_url ON rejected_councils(official_url);")

        # Drop 81 schema migration: Ensure councils new-arrival columns and llm_cache table exist
        c_cols = [r[1] for r in cur.execute("PRAGMA table_info(councils);").fetchall()]
        c_cols_to_add = [
            ("is_newly_discovered", "INTEGER", "0"),
            ("discovered_at", "TEXT", "NULL"),
            ("discovery_source", "TEXT", "NULL")
        ]
        for col, typ, dflt in c_cols_to_add:
            if col not in c_cols:
                cur.execute(f"ALTER TABLE councils ADD COLUMN {col} {typ} DEFAULT {dflt};")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS llm_cache (
                digest_hash TEXT PRIMARY KEY,
                purpose TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_cache_purpose ON llm_cache(purpose);")

        conn.commit()



        conn.close()
    except Exception as e:
        print(f"[WARN] Schema migration check notice: {e}", file=sys.stderr)

    return True


def _load_dataset_from_db(cur: sqlite3.Cursor, include_pmm_details: bool = False) -> Dict[str, Any]:
    """
    Internal core loader extracting data dictionary directly from SQLite cursor.
    If include_pmm_details is True, includes PMM local material attributes
    (local_path, download_status, file_size, downloaded_at) and crawlStatuses.
    """
    # 1. Metadata
    meta_rows = cur.execute("SELECT key, value FROM metadata;").fetchall()
    metadata = {r["key"]: r["value"] for r in meta_rows}
    last_crawl_time = metadata.get("lastCrawlTime", "")

    # 2. Configurations
    cfg_rows = cur.execute("SELECT key, value_json FROM admin_configs;").fetchall()
    configs = {}
    for r in cfg_rows:
        try:
            configs[r["key"]] = json.loads(r["value_json"])
        except (json.JSONDecodeError, TypeError, ValueError):
            configs[r["key"]] = {}

    ministries = configs.get("ministries", {})
    categories = configs.get("categories", {})
    doc_types = configs.get("docTypes", {})
    templates = configs.get("scrapingRuleTemplates", {})
    discovery_keywords = configs.get("discoveryKeywords", [])
    crawler_config = configs.get("crawlerConfig", {})
    rejected_councils = configs.get("rejectedCouncils", [])
    initial_alert_keywords = configs.get("initialAlertKeywords", [])

    # 3. Scraping Rules
    rule_rows = cur.execute("SELECT council_id, rule_json FROM scraping_rules;").fetchall()
    scraping_rules = {}
    for r in rule_rows:
        try:
            scraping_rules[r["council_id"]] = json.loads(r["rule_json"])
        except (json.JSONDecodeError, TypeError, ValueError):
            scraping_rules[r["council_id"]] = {}

    # 4. Crawl Statuses
    cs_rows = cur.execute("""
        SELECT council_id, last_attempt, result, result_reason, extraction_method,
               materials_count, dates_count, failure_reason, consecutive_failures, manual_lock_active
        FROM crawl_statuses;
    """).fetchall()
    crawl_statuses = {}
    for r in cs_rows:
        crawl_statuses[r["council_id"]] = {
            "lastAttempt": r["last_attempt"] or "",
            "result": r["result"] or "success",
            "resultReason": r["result_reason"] or "",
            "extractionMethod": r["extraction_method"] or "rule",
            "materialsCount": r["materials_count"] or 0,
            "datesCount": r["dates_count"] or 0,
            "failureReason": r["failure_reason"] or "",
            "consecutiveFailures": r["consecutive_failures"] or 0,
            "manualLockActive": bool(r["manual_lock_active"])
        }

    # 5. Council Materials
    if include_pmm_details:
        c_mat_rows = cur.execute("""
            SELECT council_id, name, url, type, manual_lock, local_path, download_status, file_size, downloaded_at
            FROM council_materials
            ORDER BY id ASC;
        """).fetchall()
    else:
        c_mat_rows = cur.execute("""
            SELECT council_id, name, url, type, manual_lock
            FROM council_materials
            ORDER BY id ASC;
        """).fetchall()

    c_mats_map = {}
    for r in c_mat_rows:
        m_item = {"name": r["name"], "url": r["url"]}
        if r["type"] and r["type"].upper() != "PDF":
            m_item["type"] = r["type"].upper()
        if r["manual_lock"]:
            m_item["manualLock"] = True
        if include_pmm_details:
            m_item["localPath"] = r["local_path"]
            m_item["downloadStatus"] = r["download_status"] or "pending"
            m_item["fileSize"] = r["file_size"]
            m_item["downloadedAt"] = r["downloaded_at"]
        c_mats_map.setdefault(r["council_id"], []).append(m_item)

    # 6. Councils
    c_rows = cur.execute("""
        SELECT id, ministry, category, name, official_url, archive_url, description,
               past_year_count, is_closed, closed_reason, manual_lock,
               is_newly_discovered, discovered_at, discovery_source
        FROM councils
        ORDER BY id ASC;
    """).fetchall()

    councils = []
    for r in c_rows:
        cid = r["id"]
        c_dict = {
            "id": cid,
            "ministry": r["ministry"],
            "category": r["category"],
            "name": r["name"]
        }
        if r["official_url"]:
            c_dict["officialUrl"] = r["official_url"]
        if r["archive_url"]:
            c_dict["archiveUrl"] = r["archive_url"]
        if r["description"]:
            c_dict["description"] = r["description"]
        c_dict["pastYearCount"] = r["past_year_count"] if r["past_year_count"] is not None else 0
        if r["manual_lock"]:
            c_dict["manualLock"] = True
        if r["is_closed"]:
            c_dict["isClosed"] = True
            if r["closed_reason"]:
                c_dict["closedReason"] = r["closed_reason"]
        if r["is_newly_discovered"]:
            c_dict["isNewlyDiscovered"] = True
        if r["discovered_at"]:
            c_dict["discoveredAt"] = r["discovered_at"]
        if r["discovery_source"]:
            c_dict["discoverySource"] = r["discovery_source"]

        mats = c_mats_map.get(cid, [])
        if include_pmm_details:
            c_dict["materials"] = mats
            c_dict["crawlStatus"] = crawl_statuses.get(cid, {})
        else:
            if mats:
                c_dict["materials"] = mats
            if cid in crawl_statuses:
                c_dict["crawlStatus"] = crawl_statuses[cid]

        councils.append(c_dict)

    # 7. Meeting Materials
    if include_pmm_details:
        mat_rows = cur.execute("""
            SELECT meeting_id, name, url, type, is_private, manual_lock, local_path, download_status, file_size, downloaded_at
            FROM materials
            ORDER BY id ASC;
        """).fetchall()
    else:
        mat_rows = cur.execute("""
            SELECT meeting_id, name, url, type, is_private, manual_lock
            FROM materials
            ORDER BY id ASC;
        """).fetchall()

    mats_map = {}
    for r in mat_rows:
        mid = r["meeting_id"]
        mat_item = {"name": r["name"], "url": r["url"]}
        if r["type"] and r["type"].upper() != "PDF":
            mat_item["type"] = r["type"].upper()
        if r["is_private"]:
            mat_item["isPrivate"] = True
        if r["manual_lock"]:
            mat_item["manualLock"] = True
        if include_pmm_details:
            mat_item["localPath"] = r["local_path"]
            mat_item["downloadStatus"] = r["download_status"] or "pending"
            mat_item["fileSize"] = r["file_size"]
            mat_item["downloadedAt"] = r["downloaded_at"]
        mats_map.setdefault(mid, []).append(mat_item)

    # 8. Meetings
    m_rows = cur.execute("""
        SELECT id, council_id, name, date, round, official_url, summary,
               tags_json, is_date_unconfirmed, is_newly_discovered,
               discovered_at, last_updated_from_crawl, manual_lock
        FROM meetings
        ORDER BY date DESC, id ASC;
    """).fetchall()

    meetings = []
    for r in m_rows:
        mid = r["id"]
        m_dict = {
            "id": mid,
            "councilId": r["council_id"],
            "name": r["name"],
            "date": r["date"]
        }
        if r["round"] is not None:
            m_dict["round"] = r["round"]
        if r["official_url"]:
            m_dict["officialUrl"] = r["official_url"]
        if r["summary"]:
            m_dict["summary"] = r["summary"]
        if r["manual_lock"]:
            m_dict["manualLock"] = True
        if r["tags_json"]:
            try:
                tags = json.loads(r["tags_json"])
                if tags:
                    m_dict["tags"] = tags
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        if r["is_date_unconfirmed"]:
            m_dict["isDateUnconfirmed"] = True
        if r["is_newly_discovered"]:
            m_dict["isNewlyDiscovered"] = True
        if r["discovered_at"]:
            m_dict["discoveredAt"] = r["discovered_at"]
        if r["last_updated_from_crawl"]:
            m_dict["lastUpdatedFromCrawl"] = r["last_updated_from_crawl"]

        m_dict["materials"] = mats_map.get(mid, [])
        meetings.append(m_dict)

    dataset = {
        "ministries": ministries,
        "councils": councils,
        "meetings": meetings,
        "categories": categories,
        "docTypes": doc_types,
        "lastCrawlTime": last_crawl_time,
        "scrapingRuleTemplates": templates,
        "scrapingRules": scraping_rules,
        "discoveryKeywords": discovery_keywords,
        "crawlerConfig": crawler_config,
        "rejectedCouncils": rejected_councils,
        "initialAlertKeywords": initial_alert_keywords
    }
    if include_pmm_details:
        dataset["crawlStatuses"] = crawl_statuses

    return dataset


def load_data_from_db(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Load complete data dictionary directly from SQLite database.
    Returns standard dictionary compatible with crawler.py and server.py.
    """
    if not ensure_database(db_path):
        return {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        return _load_dataset_from_db(cur, include_pmm_details=False)
    finally:
        conn.close()

def save_data_to_db(
    data: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
    run_export: bool = True
) -> bool:
    """
    Save complete or updated data dictionary directly to SQLite database in an ACID transaction,
    then automatically trigger the export pipeline to refresh docs/data.json and admin/admin_data.json.
    """
    if not isinstance(data, dict):
        return False

    ensure_database(db_path)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    try:
        # 1. Metadata
        last_crawl_time = data.get("lastCrawlTime")
        if last_crawl_time:
            cur.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('lastCrawlTime', ?);",
                (str(last_crawl_time),)
            )

        # 2. Admin Configurations
        configs = {
            "ministries": data.get("ministries", {}),
            "categories": data.get("categories", {}),
            "docTypes": data.get("docTypes", {}),
            "scrapingRuleTemplates": data.get("scrapingRuleTemplates", {}),
            "discoveryKeywords": data.get("discoveryKeywords", []),
            "crawlerConfig": data.get("crawlerConfig", {}),
            "rejectedCouncils": data.get("rejectedCouncils", []),
            "initialAlertKeywords": data.get("initialAlertKeywords", [])
        }
        for k, v in configs.items():
            if v is not None:
                cur.execute(
                    "INSERT OR REPLACE INTO admin_configs (key, value_json) VALUES (?, ?);",
                    (k, json.dumps(v, ensure_ascii=False))
                )

        # 3. Scraping Rules
        scraping_rules = data.get("scrapingRules", {})
        if isinstance(scraping_rules, dict):
            rule_rows = [
                (cid, json.dumps(rule, ensure_ascii=False))
                for cid, rule in scraping_rules.items()
            ]
            cur.executemany(
                "INSERT OR REPLACE INTO scraping_rules (council_id, rule_json) VALUES (?, ?);",
                rule_rows
            )

        # 4. Councils & Crawl Statuses & Council Materials
        councils = data.get("councils", [])
        if councils:
            c_rows = []
            c_mat_rows = []
            cs_rows = []

            for c in councils:
                cid = c.get("id")
                if not cid:
                    continue
                c_rows.append((
                    cid,
                    c.get("ministry", ""),
                    c.get("category", ""),
                    c.get("name", ""),
                    c.get("officialUrl", ""),
                    c.get("archiveUrl", ""),
                    c.get("description", ""),
                    c.get("pastYearCount", 0),
                    1 if c.get("isClosed") else 0,
                    c.get("closedReason", ""),
                    1 if c.get("manualLock") else 0,
                    1 if c.get("isNewlyDiscovered") else 0,
                    c.get("discoveredAt", ""),
                    c.get("discoverySource", "")
                ))

                for mat in c.get("materials", []):
                    m_url = mat.get("url")
                    if m_url:
                        c_mat_rows.append((
                            cid,
                            mat.get("name", ""),
                            m_url,
                            mat.get("type", "PDF"),
                            1 if mat.get("manualLock") else 0
                        ))

                cs = c.get("crawlStatus")
                if cs and isinstance(cs, dict):
                    cs_rows.append((
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

            # Drop 82: In-place update preserving child rows (meetings, materials) without firing CASCADE DELETE
            cur.executemany("""
                INSERT INTO councils (
                    id, ministry, category, name, official_url, archive_url, description,
                    past_year_count, is_closed, closed_reason, manual_lock,
                    is_newly_discovered, discovered_at, discovery_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    ministry = excluded.ministry,
                    category = excluded.category,
                    name = excluded.name,
                    official_url = excluded.official_url,
                    archive_url = excluded.archive_url,
                    description = excluded.description,
                    past_year_count = excluded.past_year_count,
                    is_closed = excluded.is_closed,
                    closed_reason = excluded.closed_reason,
                    manual_lock = excluded.manual_lock,
                    is_newly_discovered = excluded.is_newly_discovered,
                    discovered_at = excluded.discovered_at,
                    discovery_source = excluded.discovery_source;
            """, c_rows)

            if c_mat_rows:
                # Drop 82: Refresh council materials non-destructively preserving download_status
                cur.executemany("""
                    INSERT INTO council_materials (
                        council_id, name, url, type, manual_lock
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(council_id, url) DO UPDATE SET
                        name = excluded.name,
                        type = excluded.type,
                        manual_lock = excluded.manual_lock;
                """, c_mat_rows)

            if cs_rows:
                cur.executemany("""
                    INSERT OR REPLACE INTO crawl_statuses (
                        council_id, last_attempt, result, result_reason, extraction_method,
                        materials_count, dates_count, failure_reason, consecutive_failures, manual_lock_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, cs_rows)

        # 5. Meetings & Materials
        meetings = data.get("meetings", [])
        if meetings:
            m_rows = []
            mat_rows = []

            for m in meetings:
                mid = m.get("id")
                cid = m.get("councilId")
                if not mid or not cid:
                    continue

                tags = m.get("tags")
                tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
                is_unconf = 1 if (m.get("isDateUnconfirmed") or m.get("date") == "2099/01/01") else 0

                m_rows.append((
                    mid,
                    cid,
                    m.get("name", ""),
                    m.get("date", ""),
                    m.get("round"),
                    m.get("officialUrl", ""),
                    m.get("summary", ""),
                    tags_json,
                    is_unconf,
                    1 if m.get("isNewlyDiscovered") else 0,
                    m.get("discoveredAt", ""),
                    m.get("lastUpdatedFromCrawl", ""),
                    1 if m.get("manualLock") else 0
                ))

                for mat in m.get("materials", []):
                    mat_url = mat.get("url")
                    if mat_url:
                        mat_rows.append((
                            mid,
                            mat.get("name", ""),
                            mat_url,
                            mat.get("type", "PDF"),
                            1 if mat.get("isPrivate") else 0,
                            1 if mat.get("manualLock") else 0
                        ))

            # Drop 82: In-place update preserving child rows (materials) without firing CASCADE DELETE
            cur.executemany("""
                INSERT INTO meetings (
                    id, council_id, name, date, round, official_url, summary,
                    tags_json, is_date_unconfirmed, is_newly_discovered,
                    discovered_at, last_updated_from_crawl, manual_lock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    council_id = excluded.council_id,
                    name = excluded.name,
                    date = excluded.date,
                    round = excluded.round,
                    official_url = excluded.official_url,
                    summary = excluded.summary,
                    tags_json = excluded.tags_json,
                    is_date_unconfirmed = excluded.is_date_unconfirmed,
                    is_newly_discovered = excluded.is_newly_discovered,
                    discovered_at = excluded.discovered_at,
                    last_updated_from_crawl = excluded.last_updated_from_crawl,
                    manual_lock = excluded.manual_lock;
            """, m_rows)

            # Insert or update materials, ensuring name and manual_lock changes are applied
            cur.executemany("""
                INSERT INTO materials (
                    meeting_id, name, url, type, is_private, manual_lock
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(meeting_id, url) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    manual_lock = excluded.manual_lock;
            """, mat_rows)

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to save data to database: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

    # Automatic deterministic export pipeline
    if run_export:
        if Path(db_path).resolve() == DEFAULT_DB_PATH.resolve():
            t0 = time.time()
            success = export_data(db_path=db_path)
            if success:
                dur = time.time() - t0
                print(f"[AUTO-EXPORT] docs/data.json & admin/admin_data.json exported successfully in {dur:.2f}s.")
            return success
        return True

    return True


def update_materials_download_batch(
    records: List[Dict[str, Any]],
    db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """
    Batch update local download status for meeting materials.
    records format: [{'meeting_id': str, 'url': str, 'local_path': str, 'download_status': str, 'file_size': int, 'downloaded_at': str}]
    """
    if not records:
        return True
    if not ensure_database(db_path):
        return False

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cur.executemany("""
            UPDATE materials
            SET local_path = ?,
                download_status = ?,
                file_size = ?,
                downloaded_at = ?
            WHERE meeting_id = ? AND url = ?;
        """, [
            (
                r.get("local_path"),
                r.get("download_status", "downloaded"),
                r.get("file_size"),
                r.get("downloaded_at") or (datetime.now().strftime("%Y-%m-%d %H:%M:%S") if r.get("download_status") == "downloaded" else None),
                r.get("meeting_id"),
                r.get("url")
            )
            for r in records
        ])
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to update materials download batch: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()


def update_council_materials_download_batch(
    records: List[Dict[str, Any]],
    db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """
    Batch update local download status for council permanent materials (00_会議体資料).
    records format: [{'council_id': str, 'url': str, 'local_path': str, 'download_status': str, 'file_size': int, 'downloaded_at': str}]
    """
    if not records:
        return True
    if not ensure_database(db_path):
        return False

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cur.executemany("""
            UPDATE council_materials
            SET local_path = ?,
                download_status = ?,
                file_size = ?,
                downloaded_at = ?
            WHERE council_id = ? AND url = ?;
        """, [
            (
                r.get("local_path"),
                r.get("download_status", "downloaded"),
                r.get("file_size"),
                r.get("downloaded_at") or (datetime.now().strftime("%Y-%m-%d %H:%M:%S") if r.get("download_status") == "downloaded" else None),
                r.get("council_id"),
                r.get("url")
            )
            for r in records
        ])
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to update council materials download batch: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()


def get_materials_download_summary(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Return statistical summary of downloaded vs pending/failed materials."""
    if not ensure_database(db_path):
        return {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        # Meeting materials
        m_rows = cur.execute("""
            SELECT COALESCE(download_status, 'pending') AS status,
                   COUNT(*) AS count,
                   COALESCE(SUM(file_size), 0) AS total_size
            FROM materials
            GROUP BY download_status;
        """).fetchall()

        # Council permanent materials
        cm_rows = cur.execute("""
            SELECT COALESCE(download_status, 'pending') AS status,
                   COUNT(*) AS count,
                   COALESCE(SUM(file_size), 0) AS total_size
            FROM council_materials
            GROUP BY download_status;
        """).fetchall()

        summary = {
            "meetingMaterials": {r["status"]: {"count": r["count"], "totalSize": r["total_size"]} for r in m_rows},
            "councilMaterials": {r["status"]: {"count": r["count"], "totalSize": r["total_size"]} for r in cm_rows},
            "totalCount": 0,
            "downloadedCount": 0,
            "pendingCount": 0,
            "failedCount": 0,
            "totalSizeBytes": 0
        }

        for category in ["meetingMaterials", "councilMaterials"]:
            for status, vals in summary[category].items():
                summary["totalCount"] += vals["count"]
                summary["totalSizeBytes"] += vals["totalSize"]
                if status == "downloaded":
                    summary["downloadedCount"] += vals["count"]
                elif status == "failed":
                    summary["failedCount"] += vals["count"]
                else:
                    summary["pendingCount"] += vals["count"]

        return summary
    finally:
        conn.close()


def load_admin_full_data_from_db(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Load complete data dictionary for admin dashboard directly from SQLite DB,
    including local_path, download_status, and full council/meeting records.
    Eliminates reliance on docs/data.json in admin dashboard.
    """
    if not ensure_database(db_path):
        return {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        data = _load_dataset_from_db(cur, include_pmm_details=True)
        data["downloadSummary"] = get_materials_download_summary(db_path=db_path)
        return data
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Drop 80: Dedicated Rejected Councils (Single Source of Truth in SQLite)
# ---------------------------------------------------------------------------

def load_rejected_councils_from_db(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Load all rejected councils directly from SQLite rejected_councils table.
    Returns list of dictionaries compatible with admin/rejected_councils.json.
    """
    if not ensure_database(db_path):
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        rows = cur.execute("""
            SELECT id, name, ministry, category, official_url, rejected_at, reason
            FROM rejected_councils
            ORDER BY id ASC;
        """).fetchall()

        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "name": r["name"],
                "ministry": r["ministry"] or "",
                "category": r["category"] or "COUNCIL",
                "officialUrl": r["official_url"] or "",
                "rejectedAt": r["rejected_at"] or "",
                "reason": r["reason"] or ""
            })
        return result
    except Exception as e:
        print(f"[WARN] Failed to load rejected councils from DB: {e}", file=sys.stderr)
        return []
    finally:
        conn.close()


def save_rejected_councils_to_db(
    rejected_list: List[Dict[str, Any]],
    db_path: Path = DEFAULT_DB_PATH,
    export: bool = True
) -> bool:
    """
    Save rejected councils list to DB inside an ACID transaction,
    synchronize admin_configs, and trigger deterministic export_data pipeline.
    """
    if not ensure_database(db_path):
        return False

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cur.execute("BEGIN TRANSACTION;")
        cur.execute("DELETE FROM rejected_councils;")

        rows_to_insert = []
        for item in rejected_list:
            cid = item.get("id", "").strip()
            if not cid:
                continue
            name = item.get("name", "")
            ministry = item.get("ministry") or (cid.split("-")[0].upper() if "-" in cid else "")
            category = item.get("category") or "COUNCIL"
            url = item.get("officialUrl") or item.get("url") or ""
            rejected_at = item.get("rejectedAt") or ""
            reason = item.get("reason") or ""
            rows_to_insert.append((cid, name, ministry, category, url, rejected_at, reason))

        cur.executemany("""
            INSERT INTO rejected_councils (
                id, name, ministry, category, official_url, rejected_at, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, rows_to_insert)

        # Synchronize admin_configs for backward compatibility
        cur.execute(
            "INSERT OR REPLACE INTO admin_configs (key, value_json) VALUES (?, ?);",
            ("rejectedCouncils", json.dumps(rejected_list, ensure_ascii=False))
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to save rejected councils to DB: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

    if export:
        if Path(db_path).resolve() == DEFAULT_DB_PATH.resolve():
            export_data(db_path=db_path)
    return True


def add_rejected_council_to_db(
    council_data: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
    export: bool = True
) -> bool:
    """
    Add or update a single rejected council record in SQLite DB and export.
    """
    cid = council_data.get("id", "").strip()
    if not cid:
        return False

    if not ensure_database(db_path):
        return False

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        name = council_data.get("name", "") or cid
        ministry = council_data.get("ministry") or (cid.split("-")[0].upper() if "-" in cid else "")
        category = council_data.get("category") or "COUNCIL"
        url = council_data.get("officialUrl") or council_data.get("url") or ""
        rejected_at = council_data.get("rejectedAt") or time.strftime("%Y-%m-%d")
        reason = council_data.get("reason") or "Admin rejected council"

        cur.execute("""
            INSERT OR REPLACE INTO rejected_councils (
                id, name, ministry, category, official_url, rejected_at, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (cid, name, ministry, category, url, rejected_at, reason))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to add rejected council to DB: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

    if export:
        if Path(db_path).resolve() == DEFAULT_DB_PATH.resolve():
            export_data(db_path=db_path)
    return True


def delete_rejected_council_from_db(
    target_id: str,
    db_path: Path = DEFAULT_DB_PATH,
    export: bool = True
) -> bool:
    """
    Delete a single rejected council record from SQLite DB and export.
    """
    if not target_id:
        return False
    target_id = target_id.strip()

    if not ensure_database(db_path):
        return False

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM rejected_councils WHERE id = ?;", (target_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to delete rejected council from DB: {e}", file=sys.stderr)
        return False
    finally:
        conn.close()

    if export:
        if Path(db_path).resolve() == DEFAULT_DB_PATH.resolve():
            export_data(db_path=db_path)
    return True


def get_rejected_identifiers_from_db(
    db_path: Path = DEFAULT_DB_PATH
) -> Tuple[set, set, set]:
    """
    Get (ids_set, names_set, urls_set) directly from SQLite DB using B-tree index.
    Returns (rej_ids, rej_names, rej_urls).
    """
    if not ensure_database(db_path):
        return set(), set(), set()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        rows = cur.execute("""
            SELECT id, name, official_url FROM rejected_councils;
        """).fetchall()

        rej_ids = set()
        rej_names = set()
        rej_urls = set()
        for r in rows:
            if r[0]:
                rej_ids.add(r[0].strip())
            if r[1]:
                rej_names.add(r[1].strip())
            if r[2]:
                rej_urls.add(r[2].strip().rstrip("/"))
        return rej_ids, rej_names, rej_urls
    except Exception as e:
        print(f"[WARN] Failed to get rejected identifiers from DB: {e}", file=sys.stderr)
        return set(), set(), set()
    finally:
        conn.close()
