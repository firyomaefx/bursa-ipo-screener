"""
LLM Integration for Bursa Malaysia IPO Analysis.

Accepts scraped IPO data (not PDF) and analyzes via Ollama or OpenRouter.
"""

import json
import os
import requests
from typing import Optional

SYSTEM_PROMPT = """You are an elite Malaysian financial analyst specializing in Bursa Malaysia IPOs.
You have deep knowledge of:
- Malaysian listing requirements (LR 2.0, ACE Market rules)
- Shariah-compliance screening (SC Shariah Advisory Council methodology)
- Local sector P/E benchmarks and valuation norms
- Bursa-specific risk factors (concentration, RPTs, concession agreements)

You will receive IPO listing data scraped from public sources (Bursa Malaysia, KLSE Screener, IPOWatch).
Analyze the available data and return a STRICT JSON object with these exact keys:

{
  "ipo_name": "Company name and listing board",
  "valuation": {
    "offer_price": "RM X.XX or Not yet priced",
    "forward_pe": "X.Xx or Estimate",
    "sector_avg_pe": "X.Xx or Sector estimate",
    "pe_verdict": "Overvalued / Fair / Undervalued with one-sentence reason"
  },
  "proceeds": {
    "total_proceeds_rm": "RM XXX million or Not disclosed",
    "capex_pct": "X% or Not disclosed",
    "debt_repayment_pct": "X% or Not disclosed",
    "working_capital_pct": "X% or Not disclosed",
    "proceeds_verdict": "One-sentence assessment"
  },
  "profitability": {
    "revenue_cagr_3y": "X% or Not disclosed",
    "patami_cagr_3y": "X% or Not disclosed",
    "post_ipo_gearing": "X.Xx or Not disclosed",
    "profitability_verdict": "One-sentence assessment"
  },
  "cash_flow": {
    "cfo_to_net_profit_ratio": "X% or Not disclosed",
    "cash_flow_verdict": "One-sentence assessment"
  },
  "critical_risks": [
    {
      "risk": "Description of risk based on sector/company profile",
      "severity": "High / Medium / Low"
    }
  ],
  "shariah_compliant": "Yes / No / Unclear with reason",
  "final_verdict": "One decisive sentence: BUY / AVOID / NEUTRAL with brief reason"
}

RULES:
- Use ONLY information from the provided data.
- If a data point is missing, state "Not disclosed" — do NOT fabricate.
- For missing financials, give your best sector-based estimate and mark it as estimate.
- Assess Shariah compliance based on business activity (most Malaysian IPOs are Shariah-compliant).
- Be brutally honest. Most Malaysian IPOs are priced at a premium.
- Return ONLY valid JSON. No markdown fences, no commentary outside the JSON."""


def analyze_ipo_data(
    ipo_data: dict,
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> dict:
    provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()

    if provider == "openrouter":
        return _analyze_openrouter(ipo_data, model)
    else:
        return _analyze_ollama(ipo_data, model)


def _analyze_ollama(ipo_data: dict, model: Optional[str] = None) -> dict:
    model = model or os.getenv("LLM_MODEL", "kimi-k2.5:cloud")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    url = f"{base_url.rstrip('/')}/api/chat"

    user_content = _build_prompt(ipo_data)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {
            "temperature": 0.15,
            "num_predict": 4096,
        },
        "format": "json",
    }

    response = requests.post(url, json=payload, timeout=180)

    if response.status_code != 200:
        raise RuntimeError(f"Ollama API error {response.status_code}: {response.text[:500]}")

    data = response.json()
    raw = data.get("message", {}).get("content", "")

    if not raw:
        raise RuntimeError("Ollama returned empty response.")

    return _parse_llm_response(raw)


def _analyze_openrouter(ipo_data: dict, model: Optional[str] = None) -> dict:
    model = model or os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set.")

    user_content = _build_prompt(ipo_data)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bursa-ipo-screener.local",
        "X-Title": "Bursa IPO Screener Bot",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.15,
        "max_tokens": 4096,
    }

    payload = {k: v for k, v in payload.items() if v is not None}

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text[:500]}")

    raw = response.json()["choices"][0]["message"]["content"]
    return _parse_llm_response(raw)


def _build_prompt(ipo_data: dict) -> str:
    parts = [
        "Analyze this Bursa Malaysia IPO. Return ONLY valid JSON.\n",
        f"Company: {ipo_data.get('name', 'Unknown')}",
        f"Stock Code: {ipo_data.get('code', 'N/A')}",
        f"Ticker: {ipo_data.get('ticker', 'N/A')}",
        f"Board: {ipo_data.get('board', 'Unknown')}",
        f"Current/Last Price: {ipo_data.get('price', 'N/A')}",
        f"P/E Ratio: {ipo_data.get('pe', 'N/A')}",
        f"Market Cap: {ipo_data.get('market_cap', 'N/A')}",
        f"IPO/Listed Date: {ipo_data.get('date', 'N/A')}",
        f"Sector: {ipo_data.get('sector', 'N/A')}",
        f"Source: {ipo_data.get('source', 'N/A')}",
    ]

    if ipo_data.get("raw_data"):
        parts.append(f"\nRaw Data: {ipo_data['raw_data'][:2000]}")

    if ipo_data.get("search_context"):
        parts.append(f"\nWeb Context: {ipo_data['search_context'][:2000]}")

    return "\n".join(parts)


