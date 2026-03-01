#!/usr/bin/env python3
"""AEO Monitor - Web Server for Railway"""

import http.server
import json
import os
import sys
import urllib.parse
from pathlib import Path
from datetime import datetime

PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Load dashboard HTML
DASHBOARD_HTML = Path("dashboard.html").read_text(encoding="utf-8")

# Copy sample data if no data exists
if not (DATA_DIR / "dashboard-latest.json").exists():
    sample = Path("sample-data.json")
    if sample.exists():
        import shutil
        shutil.copy(sample, DATA_DIR / "dashboard-latest.json")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/' or path == '/dashboard':
            script = '<script>fetch("/api/data").then(r=>r.json()).then(d=>{document.getElementById("upload-section").style.display="none";renderDashboard(d)}).catch(e=>console.log(e))</script>'
            html = DASHBOARD_HTML.replace('</body>', script + '</body>')
            self.send_html(html)

        elif path == '/api/data':
            p = DATA_DIR / "dashboard-latest.json"
            if p.exists():
                self.send_json(json.loads(p.read_text(encoding="utf-8")))
            else:
                self.send_json({"error": "No data yet"}, 404)

        elif path == '/api/health':
            self.send_json({"status": "ok", "timestamp": datetime.now().isoformat()})

        else:
            self.send_error(404)

    def send_html(self, content):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content.encode())

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


if __name__ == "__main__":
    server = http.server.HTTPServer(('0.0.0.0', PORT), Handler)
    print(f"🚀 AEO Monitor running on port {PORT}")
    server.serve_forever()
