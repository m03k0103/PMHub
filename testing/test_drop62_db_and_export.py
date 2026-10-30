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
import tempfile
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
            "fts_materials",
            "rejected_councils",
            "llm_cache"
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
        self.assertIn("councilCrawlMeta", adm_data)
        self.assertIn("meetingCrawlMeta", adm_data)

        # Drop 106: Public JSON must NOT contain management-only metadata (No Leakage)
        sample_c = pub_data["councils"][0] if pub_data["councils"] else {}
        self.assertNotIn("crawlStatus", sample_c, "Council in public JSON should not have crawlStatus")
        self.assertNotIn("manualLock", sample_c, "Council in public JSON should not have manualLock")
        self.assertNotIn("discoveredAt", sample_c, "Council in public JSON should not have discoveredAt")
        self.assertNotIn("discoverySource", sample_c, "Council in public JSON should not have discoverySource")

        sample_m = pub_data["meetings"][0] if pub_data["meetings"] else {}
        self.assertNotIn("manualLock", sample_m, "Meeting in public JSON should not have manualLock")
        self.assertNotIn("discoveredAt", sample_m, "Meeting in public JSON should not have discoveredAt")
        self.assertNotIn("lastUpdatedFromCrawl", sample_m, "Meeting in public JSON should not have lastUpdatedFromCrawl")

        if sample_m.get("materials"):
            self.assertNotIn("manualLock", sample_m["materials"][0], "Material in public JSON should not have manualLock")

    def test_04_bidirectional_lossless_reversibility(self):
        """Test that seed_db -> export_data produces 100% identical JSON outputs (isolated temp fixture)."""
        with tempfile.TemporaryDirectory(prefix="pmhub_test_drop62_") as tmpdir:
            tmp_path = Path(tmpdir)
            tmp_db = tmp_path / "pmhub_test.db"
            tmp_pub = tmp_path / "data.json"
            tmp_adm = tmp_path / "admin_data.json"
            tmp_rej = tmp_path / "rejected_councils.json"

            # テスト用初期フィクスチャ (CR-166: 本番DBへの副作用排除 & 高速化)
            fixture_pub = {
                "categories": ["審議会等"],
                "councils": [
                    {
                        "category": "審議会等",
                        "id": "test-c1",
                        "materials": [
                            {"name": "会議体資料1", "url": "https://example.com/cm1.pdf"}
                        ],
                        "ministry": "test",
                        "name": "テスト審議会1",
                        "officialUrl": "https://example.com/c1",
                        "pastYearCount": 1
                    }
                ],
                "docTypes": ["議事次第", "配付資料", "議事録"],
                "lastCrawlTime": "2026-10-23T00:00:00",
                "meetings": [
                    {
                        "councilId": "test-c1",
                        "date": "2026/01/01",
                        "id": "test-c1-20260101-001",
                        "materials": [
                            {"name": "議事次第", "type": "PDF", "url": "https://example.com/c1-01.pdf"}
                        ],
                        "name": "第1回 テスト会合",
                        "officialUrl": "https://example.com/c1-01",
                        "round": 1
                    }
                ],
                "ministries": [{"id": "test", "name": "テスト省"}]
            }
            fixture_adm = {
                "crawlStatuses": {
                    "test-c1": {
                        "lastCrawl": "2026-10-23T00:00:00",
                        "meetingCount": 1,
                        "status": "success"
                    }
                },
                "crawlerConfig": {"max_workers": 2},
                "discoveryKeywords": ["審議会"],
                "initialAlertKeywords": [],
                "manualLocks": {"councilMaterials": ["test-c1:https://example.com/cm1.pdf"], "councils": ["test-c1"], "materials": ["test-c1-20260101-001:https://example.com/c1-01.pdf"], "meetings": ["test-c1-20260101-001"]},
                "councilCrawlMeta": {"test-c1": {"discoveredAt": "2026/01/01 10:00", "discoverySource": "rule"}},
                "meetingCrawlMeta": {"test-c1-20260101-001": {"discoveredAt": "2026/01/01 10:00", "lastUpdatedFromCrawl": "2026/01/01 12:00"}},
                "rejectedCouncils": [],
                "scrapingRuleTemplates": {},
                "scrapingRules": {
                    "test-c1": {
                        "officialUrl": "https://example.com/c1"
                    }
                }
            }

            # 最初のシード & エクスポートで決定論的フォーマットに初期整形
            fixture_rej = [
                {
                    "id": "test-rej1",
                    "name": "却下テスト会議体1",
                    "ministry": "TEST",
                    "category": "COUNCIL",
                    "officialUrl": "https://example.com/rej1",
                    "rejectedAt": "2026-10-24",
                    "reason": "テスト用却下理由"
                }
            ]
            with open(tmp_pub, "w", encoding="utf-8") as f:
                json.dump(fixture_pub, f, ensure_ascii=False, indent=2)
            with open(tmp_adm, "w", encoding="utf-8") as f:
                json.dump(fixture_adm, f, ensure_ascii=False, indent=2)
            with open(tmp_rej, "w", encoding="utf-8") as f:
                json.dump(fixture_rej, f, ensure_ascii=False, indent=2)

            res_init_seed = subprocess.run([
                sys.executable, str(SEED_SCRIPT),
                "--db", str(tmp_db),
                "--schema", str(SCHEMA_PATH),
                "--public-json", str(tmp_pub),
                "--admin-json", str(tmp_adm),
                "--rejected-json", str(tmp_rej)
            ], capture_output=True, text=True)
            self.assertEqual(res_init_seed.returncode, 0, f"init seed_db failed: {res_init_seed.stderr}")

            res_init_exp = subprocess.run([
                sys.executable, str(EXPORT_SCRIPT),
                "--db", str(tmp_db),
                "--public-json", str(tmp_pub),
                "--admin-json", str(tmp_adm),
                "--rejected-json", str(tmp_rej)
            ], capture_output=True, text=True)
            self.assertEqual(res_init_exp.returncode, 0, f"init export_data failed: {res_init_exp.stderr}")

            pub_before = tmp_pub.read_bytes()
            adm_before = tmp_adm.read_bytes()
            rej_before = tmp_rej.read_bytes()
            hash_pub_before = hashlib.sha256(pub_before).hexdigest()
            hash_adm_before = hashlib.sha256(adm_before).hexdigest()
            hash_rej_before = hashlib.sha256(rej_before).hexdigest()

            # 2回目の再シード & 再エクスポート（完全可逆性の検証）
            res_seed = subprocess.run([
                sys.executable, str(SEED_SCRIPT),
                "--db", str(tmp_db),
                "--schema", str(SCHEMA_PATH),
                "--public-json", str(tmp_pub),
                "--admin-json", str(tmp_adm),
                "--rejected-json", str(tmp_rej)
            ], capture_output=True, text=True)
            self.assertEqual(res_seed.returncode, 0, f"seed_db failed: {res_seed.stderr}")

            res_exp = subprocess.run([
                sys.executable, str(EXPORT_SCRIPT),
                "--db", str(tmp_db),
                "--public-json", str(tmp_pub),
                "--admin-json", str(tmp_adm),
                "--rejected-json", str(tmp_rej)
            ], capture_output=True, text=True)
            self.assertEqual(res_exp.returncode, 0, f"export_data failed: {res_exp.stderr}")

            pub_after = tmp_pub.read_bytes()
            adm_after = tmp_adm.read_bytes()
            hash_pub_after = hashlib.sha256(pub_after).hexdigest()
            hash_adm_after = hashlib.sha256(adm_after).hexdigest()

            rej_after = tmp_rej.read_bytes()
            hash_rej_after = hashlib.sha256(rej_after).hexdigest()

            self.assertEqual(hash_pub_before, hash_pub_after, "Public JSON must remain bitwise identical after re-export")
            self.assertEqual(hash_adm_before, hash_adm_after, "Admin JSON must remain bitwise identical after re-export")
            self.assertEqual(hash_rej_before, hash_rej_after, "Rejected councils JSON must remain bitwise identical after re-export")


if __name__ == "__main__":
    unittest.main()
