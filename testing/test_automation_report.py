#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定時クロール差分レポート (admin/tools/automation_report.py) 単体テスト"""

import json
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(PROJECT_ROOT, "admin"), os.path.join(PROJECT_ROOT, "admin", "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import automation_report as ar  # noqa: E402


def _snap(meetings, statuses):
    return {"meetings": meetings, "crawlStatuses": statuses}


def _st(attempt, result, consec=0):
    return {"lastAttempt": attempt, "result": result, "consecutiveFailures": consec, "failureReason": ""}


class TestAutomationReport(unittest.TestCase):

    def test_ministry_of(self):
        self.assertEqual(ar.ministry_of("cas-kokudo_kyoujinka"), "cas")
        self.assertEqual(ar.ministry_of(""), "")

    def test_diff_new_and_removed_meetings_and_materials(self):
        before = _snap({"a-x-20260101-001": 2, "a-x-20260102-002": 1}, {})
        after = _snap({"a-x-20260101-001": 5, "a-x-20260103-003": 4}, {})
        d = ar.diff_snapshots(before, after)
        self.assertEqual(d["newMeetingIds"], ["a-x-20260103-003"])
        self.assertEqual(d["removedMeetingIds"], ["a-x-20260102-002"])
        self.assertEqual(d["materialsAdded"], 3 + 4)

    def test_diff_failures_only_count_attempted_in_this_run(self):
        before = _snap({}, {
            "mof-a": _st("t1", "failed", 2),   # 前回失敗・今回未試行 → 数えない
            "mic-b": _st("t1", "success"),
            "cao-c": _st("t1", "failed", 1),
        })
        after = _snap({}, {
            "mof-a": _st("t1", "failed", 2),
            "mic-b": _st("t2", "failed", 1),   # 新規失敗
            "cao-c": _st("t2", "failed", 2),   # 継続失敗
        })
        d = ar.diff_snapshots(before, after)
        self.assertEqual(d["failedCouncils"], ["cao-c", "mic-b"])
        self.assertEqual(d["newlyFailedCouncils"], ["mic-b"])
        self.assertEqual(d["failedMinistries"], ["cao", "mic"])
        self.assertEqual(d["newlyFailedMinistries"], ["mic"])
        self.assertEqual(d["maxConsecutiveFailures"], 2)

    def test_http_block_counting(self):
        log = "GET x -> 403\nGET y -> 429 Too Many\nok 200\nGET z -> 403 403\n"
        c = ar.count_http_blocks(log)
        self.assertEqual(c, {"403": 2, "429": 1})

    def test_anomaly_threshold_failed_ministries(self):
        # 過去からの恒常的エラー（failedMinistries）が多くても、新規失敗（newlyFailedMinistries）が少なければトリップしない
        diff = {
            "failedMinistries": list("abcdefghijkl"),
            "newlyFailedMinistries": list("ab"),
            "meetingsBefore": 100,
            "meetingsAfter": 100,
            "attemptedCouncils": 1000,
        }
        self.assertFalse(ar.evaluate_anomalies(diff, {"403": 0, "429": 0})["breaker_tripped"])
        # 新規失敗省庁が5以上でトリップ
        diff["newlyFailedMinistries"] = list("abcde")
        self.assertTrue(ar.evaluate_anomalies(diff, {"403": 0, "429": 0})["breaker_tripped"])
        # 後方互換性: newlyFailedMinistries がない場合は failedMinistries で判定
        diff_legacy = {"failedMinistries": list("abcde"), "meetingsBefore": 100, "meetingsAfter": 100, "attemptedCouncils": 10}
        self.assertTrue(ar.evaluate_anomalies(diff_legacy, {"403": 0, "429": 0})["breaker_tripped"])

    def test_anomaly_meeting_shrink(self):
        diff = {"failedMinistries": [], "meetingsBefore": 1000, "meetingsAfter": 900, "attemptedCouncils": 10}
        v = ar.evaluate_anomalies(diff, {"403": 0, "429": 0})
        self.assertTrue(v["breaker_tripped"])
        diff["meetingsAfter"] = 960
        self.assertFalse(ar.evaluate_anomalies(diff, {"403": 0, "429": 0})["breaker_tripped"])

    def test_anomaly_http_blocks_surge(self):
        diff = {"failedMinistries": [], "meetingsBefore": 100, "meetingsAfter": 100, "attemptedCouncils": 100}
        self.assertTrue(ar.evaluate_anomalies(diff, {"403": 15, "429": 5})["breaker_tripped"])
        self.assertFalse(ar.evaluate_anomalies(diff, {"403": 3, "429": 0})["breaker_tripped"])

    def test_render_markdown_states_dry_run_and_verdict(self):
        diff = ar.diff_snapshots(_snap({}, {}), _snap({"a-x-20260101-001": 1}, {}))
        # dry-run
        md_dry = ar.render_markdown(diff, {"403": 0, "429": 0}, {"breaker_tripped": False, "reasons": []}, mode_label="monthly-dryrun")
        self.assertIn("commit / push は行っていません", md_dry)
        self.assertIn("異常なし", md_dry)
        self.assertIn("a-x-20260101-001", md_dry)
        # 本番自動実行
        md_prod = ar.render_markdown(diff, {"403": 0, "429": 0}, {"breaker_tripped": False, "reasons": []}, mode_label="monthly")
        self.assertIn("自動実行モード (`monthly`)", md_prod)
        self.assertNotIn("commit / push は行っていません", md_prod)

    def test_cli_report_mode_argument(self):
        with tempfile.TemporaryDirectory() as td:
            snap_path = os.path.join(td, "before.json")
            out_path = os.path.join(td, "report.md")
            with open(snap_path, "w", encoding="utf-8") as f:
                json.dump({"meetings": {}, "crawlStatuses": {}}, f)
            # --mode monthly が受け付けられ正常終了すること
            code = ar.main(["report", "--before", snap_path, "--output", out_path, "--mode", "monthly"])
            self.assertEqual(code, 0)
            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("クロール差分レポート（monthly）", content)

    def test_snapshot_and_report_are_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            pub = os.path.join(td, "data.json")
            adm = os.path.join(td, "admin_data.json")
            with open(pub, "w", encoding="utf-8") as f:
                json.dump({"meetings": [{"id": "m1", "materials": [1, 2]}]}, f)
            with open(adm, "w", encoding="utf-8") as f:
                json.dump({"crawlStatuses": {"x-y": _st("t", "success")}}, f)
            before_bytes = (open(pub, "rb").read(), open(adm, "rb").read())
            snap = ar.build_snapshot(pub, os.path.join(td, "none.json"), adm)
            self.assertEqual(snap["meetings"], {"m1": 2})
            self.assertEqual(snap["crawlStatuses"]["x-y"]["result"], "success")
            self.assertEqual(before_bytes, (open(pub, "rb").read(), open(adm, "rb").read()))


if __name__ == "__main__":
    unittest.main()
