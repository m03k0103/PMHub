#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 会議レコード重複防止・回次整合性テスト (Test for No Duplicate Meetings & Clean Rounds)
"""

import json
import os
import re
import sys
import io
from collections import defaultdict

# Windows ターミナルログの文字化け防止 (chcp 65001 & UTF-8 再構成)
if sys.platform == "win32":
    os.system("chcp 65001 > NUL 2>&1")
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass


def to_halfwidth(s):
    if not s:
        return ""
    return str(s).translate(str.maketrans('０１２３４５６７８９', '0123456789'))

def extract_round_and_type(title, council_name=""):
    t_norm = to_halfwidth(title)
    
    sub_type = ""
    fy_m = re.search(r'(令和\d+年度|平成\d+年度|令和\d+年|平成\d+年)', t_norm)
    if fy_m and fy_m.group(1) not in council_name:
        sub_type += fy_m.group(1)

    if 'フォローアップ' in t_norm:
        sub_type += "_フォローアップ会合"
    elif '幹事会' in t_norm and '幹事会' not in council_name:
        sub_type += "_幹事会"
    elif ('ワーキンググループ' in t_norm or ' WG' in t_norm) and ('WG' not in council_name and 'ワーキンググループ' not in council_name):
        sub_type += "_WG"
    elif '分科会' in t_norm and '分科会' not in council_name:
        sub_type += "_分科会"

    m = re.search(r'第\s*(\d+)\s*回', t_norm)
    return (int(m.group(1)), sub_type) if m else (None, "")


def run_test():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.abspath(os.path.join(base_dir, "..", "docs", "data.json"))
    
    if not os.path.exists(data_path):
        print(f"FAIL: {data_path} not found")
        return 1
        
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    councils = {c['id']: c for c in data.get('councils', [])}
    meetings = data.get('meetings', [])
    
    errors = []
    
    # 1. Check duplicate IDs
    id_counts = defaultdict(int)
    for m in meetings:
        id_counts[m.get('id', '')] += 1
    dup_ids = {k: v for k, v in id_counts.items() if v > 1}
    if dup_ids:
        errors.append(f"Duplicate meeting IDs found: {dup_ids}")
        
    # 2. Check duplicate (councilId, title, date)
    key_counts = defaultdict(int)
    for m in meetings:
        key_counts[(m.get('councilId'), m.get('title'), m.get('date'))] += 1
    dup_keys = {k: v for k, v in key_counts.items() if v > 1}
    if dup_keys:
        errors.append(f"Duplicate (councilId, title, date) found: {dup_keys}")
        
    # 3. Check duplicate 第n回 in same council
    meetings_by_council = defaultdict(list)
    for m in meetings:
        meetings_by_council[m.get('councilId', 'unknown')].append(m)
        
    for c_id, m_list in meetings_by_council.items():
        c_name = councils.get(c_id, {}).get('name', c_id)
        round_map = defaultdict(list)
        for m in m_list:
            r_num, sub_type = extract_round_and_type(m.get('title', ''), c_name)
            if r_num is not None:
                round_map[(r_num, sub_type)].append(m)
                
        dup_rounds = {k: ms for k, ms in round_map.items() if len(ms) > 1}
        if dup_rounds:
            for (rn, st), ms in dup_rounds.items():
                errors.append(f"Council '{c_name}' ({c_id}) has {len(ms)} records for 第{rn}回{st}: {[m.get('id') for m in ms]}")
                
    # 4. Check for crawler fragment IDs left in data.json
    crawler_subs = [m.get('id') for m in meetings if m.get('id', '').startswith('crawler-')]
    if crawler_subs:
        errors.append(f"Unmerged crawler fragment records found ({len(crawler_subs)} items): {crawler_subs[:5]}...")
        
    # 5. Check date format
    bad_dates = [m.get('date') for m in meetings if not re.match(r'^\d{4}/\d{2}/\d{2}$', m.get('date', ''))]
    if bad_dates:
        errors.append(f"Invalid date formats found ({len(bad_dates)} items): {bad_dates[:5]}")

    # 6. Check for auto-extracted generic titles
    bad_titles = [m.get('title') for m in meetings if any(w in m.get('title', '') for w in ['自動抽出', '最新資料 (', '直近会合', '最新会合'])]
    if bad_titles:
        errors.append(f"Generic/auto-extracted meeting titles found ({len(bad_titles)} items): {bad_titles[:5]}")

    # 8. Check councilId format (Must have exactly 1 hyphen: {ministry}-{slug})
    bad_c_ids = [c_id for c_id in councils.keys() if c_id.count('-') != 1 or not re.match(r'^[a-z]+-[a-z0-9_]+$', c_id)]
    if bad_c_ids:
        errors.append(f"Invalid councilId format (must be {{ministry}}-{{slug}} with 1 hyphen) ({len(bad_c_ids)} items): {bad_c_ids[:5]}")

    # 9. Check meetingId format (Must have exactly 3 hyphens: {councilId}-{YYYYMMDD}-{round/session})
    bad_m_ids = [m.get('id') for m in meetings if m.get('id', '').count('-') != 3 or not re.match(r'^[a-z]+-[a-z0-9_]+-\d{8}-[a-z0-9_]+$', m.get('id', ''))]
    if bad_m_ids:
        errors.append(f"Invalid meetingId format (must be {{councilId}}-{{YYYYMMDD}}-{{round}} with 3 hyphens) ({len(bad_m_ids)} items): {bad_m_ids[:5]}")

    if errors:
        print(f"FAILED: {len(errors)} validation errors found:")
        for e in errors:
            print(f"  - {e}")
        return 1
        
    print(f"PASSED: All {len(meetings)} meetings across {len(councils)} councils validated with zero duplicates.")
    return 0

if __name__ == '__main__':
    sys.exit(run_test())
