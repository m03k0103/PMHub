#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
政策会議ウォッチ (PM-HUB) - 会議レコード重複防止・回次整合性テスト (Test for No Duplicate Meetings & Clean Rounds)
"""

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "admin"))
from utils import setup_win32_utf8, normalize_japanese_numbers, load_data_json, validate_council_id, validate_meeting_id
setup_win32_utf8()


def extract_round_and_type(title, council_name="", url=""):
    t_norm = normalize_japanese_numbers(title)
    
    sub_type = ""
    fy_m = re.search(r'(令和\d+年度[秋|春|前半|後半]?|平成\d+年度[秋|春|前半|後半]?|令和\d+年|平成\d+年|第\d+期)', t_norm)
    if fy_m and fy_m.group(1) not in council_name:
        sub_type += fy_m.group(1)

    # 規制改革推進会議等の会期フォルダ (例: /meeting/wg/2501_01local/) による期別サブタイプ補完
    if url and not sub_type:
        wg_m = re.search(r'/meeting/wg/([^/]+)/', url)
        if wg_m:
            sub_type += f"_{wg_m.group(1)}"

    if '／' in council_name or '/' in council_name:
        for part in re.split(r'[／/]', council_name):
            part = part.strip()
            if part and part in t_norm:
                sub_type += f"_{part}"
                break

    if '総会' in t_norm and '総会' not in council_name:
        sub_type += "_総会"
    elif ('専門小委員会' in t_norm or '専門委員会' in t_norm) and ('専門小委員会' not in council_name and '専門委員会' not in council_name):
        sub_type += "_専門小委員会"
    elif '小委員会' in t_norm and '小委員会' not in council_name:
        sub_type += "_小委員会"
    elif '部会' in t_norm and '部会' not in council_name:
        sub_type += "_部会"
    elif 'フォローアップ' in t_norm:
        sub_type += "_フォローアップ会合"
    elif '幹事会' in t_norm and '幹事会' not in council_name:
        sub_type += "_幹事会"
    elif '実務者協議会' in t_norm and '実務者協議会' not in council_name:
        sub_type += "_実務者協議会"
    elif '協議会' in t_norm and '協議会' not in council_name:
        sub_type += "_協議会"
    elif '検討会' in t_norm and '検討会' not in council_name:
        sub_type += "_検討会"
    elif ('ワーキンググループ' in t_norm or ' WG' in t_norm) and ('WG' not in council_name and 'ワーキンググループ' not in council_name):
        sub_type += "_WG"
    elif '分科会' in t_norm and '分科会' not in council_name:
        sub_type += "_分科会"

    m = re.search(r'第\s*(\d+)\s*回', t_norm)
    return (int(m.group(1)), sub_type) if m else (None, "")


def run_test(data=None):
    if data is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.abspath(os.path.join(base_dir, "..", "docs", "data.json"))
        
        if not os.path.exists(data_path):
            print(f"FAIL: {data_path} not found")
            return 1
            
        data = load_data_json(data_path, cached=True)
        if not data:
            print(f"FAIL: Failed to load {data_path}")
            return 1
        
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
        
    # 2. Check duplicate (councilId, name, date)
    key_counts = defaultdict(int)
    for m in meetings:
        m_name = m.get('name') or m.get('title') or ''
        key_counts[(m.get('councilId'), m_name, m.get('date'))] += 1
    dup_keys = {k: v for k, v in key_counts.items() if v > 1}
    if dup_keys:
        errors.append(f"Duplicate (councilId, name, date) found: {dup_keys}")
        
    # 3. Check duplicate 第n回 in same council
    meetings_by_council = defaultdict(list)
    for m in meetings:
        meetings_by_council[m.get('councilId', 'unknown')].append(m)
        
    for c_id, m_list in meetings_by_council.items():
        c_name = councils.get(c_id, {}).get('name', c_id)
        round_map = defaultdict(list)
        for m in m_list:
            m_name = m.get('name') or m.get('title') or ''
            m_url = m.get('officialUrl', '')
            r_num, sub_type = extract_round_and_type(m_name, c_name, m_url)
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
    bad_names = [m.get('name') or m.get('title') for m in meetings if any(w in (m.get('name') or m.get('title') or '') for w in ['抽出', '最新回 (', '直近会合', '最新会合'])]
    if bad_names:
        errors.append(f"Generic/auto-extracted meeting names found ({len(bad_names)} items): {bad_names[:5]}")

    # 7. Check meeting name schema (Strictly enforce non-empty 'name' string, ban deprecated 'title' attribute)
    missing_names = [m.get('id') for m in meetings if not m.get('name') or not isinstance(m.get('name'), str)]
    if missing_names:
        errors.append(f"Meetings missing valid 'name' property found ({len(missing_names)} items): {missing_names[:5]}")
    erroneous_titles = [m.get('id') for m in meetings if 'title' in m]
    if erroneous_titles:
        errors.append(f"Meetings with deprecated 'title' attribute found ({len(erroneous_titles)} items): {erroneous_titles[:5]}")

    # 8. Check councilId format (Must have exactly 1 hyphen: {ministry}-{slug})
    bad_c_ids = [c_id for c_id in councils.keys() if not validate_council_id(c_id)]
    if bad_c_ids:
        errors.append(f"Invalid councilId format (must be {{ministry}}-{{slug}} with 1 hyphen) ({len(bad_c_ids)} items): {bad_c_ids[:5]}")

    # 9. Check meetingId format (Must have exactly 3 hyphens: {councilId}-{YYYYMMDD}-{round/session})
    bad_m_ids = [m.get('id') for m in meetings if not validate_meeting_id(m.get('id', ''))]
    if bad_m_ids:
        errors.append(f"Invalid meetingId format (must be {{councilId}}-{{YYYYMMDD}}-{{round}} with 3 hyphens) ({len(bad_m_ids)} items): {bad_m_ids[:5]}")

    # 10. Check materials schema (Strictly enforce 'name' attribute, ban 'title' key and empty names)
    bad_materials_title_key = []
    bad_materials_empty_name = []
    for m in meetings:
        for mat in m.get('materials', []):
            if 'title' in mat:
                bad_materials_title_key.append((m.get('id'), mat))
            if not str(mat.get('name') or '').strip():
                bad_materials_empty_name.append((m.get('id'), mat))
    if bad_materials_title_key:
        errors.append(f"Materials with deprecated 'title' key found ({len(bad_materials_title_key)} items): {[b[0] for b in bad_materials_title_key[:5]]}")
    if bad_materials_empty_name:
        errors.append(f"Materials with empty 'name' attribute found ({len(bad_materials_empty_name)} items): {[b[0] for b in bad_materials_empty_name[:5]]}")

    # 11. Check cross-council duplicate meeting officialUrls (Must not share specific meeting subpage URLs across different councils)
    generic_meeting_url_patterns = re.compile(
        r'/(?:index|default|kaisai|shingikai|top|archive|gijiroku|proceedings|report)?\.(?:html?|php)$|'
        r'/(?:council|shingi|meeting|seisaku|policy)/?$|'
        r'kisei-kaikaku/kisei/(?:meeting/)?(?:meeting|archive/meeting)\.html$|'
        r'/action/action\.html$|'
        r'/singi\.html$|'
        r'/soukai\.html$',
        re.IGNORECASE
    )
    # Known legacy cross-council pairs pending ministry-specific migration Drops
    # (Strictly no new duplicates or moj duplicates allowed)
    known_legacy_cross_pairs = {
        frozenset(['anre-souene_kihon_seisaku', 'cas-358']),
        frozenset(['caa-kaigi_kenkyu', 'caa-shokuhin_eisei_kijun']),
        frozenset(['cao-267', 'cas-shingijutsu_kouka_hyouka']),
        frozenset(['cas-1942', 'ra-fukko_suishin_kaigi']),
        frozenset(['cas-300', 'cas-346']),
        frozenset(['cas-301', 'cas-315']),
        frozenset(['cas-atarashii_shihon_honbu', 'cas-atarashii_shihon_kaigi']),
        frozenset(['cas-chukatu', 'cas-tiikisaisei']),
        frozenset(['cas-chutou_jyousei', 'cas-chutou_jyousei_tf']),
        frozenset(['cas-keizai_anzen_kentou', 'cas-keizai_anzen_suishin']),
        frozenset(['cas-zensedai_hosyo', 'cas-zensedai_shakaihosho_kochiku']),
        frozenset(['fsa-japan_stewardship', 'fsa-stewardship_h28', 'fsa-stewardship_r01', 'fsa-stewardship_r06']),
        frozenset(['fsa-japan_stewardship', 'fsa-stewardship_r06']),
        frozenset(['isa-581', 'isa-582', 'isa-583', 'isa-584', 'isa-585']),
        frozenset(['jcrc-2171', 'jcrc-587']),
        frozenset(['jsa-611', 'mext-718']),
        frozenset(['maff-651', 'maff-684']),
        frozenset(['maff-652', 'rinya-1278']),
        frozenset(['maff-656', 'maff-672']),
        frozenset(['maff-670', 'rinya-1279']),
        frozenset(['maff-shokuiku_suishin_hyouka_iinkai', 'maff-shokuiku_suishin_kaigi']),
        frozenset(['meti-sangyo_kozo', 'meti-sankoushin']),
        frozenset(['mhlw-789', 'mhlw-794', 'mhlw-shakai_hosho_nenkin']),
        frozenset(['mhlw-789', 'mhlw-shakai_hosho_nenkin']),
        frozenset(['mhlw-802', 'mhlw-shakai_hosho_shougaisha']),
        frozenset(['mhlw-807', 'mhlw-shakai_hosho_kaigo_hoken']),
        frozenset(['mhlw-816', 'mhlw-819']),
        frozenset(['mhlw-822', 'mhlw-kousei_kansenshou']),
        frozenset(['mhlw-846', 'mhlw-880']),
        frozenset(['mhlw-861', 'mhlw-868']),
        frozenset(['mhlw-871', 'mhlw-shouni_mansei_taisaku_bukai']),
        frozenset(['mhlw-873', 'mhlw-hosho_shouni']),
        frozenset(['mhlw-873', 'mhlw-shouni_mansei_taisaku_iinkai']),
        frozenset(['mhlw-874', 'mhlw-shakai_hosho_shouni_mansei_kento']),
        frozenset(['mhlw-974', 'mhlw-977']),
        frozenset(['mhlw-993', 'mhlw-994']),
        frozenset(['mhlw-anma_massage_ryouyouhi', 'mhlw-hosho_jidoukan']),
        frozenset(['mhlw-fukushi_bukai', 'mhlw-hosho_fukushi']),
        frozenset(['mhlw-hosho_jidou', 'mhlw-jidou_bukai']),
        frozenset(['mhlw-hosho_jidoukan', 'mhlw-houkago_jidoukan_wg']),
        frozenset(['mhlw-hosho_shippei', 'mhlw-toukei_shikkan_shougai']),
        frozenset(['mhlw-hosho_shouni', 'mhlw-shouni_mansei_shien']),
        frozenset(['mhlw-hosho_toukei', 'mhlw-toukei_bunkakai']),
        frozenset(['mhlw-kaigo_kyuufu_bunkakai', 'mhlw-shakai_hosho_kaigo_kyuufu']),
        frozenset(['mhlw-kougaku_ryouyouhi', 'mhlw-tokumei_iryou']),
        frozenset(['mlit-amami_shinkou', 'mlit-dokuritsu_gyosei_hyoka', 'mlit-kokudo_shingikai', 'mlit-shakai_shingikai', 'mlit-tochi_kantei']),
        frozenset(['mof-1130', 'mof-1133', 'mof-1134', 'mof-zaiseiseido_bunkakai']),
        frozenset(['mof-1130', 'mof-zaiseiseido_bunkakai']),
        frozenset(['moj-1173', 'moj-1192', 'moj-1193', 'moj-1194', 'moj-1196', 'moj-2735', 'moj-2742']),
        frozenset(['moj-1173', 'moj-1192', 'moj-1193', 'moj-1194', 'moj-1196', 'moj-2735']),
        frozenset(['moj-2742', 'moj-minji_hanketsu_db']),
        frozenset(['moj-saihan_boushi', 'moj-zenka_shikaku_wg']),
        frozenset(['npa-1200', 'npa-1201']),
        frozenset(['ppc-ai_privacy', 'ppc-personalinfo_kentoukai']),
    }

    meetings_by_url = defaultdict(list)
    for m in meetings:
        u = m.get('officialUrl', '').strip()
        if not u or u.endswith('/') or generic_meeting_url_patterns.search(u.split('#')[0]):
            continue
        meetings_by_url[u].append(m)

    cross_dups = []
    for u, m_list in meetings_by_url.items():
        c_ids = {m.get('councilId') for m in m_list}
        if len(c_ids) > 1:
            dates = {m.get('date') for m in m_list}
            names = [m.get('name', '') for m in m_list]
            # Allowed group sharing or legitimate joint meetings
            is_joint_group = (
                all(cid.startswith('cao-kisei_') for cid in c_ids)
                or all(cid.startswith('fdma-') for cid in c_ids)
                or all(cid.startswith('fsa-') for cid in c_ids)
                or all(cid.startswith('digital-') for cid in c_ids)
                or all(cid.startswith('mhlw-') for cid in c_ids)
                or all(cid.startswith('mlit-') for cid in c_ids)
                or all(cid.startswith('mext-') for cid in c_ids)
            )
            ministries = {cid.split('-')[0] for cid in c_ids}
            is_joint_title = any('合同' in n or '共同' in n for n in names)
            is_inter_ministry_joint = (len(dates) == 1 and len(ministries) > 1 and len(set(names)) == 1)
            is_joint = is_joint_group or is_joint_title or is_inter_ministry_joint
            if not is_joint and frozenset(c_ids) not in known_legacy_cross_pairs:
                cross_dups.append((u, [(m.get('id'), m.get('councilId'), m.get('name')) for m in m_list]))

    if cross_dups:
        errors.append(f"Cross-council duplicate meeting officialUrls found ({len(cross_dups)} URLs): {[cd[0] for cd in cross_dups[:5]]}")

    # 12. Check duplicate council officialUrls in councils master
    allowed_council_url_prefixes = (
        'cao-kisei_',
        'cao-pfi_',
        'mic-chihou_seido_',
        'fsa-stewardship_',
        'maff-shokuiku_',
        'cas-katsuryoku_koujou',
        'mhlw-iryou_shitsukoujou',
    )
    known_council_url_sharing = {
        'https://www.bunka.go.jp/seisaku/bunkashingikai/index.html',
        'https://www.reconstruction.go.jp/topics/cat-11/cat-47/cat-158/000815/',
        'https://www.cas.go.jp/jp/seisakukaigi/hairo_osensui/index.html',
        'https://www.cas.go.jp/jp/seisakukaigi/keikyou/index.html',
        'https://www.fsa.go.jp/singi/kinyukiki/index.html',
        'https://www.cas.go.jp/jp/gaiyou/jimu/jyouhoutyousa/intelligence_taisei.html',
        'https://www.gov-online.go.jp/prg/prg9364.html',
        'https://www.cas.go.jp/jp/seisaku/chyutoujyousei/index.html',
        'https://www.jfa.maff.go.jp/j/council/index.html',
        'https://www.maff.go.jp/j/pr/event/kaigi.release.html',
        'https://www.jfa.maff.go.jp/j/council/suisanbukai/index.html',
        'https://www.mext.go.jp/sports/b_menu/shingi/index.htm',
        'https://www.maff.go.jp/j/council/index.html',
        'https://www.maff.go.jp/j/study/index.html',
        'https://www.maff.go.jp/nval/syonin_sinsa/gijiroku/index.html',
        'https://www.rinya.maff.go.jp/j/ken_sidou/shingikai/index.html',
        'https://www.meti.go.jp/shingikai/sankoshin/sokai/index.html',
        'https://www.mext.go.jp/b_menu/shingi/chukyo/chukyo0/index.htm',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126721.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126730.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126734.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-kousei_127717.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126700.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126709.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_491253_1.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_249296.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_164149.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126716.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126693.html',
        'https://www.mhlw.go.jp/stf/shingi/shingi-hosho_126698_00022.html',
        'https://www.moj.go.jp/hisho/seisakuhyouka/hisho04_00050.html',
    }
    councils_by_url = defaultdict(list)
    for c in councils.values():
        u = c.get('officialUrl', '').strip()
        if not u:
            continue
        councils_by_url[u].append(c)

    council_dups = []
    for u, c_list in councils_by_url.items():
        if len(c_list) > 1:
            all_allowed = all(any(c['id'].startswith(p) for p in allowed_council_url_prefixes) for c in c_list)
            if not all_allowed and u not in known_council_url_sharing:
                council_dups.append((u, [c['id'] for c in c_list]))

    if council_dups:
        errors.append(f"Duplicate council officialUrls found in councils master ({len(council_dups)} URLs): {[cd[0] for cd in council_dups[:5]]}")

    # 13. Check orphaned meetings (All meeting.councilId must exist in councils)
    orphaned_m_ids = [m.get('id') for m in meetings if m.get('councilId') not in councils]
    if orphaned_m_ids:
        errors.append(f"Orphaned meetings referencing non-existent councilId found ({len(orphaned_m_ids)} items): {orphaned_m_ids[:5]}")

    if errors:
        print(f"FAILED: {len(errors)} validation errors found:")
        for e in errors:
            print(f"  - {e}")
        return 1
        
    print(f"PASSED: All {len(meetings)} meetings across {len(councils)} councils validated with zero duplicates.")
    return 0

if __name__ == '__main__':
    sys.exit(run_test())
