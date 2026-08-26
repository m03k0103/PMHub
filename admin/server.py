import http.server
import socketserver
import json
import os
import sys
import threading
import urllib.parse
from apply_report import apply_report
from discover_councils import run_discovery

PORT = 8000
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_JSON_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "data.json"))
KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), "discovery_keywords.json")
CRAWLER_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "crawler_config.json")

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
    "result": None,
    "error": None
}

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
        discovery_state["logs"].append(msg)
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

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/discovery-keywords":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if os.path.exists(KEYWORDS_FILE):
                with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps({}).encode('utf-8'))
        elif self.path == "/api/discovered-councils":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if os.path.exists(DATA_JSON_FILE):
                with open(DATA_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.wfile.write(json.dumps({"councils": data.get("discoveredCouncils", [])}).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({"councils": []}).encode('utf-8'))
        elif self.path == "/api/verification-report":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            rep_file = os.path.join(BASE_DIR, "ai_verification_report.json")
            if os.path.exists(rep_file):
                with open(rep_file, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps({}).encode('utf-8'))
        elif self.path == "/api/rejected-councils":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            rej_file = os.path.join(os.path.dirname(__file__), "rejected_councils.json")
            if os.path.exists(rej_file):
                with open(rej_file, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps([]).encode('utf-8'))
        elif self.path == "/api/get-crawler-config":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            if os.path.exists(CRAWLER_CONFIG_FILE):
                with open(CRAWLER_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(json.dumps({"llm_mode": True}).encode('utf-8'))
        elif self.path.startswith("/api/discovery-status"):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            # 返すログのオフセット処理
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            since = int(params.get("since", [0])[0])
            
            new_logs = discovery_state["logs"][since:]
            res_payload = {
                "running": discovery_state["running"],
                "progress": discovery_state["progress"],
                "current_ministry": discovery_state["current_ministry"],
                "ministry_name": discovery_state["ministry_name"],
                "current_idx": discovery_state["current_idx"],
                "total_ministries": discovery_state["total_ministries"],
                "discovered_count": discovery_state["discovered_count"],
                "logs": new_logs,
                "totalLogs": len(discovery_state["logs"]),
                "result": discovery_state["result"],
                "error": discovery_state["error"]
            }
            self.wfile.write(json.dumps(res_payload, ensure_ascii=False).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path in ("/api/save-ministry-updates", "/api/save-verification-report"):
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

        elif self.path == "/api/save-discovery-keywords":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Keywords updated"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == "/api/save-crawler-config":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                with open(CRAWLER_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Crawler config updated"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == "/api/save-rejected-councils":
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

        elif self.path == "/api/run-discovery":
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
        else:
            self.send_error(404)

if __name__ == "__main__":
    print(f"Starting PM-Hub Local Admin Server at http://localhost:{PORT}")
    print(f"Access Admin Dashboard at: http://localhost:{PORT}/admin/admin_dashboard.html")
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
