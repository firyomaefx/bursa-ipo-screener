"""
PDF Report Generator for Bursa Malaysia IPO Analysis.

Generates a professional PDF with:
- Cover page with Bursa branding
- Individual IPO analysis pages with charts
- Comparison summary table
- Risk heatmap visualization
"""

import io
import os
import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable, KeepTogether,
)
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ── Colors ──────────────────────────────────────────────────────────────────
BURSA_BLUE = HexColor("#003B6F")
BURSA_GOLD = HexColor("#C8A951")
VERDICT_BUY = HexColor("#27AE60")
VERDICT_NEUTRAL = HexColor("#F39C12")
VERDICT_AVOID = HexColor("#E74C3C")
LIGHT_BG = HexColor("#F8F9FA")
RISK_HIGH = HexColor("#E74C3C")
RISK_MED = HexColor("#F39C12")
RISK_LOW = HexColor("#27AE60")
TABLE_HEADER_BG = HexColor("#003B6F")
TABLE_ALT_BG = HexColor("#EBF5FB")


# ── Chart Generators ────────────────────────────────────────────────────────

def _generate_proceeds_chart(analysis: dict) -> bytes:
    """Pie chart of IPO proceeds allocation."""
    p = analysis.get("proceeds", {})
    
    labels = []
    sizes = []
    chart_colors = ["#3498DB", "#E74C3C", "#2ECC71", "#F39C12", "#9B59B6"]
    
    for key, label in [
        ("capex_pct", "CapEx"),
        ("debt_repayment_pct", "Debt Repayment"),
        ("working_capital_pct", "Working Capital"),
    ]:
        val = p.get(key, "0%")
        try:
            num = float(str(val).replace("%", "").strip())
            if num > 0:
                labels.append(label)
                sizes.append(num)
        except (ValueError, TypeError):
            pass
    
    if not sizes:
        labels = ["Data Not Disclosed"]
        sizes = [100]
        chart_colors = ["#BDC3C7"]

    fig, ax = plt.subplots(figsize=(4, 3), dpi=150)
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.0f%%",
        colors=chart_colors[:len(sizes)],
        startangle=90, textprops={"fontsize": 9},
    )
    for autotext in autotexts:
        autotext.set_fontsize(8)
        autotext.set_fontweight("bold")
    ax.set_title("Proceeds Allocation", fontsize=11, fontweight="bold", color="#003B6F")
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _generate_risk_chart(analysis: dict) -> bytes:
    """Horizontal bar chart of risk severity."""
    risks = analysis.get("critical_risks", [])
    if not risks:
        risks = [{"risk": "No risks identified", "severity": "Low"}]
    
    # Limit to 5 risks
    risks = risks[:5]
    
    risk_labels = [r.get("risk", "Unknown")[:40] + ("..." if len(r.get("risk", "")) > 40 else "") for r in risks]
    severities = [r.get("severity", "Medium") for r in risks]
    
    sev_map = {"High": 3, "Medium": 2, "Low": 1}
    sev_nums = [sev_map.get(s, 2) for s in severities]
    bar_colors = [
        RISK_HIGH.hexval() if s == "High" else RISK_MED.hexval() if s == "Medium" else RISK_LOW.hexval()
        for s in severities
    ]
    
    fig, ax = plt.subplots(figsize=(5, 2.5), dpi=150)
    y_pos = range(len(risks))
    bars = ax.barh(y_pos, sev_nums, color=bar_colors, height=0.6, edgecolor="white")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(risk_labels, fontsize=8)
    ax.set_xlim(0, 4)
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(["Low", "Medium", "High"], fontsize=8)
    ax.set_title("Risk Assessment", fontsize=11, fontweight="bold", color="#003B6F")
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _generate_comparison_chart(all_analyses: list) -> bytes:
    """Bar chart comparing key metrics across IPOs."""
    names = []
    pe_values = []
    verdict_colors = []
    
    for a in all_analyses[:3]:
        name = a.get("ipo_name", "Unknown")
        if len(name) > 18:
            name = name[:18] + "..."
        names.append(name)
        
        v = a.get("valuation", {})
        pe_str = v.get("forward_pe", "N/A")
        try:
            pe = float(str(pe_str).replace("x", "").replace("X", "").strip())
        except (ValueError, TypeError):
            pe = 0
        pe_values.append(pe)
        
        verdict = a.get("final_verdict", "").upper()
        if "BUY" in verdict:
            verdict_colors.append(VERDICT_BUY.hexval())
        elif "AVOID" in verdict:
            verdict_colors.append(VERDICT_AVOID.hexval())
        else:
            verdict_colors.append(VERDICT_NEUTRAL.hexval())
    
    fig, ax = plt.subplots(figsize=(5, 3), dpi=150)
    x = range(len(names))
    bars = ax.bar(x, pe_values, color=verdict_colors, width=0.6, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8, rotation=15, ha="right")
    ax.set_ylabel("Forward P/E", fontsize=9)
    ax.set_title("IPO Comparison — P/E Ratios", fontsize=11, fontweight="bold", color="#003B6F")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    # Legend
    legend_patches = [
        mpatches.Patch(color=VERDICT_BUY.hexval(), label="BUY"),
        mpatches.Patch(color=VERDICT_NEUTRAL.hexval(), label="NEUTRAL"),
        mpatches.Patch(color=VERDICT_AVOID.hexval(), label="AVOID"),
    ]
    ax.legend(handles=legend_patches, fontsize=7, loc="upper right")
    plt.tight_layout()
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _generate_verdict_gauge(analysis: dict) -> bytes:
    """Gauge-style verdict indicator."""
    verdict = analysis.get("final_verdict", "NEUTRAL").upper()
    
    if "BUY" in verdict:
        angle = 150
        gauge_color = "#27AE60"
        label = "BUY"
    elif "AVOID" in verdict:
        angle = 30
        gauge_color = "#E74C3C"
        label = "AVOID"
    else:
        angle = 90
        gauge_color = "#F39C12"
        label = "NEUTRAL"
    
    fig, ax = plt.subplots(figsize=(2.5, 1.8), dpi=150, subplot_kw={"projection": "polar"})
    
    # Background arc
    theta = np.linspace(0, np.pi, 100)
    ax.plot(theta, [1]*100, color="#BDC3C7", linewidth=12, solid_capstyle="round")
    
    # Colored sections
    ax.plot(np.linspace(0, np.pi/3, 34), [1]*34, color="#E74C3C", linewidth=12, solid_capstyle="butt")
    ax.plot(np.linspace(np.pi/3, 2*np.pi/3, 34), [1]*34, color="#F39C12", linewidth=12, solid_capstyle="butt")
    ax.plot(np.linspace(2*np.pi/3, np.pi, 34), [1]*34, color="#27AE60", linewidth=12, solid_capstyle="butt")
    
    # Needle
    needle_angle = np.radians(angle)
    ax.annotate("", xy=(needle_angle, 0.9), xytext=(0, 0),
                arrowprops=dict(arrowstyle="-|>", color="#2C3E50", lw=2.5))
    
    ax.set_ylim(0, 1.3)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["polar"].set_visible(False)
    
    ax.text(0, -0.15, label, transform=ax.transAxes, fontsize=14, fontweight="bold",
            color=gauge_color, ha="center", va="top")
    
    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ── PDF Builder ─────────────────────────────────────────────────────────────

