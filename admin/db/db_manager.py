#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Database Manager & Synchronization Pipeline (admin/db/db_manager.py)
========================================================================
Handles direct read/write operations with SQLite database (admin/pmhub.db),
and triggers deterministic export pipeline (export_data.py) to keep docs/data.json
and admin/admin_data.json continuously synchronized.
"""

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
    return True


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
            except Exception:
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
            except Exception:
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
            c_mats_map.setdefault(r["council_id"], []).append(m_item)

        # 6. Councils
        c_rows = cur.execute("""
            SELECT id, ministry, category, name, official_url, archive_url, description,
                   past_year_count, is_closed, closed_reason, manual_lock
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

            mats = c_mats_map.get(cid, [])
            if mats:
                c_dict["materials"] = mats

            if cid in crawl_statuses:
                c_dict["crawlStatus"] = crawl_statuses[cid]

            councils.append(c_dict)

        # 7. Meeting Materials
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
                except Exception:
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

        data = {
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
        return data

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
                    1 if c.get("manualLock") else 0
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

            cur.executemany("""
                INSERT OR REPLACE INTO councils (
                    id, ministry, category, name, official_url, archive_url, description,
                    past_year_count, is_closed, closed_reason, manual_lock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, c_rows)

            if c_mat_rows:
                # Refresh council materials
                cur.execute("DELETE FROM council_materials;")
                cur.executemany("""
                    INSERT INTO council_materials (
                        council_id, name, url, type, manual_lock
                    ) VALUES (?, ?, ?, ?, ?);
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

            cur.executemany("""
                INSERT OR REPLACE INTO meetings (
                    id, council_id, name, date, round, official_url, summary,
                    tags_json, is_date_unconfirmed, is_newly_discovered,
                    discovered_at, last_updated_from_crawl, manual_lock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, m_rows)

            # To avoid duplicates in materials while maintaining ACID safety,
            # we delete materials for the modified meetings or batch insert with IGNORE
            cur.executemany("""
                INSERT OR IGNORE INTO materials (
                    meeting_id, name, url, type, is_private, manual_lock
                ) VALUES (?, ?, ?, ?, ?, ?);
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
        t0 = time.time()
        success = export_data(db_path=db_path)
        if success:
            dur = time.time() - t0
            print(f"[AUTO-EXPORT] docs/data.json & admin/admin_data.json exported successfully in {dur:.2f}s.")
        return success

    return True
