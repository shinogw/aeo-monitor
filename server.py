#!/usr/bin/env python3
"""AEO Monitor Japan - Web Server with Landing Page, Diagnosis & PDF"""

import http.server
import json
import os
import sys
import re
import uuid
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DIAGNOSES_DIR = DATA_DIR / "diagnoses"
DIAGNOSES_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR = Path("templates")
STATIC_DIR = Path("static")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Load dashboard HTML
DASHBOARD_HTML = Path("dashboard.html").read_text(encoding="utf-8") if Path("dashboard.html").exists() else "<h1>Dashboard</h1>"

# Load templates
def load_template(name):
    p = TEMPLATE_DIR / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return f"<h1>Template {name} not found</h1>"

# Copy sample data if no data exists
if not (DATA_DIR / "dashboard-latest.json").exists():
    sample = Path("sample-data.json")
    if sample.exists():
        import shutil
        shutil.copy(sample, DATA_DIR / "dashboard-latest.json")


def query_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    url = "https://api.openai.com/v1/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 1.0
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def run_diagnosis(business_name: str, industry: str, area: str, queries: list) -> dict:
    """Run diagnosis: query ChatGPT for each query and analyze mentions."""
    query_results = []
    mentioned_count = 0
    all_competitors = {}

    for q in queries[:3]:
        response = query_openai(q)
        if response.startswith("ERROR"):
            query_results.append({
                "query": q, "response": response,
                "mentioned": False, "sources": [], "competitors_found": []
            })
            continue

        # Check if business is mentioned
        mentioned = business_name.lower() in response.lower()
        # Partial match
        if not mentioned:
            parts = [p for p in business_name.split() if len(p) > 1]
            mentioned = any(p.lower() in response.lower() for p in parts) if parts else False

        if mentioned:
            mentioned_count += 1

        # Extract potential competitor names (heuristic: lines with Japanese business-like names)
        competitors_found = []
        for line in response.split("\n"):
            line = line.strip().lstrip("0123456789.-•*） ")
            if len(line) > 2 and len(line) < 40 and business_name.lower() not in line.lower():
                # Simple heuristic: if it looks like a business name
                if any(c in line for c in ["店", "院", "所", "堂", "亭", "屋", "サロン", "クリニック"]):
                    name = re.sub(r'[【】「」\(\)（）：:、。].*', '', line).strip()
                    if name and len(name) > 1:
                        competitors_found.append(name)

        for c in competitors_found:
            all_competitors[c] = all_competitors.get(c, 0) + 1

        # Extract sources (URLs or site names)
        sources = re.findall(r'(?:https?://[^\s\)]+|(?:食べログ|Googleマップ|ホットペッパー|ぐるなび|Retty|公式サイト|口コミ))', response)

        query_results.append({
            "query": q,
            "response": response,
            "mentioned": mentioned,
            "sources": list(set(sources))[:5],
            "competitors_found": competitors_found
        })

    total = len(queries[:3])
    mention_rate = round(mentioned_count / total * 100) if total > 0 else 0

    # Get improvement advice
    advice = ""
    if OPENAI_API_KEY:
        # Competitors summary for prompt
    comp_summary = ", ".join([f"{c[0]}({c[1]}回)" for c in sorted_comps[:5]]) if sorted_comps else "なし"
    
    # Query details for prompt
    query_detail = ""
    for qr in query_results:
        query_detail += f"\nQ: {qr['query']}\n言及: {'あり' if qr['mentioned'] else 'なし'}\n引用ソース: {', '.join(qr.get('sources', []))}\n競合: {', '.join(qr.get('competitors_found', [])[:3])}\n"

    advice_prompt = f"""あなたはAEO（AI検索最適化）の実務コンサルタントです。
飲食店や中小企業のオーナーが**明日から実行できる**レベルの具体的な改善提案を生成してください。

## 重要ルール
- 「SEO対策を強化」「構造化データ整備」など抽象的な表現は禁止
- 必ず「何を」「どこで」「どうやって」を具体的に書く
- ITに詳しくないオーナーでも実行できる手順にする
- **Markdown形式で出力**（見出し、箇条書き、表を活用）

## クライアント情報
- 企業名: {business_name}
- 業種: {industry}
- エリア: {area}
- AI検索言及率: {mention_rate}%（{mentioned_count}/{total}クエリで言及）
- 推薦されていた競合: {comp_summary}

## 各クエリの詳細結果
{query_detail}

## 以下の形式で出力してください：

### 診断結果
- **現状**: AI検索で推薦されない直接的な原因（2行）
- **競合との差**: 推薦されている店とされていない店の具体的な違い

### 施策一覧（10個）

| # | 何をするか（具体的に） | 何が改善されるか | 効果(5) | 手軽さ(5) | スコア(/25) | 所要時間 |
|---|----------------------|----------------|---------|----------|------------|---------|

### 🎯 TOP 3 推奨施策

**施策1: [具体名]（スコア /25）**
📌 **解決する問題**: ...
📝 **やること（ステップ）**:
  1. [明日できる具体的アクション]
  2. [次にやること]
  3. [その次]
⏰ **所要時間**: 〇時間（初回）/ 週〇分（継続）
📈 **期待効果**: [数値で]
💰 **コスト**: 無料 / 月額〇円

**施策2: ...**
**施策3: ...**

### AIが推薦している競合の特徴
推薦されている店が「なぜAIに選ばれるのか」を具体的に3つ。

### 📊 参考データ
- AI検索利用者は前年比7.5倍に急増（BrightLocal 2026調査）
- AI経由の来店客は従来の4.4倍の価値がある（Semrush調査）
- 口コミ20件未満の店は47%の消費者が利用回避"""
        advice = query_openai(advice_prompt)

    # Sort competitors
    sorted_comps = sorted(all_competitors.items(), key=lambda x: -x[1])[:10]
    competitors = [{"name": name, "mentions": count} for name, count in sorted_comps]

    diagnosis_id = str(uuid.uuid4())[:8]
    result = {
        "diagnosis_id": diagnosis_id,
        "business_name": business_name,
        "industry": industry,
        "area": area,
        "mention_rate": mention_rate,
        "mentioned_count": mentioned_count,
        "total_queries": total,
        "query_results": query_results,
        "competitors": competitors,
        "advice": advice,
        "created_at": datetime.now().isoformat()
    }

    # Save
    (DIAGNOSES_DIR / f"{diagnosis_id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return result


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Landing page
        if path == '/':
            self.send_html(load_template("landing.html"))

        # Diagnosis results page
        elif path == '/diagnosis':
            self.send_html(load_template("diagnosis.html"))

        # Dashboard (legacy)
        elif path == '/dashboard':
            script = '<script>fetch("/api/data").then(r=>r.json()).then(d=>{document.getElementById("upload-section").style.display="none";renderDashboard(d)}).catch(e=>console.log(e))</script>'
            html = DASHBOARD_HTML.replace('</body>', script + '</body>')
            self.send_html(html)

        # Static files
        elif path.startswith('/static/'):
            self.serve_static(path[8:])

        # API endpoints
        elif path == '/api/data':
            p = DATA_DIR / "dashboard-latest.json"
            if p.exists():
                self.send_json(json.loads(p.read_text(encoding="utf-8")))
            else:
                self.send_json({"error": "No data yet"}, 404)

        elif path == '/api/health':
            self.send_json({"status": "ok", "timestamp": datetime.now().isoformat()})

        elif path.startswith('/api/pdf/'):
            diagnosis_id = path.split('/')[-1]
            self.serve_pdf(diagnosis_id)

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/api/diagnose':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "Invalid JSON"}, 400)
                return

            business_name = data.get("business_name", "").strip()
            industry = data.get("industry", "").strip()
            area = data.get("area", "").strip()
            queries = data.get("queries", [])
            
            if not business_name or not industry or not area:
                self.send_json({"error": "必須項目を入力してください"}, 400)
                return
            
            if not queries:
                self.send_json({"error": "検索クエリを指定してください"}, 400)
                return

            if not OPENAI_API_KEY:
                self.send_json({"error": "APIキーが設定されていません"}, 500)
                return

            try:
                result = run_diagnosis(business_name, industry, area, queries)
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
        else:
            self.send_error(404)

    def serve_static(self, filename):
        filepath = STATIC_DIR / filename
        if not filepath.exists():
            self.send_error(404)
            return
        
        ext = filepath.suffix.lower()
        content_types = {
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.ico': 'image/x-icon',
        }
        ct = content_types.get(ext, 'application/octet-stream')
        
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Cache-Control', 'public, max-age=3600')
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    def serve_pdf(self, diagnosis_id):
        diag_path = DIAGNOSES_DIR / f"{diagnosis_id}.json"
        if not diag_path.exists():
            self.send_json({"error": "Diagnosis not found"}, 404)
            return
        
        try:
            diag_data = json.loads(diag_path.read_text(encoding="utf-8"))
            from pdf_generator import generate_pdf
            pdf_bytes = generate_pdf(diag_data)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', 
                f'attachment; filename="AEO_Report_{diagnosis_id}.pdf"')
            self.end_headers()
            self.wfile.write(pdf_bytes)
        except ImportError:
            # Fallback: send HTML if weasyprint not available
            diag_data = json.loads(diag_path.read_text(encoding="utf-8"))
            from pdf_generator import generate_pdf
            html_bytes = generate_pdf(diag_data)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_bytes)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

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
    print(f"🚀 AEO Monitor Japan running on port {PORT}")
    print(f"   Landing: http://localhost:{PORT}/")
    print(f"   Dashboard: http://localhost:{PORT}/dashboard")
    server.serve_forever()
