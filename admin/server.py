import http.server
import socketserver
import json
import os
import sys
from apply_report import apply_report

PORT = 8000
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

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
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "message": "docs/data.js successfully updated!"}).encode('utf-8'))
                else:
                    self.send_response(500)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
        else:
            self.send_error(404)

if __name__ == "__main__":
    print(f"Starting PM-Hub Local Admin Server at http://localhost:{PORT}")
    print(f"Access Verification Tool at: http://localhost:{PORT}/admin/verify_new_councils.html")
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
