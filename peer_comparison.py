"""
IPO Peer Comparison Module — Phase 2

Compares IPO valuations against sector peer benchmarks for Bursa Malaysia.
Builds on scoring_engine.py to provide peer-relative analysis.
"""

from typing import Optional


SECTOR_ALIASES = {
    "technology": "Technology",
    "tech": "Technology",
    "industrial": "Industrial / Industrial Products",
    "industrial products": "Industrial / Industrial Products",
    "property": "Property / Property Development",
    "property development": "Property / Property Development",
    "healthcare": "Healthcare",
    "health": "Healthcare",
    "consumer": "Consumer / Consumer Products",
    "consumer products": "Consumer / Consumer Products",
    "construction": "Construction",
    "energy": "Energy / Oil & Gas",
    "oil & gas": "Energy / Oil & Gas",
    "oil and gas": "Energy / Oil & Gas",
    "plantation": "Plantation",
    "financial": "Financial Services",
    "financial services": "Financial Services",
    "reit": "REIT",
    "telecommunications": "Telecommunications",
    "telecom": "Telecommunications",
    "telecommunication": "Telecommunications",
    "transportation": "Transportation & Logistics",
    "transportation & logistics": "Transportation & Logistics",
    "logistics": "Transportation & Logistics",
}

SECTOR_PEERS: dict[str, dict] = {
    "Technology": {
        "avg_pe_ratio": 25.0,
        "avg_roe_pct": 15.0,
        "avg_net_margin_pct": 15.0,
        "avg_revenue_growth_pct": 20.0,
        "avg_dividend_yield_pct": 1.5,
        "top_companies": ["Inari Amertron", "Vitrox", "Mi Technovation", "Frontken", "KESM Industries"],
        "sub_sectors": ["Semiconductor", "Software", "IT Services", "Electronic Components"],
    },
    "Industrial / Industrial Products": {
        "avg_pe_ratio": 15.0,
        "avg_roe_pct": 11.0,
        "avg_net_margin_pct": 10.0,
        "avg_revenue_growth_pct": 7.0,
        "avg_dividend_yield_pct": 2.5,
        "top_companies": ["Pentamaster", "VS Industry", "SKP Resources", "SAM Engineering", "Harbour-Link"],
        "sub_sectors": ["Manufacturing", "Engineering", "Automation", "Building Materials"],
    },
    "Property / Property Development": {
        "avg_pe_ratio": 10.0,
        "avg_roe_pct": 6.5,
        "avg_net_margin_pct": 20.0,
        "avg_revenue_growth_pct": 5.0,
        "avg_dividend_yield_pct": 4.0,
        "top_companies": ["Sunway", "IOI Properties", "UEM Sunrise", "Mah Sing", "Eco World"],
        "sub_sectors": ["Residential", "Commercial", "Industrial Property", "Mixed Development"],
    },
    "Healthcare": {
        "avg_pe_ratio": 25.0,
        "avg_roe_pct": 12.0,
        "avg_net_margin_pct": 17.0,
        "avg_revenue_growth_pct": 12.0,
        "avg_dividend_yield_pct": 2.0,
        "top_companies": ["IHH Healthcare", "KPJ Healthcare", "Pharmaniaga", "Duopharma", "Hartalega"],
        "sub_sectors": ["Hospital", "Pharmaceutical", "Medical Devices", "Healthcare Services"],
    },
    "Consumer / Consumer Products": {
        "avg_pe_ratio": 17.0,
        "avg_roe_pct": 14.0,
        "avg_net_margin_pct": 10.0,
        "avg_revenue_growth_pct": 7.0,
        "avg_dividend_yield_pct": 3.0,
        "top_companies": ["Nestle Malaysia", "F&N", "Dutch Lady", "Oriental Food", "Spritzer"],
        "sub_sectors": ["F&B", "Household Products", "Personal Care", "Consumer Electronics"],
    },
    "Construction": {
        "avg_pe_ratio": 12.0,
        "avg_roe_pct": 8.0,
        "avg_net_margin_pct": 6.5,
        "avg_revenue_growth_pct": 7.0,
        "avg_dividend_yield_pct": 3.0,
        "top_companies": ["Gamuda", "IJM", "Sunway Construction", "WCT", "Kimlun"],
        "sub_sectors": ["Infrastructure", "Building Construction", "Civil Engineering", "Specialty"],
    },
    "Energy / Oil & Gas": {
        "avg_pe_ratio": 12.0,
        "avg_roe_pct": 10.0,
        "avg_net_margin_pct": 7.0,
        "avg_revenue_growth_pct": 15.0,
        "avg_dividend_yield_pct": 3.5,
        "top_companies": ["Petronas Chemicals", "Dialog Group", "Hibiscus Petroleum", "Velesto", "Sapura Energy"],
        "sub_sectors": ["Upstream", "Midstream", "Downstream", "O&G Services", "Renewable Energy"],
    },
    "Plantation": {
        "avg_pe_ratio": 17.0,
        "avg_roe_pct": 10.0,
        "avg_net_margin_pct": 12.0,
        "avg_revenue_growth_pct": 7.0,
        "avg_dividend_yield_pct": 3.0,
        "top_companies": ["Sime Darby Plantation", "IOI Corporation", "KLK", "FGV", "Genting Plantations"],
        "sub_sectors": ["Oil Palm", "Rubber", "Timber", "Downstream Processing"],
    },
    "Financial Services": {
        "avg_pe_ratio": 11.0,
        "avg_roe_pct": 11.0,
        "avg_net_margin_pct": 35.0,
        "avg_revenue_growth_pct": 4.0,
        "avg_dividend_yield_pct": 4.5,
        "top_companies": ["Maybank", "CIMB", "Public Bank", "RHB", "Hong Leong Bank"],
        "sub_sectors": ["Banking", "Insurance", "Stockbroking", "Asset Management", "Fintech"],
    },
    "REIT": {
        "avg_pe_ratio": 17.0,
        "avg_roe_pct": 7.0,
        "avg_net_margin_pct": 55.0,
        "avg_revenue_growth_pct": 4.0,
        "avg_dividend_yield_pct": 5.5,
        "top_companies": ["KLCC REIT", "IGB REIT", "Sunway REIT", "Pavilion REIT", "Axis REIT"],
        "sub_sectors": ["Retail REIT", "Office REIT", "Industrial REIT", "Hospitality REIT", "Healthcare REIT"],
    },
    "Telecommunications": {
        "avg_pe_ratio": 13.0,
        "avg_roe_pct": 10.0,
        "avg_net_margin_pct": 12.0,
        "avg_revenue_growth_pct": 3.0,
        "avg_dividend_yield_pct": 4.0,
        "top_companies": ["Maxis", "CelcomDigi", "Telekom Malaysia", "TIME DotCom"],
        "sub_sectors": ["Mobile", "Fixed Line", "Infrastructure", "Data Center"],
    },
    "Transportation & Logistics": {
        "avg_pe_ratio": 12.0,
        "avg_roe_pct": 10.0,
        "avg_net_margin_pct": 7.0,
        "avg_revenue_growth_pct": 7.0,
        "avg_dividend_yield_pct": 2.5,
        "top_companies": ["MISC", "Westports", "Tiong Nam", "Pos Malaysia", "GD Express"],
        "sub_sectors": ["Shipping", "Port Operations", "Freight Forwarding", "Courier", "Warehousing"],
    },
}

