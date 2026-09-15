import json
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import setup_win32_utf8, save_data_json_with_backup, load_rejected_councils, save_rejected_councils
setup_win32_utf8()


def _apply_field_update(item_list, target_id, field, new_val, target_name):
    """COUNCILS / MEETINGS のフィールド更新共通ハンドラ（manualLock チェック付き）"""
    for item in item_list:
        if item.get("id") == target_id:
            if item.get("manualLock", False):
                print(f"[SKIP] {target_name}.{target_id}.{field}: manualLock が設定されています（上書きスキップ）。解除するには manualLock: false を設定してください。")
                return True, False
            item[field] = new_val
            print(f"Applied {target_name}.{target_id}.{field} -> {new_val}")
            return True, True
    print(f"Warning: {target_name} item {target_id} not found")
    return False, False


def apply_report_data(report_data, data_json_path=None):
    """
    辞書オブジェクト形式のレポートデータを受け取り、docs/data.json に反映する。
    ディスク一時ファイルを作らずにインメモリで直接反映可能。
    """
    if not isinstance(report_data, dict):
        print("Error: Invalid report format (must be dict).")
        return False

    if not data_json_path:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_json_path = os.path.abspath(os.path.join(base_dir, "..", "docs", "data.json"))

    if not os.path.exists(data_json_path):
        print(f"Error: {data_json_path} does not exist.")
        return False

    corrections = report_data.get("corrections", [])
    if not corrections:
        print("No corrections found in report.")
        return True

    with open(data_json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing data.json: {e}")
            return False

    councils = data.get("councils", [])
    meetings = data.get("meetings", [])
    ministries = data.get("ministries", {})

    applied_count = 0
    for corr in corrections:
        action = corr.get("action")
        target = corr.get("target")
        target_id = corr.get("targetId")
        field = corr.get("field")
        new_val = corr.get("newValue")

        if action == "update_field":
            if target == "MINISTRIES":
                if target_id in ministries:
                    ministries[target_id][field] = new_val
                    applied_count += 1
                    print(f"Applied MINISTRIES.{target_id}.{field} -> {new_val}")
                else:
                    print(f"Warning: Ministry {target_id} not found")

            elif target in ("COUNCILS", "MEETINGS"):
                target_list = councils if target == "COUNCILS" else meetings
                found, updated = _apply_field_update(target_list, target_id, field, new_val, target)
                if updated:
                    applied_count += 1

        elif action == "remove_council" or action == "reject_council":
            # target_id はループ先頭で取得済み（二重代入を廃止）
            if target_id:
                # 削除対象の会議体情報を取得
                target_council = next((c for c in councils if c.get("id") == target_id), None)
                if not target_council:
                    # discoveredCouncils からも探す
                    target_council = next((c for c in data.get("discoveredCouncils", []) if c.get("id") == target_id), None)

                initial_len = len(councils)
                councils[:] = [c for c in councils if c.get("id") != target_id]
                if len(councils) < initial_len or target_council:
                    applied_count += 1
                    print(f"Removed council {target_id}")

                    # rejected_councils.json に記録・保存
                    try:
                        rejected_list = load_rejected_councils()
                        # 重複追加の防止
                        if not any(rc.get("id") == target_id for rc in rejected_list):
                            rej_item = {
                                "id": target_id,
                                "name": target_council.get("name") if target_council else target_id,
                                "ministry": target_council.get("ministry") if target_council else "",
                                "category": target_council.get("category", "COUNCIL") if target_council else "COUNCIL",
                                "officialUrl": target_council.get("officialUrl") if target_council else "",
                                "rejectedAt": corr.get("rejectedAt") or "2026-08-25",
                                "reason": corr.get("reason") or "Admin rejected council"
                            }
                            rejected_list.append(rej_item)
                            save_rejected_councils(rejected_list)
                            print(f"Saved rejected council {target_id} to rejected_councils.json")
                    except Exception as err:
                        print(f"Warning: Failed to update rejected_councils.json: {err}")
                else:
                    print(f"Warning: Council {target_id} to remove not found")

        elif action == "add_council":
            council = corr.get("council")
            if council and isinstance(council, dict):
                c_id = council.get("id")
                # Remove isNew if present
                council.pop("isNew", None)
                if not any(c.get("id") == c_id for c in councils):
                    councils.append(council)
                    applied_count += 1
                    print(f"Added new council: {c_id}")
                else:
                    print(f"Warning: Council {c_id} already exists")

    # 保存前に admin/backups/ にタイムスタンプ付き世代バックアップを作成して安全に上書き保存
    save_data_json_with_backup(data, data_json_path)

    print(f"\nReport applied. {applied_count} out of {len(corrections)} changes saved to data.json")
    return True


def apply_report(json_path, data_json_path=None):
    """
    JSONファイルパスからレポートを読み込み、apply_report_data に渡すラッパー（既存CLI・テスト互換）。
    """
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist.")
        return False
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        return apply_report_data(report_data, data_json_path)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_report.py <path_to_report.json> [path_to_data.json]")
        sys.exit(1)
    
    json_path = sys.argv[1]
    data_json_path = sys.argv[2] if len(sys.argv) > 2 else None
    apply_report(json_path, data_json_path)
