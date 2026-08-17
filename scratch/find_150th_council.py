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
        item_str = m.group(0)
        cid = m.group(1)
        cname = m.group(2)
        all_councils.append({"id": cid, "name": cname, "item": item_str})

print(f"Total COUNCILS in docs/data.js: {len(all_councils)}")
for i, c in enumerate(all_councils):
    if "isNew" in c["item"] or "category" not in c["item"] or "ministry" not in c["item"]:
        print(f"Index {i}: [{c['id']}] {c['name']} -> {c['item']}")
