import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
data_js_path = os.path.join(project_root, "docs", "data.js")
report_path = os.path.join(project_root, "admin", "ai_verification_report.json")

# Load COUNCILS from docs/data.js
with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

councils_match = re.search(r"const COUNCILS = (\[[\s\S]*?\n\];)", content)
councils = []
if councils_match:
    c_str = councils_match.group(1)
    for m in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"][\s\S]*?name:\s*['\"]([^'\"]+)['\"]", c_str):
        councils.append({"id": m.group(1), "name": m.group(2)})

print(f"Total COUNCILS in docs/data.js: {len(councils)}")

# Load ai_verification_report.json if exists
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    print("Checking if any council in docs/data.js has a non-approved entry in ai_verification_report.json:")
    for c in councils:
        cid = c["id"]
        if cid in report:
            verdict = report[cid].get("verdict")
            if verdict != "approved":
                print(f"  FOUND NON-APPROVED IN REPORT: [{cid}] {c['name']} (verdict: {verdict})")

# Let's check KNOWN_NEW_IDS in admin_dashboard.html
dashboard_path = os.path.join(project_root, "admin", "admin_dashboard.html")
with open(dashboard_path, "r", encoding="utf-8") as f:
    dash_content = f.read()

known_ids_match = re.search(r"const KNOWN_NEW_IDS = (\[[\s\S]*?\]);", dash_content)
known_new_ids = set()
if known_ids_match:
    known_new_ids = set(re.findall(r"['\"]([^'\"]+)['\"]", known_ids_match.group(1)))

print("Checking if any council in docs/data.js is in KNOWN_NEW_IDS:")
for c in councils:
    if c["id"] in known_new_ids:
        print(f"  FOUND IN KNOWN_NEW_IDS: [{c['id']}] {c['name']}")
