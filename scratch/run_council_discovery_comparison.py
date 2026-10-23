import os
import sys
import json
import time
import datetime
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
admin_dir = os.path.join(PROJECT_ROOT, "admin")
if admin_dir not in sys.path:
    sys.path.insert(0, admin_dir)

from discover_councils import run_discovery
from utils import load_data_json, load_rejected_councils, normalize_url_for_matching

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "scratch", "compare_council_discovery")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print("==================================================")
    print(" 新規会議体ディスカバリー 2モード比較検証スクリプト")
    print("==================================================")

    # 1. ベースライン記録
    data = load_data_json(os.path.join(PROJECT_ROOT, "docs", "data.json"))
    councils = data.get("councils", [])
    meetings = data.get("meetings", [])
    ministries = data.get("ministries", {})
    rejected = load_rejected_councils()

    baseline = {
        "recorded_at": datetime.datetime.now().isoformat(),
        "total_councils": len(councils),
        "total_meetings": len(meetings),
        "total_ministries": len(ministries),
        "total_rejected_councils": len(rejected),
        "councils_urls_count": sum(len(m.get("councilsUrls", [])) for m in ministries.values())
    }
    with open(os.path.join(OUTPUT_DIR, "baseline.json"), "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    print(f"[INFO] ベースライン記録完了: 会議体 {len(councils)} 件, 審議会一覧URL {baseline['councils_urls_count']} 件")

    # 2. ステップ 1: 省庁新着検知モード (mode="ministry_news")
    print("\n--------------------------------------------------")
    print(" [ステップ 1] 省庁新着検知モード (ministry_news) の実行")
    print("--------------------------------------------------")
    step1_logs = []
    def step1_callback(msg, payload=None):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        step1_logs.append({"time": ts, "msg": msg, "payload": payload})
        print(f"[{ts}] {msg}")

    t0 = time.time()
    start_iso1 = datetime.datetime.now().isoformat()
    discovered_step1 = run_discovery(
        progress_callback=step1_callback,
        target_ministry=None,
        dry_run=True,
        mode="ministry_news"
    )
    t1 = time.time()
    duration1 = round(t1 - t0, 2)
    end_iso1 = datetime.datetime.now().isoformat()

    step1_min_counts = Counter(c.get("ministry") for c in discovered_step1)
    step1_cat_counts = Counter(c.get("category") for c in discovered_step1)

    step1_result = {
        "mode": "ministry_news",
        "description": "各府省庁トップページ・新着・報道発表ポータルからの新規会議体検知 (--from-ministry-news)",
        "start_time": start_iso1,
        "end_time": end_iso1,
        "duration_seconds": duration1,
        "total_discovered": len(discovered_step1),
        "ministry_breakdown": dict(step1_min_counts.most_common()),
        "category_breakdown": dict(step1_cat_counts.most_common()),
        "discovered_councils": discovered_step1,
        "logs": step1_logs
    }
    with open(os.path.join(OUTPUT_DIR, "step1_ministry_news_discovery.json"), "w", encoding="utf-8") as f:
        json.dump(step1_result, f, ensure_ascii=False, indent=2)
    print(f" [ステップ 1 完了] 所要時間: {duration1} 秒, 新規検出会議体: {len(discovered_step1)} 件")

    # 3. ステップ 2: 通常巡回モード (mode="normal")
    print("\n--------------------------------------------------")
    print(" [ステップ 2] 通常巡回モード (normal: 審議会等一覧53URL巡回) の実行")
    print("--------------------------------------------------")
    step2_logs = []
    def step2_callback(msg, payload=None):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        step2_logs.append({"time": ts, "msg": msg, "payload": payload})
        print(f"[{ts}] {msg}")

    t2 = time.time()
    start_iso2 = datetime.datetime.now().isoformat()
    discovered_step2 = run_discovery(
        progress_callback=step2_callback,
        target_ministry=None,
        dry_run=True,
        mode="normal"
    )
    t3 = time.time()
    duration2 = round(t3 - t2, 2)
    end_iso2 = datetime.datetime.now().isoformat()

    step2_min_counts = Counter(c.get("ministry") for c in discovered_step2)
    step2_cat_counts = Counter(c.get("category") for c in discovered_step2)

    step2_result = {
        "mode": "normal",
        "description": "各省庁の審議会等一覧ページ (councilsUrls 53件) 巡回による新規会議体検知",
        "start_time": start_iso2,
        "end_time": end_iso2,
        "duration_seconds": duration2,
        "total_discovered": len(discovered_step2),
        "ministry_breakdown": dict(step2_min_counts.most_common()),
        "category_breakdown": dict(step2_cat_counts.most_common()),
        "discovered_councils": discovered_step2,
        "logs": step2_logs
    }
    with open(os.path.join(OUTPUT_DIR, "step2_normal_discovery.json"), "w", encoding="utf-8") as f:
        json.dump(step2_result, f, ensure_ascii=False, indent=2)
    print(f" [ステップ 2 完了] 所要時間: {duration2} 秒, 新規検出会議体: {len(discovered_step2)} 件")

    # 4. 突合・比較データセットの生成 (comparison_dataset.json)
    # URL正規化キーおよび名称での突合
    s1_map_by_url = {}
    s1_map_by_name = {}
    for c in discovered_step1:
        u = normalize_url_for_matching(c.get("officialUrl", ""))
        if u:
            s1_map_by_url[u] = c
        s1_map_by_name[c.get("name", "").strip()] = c

    overlap_councils = []
    step2_only_councils = []
    matched_s1_names = set()

    for c2 in discovered_step2:
        u2 = normalize_url_for_matching(c2.get("officialUrl", ""))
        n2 = c2.get("name", "").strip()
        matched_s1 = s1_map_by_url.get(u2) or s1_map_by_name.get(n2)
        if matched_s1:
            matched_s1_names.add(matched_s1.get("name", "").strip())
            overlap_councils.append({
                "name": n2,
                "ministry": c2.get("ministry"),
                "category_step1": matched_s1.get("category"),
                "category_step2": c2.get("category"),
                "url_step1": matched_s1.get("officialUrl"),
                "url_step2": c2.get("officialUrl"),
                "id_step1": matched_s1.get("id"),
                "id_step2": c2.get("id")
            })
        else:
            step2_only_councils.append(c2)

    step1_only_councils = [
        c1 for c1 in discovered_step1
        if c1.get("name", "").strip() not in matched_s1_names
    ]

    comparison_dataset = {
        "generated_at": datetime.datetime.now().isoformat(),
        "summary": {
            "step1_ministry_news": {
                "duration_seconds": duration1,
                "total_discovered": len(discovered_step1),
                "ministry_breakdown": dict(step1_min_counts.most_common()),
                "category_breakdown": dict(step1_cat_counts.most_common())
            },
            "step2_normal": {
                "duration_seconds": duration2,
                "total_discovered": len(discovered_step2),
                "ministry_breakdown": dict(step2_min_counts.most_common()),
                "category_breakdown": dict(step2_cat_counts.most_common())
            },
            "overlap_count": len(overlap_councils),
            "step1_only_count": len(step1_only_councils),
            "step2_only_count": len(step2_only_councils)
        },
        "overlap_councils": overlap_councils,
        "step1_only_councils": step1_only_councils,
        "step2_only_councils": step2_only_councils
    }

    with open(os.path.join(OUTPUT_DIR, "comparison_dataset.json"), "w", encoding="utf-8") as f:
        json.dump(comparison_dataset, f, ensure_ascii=False, indent=2)

    print("\n==================================================")
    print(" [ディスカバリー比較検証 完了]")
    print(f" 新着検知モード: {len(discovered_step1)} 件 ({duration1} 秒)")
    print(f" 通常巡回モード: {len(discovered_step2)} 件 ({duration2} 秒)")
    print(f" 重複検出（両方）: {len(overlap_councils)} 件")
    print(f" 新着検知のみ:     {len(step1_only_councils)} 件")
    print(f" 通常巡回のみ:     {len(step2_only_councils)} 件")
    print(f" 保存先ディレクトリ: {OUTPUT_DIR}")
    print("==================================================")

if __name__ == "__main__":
    main()
