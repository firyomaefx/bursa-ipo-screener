"""
IPO Alpha Scoring Engine — Phase 1 (Beta Core)

Quantitative scoring system for Bursa Malaysia IPOs.
7 criteria weighted to produce alpha score (0-100) with verdict (BUY/NEUTRAL/AVOID).
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── IPO Data Schema ──

@dataclass
class IPOScore:
    company_name: str
    market: str
    sector: str
    offer_price: float
    market_cap: float
    pe_ratio: Optional[float] = None
    sector_avg_pe: Optional[float] = None
    oversubscription_rate: Optional[float] = None
    proceeds_utilization: dict = field(default_factory=lambda: {
        "capex_pct": None,
        "debt_pct": None,
        "working_capital_pct": None,
    })
    net_profit_margin: Optional[float] = None
    revenue_cagr_3yr: Optional[float] = None
    shariah_compliant: Optional[bool] = None
    moratorium_period_years: Optional[float] = None
    promoter_ownership_pct: Optional[float] = None
    total_shares: int = 0
    public_float_pct: float = 0.0
    application_status: str = "Open"
    listing_date: Optional[str] = None
    alpha_score: Optional[float] = None
    verdict: Optional[str] = None
    score_breakdown: dict = field(default_factory=dict)


# ── Scoring Functions ──

def calculate_pe_discount(ipo_pe: Optional[float], sector_avg_pe: Optional[float]) -> tuple[float, str]:
    if ipo_pe is None or sector_avg_pe is None or sector_avg_pe <= 0:
        return 5.0, "PE data insufficient — neutral score"
    discount = (sector_avg_pe - ipo_pe) / sector_avg_pe
    if discount >= 0.40:
        return 15.0, f"PE discount of {discount:.1%} — strong valuation gap"
    elif discount >= 0.20:
        return 10.0, f"PE discount of {discount:.1%} — moderate gap"
    elif discount >= 0.0:
        return 5.0, f"PE at or near sector avg ({discount:.1%})"
    else:
        premium = abs(discount)
        return 0.0, f"PE premium of {premium:.1%} — expensive vs sector"


def calculate_oversubscription_score(rate: Optional[float]) -> tuple[float, str]:
    if rate is None:
        return 4.0, "Oversubscription data unavailable — assuming weak demand"
    if rate >= 20.0:
        return 15.0, f"{rate:.1f}x oversubscription — exceptional demand"
    elif rate >= 10.0:
        return 12.0, f"{rate:.1f}x oversubscription — very strong demand"
    elif rate >= 5.0:
        return 8.0, f"{rate:.1f}x oversubscription — healthy demand"
    elif rate >= 2.0:
        return 4.0, f"{rate:.1f}x oversubscription — moderate demand"
    else:
        return 0.0, f"{rate:.1f}x oversubscription — weak demand"


def calculate_proceeds_score(proceeds: dict) -> tuple[float, str]:
    capex = proceeds.get("capex_pct")
    if capex is None:
        return 5.0, "Proceeds breakdown unavailable — neutral score"
    if capex > 50:
        return 15.0, f"{capex:.0f}% for expansion/CapEx — strong growth allocation"
    elif capex >= 25:
        return 10.0, f"{capex:.0f}% for expansion — moderate growth allocation"
    else:
        return 5.0, f"Only {capex:.0f}% for expansion — mostly debt/working capital"


def calculate_profitability_score(margin: Optional[float], cagr: Optional[float]) -> tuple[float, str]:
    margin_ok = margin is not None and margin > 15.0
    cagr_ok = cagr is not None and cagr > 20.0
    if margin_ok and cagr_ok:
        return 15.0, f"Net margin {margin:.1f}% + CAGR {cagr:.1f}% — excellent fundamentals"
    elif margin_ok:
        return 8.0, f"Net margin {margin:.1f}% is healthy but growth data limited"
    elif cagr_ok:
        return 8.0, f"Revenue CAGR {cagr:.1f}% is strong but margins thin"
    elif margin is not None or cagr is not None:
        return 2.0, "Below threshold on both margins and growth"
    else:
        return 2.0, "Profitability data unavailable — conservative score"


def calculate_shariah_score(compliant: Optional[bool]) -> tuple[float, str]:
    if compliant is True:
        return 10.0, "Shariah-compliant — no restriction"
    elif compliant is False:
        return 0.0, "Non Shariah-compliant — limited investor pool"
    else:
        return 2.0, "Shariah status unknown — not yet screened"


def calculate_float_score(market_cap: float, public_float_pct: float) -> tuple[float, str]:
    float_value = market_cap * (public_float_pct / 100.0)
    if float_value > 100_000_000:
        return 15.0, f"Float RM{float_value:,.0f} — excellent liquidity"
    elif float_value > 50_000_000:
        return 10.0, f"Float RM{float_value:,.0f} — good liquidity"
    elif float_value > 20_000_000:
        return 5.0, f"Float RM{float_value:,.0f} — adequate liquidity"
    else:
        return 0.0, f"Float RM{float_value:,.0f} — thin liquidity, high impact risk"


def calculate_moratorium_score(
    moratorium_years: Optional[float],
    promoter_pct: Optional[float]
) -> tuple[float, str]:
    has_lockup = moratorium_years is not None and moratorium_years > 1.0
    high_ownership = promoter_pct is not None and promoter_pct > 50.0
    if has_lockup and high_ownership:
        return 10.0, f"Moratorium {moratorium_years:.0f}y + promoter {promoter_pct:.0f}% — strong alignment"
    elif has_lockup or high_ownership:
        reasons = []
        if has_lockup:
            reasons.append(f"moratorium {moratorium_years:.0f}y")
        if high_ownership:
            reasons.append(f"promoter {promoter_pct:.0f}%")
        return 5.0, f"{' & '.join(reasons)} — partial alignment"
    else:
        return 0.0, "No moratorium and low promoter ownership — weak alignment"


# ── Main Scoring Engine ──

def calculate_alpha_score(ipo_data: dict) -> dict:
    fields = _prepare_fields(ipo_data)
    scores: list[tuple[float, str]] = []

    scores.append(calculate_pe_discount(fields["pe"], fields["sector_pe"]))
    scores.append(calculate_oversubscription_score(fields["oversub"]))
    scores.append(calculate_proceeds_score(fields["proceeds"]))
    scores.append(calculate_profitability_score(fields["margin"], fields["cagr"]))
    scores.append(calculate_shariah_score(fields["shariah"]))
    scores.append(calculate_float_score(fields["mcap"], fields["float_pct"]))
    scores.append(calculate_moratorium_score(fields["moratorium"], fields["promoter"]))

    criteria_names = [
        "PE Discount",
        "Oversubscription Demand",
        "Proceeds Utilization",
        "Profitability & Growth",
        "Shariah Compliance",
        "Float & Liquidity",
        "Moratorium & Lock-up",
    ]

    total = 0.0
    breakdown = {}
    for name, (score, reason) in zip(criteria_names, scores):
        total += score
        breakdown[name] = {"score": score, "reason": reason}

    total = round(total, 1)

    if total >= 70:
        verdict = "BUY"
    elif total >= 50:
        verdict = "NEUTRAL"
    else:
        verdict = "AVOID"

    return {
        "total_score": total,
        "verdict": verdict,
        "breakdown": breakdown,
    }


def _prepare_fields(ipo_data: dict) -> dict:
    proceeds = ipo_data.get("proceeds_utilization", {})
    if not isinstance(proceeds, dict):
        proceeds = {}
    mcap = ipo_data.get("market_cap", 0) or 0
    return {
        "pe": ipo_data.get("pe_ratio"),
        "sector_pe": ipo_data.get("sector_avg_pe"),
        "oversub": ipo_data.get("oversubscription_rate"),
        "proceeds": proceeds,
        "margin": ipo_data.get("net_profit_margin"),
        "cagr": ipo_data.get("revenue_cagr_3yr"),
        "shariah": ipo_data.get("shariah_compliant"),
        "mcap": float(mcap),
        "float_pct": float(ipo_data.get("public_float_pct") or 0),
        "moratorium": ipo_data.get("moratorium_period_years"),
        "promoter": ipo_data.get("promoter_ownership_pct"),
    }


# ── DOM / Liquidity Risk Score ──

def assess_liquidity_risk(market: str, market_cap: float, public_float_pct: float) -> dict:
    float_value = market_cap * (public_float_pct / 100.0)
    is_ace = market.upper() == "ACE"
    low_float = float_value < 20_000_000

    if low_float and is_ace:
        risk = "HIGH"
        warning = "Low float on ACE Market — severe liquidity risk, wide bid-ask spreads expected"
    elif low_float:
        risk = "MODERATE"
        warning = "Low public float — may experience price swings on small volumes"
    elif is_ace and float_value < 50_000_000:
        risk = "MODERATE"
        warning = "ACE Market with moderate float — liquidity adequate but monitor"
    else:
        risk = "LOW"
        warning = "Adequate float and market liquidity"

    if float_value < 20_000_000:
        est_low, est_high = -15.0, 20.0
    elif float_value < 50_000_000:
        est_low, est_high = -8.0, 12.0
    elif float_value < 100_000_000:
        est_low, est_high = -5.0, 8.0
    else:
        est_low, est_high = -3.0, 5.0

    return {
        "risk_level": risk,
        "warning": warning,
        "estimated_volatility_range": f"{est_low:+.0f}% to {est_high:+.0f}% (Day 1-5)",
        "public_float_rm": float_value,
    }


# ── Full Pipeline ──

def analyze_and_score(pdf_path: str) -> dict:
    from pdf_processor import extract_prospectus_data
    from llm_analyzer import analyze_ipo_data

    pdf_data = extract_prospectus_data(pdf_path)
    llm_result = analyze_ipo_data(pdf_data)

    score_input = _llm_to_score_input(llm_result)
    score_result = calculate_alpha_score(score_input)

    ipo = IPOScore(
        company_name=llm_result.get("ipo_name", "Unknown"),
        market=llm_result.get("board", "Unknown"),
        sector=llm_result.get("sector", "Unknown"),
        offer_price=_parse_float(llm_result.get("valuation", {}).get("offer_price", "0")),
        market_cap=0.0,
        pe_ratio=_parse_float(llm_result.get("valuation", {}).get("forward_pe", "0")),
        sector_avg_pe=_parse_float(llm_result.get("valuation", {}).get("sector_avg_pe", "0")),
        net_profit_margin=score_input.get("net_profit_margin"),
        revenue_cagr_3yr=score_input.get("revenue_cagr_3yr"),
        shariah_compliant=_parse_shariah(llm_result.get("shariah_compliant", "")),
        alpha_score=score_result["total_score"],
        verdict=score_result["verdict"],
        score_breakdown=score_result["breakdown"],
    )

    return asdict(ipo)


def _llm_to_score_input(llm_result: dict) -> dict:
    proceeds = llm_result.get("proceeds", {})
    profitability = llm_result.get("profitability", {})

    capex_str = proceeds.get("capex_pct", "0%")
    debt_str = proceeds.get("debt_repayment_pct", "0%")
    wc_str = proceeds.get("working_capital_pct", "0%")

    return {
        "pe_ratio": _parse_float(llm_result.get("valuation", {}).get("forward_pe", "0")),
        "sector_avg_pe": _parse_float(llm_result.get("valuation", {}).get("sector_avg_pe", "0")),
        "proceeds_utilization": {
            "capex_pct": _parse_pct(capex_str),
            "debt_pct": _parse_pct(debt_str),
            "working_capital_pct": _parse_pct(wc_str),
        },
        "net_profit_margin": _parse_pct(profitability.get("net_profit_margin", "")),
        "revenue_cagr_3yr": _parse_pct(profitability.get("revenue_cagr_3y", "")),
        "shariah_compliant": _parse_shariah(llm_result.get("shariah_compliant", "")),
    }


def _parse_float(val: str) -> Optional[float]:
    if not val:
        return None
    val = val.strip().replace("RM", "").replace("x", "").replace(",", "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_pct(val: str) -> Optional[float]:
    if not val:
        return None
    val = val.strip().replace("%", "").replace("~", "").replace("+", "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_shariah(val: str) -> Optional[bool]:
    if not val:
        return None
    low = val.lower().strip()
    if low.startswith("yes"):
        return True
    if low.startswith("no"):
        return False
    return None


# ── JSON Storage ──

SCORES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ipo_scores.json")


def load_scores() -> list[dict]:
    if not os.path.exists(SCORES_FILE):
        return []
    with open(SCORES_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []


def save_score(ipo_score: IPOScore) -> None:
    scores = load_scores()
    data = asdict(ipo_score)
    scores.append(data)
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, indent=2, default=str)


def get_all_scores() -> list[dict]:
    return load_scores()


def get_top_scores(n: int = 5) -> list[dict]:
    scores = load_scores()
    valid = [s for s in scores if s.get("alpha_score") is not None]
    valid.sort(key=lambda x: x["alpha_score"], reverse=True)
    return valid[:n]


def search_by_sector(sector: str) -> list[dict]:
    scores = load_scores()
    ss = sector.lower().strip()
    return [s for s in scores if ss in s.get("sector", "").lower()]


# ── Demo / Test ──

def demo():
    mock_ipos = [
        {
            "company_name": "Alpha Tech Berhad",
            "market": "ACE",
            "sector": "Technology",
            "offer_price": 0.55,
            "market_cap": 120_000_000,
            "pe_ratio": 12.5,
            "sector_avg_pe": 25.0,
            "oversubscription_rate": 38.2,
            "proceeds_utilization": {"capex_pct": 60, "debt_pct": 15, "working_capital_pct": 25},
            "net_profit_margin": 18.5,
            "revenue_cagr_3yr": 35.0,
            "shariah_compliant": True,
            "moratorium_period_years": 2.0,
            "promoter_ownership_pct": 65.0,
            "total_shares": 220_000_000,
            "public_float_pct": 25.0,
            "application_status": "Open",
            "listing_date": "2025-03-15",
        },
        {
            "company_name": "Beta Manufacturing Bhd",
            "market": "Main",
            "sector": "Industrial",
            "offer_price": 1.20,
            "market_cap": 450_000_000,
            "pe_ratio": 14.0,
            "sector_avg_pe": 15.0,
            "oversubscription_rate": 6.5,
            "proceeds_utilization": {"capex_pct": 30, "debt_pct": 40, "working_capital_pct": 30},
            "net_profit_margin": 12.0,
            "revenue_cagr_3yr": 8.0,
            "shariah_compliant": True,
            "moratorium_period_years": 0.5,
            "promoter_ownership_pct": 45.0,
            "total_shares": 375_000_000,
            "public_float_pct": 30.0,
            "application_status": "Closing",
            "listing_date": "2025-04-01",
        },
        {
            "company_name": "Gamma Property Group",
            "market": "Main",
            "sector": "Property",
            "offer_price": 0.80,
            "market_cap": 80_000_000,
            "pe_ratio": 22.0,
            "sector_avg_pe": 15.0,
            "oversubscription_rate": 1.5,
            "proceeds_utilization": {"capex_pct": 15, "debt_pct": 60, "working_capital_pct": 25},
            "net_profit_margin": 5.0,
            "revenue_cagr_3yr": -2.0,
            "shariah_compliant": False,
            "moratorium_period_years": 0.0,
            "promoter_ownership_pct": 30.0,
            "total_shares": 100_000_000,
            "public_float_pct": 20.0,
            "application_status": "Listed",
            "listing_date": "2025-02-01",
        },
    ]

    print("=" * 60)
    print("  IPO ALPHA SCORING ENGINE - DEMO")
    print("=" * 60)

    for i, mock in enumerate(mock_ipos, 1):
        result = calculate_alpha_score(mock)
        risk = assess_liquidity_risk(
            mock["market"], mock["market_cap"], mock["public_float_pct"]
        )

        print()
        print("-" * 60)
        print(f"  IPO #{i}: {mock['company_name']} ({mock['market']})")
        print("-" * 60)
        print(f"  Price: RM{mock['offer_price']:.2f}  |  Sector: {mock['sector']}")
        print(f"  P/E: {mock['pe_ratio']:.1f}x  |  Sector Avg P/E: {mock['sector_avg_pe']:.1f}x")
        print(f"  Oversubscription: {mock['oversubscription_rate']:.1f}x")
        print(f"  Net Margin: {mock['net_profit_margin']:.1f}%  |  Rev CAGR: {mock['revenue_cagr_3yr']:.1f}%")
        print(f"  Shariah: {'Yes' if mock['shariah_compliant'] else 'No'}")
        print(f"  Float: RM{mock['market_cap'] * mock['public_float_pct'] / 100:,.0f}")
        print(f"  Moratorium: {mock['moratorium_period_years']}y  |  Promoter: {mock['promoter_ownership_pct']}%")
        print()
        print(f"  ==================================")
        print(f"   ALPHA SCORE: {result['total_score']:.1f}/100")
        print(f"   VERDICT: {result['verdict']}")
        print(f"  ==================================")
        print()
        print(f"  -- Score Breakdown --")
        for name, detail in result["breakdown"].items():
            bar = "#" * int(detail["score"])
            print(f"    {name:30s} {detail['score']:5.1f}  {bar}")
        print()
        print(f"  -- Liquidity Risk --")
        print(f"    Risk Level: {risk['risk_level']}")
        print(f"    {risk['warning']}")
        print(f"    Est. Volatility: {risk['estimated_volatility_range']}")

    print()
    print("=" * 60)
    print("  DEMO COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    demo()
