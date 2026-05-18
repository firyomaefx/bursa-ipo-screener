# 📊 Bursa Malaysia IPO Alpha Screener

An automated pre-listing valuation and scoring tool for Malaysian IPOs. Score any IPO across 7 criteria, compare against sector peers, and browse a database of 122 scored IPOs — all in a clean Streamlit dashboard.

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
streamlit run dashboard.py
# Opens at http://localhost:8501
```

That's it. No API keys, no database setup, no config files.

---

## 📋 What It Does

### The Dashboard

A single-page card list of Malaysian IPOs. Each card shows:

| Element | What You See |
|---------|-------------|
| **Company** | Name + Stock ticker |
| **Sector** | Industry classification |
| **Shariah Status** | ✅ Shariah or ❌ Non-Shariah badge |
| **Alpha Score** | 0–100 score, color-coded (🔵 BUY / ⚪ NEUTRAL / 🔴 AVOID) |
| **Verdict** | BUY ≥ 70 · NEUTRAL 50–69 · AVOID < 50 |

Click any card to expand and see:
- **Score gauge** — visual speedometer
- **7-criteria breakdown** — bar chart showing what drove the score
- **Peer comparison** — how this IPO stacks against its sector averages
- **Liquidity risk** — estimated trading range, float size, volatility

### Filters

| Filter | What It Does |
|--------|-------------|
| Verdict | Show only BUY / NEUTRAL / AVOID |
| Sector | Pick specific industries |
| Market | MAIN / ACE / LEAP |
| Shariah | All / Shariah-only / Non-Shariah only |
| Search | Type to find by company name |

### Actions

- **➕ Add New IPO** — manually enter IPO details (price, PE, sector, financials), get an instant score
- **🔄 Refresh** — re-score any IPO on demand (useful after updated data)

---

## 🧮 How Scoring Works (7-Criteria Alpha Score)

Each IPO gets a score out of 100 based on 7 weighted criteria:

| Criteria | Weight | What It Measures |
|----------|--------|-----------------|
| PE Discount | 15% | Is the IPO cheaper than sector average? |
| Oversubscription Demand | 15% | Strong investor demand = bullish signal |
| Proceeds Utilization | 15% | How will the raised money be used? |
| Profitability & Growth | 20% | Revenue growth and profit margins |
| Shariah Compliance | 10% | Shariah-compliant = wider investor pool |
| Float & Liquidity | 15% | Enough shares available to trade? |
| Moratorium & Lock-up | 10% | Insiders locked in = aligned incentives |

**Score → Verdict:**
- **BUY** ≥ 70 — Strong fundamentals, good demand
- **NEUTRAL** 50–69 — Average, needs more data
- **AVOID** < 50 — Weak fundamentals or insufficient data

---

## 📁 Database

All IPOs are stored in `ipo_scores.json`. Currently loaded with **122 Malaysian IPOs** across all sectors:

| Sector | Examples |
|--------|----------|
| Technology/Semicon | SkyeChip, Inari, Vitrox, Unisem, MPI |
| Technology | Oppstar, Infomina, NationGate |
| Healthcare | IHH, KPJ, Top Glove, Hartalega |
| Banking | Maybank, CIMB, Public Bank, RHB |
| Consumer | Nestle, 99 Speed Mart, MR.DIY, DXN |
| Property | EcoWorld, Mah Sing, Sime Darby Property |
| Construction | Gamuda, Sunway Construction, IJM |
| Energy | Petronas Gas, Hibiscus, Dialog, Solarvest |
| Plantation | KLK, Sime Darby Plantation, IOI |
| REIT | Axis REIT, KLCC, Pavilion, Sunway |
| Telecom | Maxis, CelcomDigi, Telekom Malaysia |
| Logistics | MISC, Westports, Pos Malaysia |
| Others | Gaming, Aviation, Automotive, Gloves |

You can add more via the **Add New IPO** button in the dashboard.

---

## 🏛 Project Structure

```
bursa-ipo-bot/
├── dashboard.py           # ⭐ Streamlit dashboard (run this)
├── scoring_engine.py      # Core scoring algorithm (7 criteria)
├── peer_comparison.py     # 12-sector benchmark comparison
├── gen_ipo_data.py        # Script to generate IPO database
├── ipo_scores.json        # Scored IPO database (122 entries)
├── streamlit_app.py       # Entry wrapper for Streamlit Cloud
├── .streamlit/config.toml # Bursa-themed UI config
├── requirements.txt       # Python dependencies
└── README.md
```

---

## 🌐 Deployment

### Local
```bash
streamlit run dashboard.py
```

### Streamlit Cloud (Free)
1. Push this repo to GitHub
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud)
3. Sign in with GitHub → **New app**
4. Select this repo, branch `master`, main file `dashboard.py`
5. Click **Deploy**

Your app will be live in a few minutes at `https://your-app-name.streamlit.app`.

---

## 📦 Tech Stack

- **Python 3.10+** — Core logic
- **Streamlit** — Web dashboard
- **Plotly** — Interactive charts (gauge, breakdown bars)
- **Pandas** — Data processing
- **Playwright** — Screenshot capture (optional)

---

## 📜 Version History

| Version | What's New |
|---------|-----------|
| v3.1.0 | Shariah/Non-Shariah filter + badges. 122 IPOs. Better README. |
| v3.0.0 | Full dashboard rewrite: single-page card list, Add New IPO, per-IPO Refresh. No auto-scan. |
| v2.0.0 | 4-tab Streamlit dashboard + peer comparison engine |
| v1.0.0 | Scoring engine + Telegram bot |

---

*Built for Malaysian retail investors. Data is for reference — always do your own due diligence.* 🇲🇾
