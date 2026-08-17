import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")
report_path = os.path.join(project_root, "admin", "ai_verification_report.json")
discovered_path = os.path.join(project_root, "admin", "discovered_councils.json")

# 1. Load data.js COUNCILS
with open(data_js_path, "r", encoding="utf-8") as f:
    data_js_content = f.read()

councils_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", data_js_content)
data_js_councils = []
if councils_match:
    c_str = councils_match.group(1).rstrip(";").strip()
    # Simple regex match for objects inside array
    for m in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?name:\s*['\"]([^'\"]+)['\"]", c_str):
        data_js_councils.append({
            "id": m.group(1),
            "name": m.group(2)
        })

print(f"Total councils currently in docs/data.js: {len(data_js_councils)}")

# 2. Load ai_verification_report.json
ai_report = {}
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        try:
            ai_report = json.load(f)
        except Exception as e:
            print("Error loading ai_verification_report.json:", e)

# 3. Load discovered_councils.json
disc_councils = []
if os.path.exists(discovered_path):
    with open(discovered_path, "r", encoding="utf-8") as f:
        disc_data = json.load(f)
        disc_councils = disc_data.get("councils", [])

disc_dict = {c["id"]: c for c in disc_councils if "id" in c}

print(f"Total items in ai_verification_report.json: {len(ai_report)}")
approved_in_report = {k: v for k, v in ai_report.items() if v.get("verdict") == "approved"}
rejected_in_report = {k: v for k, v in ai_report.items() if v.get("verdict") == "rejected"}

print(f"Approved in AI Report: {len(approved_in_report)}")
print(f"Rejected in AI Report: {len(rejected_in_report)}")

# Check overlap with data.js
unapproved_in_data_js = []
for c in data_js_councils:
    cid = c["id"]
    # Check if in ai_report as rejected
    if cid in ai_report and ai_report[cid].get("verdict") != "approved":
        unapproved_in_data_js.append((c, ai_report[cid].get("verdict"), ai_report[cid].get("reason")))

print(f"Unapproved items currently in docs/data.js: {len(unapproved_in_data_js)}")
for c, v, r in unapproved_in_data_js[:20]:
    print(f"  - [{c['id']}] {c['name']} (Verdict: {v}, Reason: {r})")
