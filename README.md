# Bursa Malaysia IPO Screener 🇲🇾

Automated IPO screening + scoring + dashboard for Malaysian IPOs.

## Quick Start

```bash
# 1. Copy and fill in your credentials
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Telegram bot (polling mode)
python app.py

# 4. OR run Streamlit Dashboard
streamlit run dashboard.py
```

## Architecture

```
┌──────────────┐   ┌──────────────────────┐   ┌─────────────────┐
│ Telegram Bot │   │  Streamlit Dashboard │   │  PDF Report     │
│ (app.py)     │   │  (dashboard.py)      │   │  (pdf_report.py)│
└──────┬───────┘   └──────────┬───────────┘   └────────┬────────┘
       │                      │                        │
       ▼                      ▼                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                    IPO Analysis Pipeline                          │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │ Scoring Engine │  │ Peer Comparison│  │ LLM Analyzer     │   │
│  │ scoring_engine │  │ peer_comparison│  │ llm_analyzer.py  │   │
│  │   .py          │  │   .py          │  │ (Ollama/OpenRtr) │   │
│  └────────────────┘  └────────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
bursa-ipo-bot/
├── app.py              # Telegram bot (Flask + polling)
├── dashboard.py        # ⭐ Streamlit web dashboard (Phase 3)
├── scoring_engine.py   # IPO Alpha Scoring Engine (Phase 1)
├── peer_comparison.py  # Sector peer comparison (Phase 2)
├── pdf_report.py       # PDF report generator with charts
├── pdf_processor.py    # PDF extraction (section-targeted)
├── llm_analyzer.py     # LLM integration (Ollama/OpenRouter)
├── ipo_scraper.py      # Playwright scraper (Bursa/KLSE)
├── ipo_monitor.py      # (legacy) old monitor
├── ipo_scores.json     # Scored IPO database (auto-generated)
├── requirements.txt
├── .env
├── .env.example
├── .streamlit/
│   └── config.toml     # Streamlit theme config
└── README.md
```

## Features

### 📊 Streamlit Dashboard (Phase 3)
- **Overview** — KPI cards, verdict pie chart, top 3 picks, sector averages
- **IPO List** — Filterable table with expandable detail cards and peer comparison
- **Sector Analysis** — Sector score heatmap, box plots, market breakdown
- **New Scan** — Manual IPO entry with real-time alpha scoring

### 📈 Alpha Scoring Engine (Phase 1)
- 7 weighted criteria → alpha score (0-100)
- PE discount (15pts), oversubscription (15pts), proceeds quality (15pts)
- Profitability & growth (15pts), Shariah (10pts), float/liquidity (15pts), moratorium (10pts)
- Verdict: BUY (≥70), NEUTRAL (50-69), AVOID (<50)
- Liquidity risk assessment with estimated volatility range
- JSON database persistence (`ipo_scores.json`)

### 🏢 Peer Comparison (Phase 2)
- 12 sector benchmarks (Technology, Healthcare, Property, Energy, etc.)
- IPO vs sector avg: P/E, net margin, revenue growth
- Peer-adjusted alpha score with score boost/penalty
- Rich insights with valuation summary

### 🤖 AI Analysis (Telegram Bot)
- Ollama (kimi-k2.5) or OpenRouter (Claude/GPT-4o)
- Valuation, proceeds breakdown, profitability, cash flow quality
- Top 3 risks with severity, Shariah screening
- Final verdict: BUY / AVOID / NEUTRAL
- Rich MarkdownV2 cards with box-drawing borders

### 📄 PDF Report
- Professional report with Bursa Malaysia branding
- Proceeds allocation pie chart
- Risk assessment bar chart
- IPO comparison chart (P/E bar with verdict colors)
- Verdict gauge indicator

## Bot Commands

- `/start` — Main menu with Search, Monitor Status, Tracked IPOs
- Auto-monitor — Scans Bursa every 60 minutes for new IPOs

## Configuration (.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Required |
| `TELEGRAM_CHAT_ID` | Your Telegram user ID | Required |
| `LLM_PROVIDER` | `ollama` or `openrouter` | `ollama` |
| `LLM_MODEL` | Model name | `kimi-k2.5:cloud` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://127.0.0.1:11434` |
| `OPENROUTER_API_KEY` | OpenRouter API key | (optional) |
| `CHECK_INTERVAL_MIN` | Auto-monitor frequency | `60` |

## Deployment

### Streamlit Cloud (dashboard only)
1. Push to GitHub
2. Connect repo at share.streamlit.io
3. Set entry point: `dashboard.py`
4. Add secrets in Streamlit Cloud dashboard
5. Done! 🚀

### Run Locally
```bash
streamlit run dashboard.py
# Opens at http://localhost:8501
```
