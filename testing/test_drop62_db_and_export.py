#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 62: Database Master & Reversible Split Export Unit Tests (U21)
===================================================================
Verifies:
1. SQLite schema DDL creation and table integrity.
2. Lossless reversibility between JSONs and SQLite database.
3. Proper separation of public data (docs/data.json) and admin data (admin/admin_data.json).
4. Git protection of admin/pmhub.db via .gitignore.
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "admin" / "db"
SCHEMA_PATH = DB_DIR / "schema.sql"
SEED_SCRIPT = DB_DIR / "seed_db.py"
EXPORT_SCRIPT = DB_DIR / "export_data.py"
PUBLIC_JSON = BASE_DIR / "docs" / "data.json"
ADMIN_JSON = BASE_DIR / "admin" / "admin_data.json"
GITIGNORE_PATH = BASE_DIR / ".gitignore"


class TestDrop62DatabaseAndExport(unittest.TestCase):
    """Test suite for Drop 62 DB master and split export architecture."""

    def test_01_schema_ddl_integrity(self):
        """Test that schema.sql creates all expected tables, indexes, and virtual tables."""
        self.assertTrue(SCHEMA_PATH.exists(), f"Schema file not found: {SCHEMA_PATH}")

        conn = sqlite3.connect(":memory:")
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            ddl = f.read()

        conn.executescript(ddl)
        cur = conn.cursor()

        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
        expected_tables = {
            "councils",
            "meetings",
            "materials",
            "council_materials",
            "scraping_rules",
            "crawl_statuses",
            "admin_configs",
            "metadata",
            "fts_materials"
        }
        for tbl in expected_tables:
            self.assertIn(tbl, tables, f"Expected table '{tbl}' not found in created schema")
        conn.close()

    def test_02_gitignore_contains_db(self):
        """Test that admin/pmhub.db and SQLite temporary files are registered in .gitignore."""
        self.assertTrue(GITIGNORE_PATH.exists(), f".gitignore not found: {GITIGNORE_PATH}")
        with open(GITIGNORE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("admin/pmhub.db", content, "admin/pmhub.db must be in .gitignore")
        self.assertIn("*.db", content, "*.db must be in .gitignore")
        self.assertIn("*.sqlite", content, "*.sqlite must be in .gitignore")

    def test_03_public_and_admin_json_separation(self):
        """Test that public docs/data.json and admin/admin_data.json have distinct and correct schemas."""
        self.assertTrue(PUBLIC_JSON.exists(), f"Public JSON not found: {PUBLIC_JSON}")
        self.assertTrue(ADMIN_JSON.exists(), f"Admin JSON not found: {ADMIN_JSON}")

        with open(PUBLIC_JSON, "r", encoding="utf-8") as f:
            pub_data = json.load(f)

        with open(ADMIN_JSON, "r", encoding="utf-8") as f:
            adm_data = json.load(f)

        # Public JSON must have essential portal keys
        self.assertIn("ministries", pub_data)
        self.assertIn("councils", pub_data)
        self.assertIn("meetings", pub_data)
        self.assertIn("categories", pub_data)
        self.assertIn("docTypes", pub_data)
        self.assertIn("lastCrawlTime", pub_data)

        # Public JSON must NOT contain crawler-only settings
        self.assertNotIn("scrapingRules", pub_data, "Public JSON should not contain scrapingRules")
        self.assertNotIn("scrapingRuleTemplates", pub_data, "Public JSON should not contain scrapingRuleTemplates")
        self.assertNotIn("crawlerConfig", pub_data, "Public JSON should not contain crawlerConfig")
        self.assertNotIn("rejectedCouncils", pub_data, "Public JSON should not contain rejectedCouncils")

        # Admin JSON must contain crawler and management configs
        self.assertIn("scrapingRules", adm_data)
        self.assertIn("scrapingRuleTemplates", adm_data)
        self.assertIn("crawlStatuses", adm_data)
        self.assertIn("discoveryKeywords", adm_data)
        self.assertIn("crawlerConfig", adm_data)
        self.assertIn("rejectedCouncils", adm_data)
        self.assertIn("manualLocks", adm_data)

        # Councils in public data must not have heavy internal crawlStatus dict
        sample_c = pub_data["councils"][0] if pub_data["councils"] else {}
        self.assertNotIn("crawlStatus", sample_c, "Council in public JSON should not have crawlStatus")

    def test_04_bidirectional_lossless_reversibility(self):
        """Test that seed_db -> export_data produces 100% identical JSON outputs."""
        pub_before = PUBLIC_JSON.read_bytes()
        adm_before = ADMIN_JSON.read_bytes()

        hash_pub_before = hashlib.sha256(pub_before).hexdigest()
        hash_adm_before = hashlib.sha256(adm_before).hexdigest()

        # Run seed_db
        res_seed = subprocess.run([sys.executable, str(SEED_SCRIPT)], capture_output=True, text=True)
        self.assertEqual(res_seed.returncode, 0, f"seed_db failed: {res_seed.stderr}")

        # Run export_data
        res_exp = subprocess.run([sys.executable, str(EXPORT_SCRIPT)], capture_output=True, text=True)
        self.assertEqual(res_exp.returncode, 0, f"export_data failed: {res_exp.stderr}")

        pub_after = PUBLIC_JSON.read_bytes()
        adm_after = ADMIN_JSON.read_bytes()

        hash_pub_after = hashlib.sha256(pub_after).hexdigest()
        hash_adm_after = hashlib.sha256(adm_after).hexdigest()

        self.assertEqual(hash_pub_before, hash_pub_after, "Public JSON must remain bitwise identical after re-export")
        self.assertEqual(hash_adm_before, hash_adm_after, "Admin JSON must remain bitwise identical after re-export")


if __name__ == "__main__":
    unittest.main()
