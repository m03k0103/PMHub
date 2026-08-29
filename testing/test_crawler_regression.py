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
import io
import unittest

# Windows ターミナルログの文字化け防止
if sys.platform == "win32":
    os.system("chcp 65001 > NUL 2>&1")
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DIR = os.path.join(PROJECT_ROOT, "admin")
sys.path.insert(0, ADMIN_DIR)

from crawler import deduplicate_data_materials, update_crawl_status
from apply_report import apply_report

class TestCrawlerManualLockProtection(unittest.TestCase):

    def test_deduplicate_materials_respects_meeting_manual_lock(self):
        """manualLock: true の会議は deduplicate_data_materials による資料削除・移動から保護されること"""
        mock_data = {
            "councils": [
                {"id": "test-council-1", "name": "テスト会議体", "url": "https://example.com/portal"}
            ],
            "meetings": [
                {
                    "id": "meet-1",
                    "councilId": "test-council-1",
                    "title": "第1回 テスト会議",
                    "date": "2026/01/01",
                    "manualLock": True,  # 手動保護
                    "materials": [
                        {"name": "報道発表特別資料", "url": "https://example.com/shared.pdf", "manualLock": True},
                        {"name": "通常資料", "url": "https://example.com/doc1.pdf"}
                    ]
                },
                {
                    "id": "meet-2",
                    "councilId": "test-council-1",
                    "title": "第2回 テスト会議",
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

        # meet-1 (locked) の資料がすべて残っていることを検証
        m1 = mock_data["meetings"][0]
        self.assertEqual(len(m1["materials"]), 2, "manualLock: true の会議資料は削除されてはいけない")
        self.assertEqual(m1["materials"][0]["url"], "https://example.com/shared.pdf")
        self.assertEqual(m1["materials"][1]["url"], "https://example.com/doc1.pdf")

    def test_deduplicate_materials_respects_material_manual_lock(self):
        """material 単体に manualLock: true が設定されている場合も重複排除から除外されること"""
        mock_data = {
            "councils": [
                {"id": "test-council-2", "name": "テスト会議体2", "url": "https://example.com/portal"}
            ],
            "meetings": [
                {
                    "id": "meet-2-1",
                    "councilId": "test-council-2",
                    "title": "第1回 テスト会議",
                    "date": "2026/01/01",
                    "manualLock": False,
                    "materials": [
                        {"name": "手動保護資料", "url": "https://example.com/shared2.pdf", "manualLock": True}
                    ]
                },
                {
                    "id": "meet-2-2",
                    "councilId": "test-council-2",
                    "title": "第2回 テスト会議",
                    "date": "2026/02/01",
                    "manualLock": False,
                    "materials": [
                        {"name": "通常資料", "url": "https://example.com/shared2.pdf"}
                    ]
                }
            ]
        }

        deduplicate_data_materials(mock_data)

        # meet-2-1 の手動保護資料が残っていること
        m2_1 = mock_data["meetings"][0]
        self.assertEqual(len(m2_1["materials"]), 1)
        self.assertEqual(m2_1["materials"][0]["name"], "手動保護資料")

    def test_apply_report_skips_locked_council_and_meeting(self):
        """apply_report は manualLock: true の会議体および会議のフィールドを上書きしないこと"""
        import tempfile

        temp_data = {
            "councils": [
                {
                    "id": "locked-council",
                    "name": "手動保護会議体",
                    "officialUrl": "https://example.com/manual-url",
                    "manualLock": True
                },
                {
                    "id": "unlocked-council",
                    "name": "非保護会議体",
                    "officialUrl": "https://example.com/old-url",
                    "manualLock": False
                }
            ],
            "meetings": [
                {
                    "id": "locked-meeting",
                    "councilId": "locked-council",
                    "officialUrl": "https://example.com/manual-meeting",
                    "manualLock": True
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as df:
            json.dump(temp_data, df, ensure_ascii=False, indent=2)
            data_path = df.name

        report_data = {
            "_format": "pmhub-verification-report-v2",
            "corrections": [
                {
                    "action": "update_field",
                    "target": "COUNCILS",
                    "targetId": "locked-council",
                    "field": "officialUrl",
                    "newValue": "https://example.com/overwritten"
                },
                {
                    "action": "update_field",
                    "target": "COUNCILS",
                    "targetId": "unlocked-council",
                    "field": "officialUrl",
                    "newValue": "https://example.com/new-url"
                },
                {
                    "action": "update_field",
                    "target": "MEETINGS",
                    "targetId": "locked-meeting",
                    "field": "officialUrl",
                    "newValue": "https://example.com/overwritten-meeting"
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as rf:
            json.dump(report_data, rf, ensure_ascii=False, indent=2)
            report_path = rf.name

        try:
            apply_report(report_path, data_json_path=data_path)

            with open(data_path, "r", encoding="utf-8") as res_f:
                updated = json.load(res_f)

            # locked-council は上書きされていないこと
            lc = next(c for c in updated["councils"] if c["id"] == "locked-council")
            self.assertEqual(lc["officialUrl"], "https://example.com/manual-url", "locked council の URL は保護されるべき")

            # unlocked-council は更新されていること
            uc = next(c for c in updated["councils"] if c["id"] == "unlocked-council")
            self.assertEqual(uc["officialUrl"], "https://example.com/new-url", "unlocked council は更新されるべき")

            # locked-meeting は上書きされていないこと
            lm = next(m for m in updated["meetings"] if m["id"] == "locked-meeting")
            self.assertEqual(lm["officialUrl"], "https://example.com/manual-meeting", "locked meeting の URL は保護されるべき")

        finally:
            if os.path.exists(data_path): os.remove(data_path)
            if os.path.exists(report_path): os.remove(report_path)

    def test_production_data_json_invariance_under_deduplication(self):
        """本番 docs/data.json の手動ロックデータに対し deduplicate_data_materials を適用しても一切変化しないこと"""
        data_json_path = os.path.join(PROJECT_ROOT, "docs", "data.json")
        self.assertTrue(os.path.exists(data_json_path), "docs/data.json が存在すること")

        with open(data_json_path, "r", encoding="utf-8") as f:
            original_data = json.load(f)

        locked_meetings_before = {
            m["id"]: copy.deepcopy(m)
            for m in original_data.get("meetings", [])
            if m.get("manualLock")
        }

        self.assertGreater(len(locked_meetings_before), 0, "手動ロックされた会議が存在すること (最低1件以上)")

        test_copy = copy.deepcopy(original_data)
        deduplicate_data_materials(test_copy)

        for m_id, original_m in locked_meetings_before.items():
            after_m = next((m for m in test_copy.get("meetings", []) if m["id"] == m_id), None)
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
                    "title": "第1回 法務省テスト検討会",
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
                    "title": "第1回 法務省テスト検討会",
                    "materials": [{"name": "第1回 議事次第", "url": "https://example.com/mat1.pdf", "type": "PDF"}],
                    "extractedDates": ["2026/03/24"]
                },
                # 新しく発見された第2回（追加されるべき）
                {
                    "subpageUrl": "https://example.com/session2.html",
                    "title": "第2回 法務省テスト検討会",
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
