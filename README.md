# Bursa Malaysia IPO Screener 🇲🇾

Automated IPO scoring + dashboard for Malaysian IPOs.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run dashboard.py
# Opens at http://localhost:8501
```

## Features

### 📊 Streamlit Dashboard v2
- **IPO Card List** — Single-page layout with tap-to-expand IPO cards
- **Color-coded scores** — Alpha Score badge & verdict badge per card
- **Tap to expand** — Score gauge, 7-criteria breakdown chart, peer comparison, liquidity assessment
- **➕ Add New IPO** — Manual entry form with on-submit scoring
- **🔄 Per-IPO Refresh** — Re-score individual IPO on demand
- **🔍 Filters** — Filter by verdict, sector, market, or search by name
- **No auto-scanning** — Everything is manual, on-demand

### 📈 Alpha Scoring Engine
- 7 weighted criteria → alpha score (0-100)
- PE discount (15pts), oversubscription (15pts), proceeds quality (15pts)
- Profitability & growth (15pts), Shariah (10pts), float/liquidity (15pts), moratorium (10pts)
- Verdict: BUY (≥70), NEUTRAL (50-69), AVOID (<50)
- Liquidity risk assessment with estimated volatility range
- JSON database persistence (`ipo_scores.json`)

### 🏢 Peer Comparison
- 12 sector benchmarks (Technology, Healthcare, Property, Energy, etc.)
- IPO vs sector avg: P/E, net margin, revenue growth
- Peer-adjusted alpha score with score boost/penalty
- Rich insights with valuation summary

## Project Structure

```
bursa-ipo-bot/
├── dashboard.py          # ⭐ Streamlit dashboard (main entry)
├── scoring_engine.py     # IPO Alpha Scoring Engine
├── peer_comparison.py    # Sector peer comparison
├── ipo_scores.json       # Scored IPO database
├── streamlit_app.py      # Streamlit Cloud entry wrapper
├── requirements.txt
├── .streamlit/
│   └── config.toml       # Streamlit theme config
└── README.md
```

## Deployment

### Run Locally
```bash
streamlit run dashboard.py
```

### Streamlit Cloud
1. Push to GitHub
2. Connect repo at [streamlit.io/cloud](https://streamlit.io/cloud)
3. Set entry point: `streamlit_app.py`
4. Deploy ✓
