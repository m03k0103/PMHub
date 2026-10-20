import os
import sys
import json
import time
import datetime
import sqlite3

# プロジェクトルート設定
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
admin_dir = os.path.join(PROJECT_ROOT, "admin")
if admin_dir not in sys.path:
    sys.path.insert(0, admin_dir)

from crawler import run_ministry_news_discovery, MINISTRY_NEWS_PORTALS

def run_step1():
    print("==================================================")
    print(" [ステップ 1] 新着検知モード (--from-ministry-news) の実行")
    print("==================================================")

    # ベースラインの読み込み
    with open("scratch/compare_crawler_modes/baseline.json", "r", encoding="utf-8") as f:
        baseline = json.load(f)
    baseline_meeting_ids = set(baseline["meeting_ids"])

    logs = []
    def on_progress(msg, payload=None):
        logs.append({"time": datetime.datetime.now().strftime("%H:%M:%S"), "msg": msg, "payload": payload})
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    start_time = time.time()
    start_iso = datetime.datetime.now().isoformat()

    res = run_ministry_news_discovery(progress_callback=on_progress)

    end_time = time.time()
    end_iso = datetime.datetime.now().isoformat()
    duration_sec = round(end_time - start_time, 2)

    # DBから最新データの取得
    conn = sqlite3.connect("admin/pmhub.db")
    c = conn.cursor()
    c.execute("SELECT * FROM meetings")
    all_meetings = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    c.execute("SELECT * FROM materials")
    all_materials = [dict(zip([col[0] for col in c.description], row)) for row in c.fetchall()]
    conn.close()

    # 新規追加された meetings
    new_meetings = [m for m in all_meetings if m["id"] not in baseline_meeting_ids]
    new_meeting_ids = {m["id"] for m in new_meetings}
    new_materials = [mat for mat in all_materials if mat["meeting_id"] in new_meeting_ids]

    # 会議ごとに materials を紐付け
    mat_by_meet = {}
    for mat in new_materials:
        mat_by_meet.setdefault(mat["meeting_id"], []).append(mat)
    for m in new_meetings:
        m["materials"] = mat_by_meet.get(m["id"], [])

    step1_result = {
        "mode": "ministry_news",
        "description": "各府省庁トップページ・新着情報・報道発表・審議会一覧からの自動検知",
        "start_time": start_iso,
        "end_time": end_iso,
        "duration_seconds": duration_sec,
        "portals_scanned_count": len(MINISTRY_NEWS_PORTALS),
        "target_ministries": list(MINISTRY_NEWS_PORTALS.keys()),
        "counts": {
            "total_meetings_after": len(all_meetings),
            "total_materials_after": len(all_materials),
            "new_meetings_count": len(new_meetings),
            "new_materials_count": len(new_materials)
        },
        "new_meetings": new_meetings,
        "logs": logs
    }

    with open("scratch/compare_crawler_modes/step1_ministry_news_result.json", "w", encoding="utf-8") as f:
        json.dump(step1_result, f, ensure_ascii=False, indent=2)

    print("\n--------------------------------------------------")
    print(f" [ステップ 1 完了] 所要時間: {duration_sec} 秒")
    print(f" 新規検知開催回: {len(new_meetings)} 件, 配付資料: {len(new_materials)} 件")
    print(" 結果保存先: scratch/compare_crawler_modes/step1_ministry_news_result.json")
    print("==================================================")

if __name__ == "__main__":
    run_step1()