GENERAL_SECTOR: dict = {
    "avg_pe_ratio": 15.0,
    "avg_roe_pct": 10.0,
    "avg_net_margin_pct": 10.0,
    "avg_revenue_growth_pct": 7.0,
    "avg_dividend_yield_pct": 2.5,
    "top_companies": ["Various"],
    "sub_sectors": ["General"],
}


def _normalize_sector(sector: str) -> str | None:
    """Match an input sector string to a canonical sector key."""
    cleaned = sector.strip().lower()
    if cleaned in SECTOR_ALIASES:
        return SECTOR_ALIASES[cleaned]
    for raw_key in SECTOR_PEERS:
        if cleaned in raw_key.lower():
            return raw_key
    return None


def get_sector_peers(sector: str, exclude_company: str = None) -> dict:
    """Return sector benchmark data for a given Malaysian IPO sector.

    Falls back to a general sector average if the sector is unknown.

    Args:
        sector: Sector name to look up.
        exclude_company: Optional company name to exclude from top_companies.

    Returns:
        Dict with sector benchmark metrics and top companies.
    """
    canonical = _normalize_sector(sector)
    if canonical is None:
        data = dict(GENERAL_SECTOR)
        data["sector_name"] = sector
    else:
        data = dict(SECTOR_PEERS[canonical])
        data["sector_name"] = canonical

    if exclude_company and exclude_company in data.get("top_companies", []):
        data["top_companies"] = [c for c in data["top_companies"] if c != exclude_company]

    return data


