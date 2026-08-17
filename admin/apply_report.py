import json
import os
import sys

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
                        m[field] = new_val
                        applied_count += 1
                        print(f"Applied MEETINGS.{target_id}.{field} -> {new_val}")
                        found = True
                        break
                if not found:
                    print(f"Warning: MEETINGS item {target_id} not found")

        elif action == "remove_council":
            target_id = corr.get("targetId")
            if target_id:
                initial_len = len(councils)
                councils[:] = [c for c in councils if c.get("id") != target_id]
                if len(councils) < initial_len:
                    applied_count += 1
                    print(f"Removed council {target_id}")
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
