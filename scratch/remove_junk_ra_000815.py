import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")

with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Fix aca-184 name from '文化審議会について' to '文化審議会'
content = content.replace("name: '文化審議会について'", "name: '文化審議会'")

# 2. Remove ra-000815-79 block
# Search for block containing id: 'ra-000815-79'
pattern = r"\s*\{\s*id:\s*['\"]ra-000815-79['\"][\s\S]*?\n\s*\},?"
new_content = re.sub(pattern, "", content)

with open(data_js_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Updated docs/data.js: removed ra-000815-79 and fixed aca-184 name.")
