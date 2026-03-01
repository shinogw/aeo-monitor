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

    # Prepare advice items
    advice_text = diagnosis_data.get("advice", "")
    advice_items = []
    if advice_text:
        lines = [l.strip() for l in advice_text.split("\n") if l.strip()]
        current = None
        for line in lines:
            if line.startswith(("1.", "2.", "3.", "①", "②", "③", "**施策", "施策")):
                if current:
                    advice_items.append(current)
                title = line.lstrip("0123456789.①②③ ").strip("*").strip()
                current = {"title": title, "description": ""}
            elif current:
                current["description"] += line + " "
        if current:
            advice_items.append(current)
    
    if not advice_items:
        advice_items = [
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
        "advice_items": advice_items[:3],
    }

    html_str = template.render(**context)

    if HAS_WEASYPRINT:
        pdf_bytes = HTML(string=html_str).write_pdf()
        return pdf_bytes
    else:
        # Fallback: return HTML as bytes (for environments without weasyprint)
        return html_str.encode("utf-8")
