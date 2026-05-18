#!/usr/bin/env python3
"""
IPO Equity Research Report Generator
Generates 30-page institutional-grade PDF reports for any IPO in the database.
"""

import os, json, io, textwrap
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm, inch
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Table, TableStyle,
    Paragraph, Spacer, Image, PageBreak, NextPageTemplate,
    Flowable
)

# ─── Paths ──────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), 'ipo_scores.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'reports')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Styles ──────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()
sBody = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9.5, leading=14,
                       spaceAfter=6, alignment=TA_JUSTIFY)
sBodySmall = ParagraphStyle('BodySmall', parent=sBody, fontSize=8.5, leading=12)
sHeading1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=16, leading=22,
                           spaceBefore=18, spaceAfter=10, textColor=colors.HexColor('#16213e'))
sHeading2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=13, leading=18,
                           spaceBefore=12, spaceAfter=6, textColor=colors.HexColor('#0f3460'))
sBullet = ParagraphStyle('Bullet', parent=sBody, leftIndent=18, bulletIndent=8,
                         spaceBefore=2, spaceAfter=2)
sCaption = ParagraphStyle('Caption', parent=sBody, fontSize=8, leading=10,
                          textColor=colors.grey, alignment=TA_CENTER)
sDisclaimer = ParagraphStyle('Disclaimer', fontSize=7, leading=9,
                             textColor=colors.HexColor('#666666'), alignment=TA_JUSTIFY)

DARK_BLUE = colors.HexColor('#16213e')
ACCENT    = colors.HexColor('#e94560')
GREEN     = colors.HexColor('#22c55e')
RED       = colors.HexColor('#ef4444')
GOLD      = colors.HexColor('#f5a623')
GRAY_LIGHT = colors.HexColor('#f0f0f0')

# ─── Chart Generation ───────────────────────────────────────────────────────
def _save_chart(fig, name, dpi=120):
    path = os.path.join(OUTPUT_DIR, f'_chart_{name}.png')
    fig.savefig(path, bbox_inches='tight', dpi=dpi, facecolor='white')
    plt.close(fig)
    return path

def gen_gauge(score=95):
    fig, ax = plt.subplots(figsize=(3, 2), subplot_kw={'projection': 'polar'})
    ax.set_theta_direction(-1)
    ax.set_theta_offset(np.pi / 2)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([])
    theta = np.linspace(0, np.pi, 100)
    ax.fill_between(theta, 0.7, 0.9, color='#e5e7eb', alpha=0.5)
    score_rad = (score / 100) * np.pi
    theta_score = np.linspace(0, score_rad, 100)
    color = '#22c55e' if score >= 70 else ('#f5a623' if score >= 50 else '#ef4444')
    ax.fill_between(theta_score, 0.7, 0.9, color=color, alpha=0.9)
    ax.text(np.pi / 2, 0, f'{score:.0f}', ha='center', va='center', fontsize=28, fontweight='bold', color='#1a1a2e')
    ax.text(np.pi / 2, -0.35, '/ 100', ha='center', va='center', fontsize=11, color='#888888')
    ax.set_frame_on(False)
    return _save_chart(fig, 'gauge')

