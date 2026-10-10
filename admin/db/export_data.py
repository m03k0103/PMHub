#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Database Exporter (export_data.py)
========================================
Exports data from SQLite database (admin/pmhub.db) into two separate JSON files:
1. docs/data.json: Slimmed down public dataset for GitHub Pages portal.
2. admin/admin_data.json: Crawler configurations, scraping rules, crawl statuses, and manual locks.

Deterministic output: Sorted keys and items to guarantee reproducible diffs.
"""

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "admin" / "pmhub.db"
DEFAULT_PUBLIC_JSON = BASE_DIR / "docs" / "data.json"
DEFAULT_ADMIN_JSON = BASE_DIR / "admin" / "admin_data.json"


def export_data(
    db_path: Path = DEFAULT_DB_PATH,
    public_json_path: Path = DEFAULT_PUBLIC_JSON,
    admin_json_path: Path = DEFAULT_ADMIN_JSON
) -> bool:
    """Export SQLite database to public and admin JSON files."""
    start_time = time.time()
    if not db_path.exists():
        print(f"[ERROR] Database file not found: {db_path}", file=sys.stderr)
        return False

    print(f"[INFO] Exporting data from {db_path}...")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # 1. Metadata
        meta_rows = cur.execute("SELECT key, value FROM metadata;").fetchall()
        metadata = {row["key"]: row["value"] for row in meta_rows}
        last_crawl_time = metadata.get("lastCrawlTime", "")

        # 2. Master & Admin Configurations
        config_rows = cur.execute("SELECT key, value_json FROM admin_configs;").fetchall()
        configs = {}
        for r in config_rows:
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

        # 3. Councils & Council Materials
        c_mat_rows = cur.execute("""
            SELECT council_id, name, url, type, manual_lock
            FROM council_materials
            ORDER BY id ASC;
        """).fetchall()

        council_mats_map = {}
        council_mat_locks = []
        for r in c_mat_rows:
            cid = r["council_id"]
            mat_item = {"name": r["name"], "url": r["url"]}
            if r["type"] and r["type"].upper() != "PDF":
                mat_item["type"] = r["type"].upper()
            if r["manual_lock"]:
                mat_item["manualLock"] = True
                council_mat_locks.append(f"{cid}:{r['url']}")
            council_mats_map.setdefault(cid, []).append(mat_item)

        c_rows = cur.execute("""
            SELECT id, ministry, category, name, official_url, archive_url, description,
                   past_year_count, is_closed, closed_reason, manual_lock
            FROM councils
            ORDER BY id ASC;
        """).fetchall()

        councils_public = []
        council_locks = []
        for r in c_rows:
            cid = r["id"]
            c_dict = {
                "id": cid,
                "ministry": r["ministry"],
                "category": r["category"],
                "name": r["name"]
            }
            if r["manual_lock"]:
                c_dict["manualLock"] = True
                council_locks.append(cid)
            if r["official_url"]:
                c_dict["officialUrl"] = r["official_url"]
            if r["archive_url"]:
                c_dict["archiveUrl"] = r["archive_url"]
            if r["description"]:
                c_dict["description"] = r["description"]
            
            c_dict["pastYearCount"] = r["past_year_count"] if r["past_year_count"] is not None else 0

            # Council materials
            mats = council_mats_map.get(cid, [])
            if mats:
                c_dict["materials"] = mats

            if r["is_closed"]:
                c_dict["isClosed"] = True
                if r["closed_reason"]:
                    c_dict["closedReason"] = r["closed_reason"]

            councils_public.append(c_dict)

        # 4. Crawl Statuses
        cs_rows = cur.execute("""
            SELECT council_id, last_attempt, result, result_reason, extraction_method,
                   materials_count, dates_count, failure_reason, consecutive_failures, manual_lock_active
            FROM crawl_statuses
            ORDER BY council_id ASC;
        """).fetchall()

        crawl_statuses = {}
        for r in cs_rows:
            cid = r["council_id"]
            crawl_statuses[cid] = {
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

        # 5. Scraping Rules
        rule_rows = cur.execute("""
            SELECT council_id, rule_json
            FROM scraping_rules
            ORDER BY council_id ASC;
        """).fetchall()

        scraping_rules = {}
        for r in rule_rows:
            cid = r["council_id"]
            try:
                scraping_rules[cid] = json.loads(r["rule_json"])
            except Exception:
                scraping_rules[cid] = {}

        # 6. Meetings & Materials
        mat_rows = cur.execute("""
            SELECT meeting_id, name, url, type, is_private, manual_lock
            FROM materials
            ORDER BY id ASC;
        """).fetchall()

        mats_map = {}
        mat_locks = []
        for r in mat_rows:
            mid = r["meeting_id"]
            mat_item = {"name": r["name"], "url": r["url"]}
            if r["type"] and r["type"].upper() != "PDF":
                mat_item["type"] = r["type"].upper()
            if r["is_private"]:
                mat_item["isPrivate"] = True
            if r["manual_lock"]:
                mat_item["manualLock"] = True
                mat_locks.append(f"{mid}:{r['url']}")
            mats_map.setdefault(mid, []).append(mat_item)

        m_rows = cur.execute("""
            SELECT id, council_id, name, date, round, official_url, summary,
                   tags_json, is_date_unconfirmed, is_newly_discovered,
                   discovered_at, last_updated_from_crawl, manual_lock
            FROM meetings
            ORDER BY date DESC, id ASC;
        """).fetchall()

        meetings_public = []
        meeting_locks = []
        for r in m_rows:
            mid = r["id"]
            m_dict = {
                "id": mid,
                "councilId": r["council_id"],
                "name": r["name"],
                "date": r["date"]
            }
            if r["manual_lock"]:
                m_dict["manualLock"] = True
                meeting_locks.append(mid)
            if r["round"] is not None:
                m_dict["round"] = r["round"]
            if r["official_url"]:
                m_dict["officialUrl"] = r["official_url"]
            if r["summary"]:
                m_dict["summary"] = r["summary"]

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
            meetings_public.append(m_dict)

        # --- Build Public Dataset (docs/data.json) ---
        public_dataset = {
            "ministries": ministries,
            "councils": councils_public,
            "meetings": meetings_public,
            "categories": categories,
            "docTypes": doc_types,
            "lastCrawlTime": last_crawl_time
        }

        # --- Build Admin Dataset (admin/admin_data.json) ---
        admin_dataset = {
            "lastCrawlTime": last_crawl_time,
            "scrapingRuleTemplates": templates,
            "scrapingRules": scraping_rules,
            "crawlStatuses": crawl_statuses,
            "discoveryKeywords": discovery_keywords,
            "crawlerConfig": crawler_config,
            "rejectedCouncils": rejected_councils,
            "initialAlertKeywords": initial_alert_keywords,
            "manualLocks": {
                "councils": sorted(council_locks),
                "meetings": sorted(meeting_locks),
                "materials": sorted(mat_locks),
                "councilMaterials": sorted(council_mat_locks)
            }
        }

        # Deterministic JSON export
        print(f"[INFO] Writing public JSON to {public_json_path}...")
        public_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(public_json_path, "w", encoding="utf-8") as f:
            json.dump(public_dataset, f, ensure_ascii=False, indent=2)

        print(f"[INFO] Writing admin JSON to {admin_json_path}...")
        admin_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(admin_json_path, "w", encoding="utf-8") as f:
            json.dump(admin_dataset, f, ensure_ascii=False, indent=2)

        elapsed = time.time() - start_time
        pub_size_mb = public_json_path.stat().st_size / (1024 * 1024)
        adm_size_mb = admin_json_path.stat().st_size / (1024 * 1024)

        print(f"[SUCCESS] Export completed successfully in {elapsed:.2f}s!")
        print(f"  Public JSON: {pub_size_mb:.2f} MB ({len(councils_public)} councils, {len(meetings_public)} meetings)")
        print(f"  Admin JSON:  {adm_size_mb:.2f} MB ({len(scraping_rules)} rules, {len(crawl_statuses)} statuses)")
        return True

    except Exception as e:
        print(f"[ERROR] Export failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = export_data()
    sys.exit(0 if success else 1)
