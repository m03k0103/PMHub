#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 定時クロール差分レポート生成ツール (Track [Automation] フェーズ1)

GitHub Actions のドライラン運用で、クロール前後の公開データ・クロール状態を比較し、
新規開催回数・新規配付資料数・失敗会議体・異常判定（サーキットブレーカー発動相当）を
Markdown とログに出力する。本ツールはデータを一切書き換えない（読み取り専用）。

使い方:
  python admin/tools/automation_report.py snapshot --out before.json
  (クロール実行)
  python admin/tools/automation_report.py report --before before.json \
      --crawl-log crawl.log --output report.md [--github-output "$GITHUB_OUTPUT"]
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_PUBLIC_JSON = os.path.join(PROJECT_ROOT, "docs", "data.json")
DEFAULT_ARCHIVE_JSON = os.path.join(PROJECT_ROOT, "docs", "data_archive.json")
DEFAULT_ADMIN_JSON = os.path.join(PROJECT_ROOT, "admin", "admin_data.json")

# サーキットブレーカー発動相当とみなす失敗省庁数（DROPS.md Track [Automation] 仕様）
FAILED_MINISTRY_THRESHOLD = 5
# 開催回総数が前回比でこの割合を超えて減少した場合も異常とみなす
MEETING_SHRINK_RATIO = 0.05

_HTTP_BLOCK_RE = re.compile(r"\b(403|429)\b")