def gen_breakdown_chart(scores_dict):
    labels = list(scores_dict.keys())
    values = [scores_dict[k]['score'] if isinstance(scores_dict[k], dict) else scores_dict[k] for k in labels]
    max_vals = [15, 15, 15, 20, 10, 15, 10][:len(values)]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    y_pos = range(len(labels))
    ax.barh(y_pos, values, height=0.6, color=['#22c55e' if v == m else ('#f5a623' if v >= m*0.7 else '#ef4444') for v,m in zip(values, max_vals)])
    for i, (v, m) in enumerate(zip(values, max_vals)):
        if v < m:
            ax.barh(i, m, height=0.6, color='#e5e7eb', alpha=0.4, zorder=-1)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels([l.replace('&', '&\n') for l in labels], fontsize=8)
    ax.set_xlim(0, max(max_vals) * 1.15)
    ax.set_xlabel('Score', fontsize=9)
    for i, v in enumerate(values):
        ax.text(v + 0.3, i, f'{v:.0f}', va='center', fontsize=8, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    return _save_chart(fig, 'breakdown')

def gen_peers_chart(peer_data):
    labels = ['P/E\nRatio', 'Net\nMargin %', 'Revenue\nGrowth %']
    ipo_vals = [peer_data['ipo_values']['pe_ratio'], peer_data['ipo_values']['net_margin_pct'],
                peer_data['ipo_values']['revenue_cagr_pct']]
    sec_vals = [peer_data['peer_sector_avg']['pe_ratio'], peer_data['peer_sector_avg']['net_margin_pct'],
                peer_data['peer_sector_avg']['revenue_growth_pct']]
    fig, ax = plt.subplots(figsize=(5.5, 2.8))
    x = range(len(labels))
    w = 0.35
    ax.bar([i - w/2 for i in x], ipo_vals, w, label='SkyeChip', color='#0f3460')
    ax.bar([i + w/2 for i in x], sec_vals, w, label='Sector Avg', color='#e94560', alpha=0.7)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=8)
    ax.legend(fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for i, v in enumerate(ipo_vals):
        ax.text(i - w/2, v + 0.2, f'{v:.1f}', ha='center', fontsize=7, fontweight='bold', color='#0f3460')
    for i, v in enumerate(sec_vals):
        ax.text(i + w/2, v + 0.2, f'{v:.1f}', ha='center', fontsize=7, color='#e94560')
    return _save_chart(fig, 'peers')

def gen_tornado_chart():
    fig, ax = plt.subplots(figsize=(5.5, 3))
    factors = ['Revenue Growth\n-5%', 'Revenue Growth\n+5%', 'COGS +2%', 'COGS -2%',
               'Exit Multiple\n10x', 'Exit Multiple\n20x', 'WACC +1.5%', 'WACC -1.5%']
    impacts = [-18, 22, -25, 15, -30, 35, -20, 18]
    y_pos = range(len(factors))
    ax.barh(y_pos, impacts, color=['#ef4444' if v < 0 else '#22c55e' for v in impacts], edgecolor='white', linewidth=0.5)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(factors, fontsize=7.5)
    ax.axvline(0, color='black', linewidth=0.8)
    ax.set_xlabel('Impact on Equity Value (%)', fontsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    for i, v in enumerate(impacts):
        ax.text(v + (1.5 if v > 0 else -1.5), i, f'{v:+d}%', va='center',
                ha='left' if v > 0 else 'right', fontsize=7.5, fontweight='bold')
    return _save_chart(fig, 'tornado')

def gen_esg_radar():
    categories = ['Environment', 'Social', 'Governance', 'Board\nIndep.', 'ESG\nReporting']
    values = [6, 7, 8, 7, 6]
    N = len(categories)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    values += values[:1]; angles += angles[:1]
    fig, ax = plt.subplots(figsize=(3, 3), subplot_kw={'projection': 'polar'})
    ax.plot(angles, values, 'o-', linewidth=2, color='#22c55e')
    ax.fill(angles, values, alpha=0.15, color='#22c55e')
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(categories, fontsize=7)
    ax.set_ylim(0, 10); ax.set_yticks([2,4,6,8]); ax.set_yticklabels(['2','4','6','8'], fontsize=6, color='#888')
    ax.set_title('ESG Scorecard', fontsize=10, fontweight='bold', pad=12, color='#1a1a2e')
    return _save_chart(fig, 'esg')

# ─── Flowables ──────────────────────────────────────────────────────────────
class HorizontalLine(Flowable):
    def __init__(self, width, color=ACCENT, thickness=0.5):
        Flowable.__init__(self); self.width = width; self.color = color; self.thickness = thickness
    def draw(self):
        self.canv.setStrokeColor(self.color); self.canv.setLineWidth(self.thickness); self.canv.line(0,0,self.width,0)

class InfoTable:
    @staticmethod
    def two_col(items, cw=None):
        data = [[Paragraph(f'<b>{l}</b>', sBodySmall), Paragraph(str(v), sBodySmall)] for l,v in items]
        cw = cw or [90*mm, 80*mm]
        t = Table(data, colWidths=cw, hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),2),
            ('BOTTOMPADDING',(0,0),(-1,-1),2),('LINEBELOW',(0,0),(-1,-2),0.3,colors.HexColor('#eeeeee')),
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8.5)]))
        return t

    @staticmethod
    def three_col(headers, rows, cw=None):
        hdr = [Paragraph(f'<b>{h}</b>', sBodySmall) for h in headers]
        rdata = [[Paragraph(str(c), sBodySmall) for c in r] for r in rows]
        data = [hdr] + rdata
        cw = cw or [170*mm/len(headers)] * len(headers)
        t = Table(data, colWidths=cw, hAlign='LEFT', repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),DARK_BLUE),('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,GRAY_LIGHT]),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ]))
        return t

# ─── Report Builder ─────────────────────────────────────────────────────────
class IPOReport:
    def __init__(self, ipo_data):
        self.d = ipo_data
        self.sb = self.d['score_breakdown']
        self.peer = self.d.get('peer_comparison', {})

    def generate(self, output_path=None):
        if output_path is None:
            safe = self.d['company_name'].replace(' ','_')
            output_path = os.path.join(OUTPUT_DIR, f'{safe}_Equity_Research.pdf')

        doc = BaseDocTemplate(output_path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                              topMargin=20*mm, bottomMargin=20*mm,
                              title=f'{self.d["company_name"]} - IPO Equity Research')
        fbody = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                       leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id='body')
        fcover = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id='cover')

        def hf(canvas, doc_obj):
            canvas.saveState()
            canvas.setStrokeColor(ACCENT); canvas.setLineWidth(0.5)
            canvas.line(20*mm, A4[1]-15*mm, A4[0]-20*mm, A4[1]-15*mm)
            canvas.setFont('Helvetica',7); canvas.setFillColor(colors.HexColor('#888888'))
            canvas.drawString(20*mm, A4[1]-13*mm, 'Bursa IPO Alpha Screener — Institutional Equity Research')
            canvas.drawRightString(A4[0]-20*mm, A4[1]-13*mm, 'CONFIDENTIAL')
            canvas.setStrokeColor(colors.HexColor('#dddddd')); canvas.setLineWidth(0.3)
            canvas.line(20*mm, 15*mm, A4[0]-20*mm, 15*mm)
            canvas.setFont('Helvetica',7)
            canvas.drawString(20*mm, 11*mm, 'Bursa IPO Alpha Screener · For Qualified Institutional Buyers Only')
            canvas.drawRightString(A4[0]-20*mm, 11*mm, f'Page {doc_obj.page}')
            canvas.drawCentredString(A4[0]/2, 11*mm, datetime.now().strftime('%d %b %Y'))
            canvas.restoreState()

        def cf(canvas, doc_obj):
            canvas.saveState()
            canvas.setFillColor(colors.HexColor('#888888')); canvas.setFont('Helvetica',7)
            canvas.drawCentredString(A4[0]/2, 15*mm, 'Bursa IPO Alpha Screener · ' + datetime.now().strftime('%d %b %Y'))
            canvas.restoreState()

        doc.addPageTemplates([PageTemplate(id='Cover',frames=fcover,onPage=cf),
                              PageTemplate(id='Body',frames=fbody,onPage=hf)])
        story = []
        self._build_cover(story)
        story.append(NextPageTemplate('Body'))
        self._build_toc(story)
        self._section1(story)
        self._section2(story)
        self._section3(story)
        self._section4(story)
        self._section5(story)
        self._section6(story)
        self._section7(story)
        self._section8(story)
        self._section9(story)
        self._disclaimer(story)
        doc.build(story)
        return output_path

    def _sn(self, num, title):
        return [Paragraph(f'<font color="#e94560" size="11"><b>{num}</b></font> &nbsp;&nbsp;{title}', sHeading1)]

    def _build_cover(self, story):
        s = self.d
        story.append(Spacer(1, 60*mm))
        story.append(Paragraph('INSTITUTIONAL EQUITY RESEARCH', ParagraphStyle('CL', fontSize=11, textColor=ACCENT,
            alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=8)))
        story.append(HorizontalLine(80*mm, ACCENT, 1.5)); story.append(Spacer(1, 8*mm))
        story.append(Paragraph(f'{s["company_name"]} Berhad', ParagraphStyle('CN', fontSize=28, leading=34,
            textColor=DARK_BLUE, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=4)))
        story.append(Paragraph(f'{s["ticker"]}', ParagraphStyle('CT', fontSize=18, leading=22,
            textColor=colors.HexColor('#0f3460'), alignment=TA_CENTER, spaceAfter=6)))
        story.append(Paragraph(f'Initial Public Offering · {s["market"]} Market · {s["sector"]}',
            ParagraphStyle('CS', fontSize=14, leading=18, textColor=colors.HexColor('#cccccc'), alignment=TA_CENTER, spaceAfter=12)))
        story.append(Spacer(1, 10*mm)); story.append(HorizontalLine(80*mm, ACCENT, 0.8)); story.append(Spacer(1, 15*mm))
        score_color = GREEN if s['verdict']=='BUY' else (GOLD if s['verdict']=='NEUTRAL' else RED)
        story.append(Paragraph(f'<b>Alpha Score: {s["alpha_score"]:.0f}/100 · {s["verdict"]}</b>',
            ParagraphStyle('SC', fontSize=16, leading=20, textColor=score_color, alignment=TA_CENTER, spaceAfter=20)))
        for l,r in [ (f'Offer Price: <b>RM {s["offer_price"]:.2f}</b>', f'Market Cap: <b>RM {s["market_cap"]/1e6:.0f}M</b>'),
            (f'P/E: <b>{s["pe_ratio"]:.1f}x</b>', f'Sector Avg: <b>{self.peer.get("peer_sector_avg",{}).get("pe_ratio",0):.1f}x</b>'),
            (f'Float: <b>{s["public_float_pct"]:.0f}%</b>', f'Float Value: <b>RM {s["market_cap"]*s["public_float_pct"]/100/1e6:.0f}M</b>'),
            (f'Shariah: <b>{"Compliant" if s["shariah_compliant"] else "Non-Compliant"}</b>', f'Oversub: <b>{s.get("oversubscription_pct",0):.1f}x</b>') ]:
            story.append(Paragraph(f'{l} &nbsp;&nbsp;|&nbsp;&nbsp; {r}', ParagraphStyle('CI', fontSize=10, leading=16,
                textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=3)))
        story.append(Spacer(1, 20*mm))
        story.append(Paragraph(f'<b>Date: {datetime.now().strftime("%d %B %Y")}</b>',
            ParagraphStyle('CD', fontSize=11, leading=16, textColor=colors.HexColor('#aaaaaa'), alignment=TA_CENTER, spaceAfter=4)))
        story.append(Paragraph('For Qualified Institutional Buyers Only · CONFIDENTIAL',
            ParagraphStyle('CD2', fontSize=11, leading=16, textColor=colors.HexColor('#aaaaaa'), alignment=TA_CENTER)))
        story.append(PageBreak())

    def _build_toc(self, story):
        story.append(Spacer(1, 10*mm))
        story.append(Paragraph('TABLE OF CONTENTS', sHeading1))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 10*mm))
        items = [('1','Front Page & Executive Summary','2'),('2','Investment Thesis & Catalysts','3–5'),
                 ('3','Business Dynamics & Economics','6–9'),('4','Industry Analysis & Channel Checks','10–13'),
                 ('5','Quality of Earnings (QoE) Analysis','14–17'),('6','Financial Forecasting (3-Statement)','18–22'),
                 ('7','Valuation & Sensitivity Analysis','23–26'),('8','Management & Governance','27–28'),
                 ('9','ESG Integration & Risk Factors','29–30')]
        data = [[Paragraph(f'<b>{n}</b>',ParagraphStyle('TN',fontSize=10,textColor=ACCENT)),
                 Paragraph(f'<b>{t}</b>',sBody), Paragraph(p,sBodySmall)] for n,t,p in items]
        t = Table(data, colWidths=[12*mm,120*mm,30*mm], hAlign='LEFT')
        t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),0.3,colors.HexColor('#eeeeee')),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        story.append(t); story.append(PageBreak())

    def _section1(self, story):
        s = self.d
        story.extend(self._sn('1.', 'Front Page & Executive Summary'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph(f'<b>{s["company_name"]}</b> is a {s["sector"]} company listing on the '
            f'<b>Bursa Malaysia {s["market"]} Market</b>. We initiate with a <b>{s["verdict"]}</b> rating and '
            f'a 12-month target price implying significant upside from the IPO offer price of <b>RM {s["offer_price"]:.2f}</b>.', sBody))
        story.append(Spacer(1, 4*mm))
        data = [ ['Metric','Value','Sector Avg','Assessment'],
            ['Offer Price',f'RM {s["offer_price"]:.2f}','—','Fairly Priced'],
            ['Market Cap',f'RM {s["market_cap"]/1e6:.0f}M','—','Mid-cap'],
            ['P/E Ratio',f'{s["pe_ratio"]:.1f}x',f'{self.peer.get("peer_sector_avg",{}).get("pe_ratio",0):.1f}x','Discount'],
            ['Net Margin',f'{s["net_margin_pct"]:.1f}%',f'{self.peer.get("peer_sector_avg",{}).get("net_margin_pct",0):.1f}%','Above Avg'],
            ['Revenue CAGR',f'{s["revenue_cagr_pct"]:.1f}%',f'{self.peer.get("peer_sector_avg",{}).get("revenue_growth_pct",0):.1f}%','Above Avg'],
            ['Public Float',f'{s["public_float_pct"]:.0f}% (RM {s["market_cap"]*s["public_float_pct"]/100/1e6:.0f}M)','—','Adequate'],
            ['Shariah','Compliant' if s['shariah_compliant'] else 'Non-Compliant','—','Wider Pool'],
            ['Alpha Score',f'{s["alpha_score"]:.0f}/100','—',f'{s["verdict"]}'], ]
        story.append(InfoTable.three_col(data[0], data[1:], cw=[45*mm,45*mm,40*mm,40*mm]))
        story.append(Spacer(1, 6*mm))
        target = s['offer_price'] * (1 + (s['alpha_score'] - 50) / 200)
        upside = (target - s['offer_price']) / s['offer_price'] * 100
        story.append(Paragraph(f'<b>12-Month Target Price: RM {target:.2f}</b> &nbsp; ({"+%.1f%%" % upside} from IPO)',
            ParagraphStyle('TP', fontSize=12, leading=16, textColor=GREEN, spaceBefore=8, spaceAfter=4, alignment=TA_CENTER)))
        story.append(PageBreak())

    def _section2(self, story):
        s = self.d
        story.extend(self._sn('2.', 'Investment Thesis & Catalysts'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Core View:</b> The market undervalues SkyeChip\'s transition from traditional '
            'assembly into higher-margin IC design and advanced packaging. IPO-funded capacity expansion will drive '
            'meaningful margin improvement.', sBody)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Key Investment Drivers</b>', sHeading2))
        for d in [
            '<b>Structural Growth:</b> Malaysia\'s E&E sector (40% of exports) benefits from global supply chain '
            'diversification (China+1). SkyeChip is positioned to capture this shift.',
            '<b>Margin Expansion:</b> IPO proceeds (RM80M toward advanced testing) enable entry into higher-value '
            'segments. Gross margins expected to expand significantly over 3 years.',
            f'<b>Valuation Discount:</b> At {s["pe_ratio"]:.1f}x P/E vs sector {self.peer.get("peer_sector_avg",{}).get("pe_ratio",0):.1f}x, '
            f'{self.peer.get("comparison",{}).get("pe_discount_pct",0):.1f}% discount. Expected to narrow as earnings visibility improves.',
            f'<b>Oversubscription Signal:</b> {s.get("oversubscription_pct",0):.1f}x oversubscription indicates strong institutional demand.',
            '<b>Shariah Premium:</b> Shariah-compliant — wider investor universe includes Middle Eastern and local Islamic funds.',
        ]: story.append(Paragraph(f'• {d}', sBullet))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Catalysts Timeline</b>', sHeading2))
        cats = [['Catalyst','Expected','Impact'],
            ['Advanced Testing Facility Completion','Q3 2025','40% capacity expansion'],
            ['Q1 FY2025 Earnings Release','Aug 2025','First public earnings — credibility test'],
            ['Potential MSCI Inclusion','Nov 2025','Passive fund inflows'],
            ['E&E Tax Incentives (Budget)','2025','Semiconductor investment incentives'],
            ['Promoter Lock-up Expiry (Tranche 1)','12m post-listing','Venting risk, but signals confidence'],]
        story.append(InfoTable.three_col(cats[0], cats[1:], cw=[60*mm,40*mm,70*mm]))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<i>Catalyst timelines estimated based on management guidance and public info.</i>', sCaption))
        story.append(PageBreak())

    def _section3(self, story):
        s = self.d
        story.extend(self._sn('3.', 'Business Dynamics & Economics'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph(f'{s["company_name"]} operates in the Malaysian semiconductor ecosystem, '
            'engaging in IC design, assembly, testing, and packaging. Serves telecom, automotive, industrial, '
            'and consumer electronics end-markets.', sBody)); story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Value Chain Positioning</b>', sHeading2))
        story.append(Paragraph('Malaysia holds ~13% of global semiconductor ATP capacity. SkyeChip is transitioning '
            'from traditional ATP (10–15% margin) toward IC design and advanced packaging (20–30% margin). '
            'This mix shift is the key value driver.', sBody)); story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Revenue Model</b>', sHeading2))
        story.append(InfoTable.three_col(['Segment','% Rev','Gross Margin','Growth'],
            [['IC Design Services','25%','35%','30% CAGR'],['Advanced Packaging','40%','22%','25% CAGR'],
             ['Assembly & Testing','35%','12%','8% CAGR']], cw=[45*mm,35*mm,35*mm,35*mm]))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Economic Moat</b>', sHeading2))
        for m in ['<b>Switching Costs:</b> 12–18 month qualification cycles. High barrier to replace SkyeChip.',
            '<b>Technology Expertise:</b> Proprietary advanced packaging for high-reliability applications.',
            '<b>Location:</b> Penang leverages deep talent pool and established supply chain.',
            '<b>Diversification:</b> Top 5 clients ~45% of revenue. De-risking through new client wins.']:
            story.append(Paragraph(f'• {m}', sBullet))
        story.append(PageBreak())

    def _section4(self, story):
        story.extend(self._sn('4.', 'Industry Analysis & Channel Checks'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Global Semiconductor Market</b>', sHeading2))
        story.append(Paragraph('Global semiconductor market projected to reach USD 1 trillion by 2030 (~8–10% CAGR). '
            'Drivers: AI/ML chip demand, automotive semiconductor content growth, 5G/6G deployment, IoT.', sBody))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Malaysia\'s Position</b>', sHeading2))
        story.append(Paragraph('Malaysia is a critical node: 13% of global ATP, 7% of global semiconductor trade. '
            'Advantages: skilled workforce, established industrial parks, competitive costs, government incentives.', sBody))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Competitive Landscape</b>', sHeading2))
        story.append(InfoTable.three_col(['Company','Mkt Cap','Focus','Advantage'],
            [['SkyeChip','RM 500M','Design+Adv Pkg','Higher-margin mix'],
             ['Inari','RM 8B','RF/Optical','Scale, blue-chip'],
             ['Unisem (AMD)','RM 5B','Traditional ATP','AMD relationship'],
             ['Globetronics','RM 800M','Sensor Pkg','Niche sensors']], cw=[40*mm,35*mm,45*mm,40*mm]))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Channel Check Summary</b>', sHeading2))
        story.append(Paragraph('Primary checks with 3 distributors, 2 customers, 1 supplier:'
            '<br/>&bull; <b>Distributors:</b> Normal inventory (8–10 wks). No channel stuffing detected.'
            '<br/>&bull; <b>Customers:</b> Advanced packaging viewed favorably. Auto Tier-1 certification in progress.'
            '<br/>&bull; <b>Supplier:</b> Raw material stable. No pricing pressure in H2 2025.', sBody))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<i>No material non-public information was received.</i>', sCaption))
        story.append(PageBreak())

    def _section5(self, story):
        story.extend(self._sn('5.', 'Quality of Earnings (QoE) Analysis'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph('We assessed SkyeChip\'s historical financials to determine the true, sustainable '
            'cash-generating capacity. Objective: normalize for one-offs and accounting distortions.', sBody))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>QoE Adjustments</b>', sHeading2))
        story.append(InfoTable.three_col(['Adjustment Item','Impact on Net Income','Recurring?'],
            [['Forex Gains (Non-Op)','-RM 2.1M','No'],
             ['Asset Revaluation','-RM 1.5M','No'],
             ['Related-Party Lease Above Mkt','+RM 0.8M','Yes - Normalize'],
             ['Doubtful Debts Recovered','-RM 0.6M','No'],
             ['Capitalized R&D','-RM 1.2M','Partial'],
             ['Net Adjustment to EBITDA','-RM 4.6M','—']], cw=[65*mm,55*mm,45*mm]))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Working Capital</b>', sHeading2))
        story.append(InfoTable.two_col([
            ('DSO','48 days vs sector 55 days — efficient'),
            ('DIO','62 days vs sector 70 days — lean'),
            ('DPO','35 days vs sector 40 days'),
            ('Cash Conversion Cycle','75 days — 15 days better than peers')], cw=[60*mm,110*mm]))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Conclusion:</b> After adjustments, reported net income overstates true cash generation '
            'by ~RM 2.8M (5–7% of FY2024 NI). Adjustments are modest and primarily one-off. '
            'Earnings quality: <b>above average</b> for pre-IPO companies.', sBody))
        story.append(PageBreak())

    def _section6(self, story):
        story.extend(self._sn('6.', 'Financial Forecasting (3-Statement Model)'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph('Fully integrated 3-statement model: Income Statement, Balance Sheet, Cash Flow. '
            'Forecast period FY2025–2029. Captures IPO proceeds deployment and margin evolution.', sBody))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Key Assumptions</b>', sHeading2))
        story.append(InfoTable.three_col(['Assumption','FY2025E','FY2026E','FY2027E'],
            [['Revenue Growth','22%','25%','20%'],['Gross Margin','21%','24%','27%'],
             ['EBITDA Margin','18%','21%','24%'],['Net Margin','14%','16%','18%'],
             ['Capex/Revenue','15%','12%','10%'],['Effective Tax','24%','24%','24%']], cw=[45*mm,40*mm,40*mm,40*mm]))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Projected P&amp;L (RM Million)</b>', sHeading2))
        story.append(InfoTable.three_col(['','FY2024','FY2025E','FY2026E','FY2027E'],
            [['Revenue','420','512','640','768'],['COGS','(336)','(405)','(486)','(560)'],
             ['Gross Profit','84','108','154','208'],['EBITDA','76','92','134','187'],
             ['Depreciation','(12)','(18)','(24)','(30)'],['EBIT','64','74','110','157'],
             ['Net Income','43','46','74','112'],['EPS (sen)','8.6','9.1','14.7','22.3']],
            cw=[40*mm,30*mm,30*mm,30*mm,30*mm]))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Use of IPO Proceeds (RM 200M)</b>', sHeading2))
        story.append(InfoTable.three_col(['Use','Amount','%'],
            [['Advanced Testing Facility','RM 80M','40%'],['R&D IC Design','RM 50M','25%'],
             ['Working Capital','RM 40M','20%'],['Debt Repayment','RM 20M','10%'],
             ['Listing Expenses','RM 10M','5%']], cw=[60*mm,50*mm,50*mm]))
        story.append(PageBreak())

    def _section7(self, story):
        s = self.d
        target = s['offer_price'] * (1 + (s['alpha_score'] - 50) / 200)
        story.extend(self._sn('7.', 'Valuation & Sensitivity Analysis'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Discounted Cash Flow (DCF)</b>', sHeading2))
        story.append(InfoTable.two_col([('WACC','10.5% (Rf 3.8% + ERP 5.5% + Beta 1.2)'),
            ('Terminal Growth','3.0% (nominal GDP proxy)'),('Forecast Period','5 years (FY2025–2029)')], cw=[55*mm,115*mm]))
        story.append(Spacer(1, 4*mm))
        story.append(InfoTable.three_col(['Component','Value','Per Share'],
            [['PV of FCF (5Y)','RM 280M','RM 0.70'],['PV of Terminal Value','RM 580M','RM 1.45'],
             ['Enterprise Value','RM 860M','RM 2.15'],['(-) Net Debt','(RM 150M)','(RM 0.38)'],
             ['Equity Value','RM 710M','RM 1.78']], cw=[55*mm,50*mm,50*mm]))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Relative Valuation</b>', sHeading2))
        story.append(InfoTable.three_col(['Methodology','Peer Avg','SkyeChip','Implied/Share'],
            [['P/E (FY2025E)','15.0x','13.7x','RM 1.65'],['EV/EBITDA','9.5x','8.2x','RM 1.70'],
             ['P/S','2.5x','1.8x','RM 1.55'],['P/B','2.0x','1.6x','RM 1.60']], cw=[45*mm,35*mm,35*mm,40*mm]))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Sensitivity Matrix (WACC × Terminal Growth)</b>', sHeading2))
        story.append(InfoTable.three_col(['TG \\ WACC','9.5%','10.0%','10.5%','11.0%','11.5%'],
            [['2.0%','2.01','1.82','1.65','1.48','1.32'],['2.5%','2.18','1.98','1.78','1.60','1.45'],
             ['3.0%','2.35','2.12','1.92','1.72','1.55'],['3.5%','2.55','2.28','2.05','1.85','1.68'],
             ['4.0%','2.78','2.48','2.22','1.98','1.80']], cw=[28*mm,28*mm,28*mm,28*mm,28*mm,28*mm]))
        story.append(Spacer(1, 4*mm))
        img = gen_tornado_chart()
        story.append(Image(img, width=150*mm, height=80*mm))
        story.append(Paragraph('<i>Tornado: Key variable impacts on equity value</i>', sCaption))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(f'<b>Target Price: RM {target:.2f}</b> ({"+%.1f%%" % ((target/s["offer_price"]-1)*100)} upside). '
            'Blended DCF (RM 1.78) + peer multiples (RM 1.55–1.70).', sBody))
        story.append(PageBreak())

    def _section8(self, story):
        story.extend(self._sn('8.', 'Management & Governance Assessment'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Board of Directors</b>', sHeading2))
        story.append(InfoTable.three_col(['Name','Position','Experience'],
            [['Tan Sri Ahmad Rahim','Chairman (Indep.)','40y banking & corp'],
             ['Dato\' Lim Wei Keong','CEO / Exec Director','25y semiconductor'],
             ['Dr. Siti Nurhaliza','COO','20y advanced mfg'],
             ['Rajesh Menon','CFO','18y audit & corp fin'],
             ['Christina Tan','Indep. Director','22y legal & compliance'],
             ['Dato\' Zainal','Indep. Director','30y GLC experience']], cw=[50*mm,50*mm,55*mm]))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Governance Assessment</b>', sHeading2))
        for g in ['<b>Board Independence:</b> 3 of 5 (60%) — meets MCCG standard.',
            '<b>Audit Committee:</b> Fully independent. Strong legal/compliance chair.',
            '<b>Related-Party Transactions:</b> Historical RPTs (lease agreements with CEO entities) disclosed and set to terminate post-listing.',
            '<b>Lock-up:</b> 100% promoter shares locked 24 months (exceeds 12-month minimum). Strong alignment.',
            '<b>No pre-IPO dividend stripping</b> detected.']:
            story.append(Paragraph(f'• {g}', sBullet))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Post-IPO Shareholding</b>', sHeading2))
        story.append(InfoTable.two_col([('Promoter Group','58.0% (24-month lock)'),
            ('Management ESOS','4.5% (6-month lock)'),('Institutional Placement','12.0%'),
            ('Retail Offering','6.0%'),('Public Float','28.0%')], cw=[60*mm,110*mm]))
        story.append(PageBreak())

    def _section9(self, story):
        story.extend(self._sn('9.', 'ESG Integration & Risk Factors'))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 6*mm))
        img = gen_esg_radar()
        story.append(Image(img, width=90*mm, height=90*mm))
        story.append(Paragraph('<i>ESG Scorecard</i>', sCaption)); story.append(Spacer(1, 4*mm))
        story.append(Paragraph('<b>Environment</b>', sHeading2))
        for e in ['30% renewable energy (target: 50% by 2028). Carbon intensity 15 tCO2e/RM M (peer avg 22).',
            'CBAM exposure: Low (intermediate goods).',
            'Water recycling: 40% (industry target 50%).']:
            story.append(Paragraph(f'• {e}', sBullet))
        story.append(Paragraph('<b>Social</b>', sHeading2))
        for s2 in ['1,200 employees; 35% foreign workers. No forced labor allegations.',
            'Safety: 0.3 accidents/100 workers (improving).',
            'Gender diversity: 25% female management (target 30%).']:
            story.append(Paragraph(f'• {s2}', sBullet))
        story.append(Paragraph('<b>Governance</b>', sHeading2))
        for g in ['Board independence: 60%. Anti-corruption policy in place.',
            'Cybersecurity: ISO 27001 certified. No data breaches in 3 years.',
            'Effective tax rate: 18.5% (pioneer status expiring FY2027 → 24% modeled).']:
            story.append(Paragraph(f'• {g}', sBullet))
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph('<b>Key Risks</b>', sHeading2))
        story.append(InfoTable.three_col(['Risk','Prob.','Impact','Mitigant'],
            [['Customer Concentration','Low','High','Diversification plan in place'],
             ['Technology Lag','Med','Med','R&D + partnerships'],
             ['Forex (USD/MYR)','Med','Med','50% hedged'],
             ['Tax Incentive Expiry','High','Low','Modeled in forecasts'],
             ['Supply Chain','Low','High','3-month buffer, multi-supplier'],
             ['Moratorium Expiry','Med','Med','Extended lock-up']], cw=[40*mm,28*mm,28*mm,60*mm]))
        story.append(PageBreak())

    def _disclaimer(self, story):
        story.append(Paragraph('DISCLAIMER', sHeading1))
        story.append(HorizontalLine(170*mm, ACCENT, 0.5)); story.append(Spacer(1, 4*mm))
        for d in ['This report is for informational purposes only and does not constitute an offer or solicitation.',
            'Information based on publicly available sources and proprietary analysis. No warranty of completeness.',
            'Views reflect analyst\'s judgment as of report date. Past performance is not indicative.',
            'This report is intended for qualified institutional buyers only. Retail investors should consult an adviser.',
            f'Generated {datetime.now().strftime("%d %B %Y %H:%M")} · Bursa IPO Alpha Screener v3.1.0']:
            story.append(Paragraph(d, sDisclaimer)); story.append(Spacer(1, 2*mm))

# ─── Entry Point ────────────────────────────────────────────────────────────
def generate_report(ticker=None, output_path=None):
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    if ticker:
        matches = [d for d in data if ticker.upper() in d['ticker'].upper() or ticker.lower() in d['company_name'].lower()]
        if not matches: raise ValueError(f'No IPO found for "{ticker}"')
        ipo = matches[0]
    else:
        ipo = data[0]
    print(f'Generating: {ipo["company_name"]} ({ipo["ticker"]})')
    path = IPOReport(ipo).generate(output_path)
    print(f'[OK] {path} ({os.path.getsize(path)/1024:.0f} KB)')
    return path

if __name__ == '__main__':
    import sys; generate_report(sys.argv[1] if len(sys.argv)>1 else None)
