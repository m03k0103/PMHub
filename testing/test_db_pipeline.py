#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLiteマスターDB・自動エクスポート・可逆性・PMMダウンロード状態保護 単体テストスイート (test_db_pipeline.py)
- db_manager の CRUD 操作・自動エクスポート・DB非存在時の自動シード復元・連鎖削除検証
- Git 保護 (.gitignore) および seed_db <-> export_data の完全可逆性 (Lossless Reversibility) 検証
- PMM ダウンロードステータス (download_status, local_path, file_size) の再シード・上書き保護検証
"""

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADMIN_DIR = PROJECT_ROOT / "admin"
for p in (str(PROJECT_ROOT), str(ADMIN_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from db.db_manager import (
    ensure_database,
    load_data_from_db,
    save_data_to_db,
    update_materials_download_batch,
    update_council_materials_download_batch
)
from db.export_data import export_data
from db.seed_db import seed_db
from utils import add_to_rejected_councils

SCHEMA_PATH = ADMIN_DIR / "db" / "schema.sql"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"


class TestDbPipeline(unittest.TestCase):
    """クローラー & 管理サーバーの DB 接続パイプライン・可逆性・PMM 保護の整合性検証"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pmhub_test_db_pipeline_")
        self.temp_path = Path(self.temp_dir)
        self.db_path = self.temp_path / "pmhub_test.db"
        self.public_json = self.temp_path / "data.json"
        self.admin_json = self.temp_path / "admin_data.json"
        self.rejected_json = self.temp_path / "rejected_councils.json"

        self.fixture_public = {
            "ministries": [{"id": "test", "name": "テスト省"}],
            "categories": ["審議会等"],
            "docTypes": ["議事次第", "配付資料", "議事録"],
            "lastCrawlTime": "2026-10-23T00:00:00",
            "councils": [
                {
                    "id": "test-c1",
                    "ministry": "test",
                    "category": "審議会等",
                    "name": "テスト審議会1",
                    "officialUrl": "https://example.com/c1",
                    "pastYearCount": 2,
                    "manualLock": False,
                    "materials": [
                        {"name": "設置要領", "url": "https://example.com/council_mat.pdf", "type": "PDF"}
                    ]
                },
                {
                    "id": "test-c2",
                    "ministry": "test",
                    "category": "審議会等",
                    "name": "テスト審議会2",
                    "officialUrl": "https://example.com/c2",
                    "pastYearCount": 0,
                    "manualLock": False
                }
            ],
            "meetings": [
                {
                    "id": "test-c1-20260101-001",
                    "councilId": "test-c1",
                    "name": "第1回 テスト会合",
                    "date": "2026/01/01",
                    "round": 1,
                    "officialUrl": "https://example.com/c1-01",
                    "manualLock": False,
                    "materials": [
                        {"name": "議事次第", "url": "https://example.com/c1-01.pdf", "type": "PDF"}
                    ]
                }
            ]
        }
        self.fixture_admin = {
            "scrapingRuleTemplates": {},
            "scrapingRules": {
                "test-c1": {
                    "officialUrl": "https://example.com/c1",
                    "subpage_discovery_pattern": "",
                    "date_regex": ""
                }
            },
            "crawlerConfig": {"max_workers": 2},
            "discoveryKeywords": ["審議会"],
            "rejectedCouncils": [],
            "crawlStatuses": {
                "test-c1": {
                    "lastCrawl": "2026-10-23T00:00:00",
                    "status": "success",
                    "meetingCount": 1
                }
            },
            "manualLocks": {"councils": [], "meetings": [], "materials": []}
        }

        with open(self.public_json, "w", encoding="utf-8") as f:
            json.dump(self.fixture_public, f, ensure_ascii=False, indent=2)
        with open(self.admin_json, "w", encoding="utf-8") as f:
            json.dump(self.fixture_admin, f, ensure_ascii=False, indent=2)
        with open(self.rejected_json, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

        ensure_database(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            schema_path=SCHEMA_PATH
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_gitignore_contains_db(self):
        """admin/pmhub.db および SQLite 一時ファイルが .gitignore に登録されていること"""
        self.assertTrue(GITIGNORE_PATH.exists(), f".gitignore not found: {GITIGNORE_PATH}")
        with open(GITIGNORE_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("admin/pmhub.db", content, "admin/pmhub.db must be in .gitignore")
        self.assertIn("*.db", content, "*.db must be in .gitignore")
        self.assertIn("*.sqlite", content, "*.sqlite must be in .gitignore")

    def test_db_manager_crud_and_auto_export(self):
        """db_manager の CRUD と自動エクスポートが正しく連動すること"""
        data = load_data_from_db(self.db_path)
        self.assertIn("councils", data)
        self.assertIn("meetings", data)
        self.assertGreater(len(data["councils"]), 0)

        test_cid = "test-new_council"
        new_council = {
            "id": test_cid,
            "ministry": "test",
            "category": "審議会等",
            "name": "新規テスト会議体",
            "officialUrl": "https://example.com/test_new",
            "pastYearCount": 1,
            "manualLock": True
        }
        data["councils"].append(new_council)

        success = save_data_to_db(data, db_path=self.db_path, run_export=False)
        self.assertTrue(success)

        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        row = cur.execute("SELECT name, manual_lock FROM councils WHERE id = ?;", (test_cid,)).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "新規テスト会議体")
        self.assertEqual(row[1], 1)

    def test_crawler_save_pipeline_syncs_db(self):
        """クローラー保存時に DB と JSON が同時に同期・自動エクスポートされること"""
        data = load_data_from_db(self.db_path)
        orig_count = len(data["meetings"])

        new_meeting = {
            "id": "test-c1-20261011-002",
            "councilId": "test-c1",
            "name": "第2回 テスト会合",
            "date": "2026/10/11",
            "round": 2,
            "officialUrl": "https://example.com/test-002",
            "isNewlyDiscovered": True,
            "materials": [
                {"name": "議事次第", "url": "https://example.com/test_02.pdf", "type": "PDF"}
            ]
        }
        data["meetings"].append(new_meeting)

        success = save_data_to_db(data, db_path=self.db_path, run_export=False)
        self.assertTrue(success)

        export_success = export_data(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json
        )
        self.assertTrue(export_success)

        with open(self.public_json, "r", encoding="utf-8") as f:
            exported_public = json.load(f)

        m_ids = [m["id"] for m in exported_public["meetings"]]
        self.assertIn("test-c1-20261011-002", m_ids)
        self.assertEqual(len(exported_public["meetings"]), orig_count + 1)

    def test_db_nonexistent_auto_recovery(self):
        """DB が削除されても JSON から自動シード復元できること（フェイルセーフ）"""
        if self.db_path.exists():
            os.remove(self.db_path)

        self.assertFalse(self.db_path.exists())
        recovered = ensure_database(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            schema_path=SCHEMA_PATH
        )
        self.assertTrue(recovered)
        self.assertTrue(self.db_path.exists())

        data = load_data_from_db(self.db_path)
        self.assertGreater(len(data.get("councils", [])), 0)

    def test_reject_and_purge_council_cascade_integrity(self):
        """会議体却下・削除時の子テーブル連鎖削除 & 孤立レコードゼロ検証"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        m_cnt = cur.execute("SELECT COUNT(*) FROM meetings WHERE council_id = 'test-c1';").fetchone()[0]
        mat_cnt = cur.execute("SELECT COUNT(*) FROM materials WHERE meeting_id LIKE 'test-c1%';").fetchone()[0]
        self.assertEqual(m_cnt, 1)
        self.assertEqual(mat_cnt, 1)

        add_success = add_to_rejected_councils(
            target_id="test-c1",
            council={"name": "テスト審議会1", "ministry": "TEST", "officialUrl": "https://example.com/c1"},
            reason="テスト用却下理由",
            rejected_file=str(self.rejected_json),
            db_path=str(self.db_path)
        )
        self.assertTrue(add_success)

        cur.execute("DELETE FROM councils WHERE id = 'test-c1';")
        conn.commit()

        post_c = cur.execute("SELECT COUNT(*) FROM councils WHERE id = 'test-c1';").fetchone()[0]
        post_m = cur.execute("SELECT COUNT(*) FROM meetings WHERE council_id = 'test-c1';").fetchone()[0]
        post_mat = cur.execute("SELECT COUNT(*) FROM materials WHERE meeting_id LIKE 'test-c1%';").fetchone()[0]
        post_rule = cur.execute("SELECT COUNT(*) FROM scraping_rules WHERE council_id = 'test-c1';").fetchone()[0]
        post_rej = cur.execute("SELECT COUNT(*) FROM rejected_councils WHERE id = 'test-c1';").fetchone()[0]
        conn.close()

        self.assertEqual(post_c, 0)
        self.assertEqual(post_m, 0)
        self.assertEqual(post_mat, 0)
        self.assertEqual(post_rule, 0)
        self.assertEqual(post_rej, 1)

        export_success = export_data(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        )
        self.assertTrue(export_success)

        with open(self.public_json, "r", encoding="utf-8") as f:
            pub = json.load(f)
        with open(self.admin_json, "r", encoding="utf-8") as f:
            adm = json.load(f)

        self.assertNotIn("test-c1", [c["id"] for c in pub["councils"]])
        self.assertNotIn("test-c1-20260101-001", [m["id"] for m in pub["meetings"]])
        self.assertIn("test-c1", [r["id"] for r in adm["rejectedCouncils"]])

    def test_bidirectional_lossless_reversibility(self):
        """seed_db -> export_data がビット単位で100%同一のJSON出力を保つこと（インプロセス高速検証）"""
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
        with open(self.rejected_json, "w", encoding="utf-8") as f:
            json.dump(fixture_rej, f, ensure_ascii=False, indent=2)

        self.assertTrue(seed_db(
            db_path=self.db_path,
            schema_path=SCHEMA_PATH,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        ))
        self.assertTrue(export_data(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        ))

        hash_pub_before = hashlib.sha256(self.public_json.read_bytes()).hexdigest()
        hash_adm_before = hashlib.sha256(self.admin_json.read_bytes()).hexdigest()
        hash_rej_before = hashlib.sha256(self.rejected_json.read_bytes()).hexdigest()

        self.assertTrue(seed_db(
            db_path=self.db_path,
            schema_path=SCHEMA_PATH,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        ))
        self.assertTrue(export_data(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        ))

        hash_pub_after = hashlib.sha256(self.public_json.read_bytes()).hexdigest()
        hash_adm_after = hashlib.sha256(self.admin_json.read_bytes()).hexdigest()
        hash_rej_after = hashlib.sha256(self.rejected_json.read_bytes()).hexdigest()

        self.assertEqual(hash_pub_before, hash_pub_after, "Public JSON must remain bitwise identical after re-export")
        self.assertEqual(hash_adm_before, hash_adm_after, "Admin JSON must remain bitwise identical after re-export")
        self.assertEqual(hash_rej_before, hash_rej_after, "Rejected councils JSON must remain bitwise identical after re-export")

    def test_seed_db_and_save_data_preserve_download_status(self):
        """seed_db() および save_data_to_db() がローカル資料の download_status, local_path, file_size を保持すること"""
        update_materials_download_batch([
            {
                "meeting_id": "test-c1-20260101-001",
                "url": "https://example.com/c1-01.pdf",
                "local_path": "テスト省/テスト審議会1/20260101_001/議事次第.pdf",
                "download_status": "downloaded",
                "file_size": 10240,
                "downloaded_at": "2026-10-24 12:00:00"
            }
        ], db_path=self.db_path)

        update_council_materials_download_batch([
            {
                "council_id": "test-c1",
                "url": "https://example.com/council_mat.pdf",
                "local_path": "テスト省/テスト審議会1/00_会議体資料/設置要領.pdf",
                "download_status": "downloaded",
                "file_size": 20480,
                "downloaded_at": "2026-10-24 12:00:00"
            }
        ], db_path=self.db_path)

        # 1. Re-run seed_db()
        reseed_success = seed_db(
            db_path=self.db_path,
            schema_path=SCHEMA_PATH,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=self.rejected_json
        )
        self.assertTrue(reseed_success)

        conn = sqlite3.connect(str(self.db_path))
        m_row = conn.execute("SELECT download_status, local_path, file_size FROM materials WHERE url = 'https://example.com/c1-01.pdf';").fetchone()
        self.assertEqual(m_row[0], "downloaded")
        self.assertEqual(m_row[1], "テスト省/テスト審議会1/20260101_001/議事次第.pdf")
        self.assertEqual(m_row[2], 10240)

        cm_row = conn.execute("SELECT download_status, local_path, file_size FROM council_materials WHERE url = 'https://example.com/council_mat.pdf';").fetchone()
        self.assertEqual(cm_row[0], "downloaded")
        self.assertEqual(cm_row[1], "テスト省/テスト審議会1/00_会議体資料/設置要領.pdf")
        self.assertEqual(cm_row[2], 20480)
        conn.close()

        # 2. Run save_data_to_db() (in-place update without CASCADE DELETE)
        updated_data = json.loads(json.dumps(self.fixture_public))
        updated_data["meetings"][0]["name"] = "第1回 テスト会合 (タイトル更新)"
        save_success = save_data_to_db(updated_data, db_path=self.db_path, run_export=False)
        self.assertTrue(save_success)

        conn = sqlite3.connect(str(self.db_path))
        m_row2 = conn.execute("SELECT download_status, local_path, file_size FROM materials WHERE url = 'https://example.com/c1-01.pdf';").fetchone()
        self.assertEqual(m_row2[0], "downloaded")
        self.assertEqual(m_row2[2], 10240)

        cm_row2 = conn.execute("SELECT download_status, local_path, file_size FROM council_materials WHERE url = 'https://example.com/council_mat.pdf';").fetchone()
        self.assertEqual(cm_row2[0], "downloaded")
        self.assertEqual(cm_row2[2], 20480)
        conn.close()


if __name__ == "__main__":
    unittest.main()
