#!/usr/bin/env python3
"""
AEO Monitor MVP v2 - AI検索モニタリングツール
設定ファイル対応 + 統計モード + レポート生成
"""

import json
import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error

# --- Config ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"


# --- AI Providers ---

def query_openai(prompt: str, model: str = "gpt-4o-mini") -> str:
    url = "https://api.openai.com/v1/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
        "temperature": 1.0
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    })
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def query_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    data = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json"
    })
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"ERROR: {e}"


def query_provider(provider: str, prompt: str) -> str:
    if provider == "chatgpt" and OPENAI_API_KEY:
        return query_openai(prompt)
    elif provider == "gemini" and GEMINI_API_KEY:
        return query_gemini(prompt)
    return f"ERROR: {provider} not configured"


# --- Analysis ---

def check_mentions(text: str, brands: list) -> dict:
    mentions = {}
    text_lower = text.lower()
    for brand in brands:
        brand_lower = brand.lower()
        mentioned = brand_lower in text_lower
        # 部分一致もチェック（「アクシス」で「税理士法人アクシス」を検出）
        partial = any(part in text_lower for part in brand_lower.split() if len(part) > 2)
        mentions[brand] = {
            "mentioned": mentioned or partial,
            "exact": mentioned,
            "partial": partial and not mentioned,
            "count": text_lower.count(brand_lower)
        }
    return mentions


# --- Statistical Runner ---

def run_statistical(config: dict) -> dict:
    """統計モードで実行（各質問をN回投げる）"""
    runs_per_query = config.get("runs_per_query", 3)
    providers = config.get("providers", ["chatgpt"])
    all_brands = config.get("target_brands", []) + config.get("competitors", [])
    queries = config.get("queries", [])
    
    all_results = []
    brand_stats = {b: {"total": 0, "mentioned": 0, "by_query": {}, "by_provider": {}} for b in all_brands}
    
    total_queries = len(queries) * runs_per_query * len(providers)
    current = 0
    
    for query in queries:
        for provider in providers:
            for run_idx in range(runs_per_query):
                current += 1
                print(f"  [{current}/{total_queries}] {provider} | Run {run_idx+1} | {query[:40]}...")
                
                response = query_provider(provider, query)
                
                if response.startswith("ERROR"):
                    print(f"    ⚠️  {response}")
                    continue
                
                mentions = check_mentions(response, all_brands)
                
                result = {
                    "timestamp": datetime.now().isoformat(),
                    "provider": provider,
                    "query": query,
                    "run": run_idx + 1,
                    "response": response,
                    "mentions": mentions
                }
                all_results.append(result)
                
                # 統計更新
                for brand, detail in mentions.items():
                    brand_stats[brand]["total"] += 1
                    if detail["mentioned"]:
                        brand_stats[brand]["mentioned"] += 1
                    
                    if query not in brand_stats[brand]["by_query"]:
                        brand_stats[brand]["by_query"][query] = {"total": 0, "mentioned": 0}
                    brand_stats[brand]["by_query"][query]["total"] += 1
                    if detail["mentioned"]:
                        brand_stats[brand]["by_query"][query]["mentioned"] += 1
                    
                    if provider not in brand_stats[brand]["by_provider"]:
                        brand_stats[brand]["by_provider"][provider] = {"total": 0, "mentioned": 0}
                    brand_stats[brand]["by_provider"][provider]["total"] += 1
                    if detail["mentioned"]:
                        brand_stats[brand]["by_provider"][provider]["mentioned"] += 1
                
                # Rate limit対策
                time.sleep(1)
    
    return {
        "config": config,
        "results": all_results,
        "brand_stats": brand_stats,
        "meta": {
            "total_queries": total_queries,
            "completed": len(all_results),
            "timestamp": datetime.now().isoformat()
        }
    }


# --- Report Generation ---