def _parse_llm_response(raw: str) -> dict:
    text = raw.strip()

    if text.startswith("```"):
        first_nl = text.index("\n")
        text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                result = json.loads(text[start:end])
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON: {e}")
        else:
            raise ValueError(f"No JSON in response: {text[:500]}")

    required = ["ipo_name", "valuation", "final_verdict"]
    missing = [k for k in required if k not in result]
    if missing:
        raise ValueError(f"Missing keys: {missing}")

    return result


def _esc(text: str) -> str:
    """Escape for Telegram MarkdownV2 — all special chars."""
    if text is None:
        return "N/A"
    text = str(text)
    for ch in "_*[]()~`>#+-=|{}.!\\":
        text = text.replace(ch, f"\\{ch}")
    return text


def format_analysis_as_markdown(analysis: dict) -> str:
    """
    Format analysis dict into the fancy IPO card format
    using Telegram MarkdownV2.
    """
    v = analysis.get("valuation", {})
    p = analysis.get("proceeds", {})
    pr = analysis.get("profitability", {})
    cf = analysis.get("cash_flow", {})
    risks = analysis.get("critical_risks", [])

    # Build risk lines
    risk_lines = ""
    for i, r in enumerate(risks[:5], 1):
        desc = _esc(r.get("risk", "N/A"))
        level = r.get("severity", "Medium").upper()
        if level.startswith("HIGH"):
            icon = "🔴"
        elif level.startswith("MED"):
            icon = "🟡"
        else:
            icon = "🟢"
        level_tag = _esc(level[:3])  # HIG/MED/LOW
        risk_lines += f"  {i}\\. {icon} {desc} \\[{level_tag}\\]\n"

    # Verdict styling
    verdict_raw = analysis.get("final_verdict", "NEUTRAL").upper()
    if "BUY" in verdict_raw and "AVOID" not in verdict_raw:
        v_icon = "🟢"
    elif "AVOID" in verdict_raw:
        v_icon = "🔴"
    else:
        v_icon = "⏸"

    # Shariah
    shariah = analysis.get("shariah_compliant", "N/A")
    sh_lower = shariah.lower() if shariah else ""
    if "yes" in sh_lower:
        s_icon = "✅"
    elif "no" in sh_lower:
        s_icon = "❌"
    else:
        s_icon = "❓"

    name = _esc(analysis.get("ipo_name", "Unknown IPO"))

    msg = f"""╔══════════════════════════════╗
 📋 *{name}*
╚══════════════════════════════╝

🏛 *Market:* {_esc(analysis.get('board', 'N/A'))} │ 💰 *Price:* {_esc(v.get('offer_price', 'N/A'))}

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
💹 *VALUATION*
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
• Forward P/E : {_esc(v.get('forward_pe', 'N/A'))}
• Sector Avg P/E: {_esc(v.get('sector_avg_pe', 'N/A'))}
• Assessment : _{_esc(v.get('pe_verdict', 'N/A'))}_

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
📦 *USE OF PROCEEDS*
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
• Total Raised : {_esc(p.get('total_proceeds_rm', 'N/A'))}
• CapEx : {_esc(p.get('capex_pct', 'N/A'))}
• Debt Repayment : {_esc(p.get('debt_repayment_pct', 'N/A'))}
• Note: _{_esc(p.get('proceeds_verdict', 'N/A'))}_

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
📈 *FINANCIAL PERFORMANCE*
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
• Revenue CAGR : {_esc(pr.get('revenue_cagr_3y', 'N/A'))}
• PATAMI CAGR : {_esc(pr.get('patami_cagr_3y', 'N/A'))}
• Post\\-IPO Gear : {_esc(pr.get('post_ipo_gearing', 'N/A'))}
• Note: _{_esc(pr.get('profitability_verdict', 'N/A'))}_

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
💵 *CASH FLOW QUALITY*
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
• CFO/Net Profit: {_esc(cf.get('cfo_to_net_profit_ratio', 'N/A'))}
• {_esc(cf.get('cash_flow_verdict', 'N/A'))}

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
⚠️ *KEY RISKS*
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
{risk_lines}▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
🕌 *SHARIAH STATUS*
▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
{s_icon} {_esc(shariah)}

╔══════════════════════════════╗
 🎯 *VERDICT: {v_icon} {_esc(analysis.get('final_verdict', 'N/A'))}*
╚══════════════════════════════╝"""

    return msg


def format_summary(analyses: list) -> str:
    """Format the final summary of all IPOs scanned."""
    lines = """╔══════════════════════════════╗
 📊 *SCAN COMPLETE — TOP 3 IPOs*
╚══════════════════════════════╝\n"""

    for i, a in enumerate(analyses, 1):
        name = _esc(a.get("ipo_name", "Unknown"))
        # Shorten name if too long
        if len(name) > 30:
            name = name[:27] + "\\."
        verdict = a.get("final_verdict", "N/A").upper()
        if "BUY" in verdict and "AVOID" not in verdict:
            v_icon = "🟢"
        elif "AVOID" in verdict:
            v_icon = "🔴"
        else:
            v_icon = "⏸"
        lines += f"{i}️⃣ {name} \\- {v_icon} {_esc(verdict)}\n"

    lines += """\n▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
_Data sourced from KLSE Screener_
_AI analysis by Ollama Cloud_
_Next auto\\-scan in 60 minutes_ ⏱
▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"""

    return lines