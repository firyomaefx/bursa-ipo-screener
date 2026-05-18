## Plan: IPO Equity Research Report Generator

### Goal
Build a monetizable report system — users click "Buy Report" on any IPO to get a 30-page institutional-grade PDF following the exact framework provided.

### Architecture

**`report_generator.py`** — Core PDF engine
- Uses ReportLab (Platypus) for page layout, headers, footers
- Matplotlib for charts: score gauge, breakdown bars, peer comp, tornado sensitivity
- Follows exact 9-section structure (30 pages)
- Takes IPO dict from ipo_scores.json + generates complete PDF

**Dashboard integration** (`dashboard.py`)
- "Buy Report (RM)" button on each IPO card → generates PDF
- For MVP: free download (payment integration later)

**Report sections (30 pages):**
1. Front Page & Executive Summary (p1-2)
2. Investment Thesis & Catalysts (p3-5)
3. Business Dynamics & Economics (p6-9)
4. Industry Analysis & Channel Checks (p10-13)
5. Quality of Earnings (QoE) Analysis (p14-17)
6. Financial Forecasting (3-Statement) (p18-22)
7. Valuation & Sensitivity Analysis (p23-26)
8. Management & Governance Assessment (p27-28)
9. ESG Integration & Risk Factors (p29-30)

### Files created
- `report_generator.py` — PDF generation engine
- `reports/` — output directory for generated PDFs

### First report
- SkyeChip (SKYECHIP) — 30-page PDF demo