def compare_ipo_to_sector(ipo: dict) -> dict:
    """Compare an IPO's key metrics against its sector peer averages.

    Args:
        ipo: IPOScore-compatible dict (from scoring_engine).

    Returns:
        Dict with IPO vs sector comparison, insights, and overall score.
    """
    sector = ipo.get("sector", "")
    peers = get_sector_peers(sector)

    ipo_pe = ipo.get("pe_ratio")
    ipo_margin = ipo.get("net_profit_margin")
    ipo_cagr = ipo.get("revenue_cagr_3yr")

    pe_discount = None
    if ipo_pe is not None and peers["avg_pe_ratio"] > 0:
        pe_discount = (peers["avg_pe_ratio"] - ipo_pe) / peers["avg_pe_ratio"] * 100

    margin_comp = _categorize_comparison(ipo_margin, peers["avg_net_margin_pct"])
    growth_comp = _categorize_comparison(ipo_cagr, peers["avg_revenue_growth_pct"])

    overall_score = _compute_overall_score(pe_discount, margin_comp, growth_comp)
    insights = _build_insights(ipo_pe, ipo_margin, ipo_cagr, peers, pe_discount)
    valuation_summary = _valuation_summary(pe_discount, margin_comp, growth_comp)

    return {
        "ipo_company": ipo.get("company_name", "Unknown"),
        "sector": peers["sector_name"],
        "market": ipo.get("market", "Unknown"),
        "peer_sector_avg": {
            "pe_ratio": peers["avg_pe_ratio"],
            "roe_pct": peers["avg_roe_pct"],
            "net_margin_pct": peers["avg_net_margin_pct"],
            "revenue_growth_pct": peers["avg_revenue_growth_pct"],
        },
        "ipo_values": {
            "pe_ratio": ipo_pe,
            "net_margin_pct": ipo_margin,
            "revenue_cagr_pct": ipo_cagr,
        },
        "comparison": {
            "pe_discount_pct": round(pe_discount, 1) if pe_discount is not None else 0.0,
            "margin_comparison": margin_comp,
            "growth_comparison": growth_comp,
            "overall_score": overall_score,
        },
        "peer_insights": insights,
        "top_sector_peers": peers.get("top_companies", []),
        "valuation_summary": valuation_summary,
    }


def _categorize_comparison(ipo_val: Optional[float], sector_avg: float) -> str:
    if ipo_val is None:
        return "At avg"
    threshold = sector_avg * 0.10
    if ipo_val > sector_avg + threshold:
        return "Above avg"
    elif ipo_val < sector_avg - threshold:
        return "Below avg"
    return "At avg"


def _compute_overall_score(
    pe_discount: Optional[float],
    margin_comp: str,
    growth_comp: str,
) -> float:
    score = 50.0

    if pe_discount is not None:
        if pe_discount >= 40:
            score += 20
        elif pe_discount >= 20:
            score += 15
        elif pe_discount >= 0:
            score += 5
        else:
            score -= 15

    if margin_comp == "Above avg":
        score += 15
    elif margin_comp == "Below avg":
        score -= 10

    if growth_comp == "Above avg":
        score += 15
    elif growth_comp == "Below avg":
        score -= 10

    return max(0.0, min(100.0, score))


