import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")
dashboard_path = os.path.join(project_root, "admin", "admin_dashboard.html")

# 1. Load KNOWN_NEW_IDS from admin_dashboard.html
with open(dashboard_path, "r", encoding="utf-8") as f:
    dash_content = f.read()

known_ids_match = re.search(r"const KNOWN_NEW_IDS = (\[[\s\S]*?\]);", dash_content)
known_new_ids = set()
if known_ids_match:
    known_new_ids = set(re.findall(r"['\"]([^'\"]+)['\"]", known_ids_match.group(1)))

# 2. Load COUNCILS from docs/data.js
with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

councils_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
all_data_js_councils = []
if councils_match:
    c_str = councils_match.group(1)
    for m in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?name:\s*['\"]([^'\"]+)['\"]", c_str):
        item_str = m.group(0)
        cid = m.group(1)
        cname = m.group(2)
        is_new = "isNew: true" in item_str
        all_data_js_councils.append({"id": cid, "name": cname, "isNew": is_new, "full": item_str})

print(f"Total COUNCILS in docs/data.js: {len(all_data_js_councils)}")

approved = []
unapproved = []

for c in all_data_js_councils:
    cid = c["id"]
    if c["isNew"] or cid in known_new_ids:
        unapproved.append(c)
    else:
        approved.append(c)

print(f"Approved count: {len(approved)}")
print(f"Unapproved count: {len(unapproved)}")

if unapproved:
    print("\nThe 1 unapproved council still in data.js:")
    for c in unapproved:
        print(f"  - [{c['id']}] {c['name']} (isNew: {c['isNew']}, in KnownIDs: {c['id'] in known_new_ids})")
