import os
import sys
import json
import time
import datetime
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
admin_dir = os.path.join(PROJECT_ROOT, "admin")
if admin_dir not in sys.path:
    sys.path.insert(0, admin_dir)

from crawler import run_meeting_crawler

def run_step2():
    print("==================================================")
    print(" [ステップ 2] 通常巡回モード (recent-years=2, recheck-recent=1) の実行")
    print("==================================================")

    # ステップ1終了時スナップショットの取得
    conn = sqlite3.connect("admin/pmhub.db")
    c = conn.cursor()
    c.execute("SELECT * FROM meetings")
    step1_meetings = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    step1_meeting_ids = {m["id"] for m in step1_meetings}
    step1_meetings_map = {m["id"]: m for m in step1_meetings}
    c.execute("SELECT * FROM materials")
    step1_materials = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    step1_material_counts = {}
    for mat in step1_materials:
        step1_material_counts[mat["meeting_id"]] = step1_material_counts.get(mat["meeting_id"], 0) + 1
    conn.close()

    logs = []
    upgraded_meetings = []

    def on_progress(msg, payload=None):
        logs.append({"time": datetime.datetime.now().strftime("%H:%M:%S"), "msg": msg, "payload": payload})
        if "資料ページ自動更新" in msg:
            upgraded_meetings.append(msg)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    start_time = time.time()
    start_iso = datetime.datetime.now().isoformat()

    stats = run_meeting_crawler(
        progress_callback=on_progress,
        workers=4,
        recent_years="2",
        recheck_recent=1,
        full_check=False,
        include_closed=False
    )

    end_time = time.time()
    end_iso = datetime.datetime.now().isoformat()
    duration_sec = round(end_time - start_time, 2)

    # クロール後データの取得
    conn = sqlite3.connect("admin/pmhub.db")
    c = conn.cursor()
    c.execute("SELECT * FROM meetings")
    all_meetings = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    c.execute("SELECT * FROM materials")
    all_materials = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    conn.close()

    # 新規追加された meetings
    new_meetings = [m for m in all_meetings if m["id"] not in step1_meeting_ids]
    new_meeting_ids = {m["id"] for m in new_meetings}
    new_materials = [mat for mat in all_materials if mat["meeting_id"] in new_meeting_ids]

    mat_by_meet = {}
    for mat in all_materials:
        mat_by_meet.setdefault(mat["meeting_id"], []).append(mat)
    for m in new_meetings:
        m["materials"] = mat_by_meet.get(m["id"], [])

    # 既存開催回の資料追加・更新の検出
    updated_existing_meetings = []
    for m in all_meetings:
        mid = m["id"]
        if mid in step1_meeting_ids:
            old_count = step1_material_counts.get(mid, 0)
            curr_count = len(mat_by_meet.get(mid, []))
            if curr_count > old_count:
                updated_existing_meetings.append({
                    "id": mid,
                    "name": m["name"],
                    "date": m["date"],
                    "council_id": m["council_id"],
                    "old_material_count": old_count,
                    "new_material_count": curr_count,
                    "added_materials": curr_count - old_count
                })

    step2_result = {
        "mode": "normal_crawl",
        "description": "直近2年アクティブ会議体個別URLの並行巡回 (recent-years=2, recheck-recent=1, workers=4)",
        "start_time": start_iso,
        "end_time": end_iso,
        "duration_seconds": duration_sec,
        "stats": stats,
        "counts": {
            "total_meetings_after": len(all_meetings),
            "total_materials_after": len(all_materials),
            "new_meetings_count": len(new_meetings),
            "new_materials_count": len(new_materials),
            "updated_existing_meetings_count": len(updated_existing_meetings)
        },
        "new_meetings": new_meetings,
        "updated_existing_meetings": updated_existing_meetings,
        "logs": logs
    }

    with open("scratch/compare_crawler_modes/step2_normal_crawl_result.json", "w", encoding="utf-8") as f:
        json.dump(step2_result, f, ensure_ascii=False, indent=2)

    # ステップ3（別AIエンジン分析）用の突合データセット生成
    with open("scratch/compare_crawler_modes/step1_ministry_news_result.json", "r", encoding="utf-8") as f:
        step1_res = json.load(f)

    comparison_dataset = {
        "generated_at": datetime.datetime.now().isoformat(),
        "summary": {
            "step1_ministry_news": {
                "duration_seconds": step1_res["duration_seconds"],
                "new_meetings_detected": step1_res["counts"]["new_meetings_count"],
                "new_materials_detected": step1_res["counts"]["new_materials_count"]
            },
            "step2_normal_crawl": {
                "duration_seconds": step2_result["duration_seconds"],
                "new_meetings_detected": step2_result["counts"]["new_meetings_count"],
                "new_materials_detected": step2_result["counts"]["new_materials_count"],
                "updated_existing_meetings": len(updated_existing_meetings)
            }
        },
        "step1_new_meetings": [
            {
                "id": m["id"],
                "name": m["name"],
                "date": m["date"],
                "council_id": m["council_id"],
                "officialUrl": m.get("official_url") or m.get("officialUrl"),
                "material_count": len(m.get("materials", []))
            } for m in step1_res["new_meetings"]
        ],
        "step2_new_meetings": [
            {
                "id": m["id"],
                "name": m["name"],
                "date": m["date"],
                "council_id": m["council_id"],
                "officialUrl": m.get("official_url") or m.get("officialUrl"),
                "material_count": len(m.get("materials", []))
            } for m in new_meetings
        ],
        "step2_updated_meetings": updated_existing_meetings
    }

    with open("scratch/compare_crawler_modes/comparison_dataset.json", "w", encoding="utf-8") as f:
        json.dump(comparison_dataset, f, ensure_ascii=False, indent=2)

    print("\n--------------------------------------------------")
    print(f" [ステップ 2 完了] 所要時間: {duration_sec} 秒")
    print(f" 新規検知開催回: {len(new_meetings)} 件, 配付資料: {len(new_materials)} 件")
    print(f" 既存開催回の資料更新: {len(updated_existing_meetings)} 件")
    print(" 結果保存先:")
    print("   - scratch/compare_crawler_modes/step2_normal_crawl_result.json")
    print("   - scratch/compare_crawler_modes/comparison_dataset.json (分析用突合データ)")
    print("==================================================")

if __name__ == "__main__":
    run_step2()
