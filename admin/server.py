import http.server
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
import sys
import shutil
import threading
import urllib.parse
from datetime import datetime
from apply_report import apply_report, apply_report_data
from discover_councils import run_discovery
from utils import (
    setup_win32_utf8, save_data_json_with_backup, load_data_json,
    load_rejected_councils, save_rejected_councils, add_to_rejected_councils,
    get_rejected_identifiers, DEFAULT_REJECTED_COUNCILS_PATH
)
setup_win32_utf8()


def _extract_delta_logs(parsed_url, state):
    """URLクエリから since_id を抽出し、該当ID以降の差分ログと最新ログIDを返す。"""
    params = urllib.parse.parse_qs(parsed_url.query)
    try:
        since_id = int(params.get("since_id", params.get("since", [0]))[0])
    except (ValueError, TypeError):
        since_id = 0
    all_logs = state.get("logs", [])
    new_logs = [l for l in all_logs if l.get("id", 0) > since_id]
    latest_id = all_logs[-1]["id"] if all_logs else 0
    return new_logs, latest_id


PORT = 8000
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "backups"))

# Global discovery status state
discovery_state = {
    "running": False,
    "progress": 0,
    "current_ministry": "",
    "ministry_name": "",
    "current_idx": 0,
    "total_ministries": 0,
    "discovered_count": 0,
    "logs": [],
    "log_seq": 0,
    "result": None,
    "error": None
}

# Global crawler status state and stop event
crawler_stop_event = threading.Event()
crawler_state = {
    "running": False,
    "stopping": False,
    "progress": 0,
    "current_idx": 0,
    "total_councils": 0,
    "current_council": "",
    "logs": [],
    "log_seq": 0,
    "stats": None,
    "error": None,
    "lastCrawlTime": "",
    "log_file": ""
}

def _crawler_worker():
    global crawler_state, crawler_stop_event
    def on_progress(msg, data=None):
        if data:
            if data.get("type") == "council_start":
                crawler_state["progress"] = data.get("progress", crawler_state["progress"])
                crawler_state["current_council"] = data.get("council_name", "")
                crawler_state["current_idx"] = data.get("current", 0)
                crawler_state["total_councils"] = data.get("total", 0)
                if data.get("log_file"):
                    crawler_state["log_file"] = data.get("log_file")
            elif data.get("type") in ("crawl_completed", "crawl_stopped"):
                crawler_state["lastCrawlTime"] = data.get("lastCrawlTime", "")
                if data.get("log_file"):
                    crawler_state["log_file"] = data.get("log_file")
        crawler_state["log_seq"] += 1
        crawler_state["logs"].append({"id": crawler_state["log_seq"], "text": msg})
        if len(crawler_state["logs"]) > 500:
            crawler_state["logs"] = crawler_state["logs"][-500:]

    try:
        stats = run_meeting_crawler(progress_callback=on_progress, stop_event=crawler_stop_event)
        crawler_state["stats"] = stats
        crawler_state["progress"] = 100
        crawler_state["running"] = False
        crawler_state["stopping"] = False
        if stats and stats.get("log_file"):
            crawler_state["log_file"] = stats.get("log_file")
    except Exception as e:
        crawler_state["error"] = str(e)
        crawler_state["running"] = False
        crawler_state["stopping"] = False

def _discovery_worker():
    global discovery_state
    def on_progress(msg, data=None):
        if data:
            if data.get("type") == "ministry_start":
                discovery_state["progress"] = data.get("progress", discovery_state["progress"])
                discovery_state["current_ministry"] = data.get("ministry", "")
                discovery_state["ministry_name"] = data.get("ministryName", "")
                discovery_state["current_idx"] = data.get("current", 0)
                discovery_state["total_ministries"] = data.get("total", 0)
            elif data.get("type") == "council_discovered":
                discovery_state["discovered_count"] += 1
        discovery_state["log_seq"] += 1
        discovery_state["logs"].append({"id": discovery_state["log_seq"], "text": msg})
        if len(discovery_state["logs"]) > 500:
            discovery_state["logs"] = discovery_state["logs"][-500:]

    try:
        discovered = run_discovery(progress_callback=on_progress)
        discovery_state["result"] = discovered
        discovery_state["progress"] = 100
        discovery_state["running"] = False
    except Exception as e:
        discovery_state["error"] = str(e)
        discovery_state["running"] = False

class CustomHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_raw_json(self, raw_json_str, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(raw_json_str.encode('utf-8') if isinstance(raw_json_str, str) else raw_json_str)

    def send_json(self, payload, status=200):
        self.send_raw_json(json.dumps(payload, ensure_ascii=False), status=status)

    def read_json_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length <= 0:
            return {}
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode('utf-8'))

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/docs/data.json", "/data.json"):
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    self.send_raw_json(f.read())
            else:
                self.send_json({})
        elif path == "/api/discovery-keywords":
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.send_json(data.get("discoveryKeywords", {}))
            else:
                self.send_json({})
        elif path == "/api/discovered-councils":
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                discovered = data.get("discoveredCouncils", [])

                # 却下済み会議体リストのロードと除外
                rej_ids, rej_names, rej_urls = get_rejected_identifiers()

                filtered = [
                    c for c in discovered
                    if c.get("id") not in rej_ids
                    and c.get("name", "").strip() not in rej_names
                    and (not c.get("officialUrl") or c.get("officialUrl").strip().rstrip("/") not in rej_urls)
                ]
                self.send_json({"councils": filtered})
            else:
                self.send_json({"councils": []})
        elif path == "/api/verification-report":
            rep_file = os.path.join(BASE_DIR, "ai_verification_report.json")
            if os.path.exists(rep_file):
                with open(rep_file, "r", encoding="utf-8") as f:
                    self.send_raw_json(f.read())
            else:
                self.send_json({})
        elif path == "/api/rejected-councils":
            rejected_list = load_rejected_councils()
            self.send_json(rejected_list)
        elif path == "/api/get-crawler-config":
            data = load_data_json(DATA_JSON_FILE)
            self.send_json(data.get("crawlerConfig", {"llm_mode": True}))
        elif path == "/api/discovery-status":
            new_logs, latest_id = _extract_delta_logs(parsed_url, discovery_state)
            res_payload = {
                "running": discovery_state["running"],
                "progress": discovery_state["progress"],
                "current_ministry": discovery_state["current_ministry"],
                "ministry_name": discovery_state["ministry_name"],
                "current_idx": discovery_state["current_idx"],
                "total_ministries": discovery_state["total_ministries"],
                "discovered_count": discovery_state["discovered_count"],
                "logs": new_logs,
                "latest_log_id": latest_id,
                "totalLogs": discovery_state["log_seq"],
                "result": discovery_state["result"],
                "error": discovery_state["error"]
            }
            self.send_json(res_payload)
        elif path == "/api/crawler-status":
            new_logs, latest_id = _extract_delta_logs(parsed_url, crawler_state)
            res_payload = {
                "running": crawler_state["running"],
                "stopping": crawler_state.get("stopping", False),
                "progress": crawler_state["progress"],
                "current_council": crawler_state["current_council"],
                "current_idx": crawler_state["current_idx"],
                "total_councils": crawler_state["total_councils"],
                "logs": new_logs,
                "latest_log_id": latest_id,
                "totalLogs": crawler_state["log_seq"],
                "stats": crawler_state["stats"],
                "error": crawler_state["error"],
                "lastCrawlTime": crawler_state["lastCrawlTime"],
                "log_file": crawler_state.get("log_file", "")
            }
            self.send_json(res_payload)
        elif path == "/api/new-meetings":
            new_list = []
            try:
                data = load_data_json(DATA_JSON_FILE)
                c_map = {c["id"]: c for c in data.get("councils", [])}
                for m in data.get("meetings", []):
                    if m.get("isNewlyDiscovered"):
                        c_info = c_map.get(m.get("councilId"), {})
                        new_list.append({
                            **m,
                            "councilName": c_info.get("name", m.get("councilId")),
                            "ministry": c_info.get("ministry", m.get("ministry", ""))
                        })
            except Exception as e:
                print(f"[WARN] Failed to read new meetings: {e}", file=sys.stderr)
            self.send_json({"count": len(new_list), "meetings": new_list})
        elif path == "/api/backups":
            backups = []
            if os.path.exists(BACKUP_DIR):
                for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
                    if f.startswith("data_") and f.endswith(".json"):
                        f_path = os.path.join(BACKUP_DIR, f)
                        sz = os.path.getsize(f_path)
                        mtime = os.path.getmtime(f_path)
                        backups.append({
                            "filename": f,
                            "sizeBytes": sz,
                            "createdAt": datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S")
                        })
            self.send_json({"backups": backups})
        else:
            super().do_GET()

    def do_POST(self):
        global crawler_state, crawler_stop_event, discovery_state
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/api/save-ministry-updates", "/api/save-verification-report"):
            try:
                data = self.read_json_body()
                report = {
                    "_format": "pmhub-verification-report-v2",
                    "exportedAt": data.get("exportedAt"),
                    "targetFile": "docs/data.json",
                    "corrections": data.get("corrections", [])
                }
                success = apply_report_data(report)
                if success:
                    self.send_json({"status": "ok", "message": "docs/data.json successfully updated!"})
                else:
                    self.send_json({"status": "error", "message": "Failed to apply report data."}, status=500)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)

        elif path == "/api/save-discovery-keywords":
            try:
                data_kw = self.read_json_body()
                if os.path.exists(DATA_JSON_FILE):
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["discoveryKeywords"] = data_kw
                    save_data_json_with_backup(data, DATA_JSON_FILE)
                self.send_json({"status": "ok", "message": "Keywords updated in data.json"})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)

        elif path == "/api/save-crawler-config":
            try:
                config_data = self.read_json_body()
                if os.path.exists(DATA_JSON_FILE):
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["crawlerConfig"] = config_data
                    save_data_json_with_backup(data, DATA_JSON_FILE)
                self.send_json({"status": "ok", "message": "Crawler config updated in data.json"})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)

        elif path == "/api/save-rejected-councils":
            try:
                data = self.read_json_body()
                save_rejected_councils(data)
                self.send_json({"status": "ok", "message": "Rejected councils updated"})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)

        elif path == "/api/reject-council":
            try:
                payload = self.read_json_body()
                target_id = payload.get("id")
                reason = payload.get("reason", "Admin rejected council")
                council_obj = payload.get("council")

                if not target_id:
                    raise ValueError("Council ID is required")

                target_council = council_obj
                data = load_data_json(DATA_JSON_FILE)
                if data:
                    councils = data.get("councils", [])
                    c_idx = next((i for i, c in enumerate(councils) if c.get("id") == target_id), None)
                    if c_idx is not None:
                        target_council = councils.pop(c_idx)
                    
                    if "discoveredCouncils" in data and isinstance(data["discoveredCouncils"], list):
                        data["discoveredCouncils"] = [c for c in data["discoveredCouncils"] if c.get("id") != target_id]

                    save_data_json_with_backup(data, DATA_JSON_FILE)

                add_to_rejected_councils(
                    target_id=target_id,
                    council=target_council,
                    reason=reason,
                    rejected_at=payload.get("rejectedAt")
                )

                self.send_json({"status": "ok", "message": f"Council {target_id} moved to rejected list"})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)

        elif path == "/api/revert-rejected-council":
            try:
                payload = self.read_json_body()
                target_id = payload.get("id")
                if not target_id:
                    raise ValueError("Council ID is required")

                rejected_list = load_rejected_councils()
                target_rej = None
                r_idx = next((i for i, c in enumerate(rejected_list) if c.get("id") == target_id), None)
                if r_idx is not None:
                    target_rej = rejected_list.pop(r_idx)
                    save_rejected_councils(rejected_list)

                if target_rej and os.path.exists(DATA_JSON_FILE):
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as df:
                        data = json.load(df)
                    
                    councils = data.setdefault("councils", [])
                    if not any(c.get("id") == target_id for c in councils):
                        councils.append({
                            "id": target_rej.get("id"),
                            "name": target_rej.get("name"),
                            "ministry": target_rej.get("ministry"),
                            "category": target_rej.get("category", "COUNCIL"),
                            "officialUrl": target_rej.get("officialUrl", ""),
                            "status": "pending"
                        })
                    if "discoveredCouncils" in data and isinstance(data["discoveredCouncils"], list):
                        data["discoveredCouncils"] = [c for c in data["discoveredCouncils"] if c.get("id") != target_id]
                    save_data_json_with_backup(data, DATA_JSON_FILE)

                self.send_json({"status": "ok", "message": f"Council {target_id} restored to councils as pending"})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)

        elif path == "/api/run-discovery":
            if discovery_state["running"]:
                self.send_json({"status": "running", "message": "Already running"})
                return

            # 初期化してバックグラウンドスレッドで起動
            discovery_state = {
                "running": True,
                "progress": 5,
                "current_ministry": "",
                "ministry_name": "",
                "current_idx": 0,
                "total_ministries": 0,
                "discovered_count": 0,
                "logs": [],
                "result": None,
                "error": None
            }
            t = threading.Thread(target=_discovery_worker, daemon=True)
            t.start()

            self.send_json({"status": "started", "message": "Discovery started in background"})

        elif path == "/api/run-crawler":
            if crawler_state["running"]:
                self.send_json({"status": "running", "message": "Crawler is already running"})
                return

            crawler_stop_event.clear()
            crawler_state = {
                "running": True,
                "stopping": False,
                "progress": 5,
                "current_idx": 0,
                "total_councils": 0,
                "current_council": "",
                "logs": [],
                "log_seq": 0,
                "stats": None,
                "error": None,
                "lastCrawlTime": "",
                "log_file": ""
            }
            t = threading.Thread(target=_crawler_worker, daemon=True)
            t.start()

            self.send_json({"status": "started", "message": "Meeting crawler started in background"})

        elif path == "/api/stop-crawler":
            if not crawler_state["running"]:
                self.send_json({"status": "not_running", "message": "Crawler is not running"})
                return

            crawler_stop_event.set()
            crawler_state["stopping"] = True
            self.send_json({"status": "stopping", "message": "Crawler stop signal sent. Finalizing..."})

        elif path == "/api/toggle-manual-lock":
            try:
                payload = self.read_json_body()
                target_id = payload.get("id")
                target_type = payload.get("type", "council")  # "council" or "meeting"
                lock_value = payload.get("manualLock", True)

                if not target_id:
                    raise ValueError("ID is required")

                if os.path.exists(DATA_JSON_FILE):
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as df:
                        data = json.load(df)

                    if target_type == "council":
                        for c in data.get("councils", []):
                            if c.get("id") == target_id:
                                c["manualLock"] = lock_value
                                break
                    elif target_type == "meeting":
                        for m in data.get("meetings", []):
                            if m.get("id") == target_id:
                                m["manualLock"] = lock_value
                                for mat in m.get("materials", []):
                                    mat["manualLock"] = lock_value
                                break

                    save_data_json_with_backup(data, DATA_JSON_FILE)

                self.send_json({
                    "status": "ok",
                    "message": f"{target_type} {target_id} manualLock set to {lock_value}"
                })
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)

        elif path == "/api/rollback-data":
            try:
                if not os.path.exists(BACKUP_DIR):
                    raise ValueError("バックアップフォルダ (admin/backups) が存在しません。")

                b_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("data_") and f.endswith(".json")], reverse=True)
                if not b_files:
                    raise ValueError("利用可能なバックアップファイルがありません。")

                latest_backup_file = b_files[0]
                latest_backup_path = os.path.join(BACKUP_DIR, latest_backup_file)

                # 念のためロールバック前の現在の状態を退避
                if os.path.exists(DATA_JSON_FILE):
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    pre_rollback_path = os.path.join(BACKUP_DIR, f"data_pre_rollback_{ts}.json")
                    shutil.copy2(DATA_JSON_FILE, pre_rollback_path)

                # バックアップファイルで data.json を上書き復元
                shutil.copy2(latest_backup_path, DATA_JSON_FILE)

                # 復元後のデータ概要を取得
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    restored_data = json.load(f)

                c_count = len(restored_data.get("councils", []))
                m_count = len(restored_data.get("meetings", []))
                last_crawl = restored_data.get("lastCrawlTime", "-")

                self.send_json({
                    "status": "ok",
                    "message": f"直前のバックアップ ({latest_backup_file}) から data.json を正常に復元しました。",
                    "backupFile": latest_backup_file,
                    "councilsCount": c_count,
                    "meetingsCount": m_count,
                    "lastCrawlTime": last_crawl,
                    "totalBackups": len(b_files)
                })
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, status=500)
        else:
            self.send_error(404)


if __name__ == "__main__":
    print(f"Starting PM-Hub Local Admin Server at http://localhost:{PORT}")
    print(f"Access Admin Dashboard at: http://localhost:{PORT}/admin/admin_dashboard.html")
    server_address = ("", PORT)
    ThreadingHTTPServer.allow_reuse_address = True
    with ThreadingHTTPServer(server_address, CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
