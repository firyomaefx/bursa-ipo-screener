Build the IPO Peer Comparison Module (Phase 2) for the bursa-ipo-bot project. This builds on the existing scoring_engine.py (Phase 1).

## Existing Files (Read these first)
- `scoring_engine.py` — Has IPOScore dataclass, 7-scoring functions, JSON storage
- `ipo_scraper.py` — Has get_current_ipos() function
- `requirements.txt` — Know existing dependencies

## What to Build

Create a new file `peer_comparison.py` with the following components:

### 1. Sector Peer Data Source
Create a function `get_sector_peers(sector: str, exclude_company: str = None) -> list[dict]` that:
- Returns hardcoded sector benchmark data for Malaysian IPO sectors (ACE + Main Market)
- Include at minimum these sectors:
  - Technology
  - Industrial / Industrial Products
  - Property / Property Development
  - Healthcare
  - Consumer / Consumer Products
  - Construction
  - Energy / Oil & Gas
  - Plantation
  - Financial Services
  - REIT
  - Telecommunications
  - Transportation & Logistics
- Each sector entry has:
  - `avg_pe_ratio: float`
  - `avg_roe_pct: float`
  - `avg_net_margin_pct: float`
  - `avg_revenue_growth_pct: float`
  - `avg_dividend_yield_pct: float`
  - `top_companies: list[str]` (3-5 well-known Bursa listed companies in that sector)
  - `sub_sectors: list[str]` (sub-categories)

For realistic data, use actual known Bursa sector averages (approximate):

| Sector | Avg PE | Avg ROE | Avg Margin | Rev Growth |
|--------|--------|---------|------------|------------|
| Technology | 22-28x | 12-18% | 12-18% | 15-25% |
| Healthcare | 20-30x | 10-15% | 15-20% | 10-15% |
| Consumer | 15-20x | 10-18% | 8-12% | 5-10% |
| Industrial | 12-18x | 8-14% | 8-12% | 5-10% |
| Property | 8-12x | 5-8% | 15-25% | 3-8% |
| Construction | 10-15x | 6-10% | 5-8% | 5-10% |
| Energy | 10-15x | 8-12% | 5-10% | 10-20% |
| Plantation | 15-20x | 8-12% | 10-15% | 5-10% |
| Financial | 10-12x | 10-12% | 30-40% | 3-5% |
| Healthcare | 20-30x | 10-15% | 15-20% | 10-15% |
| REIT | 15-20x | 6-8% | 50-60% | 3-5% |

### 2. IPO-to-Peer Comparison
Create `compare_ipo_to_sector(ipo: dict) -> dict` that:
- Takes an IPOScore-compatible dict (from scoring_engine)
- Looks up sector peers from get_sector_peers()
- Returns a dict with:
  ```python
  {
    "ipo_company": str,
    "sector": str,
    "market": str,
    "peer_sector_avg": {
      "pe_ratio": float,
      "roe_pct": float,
      "net_margin_pct": float,
      "revenue_growth_pct": float
    },
    "ipo_values": {
      "pe_ratio": float or None,
      "net_margin_pct": float or None,
      "revenue_cagr_pct": float or None
    },
    "comparison": {
      "pe_discount_pct": float,  # negative = premium, positive = discount
      "margin_comparison": str,  # "Above avg", "At avg", "Below avg"
      "growth_comparison": str,
      "overall_score": float  # 0-100, how does IPO compare to peers
    },
    "peer_insights": [
      "IPO priced at 50% discount to sector avg PE of 25.0x",
      "Net margin of 18.5% exceeds sector avg of 15.0%",
      "Revenue CAGR of 35.0% significantly above sector avg of 20.0%"
    ],
    "top_sector_peers": ["Inari Amertron", "Vitrox", "Mi Technovation"],
    "valuation_summary": str  # e.g. "Attractively valued vs peers"
  }
  ```

### 3. Peer Scoring Enhancement
Create `enhance_score_with_peers(ipo_score: dict, peer_comparison: dict) -> dict` that:
- Takes the existing alpha score from scoring_engine
- Adjusts the PE Discount score based on more granular peer comparison
- Boosts/penalizes based on peer relative performance
- Returns updated score with peer_adjusted flag

### 4. Visualization Data
Create `format_peer_comparison_table(ipo: dict, peers: dict) -> str` that:
- Returns a nicely formatted text table for CLI/Telegram display
- Shows IPO vs Sector Avg for each metric
- Uses simple ASCII (not Unicode box chars - avoid encoding issues)

### 5. Integration with Scoring Engine
Create `full_pipeline_with_peers(ipo_dict: dict) -> dict` that:
- Calls calculate_alpha_score() from scoring_engine
- Calls compare_ipo_to_sector()
- Calls enhance_score_with_peers()
- Returns combined result with both alpha score and peer analysis

### 6. Demo / Testing
Add a `demo_peer_comparison()` function that:
- Uses the same 3 mock IPOs from scoring_engine.py demo
- Shows peer comparison for each
- Prints formatted output showing IPO vs sector benchmarks

## Code Quality
- Import from scoring_engine where possible (don't duplicate)
- All functions with type hints
- Docstrings on all public functions
- Handle unknown sectors gracefully (fallback to "General" sector)
- No external dependencies beyond what's already in requirements.txt