def generate_ipo_report(analyses: list, ipo_data_list: list = None) -> str:
    """
    Generate a full PDF report from IPO analyses.
    
    Args:
        analyses: List of analysis dicts from llm_analyzer
        ipo_data_list: Original scraped IPO data (optional)
    
    Returns:
        Path to the generated PDF file.
    """
    output_dir = tempfile.mkdtemp(prefix="ipo_report_")
    pdf_path = os.path.join(output_dir, f"IPO_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=2*cm,
        bottomMargin=2*cm,
        leftMargin=2*cm,
        rightMargin=2*cm,
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        "CoverTitle", parent=styles["Title"],
        fontSize=28, textColor=BURSA_BLUE, spaceAfter=6*mm,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "CoverSub", parent=styles["Normal"],
        fontSize=14, textColor=BURSA_GOLD, spaceAfter=10*mm,
        alignment=TA_CENTER, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SectionHeader", parent=styles["Heading1"],
        fontSize=16, textColor=BURSA_BLUE, spaceBefore=8*mm, spaceAfter=4*mm,
        fontName="Helvetica-Bold", borderWidth=1, borderColor=BURSA_GOLD,
        borderPadding=3,
    ))
    styles.add(ParagraphStyle(
        "SubHeader", parent=styles["Heading2"],
        fontSize=12, textColor=HexColor("#2C3E50"), spaceBefore=4*mm, spaceAfter=2*mm,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["Normal"],
        fontSize=9, leading=13, textColor=HexColor("#2C3E50"),
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "Verdict", parent=styles["Normal"],
        fontSize=14, alignment=TA_CENTER, fontName="Helvetica-Bold",
        spaceBefore=6*mm, spaceAfter=6*mm,
    ))
    styles.add(ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=7, textColor=HexColor("#95A5A6"), alignment=TA_CENTER,
    ))
    
    elements = []
    
    # ── Cover Page ──
    elements.append(Spacer(1, 4*cm))
    elements.append(Paragraph("🇲🇾 BURSA MALAYSIA", styles["CoverTitle"]))
    elements.append(Paragraph("IPO SCREENER REPORT", styles["CoverTitle"]))
    elements.append(Spacer(1, 5*mm))
    elements.append(HRFlowable(width="60%", thickness=2, color=BURSA_GOLD, spaceAfter=5*mm, spaceBefore=2*mm))
    elements.append(Paragraph(f"Analysis Date: {datetime.now().strftime('%d %B %Y, %H:%M')}", styles["CoverSub"]))
    elements.append(Paragraph(f"IPOs Analyzed: {len(analyses)}", styles["CoverSub"]))
    elements.append(Paragraph("Powered by AI • KLSE Screener Data", styles["CoverSub"]))
    elements.append(Spacer(1, 3*cm))
    
    # Quick summary box
    summary_data = [["#", "IPO Name", "Board", "Verdict"]]
    for i, a in enumerate(analyses, 1):
        verdict = a.get("final_verdict", "N/A")
        name = a.get("ipo_name", "Unknown")
        if len(name) > 35:
            name = name[:35] + "..."
        board = "ACE/Main"
        if ipo_data_list and i-1 < len(ipo_data_list):
            board = ipo_data_list[i-1].get("board", "N/A")
        summary_data.append([str(i), name, board, verdict[:50]])
    
    summary_table = Table(summary_data, colWidths=[1*cm, 7*cm, 2.5*cm, 5.5*cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#BDC3C7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(summary_table)
    
    elements.append(PageBreak())
    
    # ── Individual IPO Pages ──
    for i, analysis in enumerate(analyses, 1):
        ipo_name = analysis.get("ipo_name", f"IPO #{i}")
        
        # Header
        elements.append(Paragraph(f"📋 {ipo_name}", styles["SectionHeader"]))
        elements.append(Spacer(1, 3*mm))
        
        # Verdict gauge + Proceeds chart side by side
        try:
            gauge_img = _generate_verdict_gauge(analysis)
            gauge_path = os.path.join(output_dir, f"gauge_{i}.png")
            with open(gauge_path, "wb") as f:
                f.write(gauge_img)
            
            proceeds_img = _generate_proceeds_chart(analysis)
            proceeds_path = os.path.join(output_dir, f"proceeds_{i}.png")
            with open(proceeds_path, "wb") as f:
                f.write(proceeds_img)
            
            chart_table = Table(
                [[Image(gauge_path, width=5*cm, height=3.5*cm),
                  Image(proceeds_path, width=7*cm, height=4.5*cm)]],
                colWidths=[5.5*cm, 7.5*cm],
            )
            chart_table.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            elements.append(chart_table)
            elements.append(Spacer(1, 4*mm))
        except Exception:
            pass  # Skip charts if they fail
        
        # Verdict text
        verdict = analysis.get("final_verdict", "N/A")
        verdict_color = VERDICT_AVOID
        if "BUY" in verdict.upper():
            verdict_color = VERDICT_BUY
        elif "NEUTRAL" in verdict.upper():
            verdict_color = VERDICT_NEUTRAL
        
        elements.append(Paragraph(
            f"<b>🎯 Verdict: {verdict}</b>",
            ParagraphStyle("vStyle", parent=styles["Verdict"], textColor=verdict_color),
        ))
        elements.append(Spacer(1, 3*mm))
        
        # Valuation table
        v = analysis.get("valuation", {})
        val_data = [
            ["Metric", "Value"],
            ["Offer Price", str(v.get("offer_price", "N/A"))],
            ["Forward P/E", str(v.get("forward_pe", "N/A"))],
            ["Sector Avg P/E", str(v.get("sector_avg_pe", "N/A"))],
            ["P/E Verdict", str(v.get("pe_verdict", "N/A"))],
        ]
        val_table = Table(val_data, colWidths=[4*cm, 12*cm])
        val_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#BDC3C7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(val_table)
        elements.append(Spacer(1, 4*mm))
        
        # Profitability table
        pr = analysis.get("profitability", {})
        prof_data = [
            ["Metric", "Value"],
            ["Revenue CAGR (3Y)", str(pr.get("revenue_cagr_3y", "N/A"))],
            ["PATAMI CAGR (3Y)", str(pr.get("patami_cagr_3y", "N/A"))],
            ["Post-IPO Gearing", str(pr.get("post_ipo_gearing", "N/A"))],
            ["Profitability Verdict", str(pr.get("profitability_verdict", "N/A"))],
        ]
        prof_table = Table(prof_data, colWidths=[4*cm, 12*cm])
        prof_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#BDC3C7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(prof_table)
        elements.append(Spacer(1, 4*mm))
        
        # Risk chart
        try:
            risk_img = _generate_risk_chart(analysis)
            risk_path = os.path.join(output_dir, f"risk_{i}.png")
            with open(risk_path, "wb") as f:
                f.write(risk_img)
            elements.append(Image(risk_path, width=12*cm, height=6*cm))
        except Exception:
            pass
        
        # Cash flow + Shariah
        cf = analysis.get("cash_flow", {})
        elements.append(Spacer(1, 3*mm))
        cf_data = [
            ["Metric", "Value"],
            ["CFO/Net Profit", str(cf.get("cfo_to_net_profit_ratio", "N/A"))],
            ["Cash Flow Verdict", str(cf.get("cash_flow_verdict", "N/A"))],
            ["Shariah Compliant", str(analysis.get("shariah_compliant", "N/A"))],
        ]
        cf_table = Table(cf_data, colWidths=[4*cm, 12*cm])
        cf_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#BDC3C7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(cf_table)
        
        # Page break between IPOs
        if i < len(analyses):
            elements.append(PageBreak())
    
    # ── Comparison Page ──
    if len(analyses) > 1:
        elements.append(PageBreak())
        elements.append(Paragraph("📊 IPO Comparison", styles["SectionHeader"]))
        elements.append(Spacer(1, 4*mm))
        
        try:
            comp_img = _generate_comparison_chart(analyses)
            comp_path = os.path.join(output_dir, "comparison.png")
            with open(comp_path, "wb") as f:
                f.write(comp_img)
            elements.append(Image(comp_path, width=14*cm, height=8*cm))
            elements.append(Spacer(1, 4*mm))
        except Exception:
            pass
        
        # Comparison table
        comp_data = [["IPO", "P/E", "Shariah", "Verdict"]]
        for a in analyses:
            name = a.get("ipo_name", "N/A")
            if len(name) > 25:
                name = name[:25] + "..."
            v = a.get("valuation", {})
            pe = str(v.get("forward_pe", "N/A"))
            shariah = str(a.get("shariah_compliant", "N/A"))
            verdict = str(a.get("final_verdict", "N/A"))
            if len(verdict) > 40:
                verdict = verdict[:40] + "..."
            comp_data.append([name, pe, shariah, verdict])
        
        comp_table = Table(comp_data, colWidths=[5*cm, 2.5*cm, 3.5*cm, 5*cm])
        comp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#BDC3C7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_BG]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(comp_table)
    
    # Footer
    elements.append(Spacer(1, 1*cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#BDC3C7")))
    elements.append(Paragraph(
        f"Generated by Bursa IPO Screener Bot • {datetime.now().strftime('%d %B %Y')} • AI-powered analysis, not financial advice",
        styles["Footer"],
    ))
    
    doc.build(elements)
    return pdf_path


def generate_and_send_pdf(analyses: list, ipo_data_list: list = None, chat_id: str = None, bot_token: str = None) -> str:
    """
    Generate PDF and send via Telegram.
    
    Returns:
        Path to the PDF file.
    """
    pdf_path = generate_ipo_report(analyses, ipo_data_list)
    
    if chat_id and bot_token:
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        
        with open(pdf_path, "rb") as f:
            files = {"document": (os.path.basename(pdf_path), f, "application/pdf")}
            data = {"chat_id": chat_id, "caption": "📋 Bursa Malaysia IPO Report — AI Analysis Summary"}
            resp = requests.post(url, files=files, data=data, timeout=60)
            
            if resp.status_code != 200:
                raise RuntimeError(f"Telegram send failed: {resp.text[:200]}")
    
    return pdf_path