def _load_json(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ministry_of(council_id):
    """会議体ID（{省庁略称}-{スラグ}）から省庁略称を返す。"""
    return str(council_id).split("-", 1)[0] if council_id else ""


def build_snapshot(public_json=DEFAULT_PUBLIC_JSON, archive_json=DEFAULT_ARCHIVE_JSON, admin_json=DEFAULT_ADMIN_JSON):
    """公開データ（現役＋アーカイブ）とクロール状態から比較用スナップショットを生成する。"""
    meetings = {}
    for path in (public_json, archive_json):
        for m in _load_json(path).get("meetings", []):
            meetings[m.get("id")] = len(m.get("materials", []) or [])
    statuses = _load_json(admin_json).get("crawlStatuses", {}) or {}
    crawl = {
        cid: {
            "lastAttempt": st.get("lastAttempt", ""),
            "result": st.get("result", ""),
            "consecutiveFailures": st.get("consecutiveFailures", 0),
            "failureReason": st.get("failureReason", ""),
        }
        for cid, st in statuses.items()
    }
    return {"createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "meetings": meetings, "crawlStatuses": crawl}


def count_http_blocks(log_text):
    """クロールログ中の 403 / 429 の出現行数を返す。"""
    counts = {"403": 0, "429": 0}
    for line in (log_text or "").splitlines():
        for code in set(_HTTP_BLOCK_RE.findall(line)):
            counts[code] += 1
    return counts


def diff_snapshots(before, after):
    """クロール前後のスナップショット差分を集計する。"""
    b_m, a_m = before.get("meetings", {}), after.get("meetings", {})
    new_ids = sorted(set(a_m) - set(b_m))
    removed_ids = sorted(set(b_m) - set(a_m))
    materials_added = sum(max(0, a_m[i] - b_m[i]) for i in set(a_m) & set(b_m))
    materials_added += sum(a_m[i] for i in new_ids)

    b_c, a_c = before.get("crawlStatuses", {}), after.get("crawlStatuses", {})
    attempted = [cid for cid, st in a_c.items() if st.get("lastAttempt") != (b_c.get(cid) or {}).get("lastAttempt")]
    failed_now = [cid for cid in attempted if a_c[cid].get("result") == "failed"]
    newly_failed = [cid for cid in failed_now if (b_c.get(cid) or {}).get("result") != "failed"]
    failed_ministries = sorted({ministry_of(cid) for cid in failed_now})
    max_consec = max((a_c[cid].get("consecutiveFailures", 0) for cid in failed_now), default=0)

    return {
        "meetingsBefore": len(b_m),
        "meetingsAfter": len(a_m),
        "newMeetingIds": new_ids,
        "removedMeetingIds": removed_ids,
        "materialsAdded": materials_added,
        "attemptedCouncils": len(attempted),
        "failedCouncils": sorted(failed_now),
        "newlyFailedCouncils": sorted(newly_failed),
        "failedMinistries": failed_ministries,
        "maxConsecutiveFailures": max_consec,
    }


def evaluate_anomalies(diff, http_blocks, ministry_threshold=FAILED_MINISTRY_THRESHOLD, shrink_ratio=MEETING_SHRINK_RATIO):
    """異常判定。1件でも該当すれば breaker_tripped=True（フェーズ1では記録のみで停止・Issue起票は行わない）。"""
    reasons = []
    if len(diff["failedMinistries"]) >= ministry_threshold:
        reasons.append(f"失敗省庁数 {len(diff['failedMinistries'])} が閾値 {ministry_threshold} 以上")
    before_n = diff["meetingsBefore"]
    if before_n and (before_n - diff["meetingsAfter"]) / before_n > shrink_ratio:
        reasons.append(f"開催回総数が {before_n} → {diff['meetingsAfter']} と {shrink_ratio:.0%} 超減少")
    if http_blocks.get("403", 0) + http_blocks.get("429", 0) > 0 and diff["attemptedCouncils"] and \
            (http_blocks["403"] + http_blocks["429"]) >= max(20, diff["attemptedCouncils"] // 10):
        reasons.append(f"403/429 が多発（403: {http_blocks['403']}行 / 429: {http_blocks['429']}行）")
    return {"breaker_tripped": bool(reasons), "reasons": reasons}


def render_markdown(diff, http_blocks, verdict, mode_label="dry-run"):
    lines = [
        f"# クロール差分レポート（{mode_label}）",
        "",
        f"- 生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- **ドライラン: `main` への commit / push は行っていません。**",
        "",
        "## 差分サマリー",
        "",
        "| 項目 | 値 |",
        "|:---|---:|",
        f"| クロール試行した会議体 | {diff['attemptedCouncils']} |",
        f"| 開催回総数（前 → 後） | {diff['meetingsBefore']} → {diff['meetingsAfter']} |",
        f"| 新規開催回 | {len(diff['newMeetingIds'])} |",
        f"| 消えた開催回 | {len(diff['removedMeetingIds'])} |",
        f"| 追加された配付資料 | {diff['materialsAdded']} |",
        f"| 今回失敗した会議体 | {len(diff['failedCouncils'])}（うち新規失敗 {len(diff['newlyFailedCouncils'])}） |",
        f"| 失敗が発生した省庁数 | {len(diff['failedMinistries'])} |",
        f"| 最大連続失敗回数 | {diff['maxConsecutiveFailures']} |",
        f"| HTTP 403 / 429（ログ行数） | {http_blocks.get('403', 0)} / {http_blocks.get('429', 0)} |",
        "",
        "## 異常判定",
        "",
    ]
    if verdict["breaker_tripped"]:
        lines.append("**サーキットブレーカー発動相当**（フェーズ2では以降の自動実行を停止し Issue を起票する条件）:")
        lines += [f"- {r}" for r in verdict["reasons"]]
    else:
        lines.append("異常なし。")
    if diff["newMeetingIds"]:
        lines += ["", "## 新規開催回（先頭30件）", ""] + [f"- `{i}`" for i in diff["newMeetingIds"][:30]]
    if diff["removedMeetingIds"]:
        lines += ["", "## 消えた開催回（先頭30件）", ""] + [f"- `{i}`" for i in diff["removedMeetingIds"][:30]]
    if diff["newlyFailedCouncils"]:
        lines += ["", "## 新規失敗の会議体（先頭30件）", ""] + [f"- `{i}`" for i in diff["newlyFailedCouncils"][:30]]
    return "\n".join(lines) + "\n"


def _write_github_output(path, verdict, diff):
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"breaker_tripped={'true' if verdict['breaker_tripped'] else 'false'}\n")
        f.write(f"new_meetings={len(diff['newMeetingIds'])}\n")
        f.write(f"materials_added={diff['materialsAdded']}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="定時クロール差分レポート（読み取り専用）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="クロール前スナップショットを保存")
    p_snap.add_argument("--out", required=True)

    p_rep = sub.add_parser("report", help="スナップショットと現在データを比較しレポート出力")
    p_rep.add_argument("--before", required=True)
    p_rep.add_argument("--crawl-log", default=None)
    p_rep.add_argument("--output", default=None, help="Markdown 出力先")
    p_rep.add_argument("--github-output", default=None, help="$GITHUB_OUTPUT パス")

    args = parser.parse_args(argv)

    if args.cmd == "snapshot":
        snap = build_snapshot()
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False)
        print(f"[INFO] スナップショット保存: 開催回 {len(snap['meetings'])} 件 / クロール状態 {len(snap['crawlStatuses'])} 件")
        return 0

    before = _load_json(args.before)
    after = build_snapshot()
    log_text = ""
    if args.crawl_log and os.path.exists(args.crawl_log):
        with open(args.crawl_log, "r", encoding="utf-8", errors="replace") as f:
            log_text = f.read()
    diff = diff_snapshots(before, after)
    http_blocks = count_http_blocks(log_text)
    verdict = evaluate_anomalies(diff, http_blocks)
    md = render_markdown(diff, http_blocks, verdict)
    print(md)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
    _write_github_output(args.github_output, verdict, diff)
    return 0  # フェーズ1: 異常でもジョブは失敗させない（記録のみ）


if __name__ == "__main__":
    sys.exit(main())
