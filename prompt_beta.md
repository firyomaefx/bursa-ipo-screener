Build the IPO Alpha Scoring Engine (Phase 1) within this existing bursa-ipo-bot project. This is PMP Phase 4 (Beta).

## Phase 1: Scoring Engine (Beta Core)

### Existing Assets (reuse these)
- `ipo_scraper.py` — Has `get_current_ipos()` function that scrapes Bursa IPO list
- `pdf_processor.py` — Extracts sections from IPO prospectus PDFs (PyMuPDF + pdfplumber)
- `llm_analyzer.py` — Calls OpenRouter API with LLM (Claude/GPT-4o) for structured analysis, returns: PE ratio, revenue/PATAMI CAGR, proceeds breakdown, gearing, CFO/Net Profit ratio, Shariah status, top risks, and verdict

### What to Build

Create a new file `scoring_engine.py` with:

**1. IPO Data Schema (`IPOScore` dataclass)**
- `company_name: str`
- `market: str` (ACE/Main/LEAP)
- `sector: str`
- `offer_price: float`
- `market_cap: float`
- `pe_ratio: float or None`
- `sector_avg_pe: float or None`
- `oversubscription_rate: float or None` (e.g. 1.19 = 1.19x)
- `proceeds_utilization: dict` (CapEx%, debt%, working capital%)
- `net_profit_margin: float or None`
- `revenue_cagr_3yr: float or None`
- `shariah_compliant: bool or None`
- `moratorium_period_years: float or None`
- `promoter_ownership_pct: float or None`
- `total_shares: int`
- `public_float_pct: float`
- `application_status: str` (e.g. "Open", "Closing", "Listed")
- `listing_date: str or None`
- `alpha_score: float or None` (0-100)
- `verdict: str or None` (BUY/NEUTRAL/AVOID)
- `score_breakdown: dict` (per-criteria scores)

**2. 7 Scoring Criteria (each 0-15 points, total 100)**

| Criteria | Weight | Scoring Logic |
|----------|--------|--------------|
| 1. PE Discount | 15 pts | Compare IPO PE vs sector avg PE. Score = 15 if discount >=40%, 10 if >=20%, 5 if >=0%, 0 if premium |
| 2. Oversubscription Demand | 15 pts | Score = 15 if >=20x, 12 if >=10x, 8 if >=5x, 4 if >=2x, 0 if <2x |
| 3. Proceeds Utilization Quality | 15 pts | Based on % for expansion/CapEx vs debt repayment/working capital. >50% expansion = 15pts, 25-50% = 10pts, else 5pts |
| 4. Profitability & Growth | 15 pts | Combine net margin quality + revenue CAGR. Margin >15% AND CAGR >20% = 15pts, one good = 8pts, else 2pts |
| 5. Shariah Compliance | 10 pts | Compliant = 10pts, Non-compliant = 0pts, Unknown/Not-screened = 2pts |
| 6. Float & Liquidity Risk | 15 pts | Based on public float size. Float >RM100M = 15pts, >RM50M = 10pts, >RM20M = 5pts, <RM20M = 0pts |
| 7. Moratorium / Promoter Lock-up | 10 pts | Long moratorium (>1yr) OR high promoter ownership (>50%) = 10pts, one present = 5pts, none = 0pts |

**Bonus: DOM/Liquidity Risk Score** (not in main score, displayed separately)
- Flag: Low float + ACE Market = HIGH liquidity risk warning
- Estimate day 1-5 volatility range based on float size

**3. Scoring Functions**
- `calculate_pe_discount(ipo_pe, sector_avg_pe) -> tuple[float, str]`
- `calculate_oversubscription_score(rate) -> tuple[float, str]`
- `calculate_proceeds_score(proceeds) -> tuple[float, str]`
- `calculate_profitability_score(margin, cagr) -> tuple[float, str]`
- `calculate_shariah_score(compliant) -> tuple[float, str]`
- `calculate_float_score(market_cap, public_float_pct) -> tuple[float, str]`
- `calculate_moratorium_score(years, promoter_pct) -> tuple[float, str]`
- `calculate_alpha_score(ipo_data: dict) -> dict` (returns total_score, verdict, breakdown)

**4. Verdict Logic**
- Score >=70: BUY
- Score 50-69: NEUTRAL 
- Score <50: AVOID

**5. Integration with existing code**
- Import from pdf_processor and llm_analyzer to feed data into scoring engine
- `analyze_and_score(pdf_path: str) -> dict` — full pipeline: extract -> LLM analyze -> score -> return

**6. Database/Storage**
- Create simple JSON file storage `ipo_scores.json` to persist scored IPOs
- Functions: `load_scores()`, `save_score(ipo_score)`, `get_all_scores()`, `get_top_scores(n)`, `search_by_sector(sector)`

### Output
- File: `scoring_engine.py` with all above functions
- Update `ipo_scraper.py` if needed to return more fields
- Test with at least 3 mock IPOs (known recent Malaysian IPOs)
- Print scored results as a demo

### Code Quality
- Type hints on all functions
- Docstrings on all public functions
- No external dependencies beyond what's already installed (pandas, pydantic if available, otherwise just dataclasses)
