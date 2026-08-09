import re

file_path = "d:/dev/PMHub/docs/data.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

updates = [
    {
        "id": "meet-2025-1003-cas-atarashii-sihon-107",
        "old_url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/index.html",
        "new_url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/kaigi/dai37/gijisidai.html"
    },
    {
        "id": "cas-roumuhi-tenka-108",
        "old_url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/index.html",
        "new_url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/wgkaisai/index.html"
    },
    {
        "id": "meet-2025-0630-cas-roumuhi-tenka-108",
        "old_url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/index.html",
        "new_url": "https://www.cas.go.jp/jp/seisaku/atarashii_sihonsyugi/wgkaisai/roumuhitenka_dai5/index.html"
    },
    {
        "id": "meet-2026-0519-cao-kisei-chiiki-wg-109",
        "old_url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html",
        "new_url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/wg/2501_01local/260519/local11_agenda.html"
    },
    {
        "id": "cao-kisei-iryou-wg-110",
        "old_url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html",
        "new_url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html#medical_2510"
    },
    {
        "id": "meet-2026-0515-cao-kisei-iryou-wg-110",
        "old_url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/meeting.html",
        "new_url": "https://www8.cao.go.jp/kisei-kaikaku/kisei/meeting/wg/2501_02medical/250501/medical05_agenda.html"
    }
]

for update in updates:
    target_id = update["id"]
    old_url = update["old_url"]
    new_url = update["new_url"]
    
    # We want to replace the first occurrence of officialUrl: 'old_url' after id: 'target_id'
    # Use [\s\S]*? to lazily match any character, including newlines.
    pattern = re.compile(rf"(id:\s*'{re.escape(target_id)}'[\s\S]*?officialUrl:\s*'){re.escape(old_url)}(')")
    
    new_content, count = pattern.subn(rf"\g<1>{new_url}\g<2>", content, count=1)
    if count == 0:
        print(f"Failed to replace for {target_id}")
    else:
        print(f"Successfully replaced for {target_id}")
        content = new_content

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
