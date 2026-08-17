import os
path = 'admin/admin_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('docs/data.js', 'docs/data.json')
c = c.replace('data.js ではありませんが', 'data.json ではありませんが')
c = c.replace("endsWith('data.js')", "endsWith('data.json')")
with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