def _build_insights(
    ipo_pe: Optional[float],
    ipo_margin: Optional[float],
    ipo_cagr: Optional[float],
    peers: dict,
    pe_discount: Optional[float],
) -> list[str]:
    insights = []
    if pe_discount is not None:
        avg_pe = peers["avg_pe_ratio"]
        if pe_discount > 0:
            insights.append(
                f"IPO priced at {pe_discount:.0f}% discount to sector avg PE of {avg_pe:.1f}x"
            )
        elif pe_discount < 0:
            insights.append(
                f"IPO priced at {abs(pe_discount):.0f}% premium to sector avg PE of {avg_pe:.1f}x"
            )
        else:
            insights.append(
                f"IPO priced in line with sector avg PE of {avg_pe:.1f}x"
            )

    if ipo_margin is not None:
        diff = ipo_margin - peers["avg_net_margin_pct"]
        if diff > 0:
            insights.append(
                f"Net margin of {ipo_margin:.1f}% exceeds sector avg of {peers['avg_net_margin_pct']:.1f}%"
            )
        else:
            insights.append(
                f"Net margin of {ipo_margin:.1f}% trails sector avg of {peers['avg_net_margin_pct']:.1f}%"
            )

    if ipo_cagr is not None:
        diff = ipo_cagr - peers["avg_revenue_growth_pct"]
        gap = abs(diff)
        if diff > 10:
            insights.append(
                f"Revenue CAGR of {ipo_cagr:.1f}% significantly above sector avg of "
                f"{peers['avg_revenue_growth_pct']:.1f}%"
            )
        elif diff > 0:
            insights.append(
                f"Revenue CAGR of {ipo_cagr:.1f}% moderately above sector avg of "
                f"{peers['avg_revenue_growth_pct']:.1f}%"
            )
        elif gap <= 10:
            insights.append(
                f"Revenue CAGR of {ipo_cagr:.1f}% trails sector avg of "
                f"{peers['avg_revenue_growth_pct']:.1f}%"
            )
        else:
            insights.append(
                f"Revenue CAGR of {ipo_cagr:.1f}% significantly below sector avg of "
                f"{peers['avg_revenue_growth_pct']:.1f}%"
            )

    return insights


def _valuation_summary(
    pe_discount: Optional[float],
    margin_comp: str,
    growth_comp: str,
) -> str:
    if pe_discount is not None and pe_discount >= 20:
        base = "Attractively valued vs peers"
    elif pe_discount is not None and pe_discount >= 0:
        base = "Fairly valued vs peers"
    elif pe_discount is not None and pe_discount >= -10:
        base = "Slightly expensive vs peers"
    else:
        base = "Expensive vs peers"

    if margin_comp == "Below avg" and growth_comp == "Below avg":
        if pe_discount is not None and pe_discount < 0:
            return "Expensive with weak fundamentals — caution"
        return f"{base} with below-average fundamentals"
    elif margin_comp == "Above avg" and growth_comp == "Above avg":
        return f"{base} with strong fundamentals"

    return base


def enhance_score_with_peers(ipo_score: dict, peer_comparison: dict) -> dict:
    """Adjust alpha score using peer comparison data.

    Modifies the PE Discount score based on granular peer comparison,
    then boosts or penalizes based on margin/growth relative to sector peers.

    Args:
        ipo_score: Result dict from calculate_alpha_score().
        peer_comparison: Result dict from compare_ipo_to_sector().

    Returns:
        Updated score dict with original and adjusted scores, flagged as peer_adjusted.
    """
    comparison = peer_comparison["comparison"]
    updated_breakdown = dict(ipo_score["breakdown"])
    current_pe_score = updated_breakdown.get("PE Discount", {}).get("score", 5.0)
    pe_discount = comparison.get("pe_discount_pct", 0.0)

    if pe_discount >= 40:
        new_pe_score = max(current_pe_score, 15.0)
    elif pe_discount >= 20:
        new_pe_score = max(current_pe_score, 12.0)
    elif pe_discount >= 0:
        new_pe_score = current_pe_score
    elif pe_discount >= -20:
        new_pe_score = min(current_pe_score, 5.0) if current_pe_score > 5.0 else current_pe_score
    else:
        new_pe_score = min(current_pe_score, 2.0) if current_pe_score > 2.0 else current_pe_score

    pe_delta = new_pe_score - current_pe_score
    if pe_delta != 0:
        updated_breakdown["PE Discount"] = {
            "score": new_pe_score,
            "reason": f"Adjusted by peer comparison ({pe_discount:+.1f}% vs sector)",
        }

    adjustment = pe_delta

    margin_comp = comparison.get("margin_comparison", "At avg")
    growth_comp = comparison.get("growth_comparison", "At avg")

    if margin_comp == "Above avg":
        adjustment += 3.0
    elif margin_comp == "Below avg":
        adjustment -= 2.0

    if growth_comp == "Above avg":
        adjustment += 3.0
    elif growth_comp == "Below avg":
        adjustment -= 2.0

    updated_score = ipo_score["total_score"] + adjustment
    updated_score = max(0.0, min(100.0, round(updated_score, 1)))

    if updated_score >= 70:
        new_verdict = "BUY"
    elif updated_score >= 50:
        new_verdict = "NEUTRAL"
    else:
        new_verdict = "AVOID"

    return {
        "original_score": ipo_score["total_score"],
        "original_verdict": ipo_score["verdict"],
        "updated_score": updated_score,
        "updated_verdict": new_verdict,
        "score_adjustment": round(adjustment, 1),
        "peer_adjusted": True,
        "breakdown": updated_breakdown,
    }


