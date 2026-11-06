#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub Database Synchronization Unit Tests (test_sync_from_json.py) [U14]
========================================================================
Validates sync_from_json.py functionality:
- Inserts new councils, meetings, and materials from JSON datasets.
- Preserves downloaded PMM file status (download_status='downloaded', local_path, etc.).
- Respects manualLock=1 records.
- Verifies dry-run non-destructiveness.
- Synchronizes admin configurations and scraping rules.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "admin"))

from admin.db.seed_db import init_db
from admin.db.sync_from_json import sync_database


class TestSyncFromJson(unittest.TestCase):
    """Unit tests for admin/db/sync_from_json.py [U14]."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_pmhub.db"
        self.schema_path = BASE_DIR / "admin" / "db" / "schema.sql"
        self.public_json_path = Path(self.temp_dir) / "data.json"
        self.archive_json_path = Path(self.temp_dir) / "data_archive.json"
        self.admin_json_path = Path(self.temp_dir) / "admin_data.json"

        # Initialize clean test DB
        conn = init_db(self.db_path, self.schema_path)
        cur = conn.cursor()

        # Seed initial council
        cur.execute(
            """
            INSERT INTO councils (id, ministry, category, name, official_url, manual_lock)
            VALUES ('cas-test_c', 'CAS', 'COUNCIL', 'テスト会議体', 'https://example.com/cas', 0)
            """
        )
        # Seed locked council
        cur.execute(
            """
            INSERT INTO councils (id, ministry, category, name, official_url, manual_lock)
            VALUES ('cas-locked_c', 'CAS', 'COUNCIL', '手動保護会議体', 'https://example.com/locked', 1)
            """
        )
        # Seed initial meeting
        cur.execute(
            """
            INSERT INTO meetings (id, council_id, name, date, round, manual_lock)
            VALUES ('cas-test_c-20260401-001', 'cas-test_c', '第1回 テスト会合', '2026/04/01', 1, 0)
            """
        )
        # Seed material with PMM downloaded status
        cur.execute(
            """
            INSERT INTO materials (
                meeting_id, name, url, type, manual_lock, local_path,
                download_status, file_size, downloaded_at
            ) VALUES (
                'cas-test_c-20260401-001', '第1回議事次第.pdf', 'https://example.com/doc1.pdf',
                'PDF', 0, 'local_docs/内閣官房/テスト会議体/20260401/第1回議事次第.pdf',
                'downloaded', 10240, '2026-04-01 12:00:00'
            )
            """
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sync_inserts_new_meeting_and_materials(self):
        """リモートで新規追加された開催回および配付資料が DB へ正しく INSERT されること"""
        mock_public = {
            "councils": [
                {"id": "cas-test_c", "name": "テスト会議体", "ministry": "CAS", "officialUrl": "https://example.com/cas"}
            ],
            "meetings": [
                {
                    "id": "cas-test_c-20260401-001",
                    "councilId": "cas-test_c",
                    "name": "第1回 テスト会合",
                    "date": "2026/04/01",
                    "materials": [
                        {"name": "第1回議事次第.pdf", "url": "https://example.com/doc1.pdf", "type": "PDF"}
                    ]
                },
                # 新着開催回
                {
                    "id": "cas-test_c-20260501-002",
                    "councilId": "cas-test_c",
                    "name": "第2回 テスト会合",
                    "date": "2026/05/01",
                    "materials": [
                        {"name": "第2回議事次第.pdf", "url": "https://example.com/doc2.pdf", "type": "PDF"}
                    ]
                }
            ]
        }
        with open(self.public_json_path, "w", encoding="utf-8") as f:
            json.dump(mock_public, f)

        stats = sync_database(
            db_path=self.db_path,
            public_json_path=self.public_json_path,
            archive_json_path=self.archive_json_path,
            admin_json_path=self.admin_json_path,
            dry_run=False,
            verbose=False
        )

        self.assertEqual(stats["meetings_inserted"], 1)
        self.assertEqual(stats["materials_inserted"], 1)

        # Verify DB content
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM meetings WHERE id = 'cas-test_c-20260501-002'")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[1], "第2回 テスト会合")

        cur.execute("SELECT download_status FROM materials WHERE url = 'https://example.com/doc2.pdf'")
        m_row = cur.fetchone()
        self.assertIsNotNone(m_row)
        self.assertEqual(m_row[0], "pending")
        conn.close()

    def test_sync_preserves_downloaded_pmm_assets(self):
        """既にダウンロード済みの PMM 配付資料ファイル情報（downloaded, local_path等）が保護されること"""
        mock_public = {
            "councils": [
                {"id": "cas-test_c", "name": "テスト会議体", "ministry": "CAS"}
            ],
            "meetings": [
                {
                    "id": "cas-test_c-20260401-001",
                    "councilId": "cas-test_c",
                    "name": "第1回 テスト会合 (改名)",
                    "date": "2026/04/01",
                    "materials": [
                        # JSON 側にはローカル保存パス情報は存在しない
                        {"name": "第1回議事次第.pdf", "url": "https://example.com/doc1.pdf", "type": "PDF"}
                    ]
                }
            ]
        }
        with open(self.public_json_path, "w", encoding="utf-8") as f:
            json.dump(mock_public, f)

        stats = sync_database(
            db_path=self.db_path,
            public_json_path=self.public_json_path,
            archive_json_path=self.archive_json_path,
            admin_json_path=self.admin_json_path,
            dry_run=False,
            verbose=False
        )

        self.assertEqual(stats["materials_pmm_preserved"], 1)

        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute(
            "SELECT download_status, local_path, file_size, downloaded_at "
            "FROM materials WHERE url = 'https://example.com/doc1.pdf'"
        )
        row = cur.fetchone()
        self.assertEqual(row[0], "downloaded", "download_status が downloaded のまま維持されること")
        self.assertEqual(row[1], "local_docs/内閣官房/テスト会議体/20260401/第1回議事次第.pdf")
        self.assertEqual(row[2], 10240)
        self.assertEqual(row[3], "2026-04-01 12:00:00")
        conn.close()

    def test_sync_respects_manual_lock(self):
        """manual_lock = 1 の会議体レコードが保護され上書きされないこと"""
        mock_public = {
            "councils": [
                {"id": "cas-locked_c", "name": "上書きされた名称", "ministry": "CAS"}
            ],
            "meetings": []
        }
        with open(self.public_json_path, "w", encoding="utf-8") as f:
            json.dump(mock_public, f)

        stats = sync_database(
            db_path=self.db_path,
            public_json_path=self.public_json_path,
            archive_json_path=self.archive_json_path,
            admin_json_path=self.admin_json_path,
            dry_run=False,
            verbose=False
        )

        self.assertEqual(stats["councils_skipped_lock"], 1)

        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM councils WHERE id = 'cas-locked_c'")
        row = cur.fetchone()
        self.assertEqual(row[0], "手動保護会議体", "manual_lock=1 のため名称が元のまま保護されること")
        conn.close()

    def test_sync_dry_run_does_not_modify_database(self):
        """--dry-run 実行時に DB が一切変更されないこと"""
        mock_public = {
            "councils": [
                {"id": "cas-new_c", "name": "新規会議体", "ministry": "CAS"}
            ],
            "meetings": []
        }
        with open(self.public_json_path, "w", encoding="utf-8") as f:
            json.dump(mock_public, f)

        stats = sync_database(
            db_path=self.db_path,
            public_json_path=self.public_json_path,
            archive_json_path=self.archive_json_path,
            admin_json_path=self.admin_json_path,
            dry_run=True,
            verbose=False
        )

        self.assertEqual(stats["councils_inserted"], 1)

        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("SELECT id FROM councils WHERE id = 'cas-new_c'")
        row = cur.fetchone()
        self.assertIsNone(row, "dry-run のため DB にコミットされていないこと")
        conn.close()


if __name__ == "__main__":
    unittest.main()
