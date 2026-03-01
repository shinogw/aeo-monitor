#!/usr/bin/env python3
"""PDF Report Generator for AEO Monitor - uses WeasyPrint for HTML→PDF"""

import os
from pathlib import Path
from datetime import datetime

try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False

TEMPLATE_DIR = Path(__file__).parent / "templates"


def parse_advice_sections(advice_text: str) -> dict:
    """Parse the full advice markdown into structured sections."""
    sections = {
        "diagnosis": "",
        "table_rows": [],
        "top3": [],
        "competitors": "",
        "stats": "",
        "full_markdown": advice_text
    }
    
    if not advice_text:
        return sections
    
    lines = advice_text.split("\n")
    current_section = None
    current_top3_item = None
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        
        # Detect sections
        if "診断結果" in stripped and stripped.startswith("#"):
            current_section = "diagnosis"
            continue
        elif "施策一覧" in stripped and stripped.startswith("#"):
            current_section = "table"
            continue
        elif "TOP 3" in stripped or "TOP3" in stripped:
            current_section = "top3"
            continue
        elif "競合の特徴" in stripped and stripped.startswith("#"):
            current_section = "competitors"
            continue
        elif "参考データ" in stripped and stripped.startswith("#"):
            current_section = "stats"
            continue
        
        # Parse table rows
        if current_section == "table" and "|" in stripped and not stripped.startswith("|--") and not stripped.startswith("| #"):
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if len(cells) >= 6 and cells[0].isdigit():
                sections["table_rows"].append({
                    "num": cells[0],
                    "action": cells[1],
                    "improvement": cells[2],
                    "effect": cells[3],
                    "ease": cells[4],
                    "score": cells[5],
                    "time": cells[6] if len(cells) > 6 else ""
                })
        
        # Parse TOP 3 items
        elif current_section == "top3":
            if stripped.startswith("**施策") or (stripped.startswith("**") and ("スコア" in stripped or "/25" in stripped)):
                if current_top3_item:
                    sections["top3"].append(current_top3_item)
                title = stripped.strip("*").strip()
                current_top3_item = {"title": title, "description": ""}
            elif current_top3_item:
                current_top3_item["description"] += stripped + "\n"
        
        # Other sections
        elif current_section == "diagnosis":
            sections["diagnosis"] += stripped + "\n"
        elif current_section == "competitors":
            sections["competitors"] += stripped + "\n"
        elif current_section == "stats":
            sections["stats"] += stripped + "\n"
    
    if current_top3_item:
        sections["top3"].append(current_top3_item)
    
    return sections


def generate_pdf(diagnosis_data: dict) -> bytes:
    """Generate a PDF report from diagnosis data. Returns PDF bytes."""
    if not HAS_JINJA:
        raise RuntimeError("jinja2 is required for PDF generation")

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html")

    # Compute grade
    rate = diagnosis_data.get("mention_rate", 0)
    if rate >= 80:
        grade, grade_class = "A", "a"
    elif rate >= 60:
        grade, grade_class = "B", "b"
    elif rate >= 40:
        grade, grade_class = "C", "c"
    elif rate >= 20:
        grade, grade_class = "D", "d"
    else:
        grade, grade_class = "F", "f"

    # Parse the full advice markdown
    advice_text = diagnosis_data.get("advice", "")
    
    # Pass full advice as markdown for detailed rendering
    # Also extract structured sections
    advice_sections = parse_advice_sections(advice_text)
    
    # Fallback advice items
    if not advice_sections.get("top3"):
        advice_sections["top3"] = [
            {"title": "Googleビジネスプロフィールの最適化", "description": "営業時間、写真、メニュー情報を最新に更新してください。"},
            {"title": "口コミの充実", "description": "お客様にGoogleマップでの口コミを依頼しましょう。"},
            {"title": "公式サイトの情報充実", "description": "サービス内容、料金、アクセス情報を詳しく掲載してください。"},
        ]

    # Shorten responses for PDF
    query_results = []
    for qr in diagnosis_data.get("query_results", []):
        qr_copy = dict(qr)
        resp = qr.get("response", "")
        qr_copy["response_short"] = resp[:300] + "..." if len(resp) > 300 else resp
        query_results.append(qr_copy)

    context = {
        "business_name": diagnosis_data.get("business_name", ""),
        "industry": diagnosis_data.get("industry", ""),
        "area": diagnosis_data.get("area", ""),
        "date": datetime.now().strftime("%Y年%m月%d日"),
        "grade": grade,
        "grade_class": grade_class,
        "mention_rate": rate,
        "total_queries": diagnosis_data.get("total_queries", 0),
        "mentioned_count": diagnosis_data.get("mentioned_count", 0),
        "competitor_count": len(diagnosis_data.get("competitors", [])),
        "query_results": query_results,
        "competitors": diagnosis_data.get("competitors", []),
        "advice_sections": advice_sections,
        "advice_full": advice_text,
    }

    html_str = template.render(**context)

    if HAS_WEASYPRINT:
        pdf_bytes = HTML(string=html_str).write_pdf()
        return pdf_bytes
    else:
        # Fallback: return HTML as bytes (for environments without weasyprint)
        return html_str.encode("utf-8")