def format_peer_comparison_table(ipo: dict, peers: dict) -> str:
    """Format IPO vs sector peer comparison as a CLI/Telegram-friendly ASCII table.

    Args:
        ipo: Original IPO data dict (for display).
        peers: Result dict from compare_ipo_to_sector().

    Returns:
        Formatted multiline string with comparison table.
    """
    lines = []
    lines.append(f"IPO vs Sector Peers: {peers['ipo_company']}")
    lines.append(f"Sector: {peers['sector']}  |  Market: {peers['market']}")
    lines.append("")

    header = f"{'Metric':<25} {'IPO':>10} {'Sector Avg':>12} {'Status':>12}"
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    ipo_pe = peers["ipo_values"]["pe_ratio"]
    avg_pe = peers["peer_sector_avg"]["pe_ratio"]
    pe_d = peers["comparison"]["pe_discount_pct"]
    if ipo_pe is not None:
        pe_status = "Discount" if pe_d > 0 else ("Premium" if pe_d < 0 else "In line")
        lines.append(f"{'P/E Ratio (x)':<25} {f'{ipo_pe:.1f}':>10} {f'{avg_pe:.1f}':>12} {pe_status:>12}")
    else:
        lines.append(f"{'P/E Ratio (x)':<25} {'N/A':>10} {f'{avg_pe:.1f}':>12} {'':>12}")

    ipo_margin = peers["ipo_values"]["net_margin_pct"]
    avg_margin = peers["peer_sector_avg"]["net_margin_pct"]
    margin_status = peers["comparison"]["margin_comparison"]
    if ipo_margin is not None:
        lines.append(f"{'Net Margin (%)':<25} {f'{ipo_margin:.1f}':>10} {f'{avg_margin:.1f}':>12} {margin_status:>12}")
    else:
        lines.append(f"{'Net Margin (%)':<25} {'N/A':>10} {f'{avg_margin:.1f}':>12} {margin_status:>12}")

    ipo_growth = peers["ipo_values"]["revenue_cagr_pct"]
    avg_growth = peers["peer_sector_avg"]["revenue_growth_pct"]
    growth_status = peers["comparison"]["growth_comparison"]
    if ipo_growth is not None:
        lines.append(f"{'Rev Growth (%)':<25} {f'{ipo_growth:.1f}':>10} {f'{avg_growth:.1f}':>12} {growth_status:>12}")
    else:
        lines.append(f"{'Rev Growth (%)':<25} {'N/A':>10} {f'{avg_growth:.1f}':>12} {growth_status:>12}")

    ipo_dy = ipo.get("dividend_yield_pct")
    avg_dy = peers["peer_sector_avg"].get("dividend_yield_pct", 0)
    if ipo_dy is not None and avg_dy:
        lines.append(f"{'Div Yield (%)':<25} {f'{ipo_dy:.1f}':>10} {f'{avg_dy:.1f}':>12} {'':>12}")

    lines.append("")
    lines.append(f"Peer Comparison Score: {peers['comparison']['overall_score']:.0f}/100")
    lines.append(f"Valuation: {peers['valuation_summary']}")

    if peers["peer_insights"]:
        lines.append("")
        lines.append("Peer Insights:")
        for insight in peers["peer_insights"]:
            lines.append(f"  * {insight}")

    if peers["top_sector_peers"]:
        lines.append("")
        lines.append(f"Top Sector Peers: {', '.join(peers['top_sector_peers'])}")

    return "\n".join(lines)


