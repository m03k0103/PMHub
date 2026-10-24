#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit test for Drop 82: PMM local material download status preservation.
Verifies that:
1. seed_db() preserves download_status, local_path, file_size, downloaded_at across database re-seeding.
2. save_data_to_db() uses ON CONFLICT DO UPDATE on councils and meetings without triggering CASCADE DELETE on child materials.
3. council_materials are preserved non-destructively in save_data_to_db().
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from admin.db.db_manager import (
    save_data_to_db,
    update_materials_download_batch,
    update_council_materials_download_batch,
    get_materials_download_summary
)
from admin.db.seed_db import init_db, seed_db
from admin.pmm.downloader import sync_local_materials_status

SCHEMA_PATH = BASE_DIR / "admin" / "db" / "schema.sql"


class TestPmmPreservation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)
        self.db_path = self.dir_path / "test_pmhub.db"
        self.public_json = self.dir_path / "data.json"
        self.admin_json = self.dir_path / "admin_data.json"
        self.rejected_json = self.dir_path / "rejected_councils.json"
        self.local_docs = self.dir_path / "local_docs"
        self.local_docs.mkdir()

        # Create sample public dataset
        self.sample_data = {
            "lastCrawlTime": "2026/10/24 12:00",
            "ministries": {
                "TEST": {"name": "テスト省", "slug": "test"}
            },
            "councils": [
                {
                    "id": "test-council_a",
                    "name": "テスト審議会A",
                    "ministry": "TEST",
                    "category": "審議会",
                    "officialUrl": "https://example.com/council_a",
                    "materials": [
                        {"name": "設置要領", "url": "https://example.com/council_mat.pdf", "type": "PDF"}
                    ]
                }
            ],
            "meetings": [
                {
                    "id": "test-council_a-20261024-001",
                    "councilId": "test-council_a",
                    "name": "第1回 テスト審議会A",
                    "date": "2026/10/24",
                    "round": 1,
                    "officialUrl": "https://example.com/meeting1",
                    "materials": [
                        {"name": "議事次第", "url": "https://example.com/mat1.pdf", "type": "PDF"},
                        {"name": "配付資料1", "url": "https://example.com/mat2.pdf", "type": "PDF"}
                    ]
                }
            ],
            "rejectedCouncils": []
        }

        with open(self.public_json, "w", encoding="utf-8") as f:
            json.dump(self.sample_data, f, ensure_ascii=False, indent=2)
        with open(self.admin_json, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        with open(self.rejected_json, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_db_preserves_download_status(self):
        """Test that seed_db() preserves download_status, local_path, etc. across re-seeding."""
        # 1. Initial seed
        success = seed_db(
            db_path=self.db_path,
            schema_path=SCHEMA_PATH,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        )
        self.assertTrue(success, "Initial seed must succeed")

        # 2. Update status to 'downloaded'
        update_materials_download_batch([
            {
                "meeting_id": "test-council_a-20261024-001",
                "url": "https://example.com/mat1.pdf",
                "local_path": "テスト省/テスト審議会A/20261024_001/議事次第.pdf",
                "download_status": "downloaded",
                "file_size": 10240,
                "downloaded_at": "2026-10-24 12:00:00"
            }
        ], db_path=self.db_path)

        update_council_materials_download_batch([
            {
                "council_id": "test-council_a",
                "url": "https://example.com/council_mat.pdf",
                "local_path": "テスト省/テスト審議会A/00_会議体資料/設置要領.pdf",
                "download_status": "downloaded",
                "file_size": 20480,
                "downloaded_at": "2026-10-24 12:00:00"
            }
        ], db_path=self.db_path)

        # Verify statuses are set
        conn = sqlite3.connect(str(self.db_path))
        m_row = conn.execute("SELECT download_status, local_path, file_size FROM materials WHERE url = 'https://example.com/mat1.pdf';").fetchone()
        self.assertEqual(m_row[0], "downloaded")
        self.assertEqual(m_row[1], "テスト省/テスト審議会A/20261024_001/議事次第.pdf")
        self.assertEqual(m_row[2], 10240)

        cm_row = conn.execute("SELECT download_status, local_path, file_size FROM council_materials WHERE url = 'https://example.com/council_mat.pdf';").fetchone()
        self.assertEqual(cm_row[0], "downloaded")
        self.assertEqual(cm_row[1], "テスト省/テスト審議会A/00_会議体資料/設置要領.pdf")
        self.assertEqual(cm_row[2], 20480)
        conn.close()

        # 3. Re-run seed_db() on the existing DB
        reseed_success = seed_db(
            db_path=self.db_path,
            schema_path=SCHEMA_PATH,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        )
        self.assertTrue(reseed_success, "Re-seed must succeed")

        # 4. Verify statuses are STILL preserved after re-seeding
        conn = sqlite3.connect(str(self.db_path))
        m_row2 = conn.execute("SELECT download_status, local_path, file_size FROM materials WHERE url = 'https://example.com/mat1.pdf';").fetchone()
        self.assertEqual(m_row2[0], "downloaded", "Material download_status must be preserved across seed_db()")
        self.assertEqual(m_row2[1], "テスト省/テスト審議会A/20261024_001/議事次第.pdf")
        self.assertEqual(m_row2[2], 10240)

        cm_row2 = conn.execute("SELECT download_status, local_path, file_size FROM council_materials WHERE url = 'https://example.com/council_mat.pdf';").fetchone()
        self.assertEqual(cm_row2[0], "downloaded", "Council material download_status must be preserved across seed_db()")
        self.assertEqual(cm_row2[1], "テスト省/テスト審議会A/00_会議体資料/設置要領.pdf")
        self.assertEqual(cm_row2[2], 20480)
        conn.close()

    def test_save_data_to_db_does_not_cascade_delete_materials(self):
        """Test that save_data_to_db() performs in-place update without wiping materials."""
        # 1. Initial seed
        seed_db(
            db_path=self.db_path,
            schema_path=SCHEMA_PATH,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        )

        # 2. Mark material as downloaded
        update_materials_download_batch([
            {
                "meeting_id": "test-council_a-20261024-001",
                "url": "https://example.com/mat1.pdf",
                "local_path": "some/path.pdf",
                "download_status": "downloaded",
                "file_size": 5555,
                "downloaded_at": "2026-10-24 12:00:00"
            }
        ], db_path=self.db_path)

        update_council_materials_download_batch([
            {
                "council_id": "test-council_a",
                "url": "https://example.com/council_mat.pdf",
                "local_path": "some/council_path.pdf",
                "download_status": "downloaded",
                "file_size": 7777,
                "downloaded_at": "2026-10-24 12:00:00"
            }
        ], db_path=self.db_path)

        # 3. Call save_data_to_db (simulating crawler saving newly crawled data)
        updated_data = json.loads(json.dumps(self.sample_data))
        updated_data["meetings"][0]["name"] = "第1回 テスト審議会A (タイトル更新)"
        save_success = save_data_to_db(updated_data, db_path=self.db_path, run_export=False)
        self.assertTrue(save_success)

        # 4. Verify materials were NOT wiped by CASCADE DELETE
        conn = sqlite3.connect(str(self.db_path))
        m_row = conn.execute("SELECT download_status, local_path, file_size FROM materials WHERE url = 'https://example.com/mat1.pdf';").fetchone()
        self.assertIsNotNone(m_row, "Material row must not be deleted")
        self.assertEqual(m_row[0], "downloaded", "Material download_status must be retained after save_data_to_db()")
        self.assertEqual(m_row[1], "some/path.pdf")
        self.assertEqual(m_row[2], 5555)

        cm_row = conn.execute("SELECT download_status, local_path, file_size FROM council_materials WHERE url = 'https://example.com/council_mat.pdf';").fetchone()
        self.assertIsNotNone(cm_row, "Council material row must not be deleted")
        self.assertEqual(cm_row[0], "downloaded", "Council material download_status must be retained after save_data_to_db()")
        self.assertEqual(cm_row[1], "some/council_path.pdf")
        self.assertEqual(cm_row[2], 7777)
        conn.close()


if __name__ == "__main__":
    unittest.main()
