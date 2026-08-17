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

print(f"Total COUNCILS count: {len(all_councils)}")
for i, c in enumerate(all_councils, 1):
    print(f"{i:3d}. [{c['id']}] {c['name']}")
