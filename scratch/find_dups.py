import os, re
path = 'docs/data.js'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to find all id values in the COUNCILS list
councils_match = re.search(r'const COUNCILS = (\[[\s\S]*?\n\];)', content)
if councils_match:
    c_str = councils_match.group(1)
    ids = re.findall(r"\{\s*id:\s*['\"]([^'\"]+)['\"]", c_str)
    from collections import Counter
    c = Counter(ids)
    dups = {k: v for k, v in c.items() if v > 1}
    print(f'Total items in COUNCILS: {len(ids)}')
    print(f'Unique IDs: {len(c)}')
    print(f'Duplicates: {dups}')
else:
    print("Could not parse COUNCILS")
