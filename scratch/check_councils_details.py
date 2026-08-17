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

meetings_match = re.search(r"const MEETINGS = (\[[\s\S]*?\n\];)", content)
meeting_counts = {}
if meetings_match:
    m_str = meetings_match.group(1)
    for m in re.finditer(r"councilId:\s*['\"]([^'\"]+)['\"]", m_str):
        cid = m.group(1)
        meeting_counts[cid] = meeting_counts.get(cid, 0) + 1

print(f"Total COUNCILS in data.js: {len(all_councils)}")

print("\nCouncils with 0 meetings in docs/data.js:")
zero_meetings = []
for c in all_councils:
    cid = c["id"]
    cnt = meeting_counts.get(cid, 0)
    if cnt == 0:
        zero_meetings.append(c)
        print(f"  - [{cid}] {c['name']}")

print(f"\nTotal zero-meeting councils: {len(zero_meetings)}")
