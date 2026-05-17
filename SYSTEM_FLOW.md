# 🇲🇾 Bursa Malaysia IPO Screener — System Flow

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     TELEGRAM USER                           │
│                   (You, @PedotTTRG)                         │
└──────────┬──────────────────────────────▲───────────────────┘
           │ /start                        │ MarkdownV2
           │ 🔍 Search Now                │ Analysis Results
           ▼                              │
┌──────────────────────────────────────────┴──────────────────┐
│                   TELEGRAM BOT API                          │
│              @BursaIPOscreener_bot                           │
│                 (Polling Mode)                               │
└──────────┬──────────────────────────────▲───────────────────┘
           │                              │
           ▼                              │
┌──────────────────────────────────────────────────────────────┐
│                     app.py (Bot Core)                        │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────┐  │
│  │ /start       │  │ Callback Handler  │  │ Auto-Monitor │  │
│  │ → Buttons    │  │ → Search Pipeline │  │ (bg thread) │  │
│  └──────────────┘  └────────┬──────────┘  └──────┬───────┘  │
└─────────────────────────────┼─────────────────────┼──────────┘
                              │                     │
              ┌───────────────┴─────────┐           │
              ▼                         ▼           ▼
┌─────────────────────────┐  ┌──────────────────────────────┐
│   STEP 1: SCRAPE        │  │   BACKGROUND MONITOR         │
│   ipo_scraper.py        │  │   (every 60 min)            │
│                         │  │   Same scrape → analyze flow │
│   Playwright Chromium   │  │   Auto-pushes new IPOs       │
│   (headless browser)    │  │   to Telegram if unseen      │
│                         │  └──────────────────────────────┘
│   ┌───────────────────┐ │
│   │ Bursa Malaysia    │ │
│   │ IPO Directory     │ │
│   └───────────────────┘ │
│   ┌───────────────────┐ │
│   │ KLSE Screener     │ │
│   │ (sorted by IPO)   │ │
│   └───────────────────┘ │
│   ┌───────────────────┐ │
│   │ IPOWatch.my       │ │
│   └───────────────────┘ │
│                         │
│   → Top 3 (deduped,    │ │
│     newest first)      │ │
└──────────┬──────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│   STEP 2: ENRICH (optional)                              │
│   Google search for financial data, PE, prospectus info  │
│   (Playwright-powered)                                    │
└──────────┬───────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│   STEP 3: AI ANALYSIS                                    │
│   llm_analyzer.py                                        │
│                                                          │
│   Provider: Ollama (default)  ── or ──  OpenRouter       │
│   Model: kimi-k2.5:cloud                Claude/GPT-4o   │
│   URL: http://127.0.0.1:11434/api/chat                   │
│                                                          │
│   System Prompt:                                         │
│   "Elite Malaysian financial analyst"                    │
│   → Returns strict JSON with:                           │
│     • Valuation (P/E vs sector)                         │
│     • Proceeds utilization                              │
│     • Profitability (CAGR, gearing)                      │
│     • Cash flow quality                                 │
│     • Top 3 critical risks                              │
│     • Shariah compliance                                │
│     • Final verdict (BUY/AVOID/NEUTRAL)                 │
└──────────┬───────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│   STEP 4: FORMAT & DELIVER                               │
│   format_analysis_as_markdown()                           │
│   → Telegram MarkdownV2                                  │
│   → Auto-split if >4096 chars                            │
│   → Sent to user's Telegram                              │
└──────────────────────────────────────────────────────────┘
```

## Process Flow (Step by Step)

### User-Triggered Search

```
User sends /start
  → Bot shows: [🔍 Search Top 3 IPOs Now] [📊 Auto-Monitor Status]

User taps "Search Now"
  → Bot: "Scanning Bursa Malaysia..."
  → Playwright launches headless Chromium
  → Loads Bursa IPO Directory (JS-rendered)
  → Loads KLSE Screener (IPO-sorted)
  → Loads IPOWatch.my
  → Extracts IPO entries from each page
  → Deduplicates by company name
  → Sorts by date (newest first)
  → Takes top 3

For each IPO (1-3):
  → Bot: "IPO 1/3: [Company Name] - Analyzing..."
  → Sends data to Ollama API (kimi-k2.5:cloud)
  → LLM analyzes as Malaysian financial analyst
  → Returns structured JSON
  → Formats as MarkdownV2
  → Sends analysis to Telegram

  → Bot: "✅ Top 3 IPO scan complete!"
```

### Background Auto-Monitor

```
Every 60 minutes (configurable):
  → Playwright scrapes all 3 sources
  → Compares against seen DB (ipo_seen.json)
  → If new IPO found:
    → Analyze via Ollama
    → Push to Telegram: "🆕 New IPO Detected!"
    → Save to seen DB
  → If no new IPOs: silent (no message)
```

## File Structure

```
bursa-ipo-bot/
├── app.py              ← Bot core + handlers + auto-monitor thread
├── ipo_scraper.py      ← Playwright scraper (JS-friendly)
├── llm_analyzer.py     ← Ollama/OpenRouter LLM integration
├── pdf_processor.py    ← (legacy) PDF extraction
├── ipo_monitor.py      ← (legacy) old monitor without Playwright
├── requirements.txt    ← Dependencies
├── .env                ← Secrets (TELEGRAM_BOT_TOKEN, etc.)
├── .env.example        ← Template
├── .gitignore
└── README.md
```

## Key Config (.env)

| Variable | Default | Purpose |
|----------|---------|---------|
| TELEGRAM_BOT_TOKEN | required | Bot auth |
| TELEGRAM_CHAT_ID | required | Your user ID for auto-notifications |
| LLM_PROVIDER | ollama | ollama or openrouter |
| LLM_MODEL | kimi-k2.5:cloud | Model for analysis |
| OLLAMA_BASE_URL | http://127.0.0.1:11434 | Ollama API |
| CHECK_INTERVAL_MIN | 60 | Auto-monitor frequency |
| MAX_PDF_SIZE_MB | 20 | (legacy) PDF upload limit |