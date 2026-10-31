# -*- coding: utf-8 -*-
"""
host_manager.py:
クローラーのホスト抽出・分散 (interleave_by_host_and_ministry) および省庁ドメイン管理 (Drop 115)
"""

import os
import json
import urllib.parse
from collections import defaultdict, deque

def _extract_council_host(c):
    u = c.get("officialUrl") or c.get("url") or ""
    if u:
        h = urllib.parse.urlparse(u).netloc.lower()
        if h:
            return h
    return (c.get("ministry") or "OTHER").lower() + ".go.jp"

def interleave_by_host_and_ministry(councils):
    """
    同一ホスト名（ドメイン）および同一省庁への連続アクセスを防止するため、
    ホスト名（netloc）を主キー、省庁を副キーとして均等間隔（インターリーブ）で
    巡回順序を並び替える（CR-21）。
    METIとANRE等の同一ドメイン（www.meti.go.jp）連続アクセスを根本回避する。
    """
    if not councils:
        return []
    from collections import defaultdict, deque
    buckets = defaultdict(deque)
    for c in councils:
        h = _extract_council_host(c)
        buckets[h].append(c)
    
    # 件数が多い順にソートしたホストリスト
    sorted_hosts = sorted(buckets.keys(), key=lambda k: len(buckets[k]), reverse=True)
    
    # ラウンドロビン抽出
    interleaved = []
    while buckets:
        for h in list(sorted_hosts):
            if h in buckets and buckets[h]:
                interleaved.append(buckets[h].popleft())
                if not buckets[h]:
                    del buckets[h]
                    
    # 末尾に同一ホストが連続して残る場合、先頭側の別のホストの隙間に遡って挿入・分散
    final_list = []
    for item in interleaved:
        item_host = _extract_council_host(item)
        if not final_list or _extract_council_host(final_list[-1]) != item_host:
            final_list.append(item)
        else:
            # 連続してしまう場合は、直前・直後と異なるホストの隙間に遡って挿入
            inserted = False
            for idx in range(len(final_list) - 1, 0, -1):
                prev_h = _extract_council_host(final_list[idx - 1])
                curr_h = _extract_council_host(final_list[idx])
                if prev_h != item_host and curr_h != item_host:
                    final_list.insert(idx, item)
                    inserted = True
                    break
            if not inserted:
                final_list.append(item)
                
    return final_list

interleave_by_ministry = interleave_by_host_and_ministry

get_council_host = _extract_council_host

extract_host = _extract_council_host


def _build_other_ministry_domains_map(ministry_domains_dict):
    """
    各省庁について、自省庁（および親省庁・外局の共有ドメイン）以外の他省庁ドメイン一覧を構築する。
    例: ANRE (enecho.meti.go.jp, meti.go.jp) の場合、meti.go.jp 系は除外し他省庁ドメインのみを返す。
    """
    all_domains = sorted({
        d.lower().strip()
        for dlist in ministry_domains_dict.values()
        for d in (dlist or [])
        if d and isinstance(d, str)
    })
    other_map = {}
    for m_code, own_list in ministry_domains_dict.items():
        own_norm = [d.lower().strip() for d in (own_list or []) if d and isinstance(d, str)]
        others = []
        for d in all_domains:
            if any(d == od or d.endswith("." + od) or od.endswith("." + d) for od in own_norm):
                continue
            others.append(d)
        other_map[m_code] = tuple(others)
