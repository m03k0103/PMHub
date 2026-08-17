import json
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
discovered_file = os.path.join(project_root, "admin", "discovered_councils.json")
data_js_file = os.path.join(project_root, "docs", "data.js")

with open(discovered_file, "r", encoding="utf-8") as f:
    disc_data = json.load(f)

councils = disc_data.get("councils", [])

councils_to_add = [
    {
        "id": "mof-1731",
        "name": "財政制度等審議会 財政制度分科会 法制・公会計部会",
        "ministry": "MOF",
        "category": "SECTION",
        "officialUrl": "https://www.mof.go.jp/about_mof/councils/fiscal_system_council/sub-of_fiscal_system/proceedings_pf/index.html",
        "isNew": True,
        "trackedSince": "2026-08-11",
        "sourcePageUrl": "https://www.mof.go.jp/about_mof/councils/fiscal_system_council/index.html"
    },
    {
        "id": "mof-1732",
        "name": "財政制度等審議会財政制度分科会 公聴会等",
        "ministry": "MOF",
        "category": "SUBCOMMITTEE",
        "officialUrl": "https://www.mof.go.jp/about_mof/councils/fiscal_system_council/sub-of_fiscal_system/local_hearing/index.html",
        "isNew": True,
        "trackedSince": "2026-08-11",
        "sourcePageUrl": "https://www.mof.go.jp/about_mof/councils/fiscal_system_council/index.html"
    }
]

existing_urls = {c.get("officialUrl") for c in councils if c.get("officialUrl")}
existing_names = {c.get("name") for c in councils if c.get("name")}

added = 0
for new_c in councils_to_add:
    if new_c["officialUrl"] not in existing_urls and new_c["name"] not in existing_names:
        councils.append(new_c)
        existing_urls.add(new_c["officialUrl"])
        existing_names.add(new_c["name"])
        added += 1

disc_data["councils"] = councils
disc_data["totalDiscovered"] = len(councils)

with open(discovered_file, "w", encoding="utf-8") as f:
    json.dump(disc_data, f, ensure_ascii=False, indent=2)

print(f"Added {added} new MOF councils to discovered_councils.json. Total count: {len(councils)}")
