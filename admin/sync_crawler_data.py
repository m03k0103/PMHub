import json
import os
import re
import subprocess
import sys
from datetime import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(base_dir, "scraped_councils_output.json")
data_js_path = os.path.abspath(os.path.join(base_dir, "..", "docs", "data.js"))

if not os.path.exists(json_path):
    print(f"Error: {json_path} does not exist.")
    sys.exit(1)

with open(json_path, "r", encoding="utf-8") as f:
    scraped_data = json.load(f)

with open(data_js_path, "r", encoding="utf-8") as f:
    content = f.read()

# MEETINGS の配列定義部分を見つける
# 例: const MEETINGS = [ ... ];
meetings_match = re.search(r"(const MEETINGS\s*=\s*\[)([\s\S]*?)(\n\];)", content)
if not meetings_match:
    print("Error: MEETINGS array pattern not found in data.js")
    sys.exit(1)

prefix_decl = meetings_match.group(1)
body_str = meetings_match.group(2)
suffix_bracket = meetings_match.group(3)

# 既存の全IDを抽出して重複追加を防止
existing_ids = set(re.findall(r"id:\s*['\"]([^'\"]+)['\"]", body_str))

new_items = []

for council in scraped_data:
    c_id = council.get("councilId")
    if not c_id:
        continue
    c_name = council.get("councilName", "不明な会議体")
    ministry = council.get("ministry", "UNKNOWN")
    official_url = council.get("officialUrl", "")
    subpages = council.get("subpageMeetings", [])
    top_materials = council.get("materials", [])
    
    if subpages:
        for i, sub in enumerate(subpages):
            m_id = f"crawler-{c_id}-sub{i}"
            if m_id in existing_ids:
                continue
            
            title = sub.get("title", f"{c_name} (サブページ)")
            mats = sub.get("materials", [])
            dates = sub.get("extractedDates", [])
            date_str = dates[0] if dates else datetime.now().strftime("%Y-%m-%d")
            
            mats_str = ",\n      ".join([
                f"{{ name: {repr(m['name'])}, url: {repr(m['url'])}, type: {repr(m.get('type',''))} }}"
                for m in mats if isinstance(m, dict) and 'name' in m and 'url' in m
            ])
            
            new_item = f"""  {{
    id: '{m_id}',
    councilId: '{c_id}',
    councilName: '{c_name}',
    title: {repr(title)},
    date: '{date_str}',
    ministry: '{ministry}',
    category: 'council',
    officialUrl: '{sub.get("subpageUrl", official_url)}',
    materials: [
      {mats_str}
    ]
  }}"""
            new_items.append(new_item)
            existing_ids.add(m_id)

    elif top_materials:
        m_id = f"crawler-{c_id}-top"
        if m_id in existing_ids:
            continue
        
        mats_str = ",\n      ".join([
            f"{{ name: {repr(m['name'])}, url: {repr(m['url'])}, type: {repr(m.get('type',''))} }}"
            for m in top_materials if isinstance(m, dict) and 'name' in m and 'url' in m
        ])
        
        new_item = f"""  {{
    id: '{m_id}',
    councilId: '{c_id}',
    councilName: '{c_name}',
    title: '{c_name} 最新資料 (自動抽出)',
    date: '{datetime.now().strftime("%Y-%m-%d")}',
    ministry: '{ministry}',
    category: 'council',
    officialUrl: '{official_url}',
    materials: [
      {mats_str}
    ]
  }}"""
        new_items.append(new_item)
        existing_ids.add(m_id)

if not new_items:
    print("No new items to add.")
else:
    # body_str の末尾の空白をトリム
    body_trimmed = body_str.rstrip()
    # 既存の最後のオブジェクトの末尾にカンマがない場合はカンマを追加
    if body_trimmed and not body_trimmed.endswith(","):
        body_trimmed += ","
    
    new_items_joined = ",\n".join(new_items)
    
    updated_body = body_trimmed + "\n" + new_items_joined + "\n"
    new_content = content[:meetings_match.start(2)] + updated_body + content[meetings_match.end(2):]
    
    with open(data_js_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"Successfully appended {len(new_items)} new meeting items to docs/data.js.")

# 自動構文チェック & バリデーションテスト
print("\n--- Running automated syntax verification on docs/data.js ---")
node_code = (
    "const vm = require('vm'); const fs = require('fs'); "
    "const code = fs.readFileSync('./docs/data.js', 'utf8'); "
    "const res = vm.runInNewContext(code + '\\n; ({COUNCILS: typeof COUNCILS !== \\'undefined\\' ? COUNCILS : [], MEETINGS: typeof MEETINGS !== \\'undefined\\' ? MEETINGS : []});'); "
    "console.log('VALIDATION SUCCESS! COUNCILS count:', res.COUNCILS.length, 'MEETINGS count:', res.MEETINGS.length);"
)

test_proc = subprocess.run(["node", "-e", node_code], cwd=os.path.abspath(os.path.join(base_dir, "..")), capture_output=True, text=True)

if test_proc.returncode == 0:
    print(test_proc.stdout.strip())
    print("--- Test Passed ---")
else:
    print("[ERROR] Automated test failed!")
    print(test_proc.stderr.strip())
    sys.exit(1)
