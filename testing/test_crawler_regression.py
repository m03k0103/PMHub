#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - クロール回帰テストスイート (test_crawler_regression.py)

手動で追加・更新された会議体 (COUNCILS)、会議 (MEETINGS)、資料 (MATERIALS) について、
クローラーの処理 (deduplicate_data_materials, update_crawl_status, apply_report) を
実行した場合にも、手動登録データが上書き・破損・削除されず完全同一に保護されるかを自動検証する。
"""

import sys
import os
import json
import copy
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")
sys.path.insert(0, ADMIN_DIR)
from utils import setup_win32_utf8, load_data_json
setup_win32_utf8()


from crawler import deduplicate_data_materials, update_crawl_status, sync_new_meetings_from_crawl
from apply_report import apply_report

class TestCrawlerManualLockProtection(unittest.TestCase):

    def test_deduplicate_materials_respects_meeting_manual_lock(self):
        """manualLock: true の会議は deduplicate_data_materials による資料削除・移動から保護されること"""
        mock_data = {
            "councils": [
                {"id": "test-council_1", "name": "テスト会議体", "url": "https://example.com/portal"}
            ],
            "meetings": [
                {
                    "id": "test-council_1-20260101-001",
                    "councilId": "test-council_1",
                    "name": "第1回 テスト会議",
                    "date": "2026/01/01",
                    "manualLock": True,  # 手動保護
                    "materials": [
                        {"name": "報道発表特別資料", "url": "https://example.com/shared.pdf", "manualLock": True},
                        {"name": "通常資料", "url": "https://example.com/doc1.pdf"}
                    ]
                },
                {
                    "id": "test-council_1-20260201-002",
                    "councilId": "test-council_1",
                    "name": "第2回 テスト会議",
                    "date": "2026/02/01",
                    "manualLock": False,
                    "materials": [
                        {"name": "重複資料", "url": "https://example.com/shared.pdf"}
                    ]
                }
            ]
        }

        # クローラーの重複排除を実行
        deduplicate_data_materials(mock_data)

        # test-council_1-20260101-001 (locked) の資料がすべて残っていることを検証
        m1 = mock_data["meetings"][0]
        self.assertEqual(len(m1["materials"]), 2, "manualLock: true の会議資料は削除されてはいけない")
        self.assertEqual(m1["materials"][0]["url"], "https://example.com/shared.pdf")
        self.assertEqual(m1["materials"][1]["url"], "https://example.com/doc1.pdf")

    def test_deduplicate_materials_respects_material_manual_lock(self):
        """material 単体に manualLock: true が設定されている場合も重複排除から除外されること"""
        mock_data = {
            "councils": [
                {"id": "test-council_2", "name": "テスト会議体2", "url": "https://example.com/portal"}
            ],
            "meetings": [
                {
                    "id": "test-council_2-20260101-001",
                    "councilId": "test-council_2",
                    "name": "第1回 テスト会議",
                    "date": "2026/01/01",
                    "manualLock": False,
                    "materials": [
                        {"name": "手動保護資料", "url": "https://example.com/shared2.pdf", "manualLock": True}
                    ]
                },
                {
                    "id": "test-council_2-20260201-002",
                    "councilId": "test-council_2",
                    "name": "第2回 テスト会議",
                    "date": "2026/02/01",
                    "manualLock": False,
                    "materials": [
                        {"name": "通常資料", "url": "https://example.com/shared2.pdf"}
                    ]
                }
            ]
        }

        deduplicate_data_materials(mock_data)

        # test-council_2-20260101-001 の手動保護資料が残っていること
        m2_1 = mock_data["meetings"][0]
        self.assertEqual(len(m2_1["materials"]), 1)
        self.assertEqual(m2_1["materials"][0]["name"], "手動保護資料")

    def test_apply_report_skips_locked_council_and_meeting(self):
        """apply_report は manualLock: true の会議体および会議を JSON および SQLite DB 双方で保護すること (Drop 94)"""
        import tempfile
        import sqlite3
        from pathlib import Path
        try:
            from db.db_manager import ensure_database, save_data_to_db
        except ImportError:
            from admin.db.db_manager import ensure_database, save_data_to_db

        temp_dir = tempfile.mkdtemp(prefix="pmhub_test_apply_")
        t_path = Path(temp_dir)
        data_path = str(t_path / "data.json")
        admin_path = str(t_path / "admin_data.json")
        db_path = str(t_path / "test.db")
        schema_path = os.path.join(ADMIN_DIR, "db", "schema.sql")

        temp_data = {
            "councils": [
                {
                    "id": "test-locked_council",
                    "ministry": "TEST",
                    "category": "審議会等",
                    "name": "手動保護会議体",
                    "officialUrl": "https://example.com/manual-url",
                    "manualLock": True
                },
                {
                    "id": "test-unlocked_council",
                    "ministry": "TEST",
                    "category": "審議会等",
                    "name": "非保護会議体",
                    "officialUrl": "https://example.com/old-url",
                    "manualLock": False
                }
            ],
            "meetings": [
                {
                    "id": "test-locked_council-20260101-001",
                    "councilId": "test-locked_council",
                    "name": "第1回 テスト会合",
                    "date": "2026/01/01",
                    "officialUrl": "https://example.com/manual-meeting",
                    "manualLock": True,
                    "materials": []
                }
            ]
        }

        with open(data_path, "w", encoding="utf-8") as df:
            json.dump(temp_data, df, ensure_ascii=False, indent=2)
        with open(admin_path, "w", encoding="utf-8") as af:
            json.dump({}, af, ensure_ascii=False, indent=2)

        ensure_database(db_path=Path(db_path), public_json_path=Path(data_path), admin_json_path=Path(admin_path), schema_path=Path(schema_path))

        report_data = {
            "_format": "pmhub-verification-report-v2",
            "corrections": [
                {
                    "action": "update_field",
                    "target": "COUNCILS",
                    "targetId": "test-locked_council",
                    "field": "officialUrl",
                    "newValue": "https://example.com/overwritten"
                },
                {
                    "action": "update_field",
                    "target": "COUNCILS",
                    "targetId": "test-unlocked_council",
                    "field": "officialUrl",
                    "newValue": "https://example.com/new-url"
                },
                {
                    "action": "update_field",
                    "target": "MEETINGS",
                    "targetId": "test-locked_council-20260101-001",
                    "field": "officialUrl",
                    "newValue": "https://example.com/overwritten-meeting"
                }
            ]
        }

        report_path = str(t_path / "report.json")
        with open(report_path, "w", encoding="utf-8") as rf:
            json.dump(report_data, rf, ensure_ascii=False, indent=2)

        try:
            apply_report(report_path, data_json_path=data_path, db_path=db_path)

            with open(data_path, "r", encoding="utf-8") as res_f:
                updated = json.load(res_f)

            # JSON 検証: test-locked_council は上書きされていないこと
            lc = next(c for c in updated["councils"] if c["id"] == "test-locked_council")
            self.assertEqual(lc["officialUrl"], "https://example.com/manual-url", "locked council の URL は保護されるべき")

            # JSON 検証: test-unlocked_council は更新されていること
            uc = next(c for c in updated["councils"] if c["id"] == "test-unlocked_council")
            self.assertEqual(uc["officialUrl"], "https://example.com/new-url", "unlocked council は更新されるべき")

            # JSON 検証: test-locked_council-20260101-001 は上書きされていないこと
            lm = next(m for m in updated["meetings"] if m["id"] == "test-locked_council-20260101-001")
            self.assertEqual(lm["officialUrl"], "https://example.com/manual-meeting", "locked meeting の URL は保護されるべき")

            # SQLite DB 検証: DB 内のレコードも manualLock を遵守して更新/保護されていること
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            db_lc = cur.execute("SELECT official_url, manual_lock FROM councils WHERE id = 'test-locked_council';").fetchone()
            self.assertEqual(db_lc[0], "https://example.com/manual-url", "DB 内の locked council URL が保護されていること")
            self.assertEqual(db_lc[1], 1)

            db_uc = cur.execute("SELECT official_url, manual_lock FROM councils WHERE id = 'test-unlocked_council';").fetchone()
            self.assertEqual(db_uc[0], "https://example.com/new-url", "DB 内の unlocked council URL が更新されていること")
            self.assertEqual(db_uc[1], 0)

            db_lm = cur.execute("SELECT official_url, manual_lock FROM meetings WHERE id = 'test-locked_council-20260101-001';").fetchone()
            self.assertEqual(db_lm[0], "https://example.com/manual-meeting", "DB 内の locked meeting URL が保護されていること")
            self.assertEqual(db_lm[1], 1)
            conn.close()

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_production_data_json_invariance_under_deduplication(self):
        """本番 docs/data.json の手動ロックデータに対し deduplicate_data_materials を適用しても一切変化しないこと"""
        data_json_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        self.assertTrue(os.path.exists(data_json_path), "docs/data.json が存在すること")

        original_data = load_data_json(data_json_path, cached=True)
        self.assertTrue(bool(original_data), "docs/data.json が正常に読み込めること")

        locked_meetings_before = {
            m["id"]: copy.deepcopy(m)
            for m in original_data.get("meetings", [])
            if m.get("manualLock")
        }

        self.assertGreater(len(locked_meetings_before), 0, "手動ロックされた会議が存在すること (最低1件以上)")

        # 40MB 全体の deepcopy を避け、手動ロック対象が存在する会議体・会議のサブセットに対して重複排除を実行
        locked_council_ids = {m.get("councilId") for m in locked_meetings_before.values() if m.get("councilId")}
        test_subset = {
            "councils": [copy.deepcopy(c) for c in original_data.get("councils", []) if c.get("id") in locked_council_ids],
            "meetings": [copy.deepcopy(m) for m in original_data.get("meetings", []) if m.get("councilId") in locked_council_ids]
        }
        deduplicate_data_materials(test_subset)

        for m_id, original_m in locked_meetings_before.items():
            after_m = next((m for m in test_subset.get("meetings", []) if m["id"] == m_id), None)
            self.assertIsNotNone(after_m, f"会議 {m_id} が維持されていること")
            self.assertEqual(
                original_m["materials"],
                after_m["materials"],
                f"会議 {m_id} の materials 配列が重複排除処理によって一切改変されていないこと"
            )

    def test_sync_new_meetings_adds_unregistered_session_and_preserves_locked(self):
        """新規開催回が発見された場合に正しく追加され、既存のロック済み会議が破壊されないこと"""
        from crawler import sync_new_meetings_from_crawl

        mock_data = {
            "councils": [
                {
                    "id": "moj-test_council",
                    "name": "法務省テスト検討会",
                    "ministry": "MOJ",
                    "officialUrl": "https://example.com/portal",
                    "pastYearCount": 1,
                    "manualLock": True
                }
            ],
            "meetings": [
                {
                    "id": "moj-test_council-20260324-001",
                    "councilId": "moj-test_council",
                    "name": "第1回 法務省テスト検討会",
                    "date": "2026/03/24",
                    "officialUrl": "https://example.com/session1.html",
                    "manualLock": True,
                    "materials": [
                        {"name": "第1回 議事次第", "url": "https://example.com/mat1.pdf", "type": "PDF", "manualLock": True}
                    ]
                }
            ]
        }

        mock_scraped_item = {
            "councilId": "moj-test_council",
            "subpageMeetings": [
                # 既存の第1回（スキップされるべき）
                {
                    "subpageUrl": "https://example.com/session1.html",
                    "name": "第1回 法務省テスト検討会",
                    "materials": [{"name": "第1回 議事次第", "url": "https://example.com/mat1.pdf", "type": "PDF"}],
                    "extractedDates": ["2026/03/24"]
                },
                # 新しく発見された第2回（追加されるべき）
                {
                    "subpageUrl": "https://example.com/session2.html",
                    "name": "第2回 法務省テスト検討会",
                    "materials": [
                        {"name": "第2回 議事次第 (PDF)", "url": "https://example.com/mat2-1.pdf", "type": "PDF"},
                        {"name": "第2回 配布資料 (PDF)", "url": "https://example.com/mat2-2.pdf", "type": "PDF"}
                    ],
                    "extractedDates": ["2026/04/15"]
                }
            ]
        }

        target = mock_data["councils"][0]
        added = sync_new_meetings_from_crawl(mock_data, target, mock_scraped_item)

        self.assertEqual(added, 1, "新規開催回（第2回）の1件のみが追加されること")
        self.assertEqual(len(mock_data["meetings"]), 2, "合計会議数が2件になること")

        # 第1回（手動ロック）が保護されていること
        m1 = next(m for m in mock_data["meetings"] if m["officialUrl"] == "https://example.com/session1.html")
        self.assertTrue(m1.get("manualLock"), "既存会議の manualLock が維持されていること")
        self.assertEqual(len(m1["materials"]), 1)

        # 第2回が正しく構築されていること
        m2 = next(m for m in mock_data["meetings"] if m["officialUrl"] == "https://example.com/session2.html")
        self.assertEqual(m2["date"], "2026/04/15")
        self.assertEqual(len(m2["materials"]), 2)
        self.assertEqual(m2["materials"][0]["url"], "https://example.com/mat2-1.pdf")
        self.assertEqual(target["pastYearCount"], 2, "pastYearCount が更新されていること")

    def test_sync_new_meetings_upgrades_parent_url_when_specific_page_discovered(self):
        """開催前で親URLのままだった既存会議に、開催後に個別資料ページが発見された場合、自動昇格・資料更新されること"""
        from crawler import sync_new_meetings_from_crawl

        mock_data = {
            "councils": [
                {
                    "id": "mhlw-test_kaigo",
                    "name": "社会保障審議会 介護給付費分科会",
                    "ministry": "MHLW",
                    "officialUrl": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126698_00022.html",
                    "pastYearCount": 1,
                    "manualLock": True
                }
            ],
            "meetings": [
                {
                    "id": "mhlw-test_kaigo-20260828-263",
                    "councilId": "mhlw-test_kaigo",
                    "name": "第263回 社会保障審議会 介護給付費分科会",
                    "date": "2026/08/28",
                    "officialUrl": "https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126698_00022.html", # 開催前で親URLのまま
                    "materials": [] # 資料未掲載
                }
            ]
        }

        mock_scraped_item = {
            "subpageMeetings": [
                {
                    "subpageUrl": "https://www.mhlw.go.jp/stf/newpage_75439.html",
                    "name": "第263回社会保障審議会介護給付費分科会（web会議）資料",
                    "extractedDates": ["令和8年8月28日"],
                    "materials": [
                        {"name": "議事次第", "url": "https://www.mhlw.go.jp/content/001743312.pdf", "type": "PDF"},
                        {"name": "資料1", "url": "https://www.mhlw.go.jp/content/001743314.pdf", "type": "PDF"}
                    ]
                }
            ]
        }

        target = mock_data["councils"][0]
        added = sync_new_meetings_from_crawl(mock_data, target, mock_scraped_item)

        self.assertEqual(added, 1, "既存会議（第263回）が資料ページURLへ自動昇格・更新されること")
        self.assertEqual(len(mock_data["meetings"]), 1, "会議総数は1件のまま（重複追加されないこと）")

        m263 = mock_data["meetings"][0]
        self.assertEqual(m263["officialUrl"], "https://www.mhlw.go.jp/stf/newpage_75439.html", "officialUrl が個別資料ページURLに更新されていること")
        self.assertEqual(len(m263["materials"]), 2, "資料2件が同期されていること")
        self.assertEqual(m263["materials"][0]["url"], "https://www.mhlw.go.jp/content/001743312.pdf")

    def test_drop95_rule_driven_subpage_filtering(self):
        """Drop 95: スクレイピングルールによる汎用サブページ除外・必須判定が正しく動作すること"""
        mock_data = {
            "councils": [
                {
                    "id": "test-rule_council",
                    "name": "テストルール会議体",
                    "officialUrl": "https://example.com/parent_portal",
                    "ministry": "TEST"
                }
            ],
            "meetings": [],
            "scrapingRules": {
                "test-rule_council": {
                    "disallow_self_url": True,
                    "exclude_subpage_url_patterns": ["/sub_excluded/", "bridge_wg"],
                    "exclude_subpage_title_keywords": ["ワーキンググループ", "tax commission"],
                    "require_subpage_url_patterns": ["singi"]
                }
            }
        }

        mock_scraped = {
            "subpageMeetings": [
                # 1. 自己URL参照（disallow_self_url で除外）
                {
                    "subpageUrl": "https://example.com/parent_portal",
                    "name": "第1回 テストルール会議体",
                    "materials": [{"name": "資料1", "url": "https://example.com/p1.pdf"}]
                },
                # 2. URL除外パターン一致（/sub_excluded/ で除外）
                {
                    "subpageUrl": "https://example.com/singi/sub_excluded/m01.html",
                    "name": "第2回 テストルール会議体",
                    "materials": [{"name": "資料2", "url": "https://example.com/p2.pdf"}]
                },
                # 3. タイトル除外キーワード一致（ワーキンググループ で除外）
                {
                    "subpageUrl": "https://example.com/singi/valid_wg.html",
                    "name": "第1回 テストルール会議体 ワーキンググループ",
                    "materials": [{"name": "資料3", "url": "https://example.com/p3.pdf"}]
                },
                # 4. 必須URLパターン不一致（singi を含まないため除外）
                {
                    "subpageUrl": "https://example.com/news/m04.html",
                    "name": "第3回 テストルール会議体",
                    "materials": [{"name": "資料4", "url": "https://example.com/p4.pdf"}]
                },
                # 5. 正規開催回（全条件クリアで追加対象）
                {
                    "subpageUrl": "https://example.com/singi/m05.html",
                    "name": "第4回 テストルール会議体",
                    "extractedDates": ["令和8年5月10日"],
                    "materials": [{"name": "資料5", "url": "https://example.com/p5.pdf"}]
                }
            ]
        }

        target = mock_data["councils"][0]
        added = sync_new_meetings_from_crawl(mock_data, target, mock_scraped)

        self.assertEqual(added, 1, "フィルタを通過した1件のみが追加されること")
        self.assertEqual(len(mock_data["meetings"]), 1)
        self.assertEqual(mock_data["meetings"][0]["name"], "第4回 テストルール会議体")
        self.assertEqual(mock_data["meetings"][0]["officialUrl"], "https://example.com/singi/m05.html")

    def test_drop95_zero_council_id_hardcodes_in_crawler(self):
        """Drop 95: crawler.py 内に特定会議体IDのハードコード分岐が一切存在しないこと"""
        import re
        crawler_path = os.path.join(ADMIN_DIR, "crawler.py")
        with open(crawler_path, "r", encoding="utf-8") as f:
            crawler_code = f.read()

        prohibited_councils = [
            "cao-zei_cho", "cao-cstp", "fsa-code_followup",
            "fsa-japan_stewardship", "fsa-stewardship_h28",
            "fsa-stewardship_r01", "fsa-stewardship_r06"
        ]
        for cid in prohibited_councils:
            self.assertNotIn(
                cid, crawler_code,
                f"crawler.py に特定会議体ID '{cid}' がハードコードされています。scraping_rules へ移行してください。"
            )

        # council_id == "..." や council_id in (...) のハードコード判定が0件であること
        pattern = r'''council_id\s*(?:==|in)\s*['"\(\[]'''
        matches = re.findall(pattern, crawler_code)
        self.assertEqual(
            len(matches), 0,
            f"crawler.py に council_id の直接ハードコード分岐が検出されました: {matches}"
        )

def run_tests():

    print("==================================================")
    print(" クロールデータ保護・回帰テスト (test_crawler_regression.py)")
    print("==================================================")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCrawlerManualLockProtection)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\n[PASS] すべてのクロール回帰テストに合格しました。手動登録データは完全に保護されています。")
        return True
    else:
        print("\n[FAIL] クロール回帰テストで不一致・不合格が検出されました。")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
