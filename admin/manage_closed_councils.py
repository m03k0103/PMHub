#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
admin/manage_closed_councils.py
===============================
法改正等により明確に廃止された会議体のマスター管理ツール（CR-24, CR-25）

【運用原則】
- 単なる長期間未開催や休眠状態の会議体に isClosed: true を付与してはならない。
- 法改正、省庁統廃合、時限立法期限満了等の公的根拠が明確な会議体にのみ厳格に設定する。
- 理由（closedReason）の記録を必須とする。

【使用例】
  # 廃止設定済み会議体の一覧表示
  python admin/manage_closed_councils.py --list

  # 廃止会議体の設定（dry-run）
  python admin/manage_closed_councils.py --set cas-old_council --reason "内閣官房令改正に伴う廃止"

  # 廃止会議体の設定（実反映）
  python admin/manage_closed_councils.py --set cas-old_council --reason "内閣官房令改正に伴う廃止" --apply

  # 廃止フラグの解除
  python admin/manage_closed_councils.py --unset cas-old_council --apply
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_win32_utf8, load_data_json, save_data_json_with_backup

setup_win32_utf8()

DATA_JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))


def list_closed_councils(data):
    """廃止設定されている会議体の一覧を表示"""
    councils = data.get("councils", [])
    closed_list = [c for c in councils if c.get("isClosed") is True]

    print(f"\n=======================================================")
    print(f" 法改正等廃止会議体一覧 (isClosed: true): 計 {len(closed_list)} 件")
    print(f"=======================================================")
    if not closed_list:
        print("  現在、isClosed: true に設定されている会議体はありません。")
    for idx, c in enumerate(closed_list, 1):
        cid = c.get("id")
        name = c.get("name")
        ministry = c.get("ministry")
        reason = c.get("closedReason", "理由未記載")
        print(f"[{idx:3d}] [{ministry}] {cid}")
        print(f"      名称: {name}")
        print(f"      根拠・理由: {reason}")
    print("=======================================================\n")
    return closed_list


def set_council_closed(data, council_id, reason, apply=False):
    """会議体に isClosed: true を設定"""
    councils = data.get("councils", [])
    target = None
    for c in councils:
        if c.get("id") == council_id:
            target = c
            break

    if not target:
        print(f"[ERROR] 会議体 ID '{council_id}' が docs/data.json 内に見つかりません。", file=sys.stderr)
        return False

    print(f"\n対象会議体: [{target.get('ministry')}] {target.get('name')} ({council_id})")
    print(f"設定内容: isClosed = True, closedReason = '{reason}'")

    if not apply:
        print("\n⚠️  [DRY-RUN] 変更は保存されていません。反映するには --apply を指定してください。\n")
        return True

    target["isClosed"] = True
    target["closedReason"] = reason
    target["closedUpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # scrapingRules 側にも連動して記録
    scraping_rules = data.get("scrapingRules", {})
    if council_id in scraping_rules and isinstance(scraping_rules[council_id], dict):
        scraping_rules[council_id]["isClosed"] = True

    if save_data_json_with_backup(data):
        print(f"✅ [SUCCESS] 会議体 '{council_id}' を廃止（isClosed: true）として保存しました。")
        return True
    else:
        print(f"❌ [FAILED] 保存に失敗しました。", file=sys.stderr)
        return False


def unset_council_closed(data, council_id, apply=False):
    """会議体の isClosed フラグを解除"""
    councils = data.get("councils", [])
    target = None
    for c in councils:
        if c.get("id") == council_id:
            target = c
            break

    if not target:
        print(f"[ERROR] 会議体 ID '{council_id}' が docs/data.json 内に見つかりません。", file=sys.stderr)
        return False

    if not target.get("isClosed"):
        print(f"[INFO] 会議体 '{council_id}' はすでに isClosed: true ではありません。")
        return True

    print(f"\n対象会議体: [{target.get('ministry')}] {target.get('name')} ({council_id})")
    print(f"解除内容: isClosed フラグを削除/解除")

    if not apply:
        print("\n⚠️  [DRY-RUN] 変更は保存されていません。反映するには --apply を指定してください。\n")
        return True

    target.pop("isClosed", None)
    target.pop("closedReason", None)
    target.pop("closedUpdatedAt", None)

    scraping_rules = data.get("scrapingRules", {})
    if council_id in scraping_rules and isinstance(scraping_rules[council_id], dict):
        scraping_rules[council_id].pop("isClosed", None)

    if save_data_json_with_backup(data):
        print(f"✅ [SUCCESS] 会議体 '{council_id}' の isClosed 設定を解除しました。")
        return True
    else:
        print(f"❌ [FAILED] 保存に失敗しました。", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="法改正等廃止会議体マスター管理ツール (CR-25)")
    parser.add_argument("--list", action="store_true", help="isClosed: true に設定されている会議体一覧を表示")
    parser.add_argument("--set", dest="target_id", help="廃止設定する会議体ID")
    parser.add_argument("--reason", help="廃止の公的根拠・理由（法令名、改正内容等）")
    parser.add_argument("--unset", dest="unset_id", help="廃止設定を解除する会議体ID")
    parser.add_argument("--apply", action="store_true", help="変更を docs/data.json に保存する")
    args = parser.parse_args()

    data = load_data_json(DATA_JSON_PATH)

    if args.list or (not args.target_id and not args.unset_id):
        list_closed_councils(data)
        return

    if args.target_id:
        if not args.reason:
            print("[ERROR] --set を指定する場合、廃止の根拠・理由（--reason）が必須です。", file=sys.stderr)
            sys.exit(1)
        set_council_closed(data, args.target_id, args.reason, apply=args.apply)
        return

    if args.unset_id:
        unset_council_closed(data, args.unset_id, apply=args.apply)
        return


if __name__ == "__main__":
    main()
