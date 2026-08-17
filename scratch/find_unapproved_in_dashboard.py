import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")
dashboard_path = os.path.join(project_root, "admin", "admin_dashboard.html")

with open(dashboard_path, "r", encoding="utf-8") as f:
    dash_content = f.read()

known_ids_match = re.search(r"const KNOWN_NEW_IDS = (\[[\s\S]*?\]);", dash_content)
known_new_ids = set()
if known_ids_match:
    known_new_ids = set(re.findall(r"['\"]([^'\"]+)['\"]", known_ids_match.group(1)))

with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

councils_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
all_councils = []
if councils_match:
    c_str = councils_match.group(1)
    for m in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?name:\s*['\"]([^'\"]+)['\"]", c_str):
        item_str = m.group(0)
        cid = m.group(1)
        cname = m.group(2)
        all_councils.append({"id": cid, "name": cname, "item": item_str})

print(f"Total items in docs/data.js: {len(all_councils)}")

# Let's check every single item ID in docs/data.js
for i, c in enumerate(all_councils):
    cid = c["id"]
    if cid in known_new_ids or "isNew: true" in c["item"]:
        print(f"UNAPPROVED ITEM found in data.js: Index {i}, ID: {cid}, Name: {c['name']}")