def generate_reports(data: dict) -> dict:
    """全形式でレポート生成"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    config = data["config"]
    brand_stats = data["brand_stats"]
    results = data["results"]
    paths = {}
    
    # 1. Raw JSON data
    json_path = DATA_DIR / f"raw-{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    paths["json"] = str(json_path)
    
    # 2. CSV summary
    csv_path = OUTPUT_DIR / f"summary-{date_str}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["brand", "mention_rate", "mentioned", "total", "is_target"])
        target = config.get("target_brands", [])
        for brand, stats in sorted(brand_stats.items(), key=lambda x: -x[1]["mentioned"]/max(x[1]["total"],1)):
            rate = stats["mentioned"] / stats["total"] * 100 if stats["total"] > 0 else 0
            writer.writerow([brand, f"{rate:.1f}%", stats["mentioned"], stats["total"], brand in target])
    paths["csv"] = str(csv_path)
    
    # 3. Markdown report
    md = generate_markdown_report(data, date_str)
    md_path = OUTPUT_DIR / f"report-{date_str}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    paths["md"] = str(md_path)
    
    # 4. Dashboard data (JSON for web UI)
    dash_data = generate_dashboard_data(data)
    dash_path = DATA_DIR / f"dashboard-{date_str}.json"
    # Also save as latest
    dash_latest = DATA_DIR / "dashboard-latest.json"
    for p in [dash_path, dash_latest]:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(dash_data, f, ensure_ascii=False, indent=2)
    paths["dashboard"] = str(dash_latest)
    
    return paths


def generate_markdown_report(data: dict, date_str: str) -> str:
    config = data["config"]
    brand_stats = data["brand_stats"]
    target = config.get("target_brands", [])
    
    lines = []
    lines.append(f"# AEO Monitor Report")
    lines.append(f"**日時:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**クライアント:** {config.get('client_name', 'N/A')}")
    lines.append(f"**業種:** {config.get('industry', 'N/A')} | **地域:** {config.get('region', 'N/A')}")
    lines.append(f"**実行回数:** 各質問 × {config.get('runs_per_query', 1)}回")
    lines.append("")
    
    # Overall ranking
    lines.append("## 📊 ブランド言及ランキング")
    lines.append("| 順位 | ブランド | 言及率 | 言及/全体 | 種別 |")
    lines.append("|------|---------|--------|----------|------|")
    
    sorted_brands = sorted(brand_stats.items(), key=lambda x: -x[1]["mentioned"]/max(x[1]["total"],1))
    for i, (brand, stats) in enumerate(sorted_brands, 1):
        rate = stats["mentioned"] / stats["total"] * 100 if stats["total"] > 0 else 0
        label = "🎯 自社" if brand in target else "🏢 競合"
        bar = "█" * int(rate / 10) + "░" * (10 - int(rate / 10))
        lines.append(f"| {i} | {brand} | {bar} {rate:.0f}% | {stats['mentioned']}/{stats['total']} | {label} |")
    
    # Per-query breakdown
    lines.append("")
    lines.append("## 📝 質問別詳細")
    for query in config.get("queries", []):
        lines.append(f"\n### Q: {query}")
        lines.append("| ブランド | 言及率 |")
        lines.append("|---------|--------|")
        for brand, stats in sorted_brands:
            q_stats = stats["by_query"].get(query, {"total": 0, "mentioned": 0})
            if q_stats["total"] > 0:
                rate = q_stats["mentioned"] / q_stats["total"] * 100
                icon = "✅" if rate > 0 else "❌"
                lines.append(f"| {icon} {brand} | {rate:.0f}% ({q_stats['mentioned']}/{q_stats['total']}) |")
    
    # Recommendations
    lines.append("")
    lines.append("## 💡 改善提案")
    
    target_stats = {b: s for b, s in brand_stats.items() if b in target}
    comp_stats = {b: s for b, s in brand_stats.items() if b not in target}
    
    for brand, stats in target_stats.items():
        rate = stats["mentioned"] / stats["total"] * 100 if stats["total"] > 0 else 0
        if rate == 0:
            lines.append(f"- 🔴 **{brand}**: AI検索で全く推薦されていません。緊急対策が必要です。")
        elif rate < 30:
            lines.append(f"- 🟡 **{brand}**: 言及率{rate:.0f}%。改善の余地があります。")
        else:
            lines.append(f"- 🟢 **{brand}**: 言及率{rate:.0f}%。良好な状態です。")
    
    best_comp = max(comp_stats.items(), key=lambda x: x[1]["mentioned"]/max(x[1]["total"],1)) if comp_stats else None
    if best_comp:
        comp_rate = best_comp[1]["mentioned"] / max(best_comp[1]["total"], 1) * 100
        lines.append(f"- 📈 競合トップは **{best_comp[0]}** (言及率{comp_rate:.0f}%) — ベンチマーク対象")
    
    return "\n".join(lines)


def generate_dashboard_data(data: dict) -> dict:
    """Webダッシュボード用JSON"""
    config = data["config"]
    brand_stats = data["brand_stats"]
    target = config.get("target_brands", [])
    
    brands = []
    for brand, stats in brand_stats.items():
        rate = stats["mentioned"] / stats["total"] * 100 if stats["total"] > 0 else 0
        brands.append({
            "name": brand,
            "mention_rate": round(rate, 1),
            "mentioned": stats["mentioned"],
            "total": stats["total"],
            "is_target": brand in target,
            "by_query": {
                q: {
                    "rate": round(s["mentioned"]/s["total"]*100, 1) if s["total"] > 0 else 0,
                    "mentioned": s["mentioned"],
                    "total": s["total"]
                }
                for q, s in stats["by_query"].items()
            }
        })
    
    brands.sort(key=lambda x: -x["mention_rate"])
    
    return {
        "generated_at": datetime.now().isoformat(),
        "client": config.get("client_name", ""),
        "industry": config.get("industry", ""),
        "region": config.get("region", ""),
        "runs_per_query": config.get("runs_per_query", 1),
        "total_queries": data["meta"]["completed"],
        "brands": brands,
        "queries": config.get("queries", [])
    }


# --- Main ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 aeo_monitor.py <config.json>")
        print("Example: python3 aeo_monitor.py ../configs/sample-tax.json")
        sys.exit(1)
    
    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    print("🔍 AEO Monitor v2 - 統計モード")
    print(f"クライアント: {config.get('client_name', 'N/A')}")
    print(f"業種: {config.get('industry', 'N/A')} | 地域: {config.get('region', 'N/A')}")
    print(f"質問数: {len(config.get('queries', []))} | 実行回数: {config.get('runs_per_query', 1)}回/質問")
    print(f"ブランド: {len(config.get('target_brands', []))}社(自社) + {len(config.get('competitors', []))}社(競合)")
    print("=" * 50)
    
    # Build full config with brands in queries
    full_config = dict(config)
    full_queries = []
    for q in config.get("queries", []):
        full_queries.append({
            "prompt": q,
            "brands": config.get("target_brands", []) + config.get("competitors", [])
        })
    
    data = run_statistical(full_config)
    paths = generate_reports(data)
    
    print("\n" + "=" * 50)
    print("📊 レポート生成完了:")
    for fmt, path in paths.items():
        print(f"  {fmt}: {path}")
    
    # Print summary
    print("\n📈 サマリー:")
    target = config.get("target_brands", [])
    for brand, stats in sorted(data["brand_stats"].items(), key=lambda x: -x[1]["mentioned"]/max(x[1]["total"],1)):
        rate = stats["mentioned"] / stats["total"] * 100 if stats["total"] > 0 else 0
        label = "🎯" if brand in target else "🏢"
        bar = "█" * int(rate / 5) + "░" * (20 - int(rate / 5))
        print(f"  {label} {brand:20s} {bar} {rate:.0f}% ({stats['mentioned']}/{stats['total']})")


if __name__ == "__main__":
    main()
