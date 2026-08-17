import json
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
report_path = os.path.join(project_root, "admin", "ai_verification_report.json")
data_js_path = os.path.join(project_root, "docs", "data.js")

if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    print("Total items in AI report:", len(report))
    for k, v in report.items():
        if v.get("verdict") != "approved":
            print(f"  - [{k}] Verdict: {v.get('verdict')}, Reason: {v.get('reason')}")
