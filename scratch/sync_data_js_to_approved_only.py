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

# 2. Parse data.js
with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

councils_match = re.search(r"(const COUNCILS\s*=\s*\[)([\s\S]*?)(\n\];)", content)
if not councils_match:
    print("COUNCILS array not found")
    exit(1)

raw_councils_block = councils_match.group(2)

# Parse individual council object blocks using regex
item_regex = re.compile(r"(\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?\n\s*\},?)", re.MULTILINE)

kept_councils_str = []
removed_councils = []

for m in item_regex.finditer(raw_councils_block):
    full_item = m.group(1)
    cid = m.group(2)
    is_new = "isNew: true" in full_item
    
    # Non-approved criteria: is in KNOWN_NEW_IDS or has isNew: true
    if is_new or cid in known_new_ids:
        # Check council name for log
        name_m = re.search(r"name:\s*['\"]([^'\"]+)['\"]", full_item)
        cname = name_m.group(1) if name_m else cid
        removed_councils.append((cid, cname))
    else:
        # Keep item, remove trailing comma if needed later
        item_clean = full_item.strip().rstrip(",")
        kept_councils_str.append(item_clean)

print(f"Total councils before cleanup: {len(kept_councils_str) + len(removed_councils)}")
print(f"Kept (Approved) councils: {len(kept_councils_str)}")
print(f"Removed (Unapproved / New / KnownNew) councils: {len(removed_councils)}")

print("\nRemoved Councils Sample:")
for cid, cname in removed_councils[:15]:
    print(f"  - [{cid}] {cname}")

# Reconstruct COUNCILS array
new_councils_block = "\n" + ",\n".join(kept_councils_str) + "\n"
new_content = content[:councils_match.start(2)] + new_councils_block + content[councils_match.end(2):]

with open(data_js_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("\nUpdated docs/data.js successfully!")
