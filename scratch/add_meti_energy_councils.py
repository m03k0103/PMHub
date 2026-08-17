import json
import os
import re
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, ".."))
discovered_file = os.path.join(project_root, "admin", "discovered_councils.json")
data_js_file = os.path.join(project_root, "docs", "data.js")

# 1. Fetch content of https://www.meti.go.jp/shingikai/energy_environment/
base_url = "https://www.meti.go.jp/shingikai/energy_environment/"
req = urllib.request.Request(base_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
with urllib.request.urlopen(req) as response:
    html_content = response.read().decode("utf-8", errors="replace")

soup = BeautifulSoup(html_content, "html.parser")
base_url = "https://www.meti.go.jp/shingikai/energy_environment/"

# Find links inside ul.lineShin
ul = soup.find("ul", class_="lineShin")
extracted_items = []
if ul:
    for a in ul.find_all("a", href=True):
        href = a["href"].strip()
        name = a.get_text(strip=True)
        # Remove special characters
        name = re.sub(r'[\s\u00a0]+', ' ', name).strip()
        
        abs_url = urllib.parse.urljoin(base_url, href)
        
        category = "STUDY"
        if "部会" in name:
            category = "SECTION"
        elif "分科会" in name:
            category = "SUBCOMMITTEE"
        elif "ワーキンググループ" in name or "WG" in name:
            category = "WORKING_GROUP"
        elif "検討会" in name or "研究会" in name or "勉強会" in name:
            category = "STUDY"
        elif "委員会" in name:
            category = "COMMITTEE"
        elif "協議会" in name or "会議" in name or "プラットフォーム" in name:
            category = "HQ"
            
        extracted_items.append({
            "name": name,
            "url": abs_url,
            "category": category
        })

print(f"Extracted {len(extracted_items)} items from METI Energy & Environment page.")

# 2. Update discovered_councils.json
with open(discovered_file, "r", encoding="utf-8") as f:
    disc_data = json.load(f)

councils = disc_data.get("councils", [])

# Remove anre-204 (その他、各種研究会・検討会等はこちら（経済産業省WEBサイト）)
filtered_councils = [
    c for c in councils 
    if not (c.get("id") == "anre-204" or "その他、各種研究会・検討会等はこちら" in c.get("name", ""))
]
print(f"Removed item #204 / anre-204. Remaining councils: {len(filtered_councils)}")

# Track existing URLs and Names for deduplication
existing_urls = {c.get("officialUrl") for c in filtered_councils if c.get("officialUrl")}
existing_names = {c.get("name") for c in filtered_councils if c.get("name")}

max_seq = 183
for c in filtered_councils:
    cid = c.get("id", "")
    m = re.search(r"-(\d+)$", cid)
    if m:
        max_seq = max(max_seq, int(m.group(1)))

added_count = 0
for item in extracted_items:
    if item["url"] in existing_urls or item["name"] in existing_names:
        continue
        
    max_seq += 1
    new_id = f"meti-{max_seq}"
    
    new_council = {
        "id": new_id,
        "name": item["name"],
        "ministry": "METI",
        "category": item["category"],
        "officialUrl": item["url"],
        "isNew": True,
        "trackedSince": "2026-08-11",
        "sourcePageUrl": base_url
    }
    
    filtered_councils.append(new_council)
    existing_urls.add(item["url"])
    existing_names.add(item["name"])
    added_count += 1

disc_data["councils"] = filtered_councils
disc_data["totalDiscovered"] = len(filtered_councils)

with open(discovered_file, "w", encoding="utf-8") as f:
    json.dump(disc_data, f, ensure_ascii=False, indent=2)

print(f"Added {added_count} new METI Energy & Environment councils to discovered_councils.json.")
print(f"New total councils count in discovered_councils.json: {len(filtered_councils)}")

# 3. Add URL to data.js MINISTRIES.METI.councilsUrls if not present
with open(data_js_file, "r", encoding="utf-8") as f:
    data_js_content = f.read()

if base_url not in data_js_content:
    data_js_content = data_js_content.replace(
        "'https://www.meti.go.jp/shingikai/index.html'",
        "'https://www.meti.go.jp/shingikai/index.html', 'https://www.meti.go.jp/shingikai/energy_environment/'"
    )
    with open(data_js_file, "w", encoding="utf-8") as f:
        f.write(data_js_content)
    print("Added METI energy_environment URL to docs/data.js councilsUrls.")
