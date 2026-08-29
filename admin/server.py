import http.server
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
import sys
import threading
import urllib.parse
from datetime import datetime
from apply_report import apply_report
from discover_councils import run_discovery
from crawler import run_meeting_crawler, save_data_json_with_backup

PORT = 8000
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))

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

# Global crawler status state
crawler_state = {
    "running": False,
    "progress": 0,
    "current_idx": 0,
    "total_councils": 0,
    "current_council": "",
    "logs": [],
    "log_seq": 0,
    "stats": None,
    "error": None,
    "lastCrawlTime": ""
}

def _crawler_worker():
    global crawler_state
    def on_progress(msg, data=None):
        if data:
            if data.get("type") == "council_start":
                crawler_state["progress"] = data.get("progress", crawler_state["progress"])
                crawler_state["current_council"] = data.get("council_name", "")
                crawler_state["current_idx"] = data.get("current", 0)
                crawler_state["total_councils"] = data.get("total", 0)
            elif data.get("type") == "crawl_completed":
                crawler_state["lastCrawlTime"] = data.get("lastCrawlTime", "")
        crawler_state["log_seq"] += 1
        crawler_state["logs"].append({"id": crawler_state["log_seq"], "text": msg})
        if len(crawler_state["logs"]) > 500:
            crawler_state["logs"] = crawler_state["logs"][-500:]

    try:
        stats = run_meeting_crawler(progress_callback=on_progress)
        crawler_state["stats"] = stats
        crawler_state["progress"] = 100
        crawler_state["running"] = False
    except Exception as e:
        crawler_state["error"] = str(e)
        crawler_state["running"] = False

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

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/docs/data.json", "/data.json"):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps({}).encode('utf-8'))
        elif path == "/api/discovery-keywords":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.wfile.write(json.dumps(data.get("discoveryKeywords", {})).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({}).encode('utf-8'))
        elif path == "/api/discovered-councils":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                discovered = data.get("discoveredCouncils", [])

                # 却下済み会議体リストのロードと除外
                rej_file = os.path.join(os.path.dirname(__file__), "rejected_councils.json")
                rej_ids = set()
                rej_names = set()
                rej_urls = set()
                if os.path.exists(rej_file):
                    try:
                        with open(rej_file, "r", encoding="utf-8") as rf:
                            rej_list = json.load(rf)
                            for rc in rej_list:
                                if rc.get("id"): rej_ids.add(rc.get("id"))
                                if rc.get("name"): rej_names.add(rc.get("name").strip())
                                if rc.get("officialUrl"): rej_urls.add(rc.get("officialUrl").rstrip("/"))
                    except Exception:
                        pass

                filtered = [
                    c for c in discovered
                    if c.get("id") not in rej_ids
                    and c.get("name", "").strip() not in rej_names
                    and (not c.get("officialUrl") or c.get("officialUrl").rstrip("/") not in rej_urls)
                ]
                self.wfile.write(json.dumps({"councils": filtered}).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({"councils": []}).encode('utf-8'))
        elif path == "/api/verification-report":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            rep_file = os.path.join(BASE_DIR, "ai_verification_report.json")
            if os.path.exists(rep_file):
                with open(rep_file, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps({}).encode('utf-8'))
        elif path == "/api/rejected-councils":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            rej_file = os.path.join(os.path.dirname(__file__), "rejected_councils.json")
            if os.path.exists(rej_file):
                with open(rej_file, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps([]).encode('utf-8'))
        elif path == "/api/get-crawler-config":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.wfile.write(json.dumps(data.get("crawlerConfig", {"llm_mode": True})).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({"llm_mode": True}).encode('utf-8'))
        elif path == "/api/discovery-status":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            query = parsed_url.query
            params = urllib.parse.parse_qs(query)
            since_id = int(params.get("since_id", params.get("since", [0]))[0])
            
            all_logs = discovery_state["logs"]
            new_logs = [l for l in all_logs if l["id"] > since_id]
            latest_id = all_logs[-1]["id"] if all_logs else 0

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
            self.wfile.write(json.dumps(res_payload, ensure_ascii=False).encode('utf-8'))
        elif path == "/api/crawler-status":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            query = parsed_url.query
            params = urllib.parse.parse_qs(query)
            since_id = int(params.get("since_id", params.get("since", [0]))[0])
            
            all_logs = crawler_state["logs"]
            new_logs = [l for l in all_logs if l["id"] > since_id]
            latest_id = all_logs[-1]["id"] if all_logs else 0

            res_payload = {
                "running": crawler_state["running"],
                "progress": crawler_state["progress"],
                "current_council": crawler_state["current_council"],
                "current_idx": crawler_state["current_idx"],
                "total_councils": crawler_state["total_councils"],
                "logs": new_logs,
                "latest_log_id": latest_id,
                "totalLogs": crawler_state["log_seq"],
                "stats": crawler_state["stats"],
                "error": crawler_state["error"],
                "lastCrawlTime": crawler_state["lastCrawlTime"]
            }
            self.wfile.write(json.dumps(res_payload, ensure_ascii=False).encode('utf-8'))
        elif path == "/api/new-meetings":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            new_list = []
            if os.path.exists(DATA_JSON_FILE):
                try:
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
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
            self.wfile.write(json.dumps({"count": len(new_list), "meetings": new_list}, ensure_ascii=False).encode('utf-8'))
        elif path == "/api/backups":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            backup_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "backups"))
            backups = []
            if os.path.exists(backup_dir):
                for f in sorted(os.listdir(backup_dir), reverse=True):
                    if f.startswith("data_") and f.endswith(".json"):
                        f_path = os.path.join(backup_dir, f)
                        sz = os.path.getsize(f_path)
                        mtime = os.path.getmtime(f_path)
                        backups.append({
                            "filename": f,
                            "sizeBytes": sz,
                            "createdAt": datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S")
                        })
            self.wfile.write(json.dumps({"backups": backups}, ensure_ascii=False).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in ("/api/save-ministry-updates", "/api/save-verification-report"):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                report = {
                    "_format": "pmhub-verification-report-v2",
                    "exportedAt": data.get("exportedAt"),
                    "targetFile": "docs/data.js",
                    "corrections": data.get("corrections", [])
                }
                temp_json = os.path.join(os.path.dirname(__file__), "_temp_update.json")
                with open(temp_json, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)

                success = apply_report(temp_json)
                if os.path.exists(temp_json):
                    os.remove(temp_json)

                if success:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "message": "docs/data.js successfully updated!"}).encode('utf-8'))
                else:
                    self.send_response(500)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif path == "/api/save-discovery-keywords":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data_kw = json.loads(post_data.decode('utf-8'))
                if os.path.exists(DATA_JSON_FILE):
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["discoveryKeywords"] = data_kw
                    with open(DATA_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Keywords updated in data.json"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif path == "/api/save-crawler-config":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                config_data = json.loads(post_data.decode('utf-8'))
                if os.path.exists(DATA_JSON_FILE):
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["crawlerConfig"] = config_data
                    with open(DATA_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Crawler config updated in data.json"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif path == "/api/save-rejected-councils":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                rej_file = os.path.join(os.path.dirname(__file__), "rejected_councils.json")
                with open(rej_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Rejected councils updated"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif path == "/api/reject-council":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                target_id = payload.get("id")
                reason = payload.get("reason", "Admin rejected council")
                council_obj = payload.get("council")

                if not target_id:
                    raise ValueError("Council ID is required")

                rej_file = os.path.join(os.path.dirname(__file__), "rejected_councils.json")
                rejected_list = []
                if os.path.exists(rej_file):
                    with open(rej_file, "r", encoding="utf-8") as rf:
                        rejected_list = json.load(rf)

                target_council = council_obj
                if os.path.exists(DATA_JSON_FILE):
                    with open(DATA_JSON_FILE, "r", encoding="utf-8") as df:
                        data = json.load(df)
                    
                    councils = data.get("councils", [])

                    c_idx = next((i for i, c in enumerate(councils) if c.get("id") == target_id), None)
                    if c_idx is not None:
                        target_council = councils.pop(c_idx)
                    
                    if "discoveredCouncils" in data:
                        del data["discoveredCouncils"]

                    with open(DATA_JSON_FILE, "w", encoding="utf-8") as df:
                        json.dump(data, df, ensure_ascii=False, indent=2)

                if not any(rc.get("id") == target_id for rc in rejected_list):
                    rej_item = {
                        "id": target_id,
                        "name": target_council.get("name") if target_council else target_id,
                        "ministry": target_council.get("ministry") if target_council else "",
                        "category": target_council.get("category", "COUNCIL") if target_council else "COUNCIL",
                        "officialUrl": target_council.get("officialUrl") if target_council else "",
                        "rejectedAt": payload.get("rejectedAt") or "2026-08-27",
                        "reason": reason
                    }
                    rejected_list.append(rej_item)
                    with open(rej_file, "w", encoding="utf-8") as wf:
                        json.dump(rejected_list, wf, ensure_ascii=False, indent=2)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": f"Council {target_id} moved to rejected list"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif path == "/api/revert-rejected-council":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                target_id = payload.get("id")
                if not target_id:
                    raise ValueError("Council ID is required")

                rej_file = os.path.join(os.path.dirname(__file__), "rejected_councils.json")
                rejected_list = []
                target_rej = None
                if os.path.exists(rej_file):
                    with open(rej_file, "r", encoding="utf-8") as rf:
                        rejected_list = json.load(rf)
                    
                    r_idx = next((i for i, c in enumerate(rejected_list) if c.get("id") == target_id), None)
                    if r_idx is not None:
                        target_rej = rejected_list.pop(r_idx)
                        with open(rej_file, "w", encoding="utf-8") as wf:
                            json.dump(rejected_list, wf, ensure_ascii=False, indent=2)

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
                    if "discoveredCouncils" in data:
                        del data["discoveredCouncils"]
                    with open(DATA_JSON_FILE, "w", encoding="utf-8") as df:
                        json.dump(data, df, ensure_ascii=False, indent=2)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": f"Council {target_id} restored to councils as pending"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif path == "/api/run-discovery":
            global discovery_state
            if discovery_state["running"]:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "running", "message": "Already running"}).encode('utf-8'))
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

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "message": "Discovery started in background"}).encode('utf-8'))

        elif path == "/api/run-crawler":
            global crawler_state
            if crawler_state["running"]:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "running", "message": "Crawler is already running"}).encode('utf-8'))
                return

            crawler_state = {
                "running": True,
                "progress": 5,
                "current_idx": 0,
                "total_councils": 0,
                "current_council": "",
                "logs": [],
                "stats": None,
                "error": None,
                "lastCrawlTime": ""
            }
            t = threading.Thread(target=_crawler_worker, daemon=True)
            t.start()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "message": "Meeting crawler started in background"}).encode('utf-8'))
        elif path == "/api/toggle-manual-lock":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
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

                    with open(DATA_JSON_FILE, "w", encoding="utf-8") as df:
                        json.dump(data, df, ensure_ascii=False, indent=2)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "ok",
                    "message": f"{target_type} {target_id} manualLock set to {lock_value}"
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

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
