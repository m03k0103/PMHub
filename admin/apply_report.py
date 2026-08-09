import json
import os
import sys
import re

def apply_report(json_path, data_js_path=None):
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist.")
        return False

    if not data_js_path:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_js_path = os.path.abspath(os.path.join(base_dir, "..", "docs", "data.js"))

    if not os.path.exists(data_js_path):
        print(f"Error: {data_js_path} does not exist.")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    corrections = report.get("corrections", [])
    if not corrections:
        print("No corrections found in JSON.")
        return True

    with open(data_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    applied_count = 0
    for corr in corrections:
        action = corr.get("action")
        target = corr.get("target")
        target_id = corr.get("targetId")
        field = corr.get("field")
        new_val = corr.get("newValue")

        if action == "update_field":
            val_str = json.dumps(new_val, ensure_ascii=False).replace('"', "'") if isinstance(new_val, (str, list, bool)) else str(new_val)
            if isinstance(new_val, bool):
                val_str = "true" if new_val else "false"

            if target == "MINISTRIES":
                pattern = re.compile(rf"({re.escape(target_id)}:\s*\{{[\s\S]*?\}})")
                match = pattern.search(content)
                if match:
                    block = match.group(1)
                    if field in ("councilsUrls", "councilsUrl"):
                        field_pattern = re.compile(r"(councilsUrls:\s*\[[\s\S]*?\]|councilsUrl:\s*'[^']*'|councilsUrls:\s*[^,\n}]+)")
                        if field_pattern.search(block):
                            new_block = field_pattern.sub(f"councilsUrls: {val_str}", block)
                        else:
                            new_block = block.rstrip("} \t\n") + f", councilsUrls: {val_str} }}"
                    elif field == "officialUrl":
                        field_pattern = re.compile(r"(officialUrl:\s*'[^']*'|officialUrl:\s*[^,\n}]+)")
                        if field_pattern.search(block):
                            new_block = field_pattern.sub(f"officialUrl: {val_str}", block)
                        else:
                            new_block = block.rstrip("} \t\n") + f", officialUrl: {val_str} }}"
                    elif field == "hasCouncils":
                        field_pattern = re.compile(r"(hasCouncils:\s*(true|false))")
                        if field_pattern.search(block):
                            new_block = field_pattern.sub(f"hasCouncils: {val_str}", block)
                        else:
                            new_block = block.rstrip("} \t\n") + f", hasCouncils: {val_str} }}"
                    else:
                        field_pattern = re.compile(rf"({re.escape(field)}:\s*)[^,\n}}]+")
                        if field_pattern.search(block):
                            new_block = field_pattern.sub(rf"\g<1>{val_str}", block)
                        else:
                            new_block = block.rstrip("} \t\n") + f", {field}: {val_str} }}"

                    content = content.replace(block, new_block)
                    applied_count += 1
                    print(f"Applied MINISTRIES.{target_id}.{field} -> {new_val}")
                else:
                    print(f"Warning: Ministry {target_id} not found in data.js")

            elif target in ("COUNCILS", "MEETINGS"):
                pattern = re.compile(rf"(id:\s*'{re.escape(target_id)}'[\s\S]*?\n\s*\}})")
                match = pattern.search(content)
                if match:
                    block = match.group(1)
                    field_pattern = re.compile(rf"({re.escape(field)}:\s*)[^,\n}}]+")
                    if field_pattern.search(block):
                        new_block = field_pattern.sub(rf"\g<1>{val_str}", block)
                    else:
                        new_block = block.rstrip("} \t\n") + f", {field}: {val_str} }}"
                    content = content.replace(block, new_block)
                    applied_count += 1
                    print(f"Applied {target}.{target_id}.{field} -> {new_val}")
                else:
                    print(f"Warning: {target} item {target_id} not found in data.js")

    with open(data_js_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully applied {applied_count} correction(s) to {data_js_path}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_report.py <path_to_json_report>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    apply_report(json_file)
