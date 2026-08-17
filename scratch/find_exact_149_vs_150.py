import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")

with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

councils_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
all_councils = []
if councils_match:
    c_str = councils_match.group(1)
    for m in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?name:\s*['\"]([^'\"]+)['\"]", c_str):
        all_councils.append({"id": m.group(1), "name": m.group(2)})

# Check duplicate IDs
seen = set()
duplicates = []
for c in all_councils:
    if c["id"] in seen:
        duplicates.append(c)
    seen.add(c["id"])

print(f"Total COUNCILS in docs/data.js: {len(all_councils)}")
print(f"Unique IDs: {len(seen)}")
if duplicates:
    print("Duplicates found:")
    for d in duplicates:
        print("  -", d)

# Check KNOWN_NEW_IDS in admin_dashboard.html
dashboard_path = os.path.join(project_root, "admin", "admin_dashboard.html")
with open(dashboard_path, "r", encoding="utf-8") as f:
    dash_content = f.read()

known_ids_match = re.search(r"const KNOWN_NEW_IDS = (\[[\s\S]*?\]);", dash_content)
known_new_ids = set()
if known_ids_match:
    known_new_ids = set(re.findall(r"['\"]([^'\"]+)['\"]", known_ids_match.group(1)))

print("Checking if any item in docs/data.js is in KNOWN_NEW_IDS:")
found_known = [c for c in all_councils if c["id"] in known_new_ids]
print(f"Found in KNOWN_NEW_IDS: {len(found_known)}")
for c in found_known:
    print("  -", c)
