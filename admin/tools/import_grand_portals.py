"""
import_grand_portals.py:
Drop 114: Track [Grand-Portals] 5大親ポータル会議体の網羅的正常化
対象:
1. meti-sankoshin_chiteki_zaisan (METI/JPO)
2. cao-252 (SCJ)
3. jfa-shigen_kanri_houshin (JFA)
4. mic-fufuku_shinsa (MIC)
5. mext-715 (MEXT)
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import unicodedata
import json
import time
import os

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8'
}

def clean_text(s):
    if not s:
        return ""
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'\s+', ' ', s).strip()

def parse_wareki(txt):
    """令和/平成/昭和の日付を YYYY/MM/DD に変換"""
    txt = unicodedata.normalize('NFKC', txt)
    m = re.search(r'(令和|平成|昭和)\s*(\d+|元)年\s*(\d+)月\s*(\d+)日', txt)
    if not m:
        return None
    era, y_str, m_str, d_str = m.groups()
    y = 1 if y_str == '元' else int(y_str)
    if era == '令和':
        year = 2018 + y
    elif era == '平成':
        year = 1988 + y
    elif era == '昭和':
        year = 1925 + y
    else:
        return None
    return f"{year:04d}/{int(m_str):02d}/{int(d_str):02d}"

def get_soup(url):
    time.sleep(0.35)
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.encoding = r.apparent_encoding
    return BeautifulSoup(r.text, 'html.parser')

def run_import(dry_run=True):
    conn = sqlite3.connect('admin/pmhub.db')
    c = conn.cursor()

    collected_meetings = []
    updated_councils = []
    new_scraping_rules = {}

    # =========================================================================
    # 1. METI/JPO: 産業構造審議会 知的財産分科会
    # =========================================================================
    print("--- 1. METI/JPO 知的財産分科会 ---")
    jpo_url = "https://www.jpo.go.jp/resources/shingikai/sangyo-kouzou/shousai/chizai_bunkakai/index.html"
    updated_councils.append((jpo_url, "meti-sankoshin_chiteki_zaisan"))
    new_scraping_rules["meti-sankoshin_chiteki_zaisan"] = {
        "officialUrl": jpo_url,
        "template": "tpl-general-multiministry-session",
        "subpage_discovery_pattern": "[^\"']*(?:chizai_bunkakai/\\d+-(?:gijiyoushi|shiryou)\\.html|gijiroku\\.pdf)",
        "pdf_selector": "a[href*='.pdf'], a[href*='.PDF']",
        "date_regex": "(\\d{4}年\\d{1,2}月\\d{1,2}日|令和\\d+年\\d{1,2}月\\d{1,2}日|平成\\d+年\\d{1,2}月\\d{1,2}日)",
        "manualLock": True
    }
    s_jpo = get_soup(jpo_url)
    tables = s_jpo.find_all('table')
    if len(tables) >= 2:
        for tr in tables[0].find_all('tr')[1:]:
            tds = tr.find_all(['td', 'th'])
            if len(tds) < 2:
                continue
            name_raw = clean_text(tds[0].get_text())
            m_kai = re.search(r'第(\d+)回', name_raw)
            date_str = parse_wareki(name_raw)
            if not m_kai or not date_str:
                continue
            num = int(m_kai.group(1))
            date_digits = date_str.replace('/', '')
            m_id = f"meti-sankoshin_chiteki_zaisan-{date_digits}-{num:03d}"
            m_name = f"第{num}回 産業構造審議会 知的財産分科会"
            
            mats = []
            for td in tds[1:]:
                for a in td.find_all('a', href=True):
                    mat_title = clean_text(a.get_text())
                    mat_url = urljoin(jpo_url, a['href'])
                    if mat_title and mat_url:
                        if mat_title in ['配付資料', '配布資料', '資料', '議事要旨', '議事録']:
                            mat_title = f"{m_name} {mat_title}"
                        mats.append({"name": mat_title, "url": mat_url})
            
            collected_meetings.append({
                "council_id": "meti-sankoshin_chiteki_zaisan",
                "meeting_id": m_id,
                "name": m_name,
                "date": date_str,
                "official_url": jpo_url,
                "materials": mats
            })

        for i, tr in enumerate(tables[1].find_all('tr')[1:], start=1):
            tds = tr.find_all(['td', 'th'])
            if len(tds) < 2:
                continue
            name_raw = clean_text(tds[0].get_text())
            m_kai = re.search(r'第(\d+)回', name_raw)
            date_str = parse_wareki(name_raw)
            if not m_kai or not date_str:
                continue
            num = int(m_kai.group(1))
            date_digits = date_str.replace('/', '')
            m_id = f"meti-sankoshin_chiteki_zaisan-{date_digits}-s{num:02d}"
            m_name = f"第{num}回 産業構造審議会 知的財産分科会 政策部会"
            
            mats = []
            for td in tds[1:]:
                for a in td.find_all('a', href=True):
                    mat_title = clean_text(a.get_text())
                    mat_url = urljoin(jpo_url, a['href'])
                    if mat_title and mat_url:
                        if mat_title in ['配付資料', '配布資料', '資料', '議事要旨', '議事録']:
                            mat_title = f"{m_name} {mat_title}"
                        mats.append({"name": mat_title, "url": mat_url})
            
            collected_meetings.append({
                "council_id": "meti-sankoshin_chiteki_zaisan",
                "meeting_id": m_id,
                "name": m_name,
                "date": date_str,
                "official_url": jpo_url,
                "materials": mats
            })

    print(f"JPO meetings collected: {len([m for m in collected_meetings if m['council_id'] == 'meti-sankoshin_chiteki_zaisan'])}")

    # =========================================================================
    # 2. CAO-252: 日本学術会議（幹事会）
    # =========================================================================
    print("--- 2. CAO-252 日本学術会議 幹事会 ---")
    scj_url = "https://www.scj.go.jp/ja/member/iinkai/kanji/index.html"
    updated_councils.append((scj_url, "cao-252"))
    new_scraping_rules["cao-252"] = {
        "officialUrl": scj_url,
        "template": "tpl-general-round-subpage",
        "subpage_discovery_pattern": "[^\"']*(?:siryo\\d+\\.html)",
        "pdf_selector": "a[href*='.pdf'], a[href*='.PDF']",
        "date_regex": "(?:令和|平成)\\s*\\d+年\\s*\\d+月\\s*\\d+日",
        "manualLock": True
    }
    s_scj = get_soup(scj_url)
    for a in s_scj.find_all('a', href=True):
        href = a['href']
        m_kai = re.search(r'siryo(\d+)\.html', href)
        if not m_kai:
            continue
        num = int(m_kai.group(1))
        
        tr = a.find_parent('tr')
        date_str = None
        if tr:
            date_str = parse_wareki(tr.get_text())
        if not date_str:
            for p in [a.parent, a.parent.parent if a.parent else None]:
                if p:
                    date_str = parse_wareki(p.get_text())
                    if date_str:
                        break
        if not date_str:
            continue
        
        date_digits = date_str.replace('/', '')
        m_id = f"cao-252-{date_digits}-{num:03d}"
        m_name = f"第{num}回 日本学術会議 幹事会"
        sub_url = urljoin(scj_url, href)
        
        mats = []
        try:
            sub_soup = get_soup(sub_url)
            for sa in sub_soup.find_all('a', href=True):
                s_href = sa['href']
                if s_href.lower().endswith('.pdf'):
                    mat_title = clean_text(sa.get_text())
                    mat_url = urljoin(sub_url, s_href)
                    if mat_title and mat_url:
                        if mat_title in ['配付資料', '配布資料', '資料', '議事要旨', '議事録']:
                            mat_title = f"{m_name} {mat_title}"
                        mats.append({"name": mat_title, "url": mat_url})
        except Exception as e:
            print(f"Error fetching subpage {sub_url}: {e}")

        if not mats:
            mats.append({"name": m_name, "url": sub_url})

        collected_meetings.append({
            "council_id": "cao-252",
            "meeting_id": m_id,
            "name": m_name,
            "date": date_str,
            "official_url": sub_url,
            "materials": mats
        })

    print(f"SCJ meetings collected: {len([m for m in collected_meetings if m['council_id'] == 'cao-252'])}")

    # =========================================================================
    # 3. JFA: 水産庁 資源管理方針に関する検討会（系群・海域別完全一意化）
    # =========================================================================
    print("--- 3. JFA 資源管理方針に関する検討会 ---")
    jfa_url = "https://www.jfa.maff.go.jp/j/study/kanri/231027_3.html"
    updated_councils.append((jfa_url, "jfa-shigen_kanri_houshin"))
    new_scraping_rules["jfa-shigen_kanri_houshin"] = {
        "officialUrl": jfa_url,
        "template": "tpl-general-round-subpage",
        "subpage_discovery_pattern": "[^\"']*(?:kanri/\\d+(?:_\\d+)?\\.html)",
        "pdf_selector": "a[href*='.pdf'], a[href*='.PDF']",
        "date_regex": "(?:令和|平成)\\s*\\d+年\\s*\\d+月\\s*\\d+日",
        "manualLock": True
    }
    
    jfa_targets = [
        ("サバ類", "https://www.jfa.maff.go.jp/j/study/kanri/231027_3.html"),
        ("マアジ・マイワシ", "https://www.jfa.maff.go.jp/j/study/kanri/231027_10.html"),
        ("スケトウダラ", "https://www.jfa.maff.go.jp/j/study/kanri/231027.html"),
        ("ズワイガニ", "https://www.jfa.maff.go.jp/j/study/kanri/231027_9.html")
    ]
    
    seen_jfa_keys = set()
    for fish_name, f_url in jfa_targets:
        try:
            s_fish = get_soup(f_url)
            for el in s_fish.find_all(['div', 'p']):
                txt = clean_text(el.get_text())
                if not re.search(r'第\s*\d+\s*回\s*[：:]', txt):
                    continue
                if len(txt) > 200:
                    continue
                
                m_kai = re.search(r'第(\d+)回', txt)
                date_str = parse_wareki(txt)
                if not m_kai or not date_str:
                    continue
                kai_num = int(m_kai.group(1))
                
                sub_group = ""
                prev = el.find_previous(['h2', 'h3', 'h4', 'strong', 'p'])
                if prev:
                    pt = clean_text(prev.get_text())
                    for kw in ['対馬暖流系群', '太平洋系群', '日本海系群', 'オホーツク海系群', '北部系群', '南部系群', 'A海域', 'B海域', '本州四国系群', '九州系群']:
                        if kw in pt:
                            sub_group = kw
                            break
                
                tag_str = f"（{fish_name}{(' ' + sub_group) if sub_group else ''}）"
                m_name = f"第{kai_num}回 資源管理方針に関する検討会{tag_str}"
                
                # 一意性チェック (fish_name, sub_group, kai_num, date_str)
                u_key = (fish_name, sub_group, kai_num, date_str)
                if u_key in seen_jfa_keys:
                    continue
                seen_jfa_keys.add(u_key)
                
                date_digits = date_str.replace('/', '')
                m_id = f"jfa-shigen_kanri_houshin-{date_digits}-{kai_num:03d}"
                
                pdfs = []
                for a in el.find_all('a', href=lambda h: h and h.lower().endswith('.pdf')):
                    pdfs.append((clean_text(a.get_text()), urljoin(f_url, a['href'])))
                
                curr = el.next_sibling
                while curr:
                    curr_txt = clean_text(getattr(curr, 'text', ''))
                    if re.search(r'第\s*\d+\s*回\s*[：:]', curr_txt):
                        break
                    if hasattr(curr, 'find_all'):
                        for a in curr.find_all('a', href=lambda h: h and h.lower().endswith('.pdf')):
                            pdfs.append((clean_text(a.get_text()), urljoin(f_url, a['href'])))
                    curr = curr.next_sibling
                
                mats = []
                for p_name, p_url in pdfs:
                    if p_name in ['配付資料', '配布資料', '資料', '議事要旨', '議事録']:
                        p_name = f"{m_name} {p_name}"
                    mats.append({"name": p_name, "url": p_url})

                collected_meetings.append({
                    "council_id": "jfa-shigen_kanri_houshin",
                    "meeting_id": m_id,
                    "name": m_name,
                    "date": date_str,
                    "official_url": f_url,
                    "materials": mats
                })
        except Exception as e:
            print(f"Error fetching JFA {fish_name}: {e}")

    print(f"JFA meetings collected: {len([m for m in collected_meetings if m['council_id'] == 'jfa-shigen_kanri_houshin'])}")

    # =========================================================================
    # 4. MIC: 総務省 行政不服審査会
    # =========================================================================
    print("--- 4. MIC 行政不服審査会 ---")
    mic_url = "https://www.soumu.go.jp/main_sosiki/singi/fufukushinsa/katsudou/index.html"
    updated_councils.append((mic_url, "mic-fufuku_shinsa"))
    new_scraping_rules["mic-fufuku_shinsa"] = {
        "officialUrl": mic_url,
        "template": "tpl-general-round-subpage",
        "subpage_discovery_pattern": "[^\"']*(?:katsudou/.*|toushin_.*\\.html)",
        "pdf_selector": "a[href*='.pdf'], a[href*='.PDF']",
        "manualLock": True
    }
    s_mic = get_soup(mic_url)
    for a in s_mic.find_all('a', href=True):
        txt = clean_text(a.get_text())
        href = a['href']
        if '年度' in txt and href.lower().endswith('.pdf'):
            m_yr = re.search(r'(令和|平成)\s*(\d+|元)年度', txt)
            if not m_yr:
                continue
            era, y_str = m_yr.groups()
            y = 1 if y_str == '元' else int(y_str)
            yr_val = (2018 + y) if era == '令和' else (1988 + y)
            kai_num = yr_val - 2016 + 1
            date_str = f"{yr_val:04d}/06/01"
            date_digits = f"{yr_val:04d}0601"
            m_id = f"mic-fufuku_shinsa-{date_digits}-{kai_num:03d}"
            m_name = f"第{kai_num}回 行政不服審査会（{txt}）"
            mat_url = urljoin(mic_url, href)
            mats = [{"name": f"第{kai_num}回 行政不服審査会 活動報告（{txt}）", "url": mat_url}]
            
            collected_meetings.append({
                "council_id": "mic-fufuku_shinsa",
                "meeting_id": m_id,
                "name": m_name,
                "date": date_str,
                "official_url": mic_url,
                "materials": mats
            })

    print(f"MIC meetings collected: {len([m for m in collected_meetings if m['council_id'] == 'mic-fufuku_shinsa'])}")

    # =========================================================================
    # 5. MEXT: 文部科学省 大学設置・学校法人審議会
    # =========================================================================
    print("--- 5. MEXT 大学設置・学校法人審議会 ---")
    mext_url = "https://www.mext.go.jp/b_menu/shingi/daigaku/toushin/index.html"
    updated_councils.append((mext_url, "mext-715"))
    new_scraping_rules["mext-715"] = {
        "officialUrl": mext_url,
        "template": "tpl-general-round-subpage",
        "subpage_discovery_pattern": "[^\"']*(?:toushin/.*\\.htm)",
        "pdf_selector": "a[href*='.pdf'], a[href*='.PDF']",
        "date_regex": "(?:令和|平成)\\s*\\d+年\\s*\\d+月\\s*\\d+日",
        "manualLock": True
    }
    s_mext = get_soup(mext_url)
    mext_links = []
    for a in s_mext.find_all('a', href=True):
        txt = clean_text(a.get_text())
        href = a['href']
        if any(k in txt for k in ['開設予定', '収容定員']) and ('htm' in href):
            mext_links.append((txt, urljoin(mext_url, href)))
            if len(mext_links) >= 15:
                break
                
    mext_seq = 1
    for title_txt, sub_url in mext_links:
        try:
            sub_s = get_soup(sub_url)
            attach_links = []
            for sa in sub_s.find_all('a', href=True):
                s_txt = clean_text(sa.get_text())
                s_href = sa['href']
                if '答申について' in s_txt:
                    attach_links.append((s_txt, urljoin(sub_url, s_href)))
            
            if not attach_links:
                attach_links = [(title_txt, sub_url)]
            
            for att_title, att_url in attach_links[:2]:
                att_s = get_soup(att_url)
                date_str = parse_wareki(att_title)
                if not date_str:
                    date_str = parse_wareki(att_s.get_text()[:500])
                if not date_str:
                    date_str = "2024/04/01"
                
                date_digits = date_str.replace('/', '')
                m_id = f"mext-715-{date_digits}-s{mext_seq:02d}"
                mext_seq += 1
                
                mats = []
                for pa in att_s.find_all('a', href=True):
                    if pa['href'].lower().endswith('.pdf'):
                        mat_title = clean_text(pa.get_text())
                        mat_url = urljoin(att_url, pa['href'])
                        if mat_title and mat_url:
                            if mat_title in ['配付資料', '配布資料', '資料', '議事要旨', '議事録']:
                                mat_title = f"{att_title} {mat_title}"
                            mats.append({"name": mat_title, "url": mat_url})
                
                if not mats:
                    mats.append({"name": att_title, "url": att_url})
                
                collected_meetings.append({
                    "council_id": "mext-715",
                    "meeting_id": m_id,
                    "name": att_title,
                    "date": date_str,
                    "official_url": att_url,
                    "materials": mats
                })
        except Exception as e:
            print(f"Error fetching MEXT {title_txt}: {e}")

    print(f"MEXT meetings collected: {len([m for m in collected_meetings if m['council_id'] == 'mext-715'])}")
    print(f"\nTOTAL meetings collected across all 5 councils: {len(collected_meetings)}")

    # =========================================================================
    # DB 投入
    # =========================================================================
    if dry_run:
        print("\n[DRY RUN] No database changes made.")
        return collected_meetings

    print("\n[APPLYING TO DATABASE]...")
    # Delete previous meetings/materials for all 5 target councils to ensure clean state
    target_ids = ['meti-sankoshin_chiteki_zaisan', 'cao-252', 'jfa-shigen_kanri_houshin', 'mic-fufuku_shinsa', 'mext-715']
    for t_cid in target_ids:
        c.execute("DELETE FROM materials WHERE meeting_id IN (SELECT id FROM meetings WHERE council_id = ?)", (t_cid,))
        c.execute("DELETE FROM meetings WHERE council_id = ?", (t_cid,))

    # 1. Update council official_urls
    for official_url, c_id in updated_councils:
        c.execute("UPDATE councils SET official_url = ?, manual_lock = 1, updated_at = datetime('now') WHERE id = ?", (official_url, c_id))
        print(f"Updated council {c_id} official_url -> {official_url}")

    # 2. Update scraping rules
    for c_id, rule_dict in new_scraping_rules.items():
        c.execute("""
            UPDATE scraping_rules SET 
                rule_json = ?, updated_at = datetime('now')
            WHERE council_id = ?
        """, (json.dumps(rule_dict, ensure_ascii=False), c_id))
        print(f"Updated scraping rule for {c_id}")

    # 3. Insert meetings and materials
    ins_m_cnt = 0
    ins_mat_cnt = 0
    for m in collected_meetings:
        c.execute("""
            INSERT INTO meetings (id, council_id, name, date, official_url, manual_lock, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
        """, (m['meeting_id'], m['council_id'], m['name'], m['date'], m['official_url']))
        ins_m_cnt += 1

        seen_urls = set()
        for mat in m['materials']:
            m_url = mat['url']
            if m_url in seen_urls:
                continue
            seen_urls.add(m_url)
            c.execute("""
                INSERT OR REPLACE INTO materials (meeting_id, name, url, manual_lock, created_at)
                VALUES (?, ?, ?, 1, datetime('now'))
            """, (m['meeting_id'], mat['name'], m_url))
            ins_mat_cnt += 1

    conn.commit()
    conn.close()
    print(f"Database update successfully completed! Inserted {ins_m_cnt} meetings and {ins_mat_cnt} materials.")

if __name__ == '__main__':
    import sys
    dry_run = True
    if '--apply' in sys.argv:
        dry_run = False
    run_import(dry_run=dry_run)