def full_pipeline_with_peers(ipo_dict: dict) -> dict:
    """Run full analysis pipeline including alpha score and peer comparison.

    Steps:
        1. Calculate alpha score via scoring_engine.calculate_alpha_score()
        2. Compare IPO to sector peers via compare_ipo_to_sector()
        3. Enhance alpha score with peer data via enhance_score_with_peers()

    Args:
        ipo_dict: IPO data dict compatible with IPOScore.

    Returns:
        Combined result with alpha score, peer comparison, and enhanced score.
    """
    from scoring_engine import calculate_alpha_score

    alpha = calculate_alpha_score(ipo_dict)
    peers = compare_ipo_to_sector(ipo_dict)
    enhanced = enhance_score_with_peers(alpha, peers)

    return {
        "ipo_company": ipo_dict.get("company_name", "Unknown"),
        "sector": ipo_dict.get("sector", "Unknown"),
        "market": ipo_dict.get("market", "Unknown"),
        "alpha_score": alpha,
        "peer_comparison": peers,
        "peer_enhanced_score": enhanced,
    }


def demo_peer_comparison():
    """Run peer comparison demo using the 3 mock IPOs from scoring_engine."""
    from scoring_engine import calculate_alpha_score, assess_liquidity_risk

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

    print("=" * 72)
    print("  IPO PEER COMPARISON MODULE - DEMO")
    print("  Phase 2: Sector Benchmark Analysis")
    print("=" * 72)

    for i, mock in enumerate(mock_ipos, 1):
        result = full_pipeline_with_peers(mock)
        risk = assess_liquidity_risk(
            mock["market"], mock["market_cap"], mock["public_float_pct"]
        )

        print()
        print("-" * 72)
        print(f"  IPO #{i}: {result['ipo_company']} ({result['market']})")
        print("-" * 72)

        print()
        print(f"  [Alpha Score: {result['alpha_score']['total_score']:.1f}/100  |  "
              f"Verdict: {result['alpha_score']['verdict']}]")

        print()
        print("  -- Peer Comparison --")

        peers = result["peer_comparison"]
        print(f"  Sector: {peers['sector']}")
        print(f"  Comparable Peers: {', '.join(peers['top_sector_peers'])}")
        print()

        comp = peers["comparison"]
        print(f"  {'Metric':<20} {'IPO':>8} {'Sector Avg':>12} {'Status':>12}")
        print(f"  {'-'*52}")

        ipo_pe = peers["ipo_values"]["pe_ratio"]
        pe_label = "Discount" if comp["pe_discount_pct"] > 0 else ("Premium" if comp["pe_discount_pct"] < 0 else "In line")
        print(f"  {'P/E Ratio':<20} {f'{ipo_pe:.1f}x' if ipo_pe else 'N/A':>8} "
              f"{peers['peer_sector_avg']['pe_ratio']:.1f}x {pe_label:>12}")

        ipo_m = peers["ipo_values"]["net_margin_pct"]
        print(f"  {'Net Margin':<20} {f'{ipo_m:.1f}%' if ipo_m else 'N/A':>8} "
              f"{peers['peer_sector_avg']['net_margin_pct']:.1f}% {comp['margin_comparison']:>12}")

        ipo_g = peers["ipo_values"]["revenue_cagr_pct"]
        print(f"  {'Rev Growth':<20} {f'{ipo_g:.1f}%' if ipo_g else 'N/A':>8} "
              f"{peers['peer_sector_avg']['revenue_growth_pct']:.1f}% {comp['growth_comparison']:>12}")

        print()
        print(f"  Peer Comparison Score: {comp['overall_score']:.0f}/100")
        print(f"  Valuation: {peers['valuation_summary']}")

        enhanced = result["peer_enhanced_score"]
        if enhanced["score_adjustment"] != 0:
            adj_sign = "+" if enhanced["score_adjustment"] > 0 else ""
            print(f"  Peer-Adjusted Score: {enhanced['updated_score']:.1f}/100 "
                  f"({adj_sign}{enhanced['score_adjustment']:.1f} pts)  |  "
                  f"Adjusted Verdict: {enhanced['updated_verdict']}")
        else:
            print(f"  Peer-Adjusted Score: {enhanced['updated_score']:.1f}/100  |  "
                  f"Verdict: {enhanced['updated_verdict']}")

        if peers["peer_insights"]:
            print()
            print("  Insights:")
            for insight in peers["peer_insights"]:
                print(f"    * {insight}")

        print()
        print(f"  -- Liquidity Risk --")
        print(f"  Risk Level: {risk['risk_level']}")
        print(f"  {risk['warning']}")

    print()
    print("=" * 72)
    print("  DEMO COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    demo_peer_comparison()
