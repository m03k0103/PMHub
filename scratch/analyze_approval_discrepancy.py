import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")

with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

# Extract KNOWN_NEW_IDS from admin_dashboard.html
dashboard_path = os.path.join(project_root, "admin", "admin_dashboard.html")
with open(dashboard_path, "r", encoding="utf-8") as f:
    dash_content = f.read()

known_ids_match = re.search(r"const KNOWN_NEW_IDS = (\[[\s\S]*?\]);", dash_content)
known_new_ids = set()
if known_ids_match:
    known_new_ids = set(re.findall(r"['\"]([^'\"]+)['\"]", known_ids_match.group(1)))

print(f"Total KNOWN_NEW_IDS in admin_dashboard.html: {len(known_new_ids)}")

# Extract COUNCILS from docs/data.js
councils_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
all_data_js_councils = []
if councils_match:
    c_str = councils_match.group(1)
    for m in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?name:\s*['\"]([^'\"]+)['\"]", c_str):
        all_data_js_councils.append({
            "id": m.group(1),
            "name": m.group(2),
            "isNew": "isNew: true" in m.group(0)
        })

print(f"Total COUNCILS in docs/data.js: {len(all_data_js_councils)}")

# In admin_dashboard.html, baseCouncils default verdict logic:
# const defaultV = (c.isNew === true || knownIdSet.has(c.id)) ? null : 'approved';

base_approved = []
base_pending = []

for c in all_data_js_councils:
    cid = c["id"]
    if c["isNew"] or cid in known_new_ids:
        base_pending.append(c)
    else:
        base_approved.append(c)

print(f"Base councils defaulting to 'approved': {len(base_approved)}")
print(f"Base councils defaulting to 'pending' (null): {len(base_pending)}")
print("\nCouncils defaulting to 'pending' (the 48-61 unapproved items):")
for c in base_pending:
    print(f"  - [{c['id']}] {c['name']}")
