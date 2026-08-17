import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")
dashboard_path = os.path.join(project_root, "admin", "admin_dashboard.html")

# 1. Parse KNOWN_NEW_IDS
with open(dashboard_path, "r", encoding="utf-8") as f:
    dash_content = f.read()

known_match = re.search(r"const KNOWN_NEW_IDS = (\[[\s\S]*?\]);", dash_content)
known_ids = set(re.findall(r"['\"]([^'\"]+)['\"]", known_match.group(1))) if known_match else set()

# 2. Parse COUNCILS from docs/data.js
with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

councils_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
councils = []
if councils_match:
    c_str = councils_match.group(1)
    for m in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?name:\s*['\"]([^'\"]+)['\"]", c_str):
        full_block = m.group(0)
        cid = m.group(1)
        cname = m.group(2)
        is_new = "isNew: true" in full_block
        councils.append({"id": cid, "name": cname, "isNew": is_new, "block": full_block})

print(f"Total COUNCILS in docs/data.js: {len(councils)}")

approved_by_default = []
unapproved_by_default = []

for c in councils:
    cid = c["id"]
    if c["isNew"] or cid in known_ids:
        unapproved_by_default.append(c)
    else:
        approved_by_default.append(c)

print(f"Default Approved count: {len(approved_by_default)}")
print(f"Default Unapproved count: {len(unapproved_by_default)}")

if unapproved_by_default:
    print("Unapproved items:")
    for c in unapproved_by_default:
        print("  -", c["id"], c["name"])
