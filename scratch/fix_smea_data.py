import json
import os
import re

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
discovered_file = os.path.join(project_root, "admin", "discovered_councils.json")
data_js_file = os.path.join(project_root, "docs", "data.js")

# 1. Update data.js MINISTRIES.SMEA.councilsUrls to use index.html
with open(data_js_file, "r", encoding="utf-8") as f:
    data_js_content = f.read()

old_url = "'https://www.chusho.meti.go.jp/koukai/kenkyukai/'"
new_url = "'https://www.chusho.meti.go.jp/koukai/kenkyukai/index.html'"

if old_url in data_js_content:
    data_js_content = data_js_content.replace(old_url, new_url)
    with open(data_js_file, "w", encoding="utf-8") as f:
        f.write(data_js_content)
    print("Updated docs/data.js MINISTRIES.SMEA.councilsUrls")
else:
    print("docs/data.js already has the updated SMEA kenkyukai URL or pattern not found.")

# 2. Process discovered_councils.json
if not os.path.exists(discovered_file):
    print("discovered_councils.json not found")
    exit(0)

with open(discovered_file, "r", encoding="utf-8") as f:
    disc_data = json.load(f)

councils = disc_data.get("councils", [])

def clean_council_name(name):
    # Remove prefix date / meeting numbers
    name = re.sub(r'^(令和\d+年\d+月\d+日開催|令和\d+年\d+月\d+日|令和\d+年|平成\d+年|\b\d{4}年\d+月\d+日開催?)\s*', '', name)
    name = re.sub(r'^(第[0-9０-９一-九]+回|第[0-9０-９一-九]+回\s*)\s*', '', name)
    name = re.sub(r'^(令和\d+年\s*第[0-9０-９一-九]+回|平成\d+年\s*第[0-9０-９一-九]+回)\s*', '', name)
    # Remove trailing '配布資料', '取りまとめ...', 'の開催について' etc.
    name = re.sub(r'\s*(配布資料|取りまとめ.*|について|開催概要|議事要旨|議事録)$', '', name)
    return name.strip()

non_smea_councils = []
smea_meeting_councils = []
smea_parent_councils = {}

for c in councils:
    is_smea = (c.get("ministry") == "SMEA") or ("chusho.meti.go.jp" in c.get("officialUrl", ""))
    name = c.get("name", "")
    
    # Check if it has "第X回" or date meeting patterns
    is_meeting_pattern = bool(re.search(r'第[0-9０-９一-九]+回|令和\d+年|\d{4}年\d+月\d+日', name))
    
    if is_smea and is_meeting_pattern:
        parent_name = clean_council_name(name)
        if not parent_name:
            parent_name = name
            
        smea_meeting_councils.append(c)
        
        # Track parent council
        if parent_name not in smea_parent_councils:
            smea_parent_councils[parent_name] = {
                "id": f"smea-parent-{len(smea_parent_councils)+1}",
                "name": parent_name,
                "ministry": "SMEA",
                "category": "STUDY" if "研究会" in parent_name else ("COMMITTEE" if "委員会" in parent_name else "STUDY"),
                "officialUrl": "https://www.chusho.meti.go.jp/koukai/kenkyukai/index.html",
                "isNew": True,
                "trackedSince": c.get("trackedSince", "2026-08-09"),
                "sourcePageUrl": "https://www.chusho.meti.go.jp/koukai/kenkyukai/index.html"
            }
    else:
        # Keep non-meeting items (including normal parent councils or non-SMEA councils)
        # Update SMEA sourcePageUrl if relevant
        if is_smea and "kenkyukai" in c.get("sourcePageUrl", ""):
            c["sourcePageUrl"] = "https://www.chusho.meti.go.jp/koukai/kenkyukai/index.html"
        non_smea_councils.append(c)

print(f"Original total councils in discovered_councils.json: {len(councils)}")
print(f"Identified SMEA meeting-like items removed from councils list: {len(smea_meeting_councils)}")
print(f"Created/Consolidated SMEA parent councils: {len(smea_parent_councils)}")

# Combine non-meeting councils + consolidated SMEA parent councils
updated_councils = non_smea_councils + list(smea_parent_councils.values())
disc_data["councils"] = updated_councils
disc_data["totalDiscovered"] = len(updated_councils)

with open(discovered_file, "w", encoding="utf-8") as f:
    json.dump(disc_data, f, ensure_ascii=False, indent=2)

print(f"Updated discovered_councils.json. New total councils: {len(updated_councils)}")

# List extracted SMEA parent councils
print("\nConsolidated SMEA Parent Councils:")
for name in sorted(smea_parent_councils.keys()):
    print("  -", name)
