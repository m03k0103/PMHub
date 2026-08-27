import json
import os
import sys
import io

# Windows ターミナルログの文字化け防止 (chcp 65001 & UTF-8 再構成)
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


def apply_report(json_path, data_json_path=None):
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist.")
        return False

    if not data_json_path:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_json_path = os.path.abspath(os.path.join(base_dir, "..", "docs", "data.json"))

    if not os.path.exists(data_json_path):
        print(f"Error: {data_json_path} does not exist.")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    corrections = report.get("corrections", [])
    if not corrections:
        print("No corrections found in JSON.")
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

            elif target == "COUNCILS":
                found = False
                for c in councils:
                    if c.get("id") == target_id:
                        if c.get("manualLock", False):
                            print(f"[SKIP] COUNCILS.{target_id}.{field}: manualLock が設定されています（上書きスキップ）。解除するには manualLock: false を設定してください。")
                            found = True
                            break
                        c[field] = new_val
                        applied_count += 1
                        print(f"Applied COUNCILS.{target_id}.{field} -> {new_val}")
                        found = True
                        break
                if not found:
                    print(f"Warning: COUNCILS item {target_id} not found")

            elif target == "MEETINGS":
                found = False
                for m in meetings:
                    if m.get("id") == target_id:
                        if m.get("manualLock", False):
                            print(f"[SKIP] MEETINGS.{target_id}.{field}: manualLock が設定されています（上書きスキップ）。解除するには manualLock: false を設定してください。")
                            found = True
                            break
                        m[field] = new_val
                        applied_count += 1
                        print(f"Applied MEETINGS.{target_id}.{field} -> {new_val}")
                        found = True
                        break
                if not found:
                    print(f"Warning: MEETINGS item {target_id} not found")

        elif action == "remove_council" or action == "reject_council":
            target_id = corr.get("targetId")
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
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        rejected_file = os.path.join(base_dir, "rejected_councils.json")
                        rejected_list = []
                        if os.path.exists(rejected_file):
                            with open(rejected_file, "r", encoding="utf-8") as rf:
                                rejected_list = json.load(rf)

                        # 重複追加の防止
                        if not any(rc.get("id") == target_id for rc in rejected_list):
                            rej_item = {
                                "id": target_id,
                                "name": target_council.get("name") if target_council else target_id,
                                "ministry": target_council.get("ministry") if target_council else "",
                                "category": target_council.get("category", "COUNCIL") if target_council else "COUNCIL",
                                "officialUrl": target_council.get("officialUrl") if target_council else "",
                                "sourcePageUrl": target_council.get("sourcePageUrl", "") if target_council else "",
                                "rejectedAt": corr.get("rejectedAt") or "2026-08-25",
                                "reason": corr.get("reason") or "Admin rejected council"
                            }
                            rejected_list.append(rej_item)
                            with open(rejected_file, "w", encoding="utf-8") as wf:
                                json.dump(rejected_list, wf, ensure_ascii=False, indent=2)
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

    # Save back to data.json
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nReport applied. {applied_count} out of {len(corrections)} changes saved to data.json")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_report.py <path_to_report.json> [path_to_data.json]")
        sys.exit(1)
    
    json_path = sys.argv[1]
    data_json_path = sys.argv[2] if len(sys.argv) > 2 else None
    apply_report(json_path, data_json_path)
