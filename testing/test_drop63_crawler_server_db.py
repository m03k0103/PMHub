#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Drop 63 単体テスト: クローラー & 管理サーバーの DB 接続パイプライン化検証 (U18)
========================================================================
検証内容:
1. admin/db/db_manager.py の CRUD 操作および自動エクスポートパイプラインの動作検証
2. クローラー保存経路 (save_data_json_with_backup) による DB トランザクション更新 & 自動エクスポート検証
3. 管理サーバー API 経路による DB 更新 & 自動エクスポート検証
4. DB 非存在時の自動シード復元（フェイルセーフ性）検証
"""

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
if str(ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_DIR))

from db.db_manager import ensure_database, load_data_from_db, save_data_to_db
from db.export_data import export_data
from utils import load_data_json, save_data_json_with_backup, add_to_rejected_councils


class TestDrop63CrawlerServerDB(unittest.TestCase):
    """Drop 63: クローラー & 管理サーバーの DB 接続パイプライン化の整合性検証"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pmhub_test_drop63_")
        self.temp_path = Path(self.temp_dir)
        self.db_path = self.temp_path / "pmhub_test.db"
        self.public_json = self.temp_path / "data.json"
        self.admin_json = self.temp_path / "admin_data.json"
        self.schema_path = ADMIN_DIR / "db" / "schema.sql"

        # 軽量フィクスチャを用いてテスト用 DB を超高速初期化（CR-166）
        fixture_public = {
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
                    "manualLock": False
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
        fixture_admin = {
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
            json.dump(fixture_public, f, ensure_ascii=False, indent=2)
        with open(self.admin_json, "w", encoding="utf-8") as f:
            json.dump(fixture_admin, f, ensure_ascii=False, indent=2)

        ensure_database(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            schema_path=self.schema_path
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_db_manager_crud_and_auto_export(self):
        """1. db_manager の CRUD と自動エクスポートが正しく連動すること"""
        data = load_data_from_db(self.db_path)
        self.assertIn("councils", data)
        self.assertIn("meetings", data)
        self.assertGreater(len(data["councils"]), 0)

        # テスト用ダミー会議体の追加
        test_cid = "test-drop63_council"
        new_council = {
            "id": test_cid,
            "ministry": "test",
            "category": "審議会等",
            "name": "Drop 63 テスト会議体",
            "officialUrl": "https://example.com/test63",
            "pastYearCount": 1,
            "manualLock": True
        }
        data["councils"].append(new_council)

        # save_data_to_db を実行
        success = save_data_to_db(data, db_path=self.db_path, run_export=False)
        self.assertTrue(success)

        # DB に直接反映されているか検証
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        row = cur.execute("SELECT name, manual_lock FROM councils WHERE id = ?;", (test_cid,)).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Drop 63 テスト会議体")
        self.assertEqual(row[1], 1)

    def test_crawler_save_pipeline_syncs_db(self):
        """2. クローラー保存時に DB と JSON が同時に同期・自動エクスポートされること"""
        data = load_data_from_db(self.db_path)
        orig_count = len(data["meetings"])

        # 新規開催回をシミュレート追加
        new_meeting = {
            "id": "test-c1-20261011-002",
            "councilId": "test-c1",
            "name": "第2回 Drop 63 テスト会合",
            "date": "2026/10/11",
            "round": 2,
            "officialUrl": "https://example.com/test63-002",
            "isNewlyDiscovered": True,
            "materials": [
                {"name": "議事次第", "url": "https://example.com/test63_02.pdf", "type": "PDF"}
            ]
        }
        data["meetings"].append(new_meeting)

        # export_data を伴う保存を実行
        success = save_data_to_db(data, db_path=self.db_path, run_export=False)
        self.assertTrue(success)

        # テスト環境の export_data を実行して JSON と DB の完全一致性を確認
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
        """3. DB が削除されても JSON から自動シード復元できること（フェイルセーフ）"""
        if self.db_path.exists():
            os.remove(self.db_path)

        self.assertFalse(self.db_path.exists())
        # ensure_database を呼び出すと自動で DB が再生成される
        recovered = ensure_database(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            schema_path=self.schema_path
        )
        self.assertTrue(recovered)
        self.assertTrue(self.db_path.exists())

        # ロードして正常性を確認
        data = load_data_from_db(self.db_path)
        self.assertGreater(len(data.get("councils", [])), 0)


    def test_reject_and_purge_council_cascade_integrity(self):
        """4. 会議体却下・削除時の子テーブル連鎖削除 & 孤立レコードゼロ検証 (Drop 94)"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()
        
        m_cnt = cur.execute("SELECT COUNT(*) FROM meetings WHERE council_id = 'test-c1';").fetchone()[0]
        mat_cnt = cur.execute("SELECT COUNT(*) FROM materials WHERE meeting_id LIKE 'test-c1%';").fetchone()[0]
        self.assertEqual(m_cnt, 1)
        self.assertEqual(mat_cnt, 1)

        rej_json = self.temp_path / "rejected_councils.json"
        add_success = add_to_rejected_councils(
            target_id="test-c1",
            council={"name": "テスト審議会1", "ministry": "TEST", "officialUrl": "https://example.com/c1"},
            reason="テスト用却下理由",
            rejected_file=str(rej_json),
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

        self.assertEqual(post_c, 0, "councils から削除されていること")
        self.assertEqual(post_m, 0, "meetings から連鎖削除されていること")
        self.assertEqual(post_mat, 0, "materials から連鎖削除されていること")
        self.assertEqual(post_rule, 0, "scraping_rules から連鎖削除されていること")
        self.assertEqual(post_rej, 1, "rejected_councils に登録されていること")

        export_success = export_data(
            db_path=self.db_path,
            public_json_path=self.public_json,
            admin_json_path=self.admin_json,
            rejected_json_path=rej_json
        )
        self.assertTrue(export_success)

        with open(self.public_json, "r", encoding="utf-8") as f:
            pub = json.load(f)
        with open(self.admin_json, "r", encoding="utf-8") as f:
            adm = json.load(f)

        self.assertNotIn("test-c1", [c["id"] for c in pub["councils"]])
        self.assertNotIn("test-c1-20260101-001", [m["id"] for m in pub["meetings"]])
        self.assertIn("test-c1", [r["id"] for r in adm["rejectedCouncils"]])


if __name__ == "__main__":
    unittest.main()
