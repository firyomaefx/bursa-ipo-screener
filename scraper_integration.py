"""
Scraper Integration — Sync wrapper for the async IPO scraper.
Designed for Streamlit (single-threaded) use.
Runs Playwright in a subprocess to avoid event loop conflicts.
"""
import json, sys, os, subprocess, time, re, logging
from pathlib import Path

logger = logging.getLogger(__name__)

BOT_DIR = Path(__file__).parent
SCORES_FILE = BOT_DIR / "ipo_scores.json"

# ── Sync wrapper ────────────────────────────────────────────────────────────

def scrape_current_ipos(limit: int = 5) -> list[dict]:
    """
    Run the async scraper in a subprocess and return results.
    Falls back to cached data if scraping fails.
    """
    script = f"""
import asyncio, json, sys
sys.path.insert(0, r'{BOT_DIR}')
from ipo_scraper import get_current_ipos_async
ipos = asyncio.run(get_current_ipos_async(limit={limit}))
print(json.dumps(ipos))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=60,
            cwd=str(BOT_DIR),
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if isinstance(data, list):
                logger.info(f"Scraped {len(data)} IPOs from Bursa")
                return data
        if result.stderr:
            logger.warning(f"Scraper stderr: {result.stderr[:300]}")
    except subprocess.TimeoutExpired:
        logger.warning("Scraper timed out (60s)")
    except json.JSONDecodeError as e:
        logger.warning(f"Scraper output parse error: {e}")
    except Exception as e:
        logger.warning(f"Scraper error: {e}")

    return []


# ── Field mapping ───────────────────────────────────────────────────────────

def map_scraped_to_ipo_input(scraped: dict) -> dict:
    """
    Map scraped fields to scoring engine input format.
    Missing fields get sensible defaults or None (engine handles gracefully).
    """
    # Try to extract numeric price
    price_str = scraped.get("price", "0")
    try:
        price = float(re.sub(r'[^\d.]', '', price_str))
    except (ValueError, TypeError):
        price = 0.0

    # Market / Board mapping
    board = scraped.get("board", "Unknown").lower()
    if "ace" in board:
        market = "ACE"
    elif "leap" in board:
        market = "LEAP"
    elif "main" in board:
        market = "Main"
    else:
        market = "ACE"  # default - most IPOs on ACE

    # Extract total shares and market cap from issue_size
    # Format: "934,449,089 Market Cap: 186,889,818"
    issue_size = scraped.get("issue_size", "")
    total_shares = scraped.get("total_shares", 0)
    market_cap = scraped.get("market_cap", 0)

    if not total_shares and issue_size:
        # Pattern: "XXX,XXX,YYY Market Cap: ZZZ,ZZZ"
        mcap_match = re.search(r'Market Cap:\s*([\d,]+)', issue_size, re.I)
        if mcap_match:
            try:
                market_cap = int(mcap_match.group(1).replace(',', ''))
            except:
                pass
        # First number before "Market Cap" is usually total shares
        shares_match = re.search(r'([\d,]+)\s+Market Cap', issue_size, re.I)
        if shares_match:
            try:
                total_shares = int(shares_match.group(1).replace(',', ''))
            except:
                pass

    if not total_shares:
        total_shares = 50_000_000
    if not market_cap:
        market_cap = total_shares * price if price > 0 else 50_000_000

    # Sector mapping (normalize to peer_comparison sectors)
    sector = scraped.get("sector", "Technology")
    sector_map = {
        "technology": "Technology",
        "tech": "Technology",
        "consumer": "Consumer",
        "consumer products": "Consumer",
        "consumer products & services": "Consumer",
        "consumer non-cyclical": "Consumer",
        "consumer cyclical": "Consumer",
        "industrial": "Industrial",
        "industrial products": "Industrial",
        "industrial products & services": "Industrial",
        "industrial services": "Industrial",
        "industrial materials": "Industrial",
        "healthcare": "Healthcare",
        "health": "Healthcare",
        "construction": "Construction",
        "property": "Property",
        "property & construction": "Property",
        "real estate": "Property",
        "finance": "Financial Services",
        "financial": "Financial Services",
        "financial services": "Financial Services",
        "financial services & investment": "Financial Services",
        "plantation": "Plantation",
        "telco": "Telecommunications",
        "telecommunications": "Telecommunications",
        "telecom": "Telecommunications",
        "media": "Media & Entertainment",
        "entertainment": "Media & Entertainment",
        "energy": "Energy",
        "oil & gas": "Energy",
        "transportation": "Transportation & Logistics",
        "logistics": "Transportation & Logistics",
        "transportation & logistics": "Transportation & Logistics",
        "reit": "REIT",
        "automotive": "Consumer",
        "education": "Consumer",
        "gaming": "Technology",
        "food & beverages": "Consumer",
        "food & beverage": "Consumer",
        "f&b": "Consumer",
        "rubber": "Industrial",
        "packaging": "Industrial",
        "electrical": "Industrial",
        "electronics": "Technology",
        "semiconductor": "Technology",
        "software": "Technology",
        "services": "Consumer",
        "trading": "Consumer",
        "retail": "Consumer",
        "building materials": "Construction",
        "mining": "Industrial",
        "mineral": "Industrial",
        "machinery": "Industrial",
        "equipment": "Industrial",
        "chemical": "Industrial",
        "pharmaceutical": "Healthcare",
        "biotech": "Healthcare",
        "medical": "Healthcare",
        "insurance": "Financial Services",
        "bank": "Financial Services",
        "banking": "Financial Services",
        "hotel": "Consumer",
        "leisure": "Consumer",
        "solar": "Energy",
        "renewable": "Energy",
        "water": "Industrial",
        "waste": "Industrial",
        "metal": "Industrial",
        "steel": "Industrial",
        "furniture": "Consumer",
        "textile": "Consumer",
        "apparel": "Consumer",
        "printing": "Industrial",
        "engineering": "Industrial",
        "infrastructure": "Construction",
        "defense": "Industrial",
        "aerospace": "Industrial",
        "marine": "Transportation & Logistics",
        "shipping": "Transportation & Logistics",
        "port": "Transportation & Logistics",
        "warehouse": "Transportation & Logistics",
        "glove": "Healthcare",
        "rubber glove": "Healthcare",
        "nitrile glove": "Healthcare",
        "diversified": "Industrial",
        "conglomerate": "Consumer",
        "closed-end fund": "Financial Services",
        "special purpose": "Financial Services",
        "special purpose acquisition": "Financial Services",
    }
    sector_lower = sector.lower().strip()
    mapped_sector = sector_map.get(sector_lower, sector)

    # Name
    company_name = scraped.get("name", "Unknown")
    ticker = scraped.get("ticker", "")

    # Build input dict for scoring engine
    return {
        "company_name": company_name,
        "ticker": ticker,
        "market": market,
        "sector": mapped_sector,
        "offer_price": price,
        "market_cap": int(market_cap),
        "total_shares": int(total_shares),
        "pe_ratio": None,                # not available from scraper
        "sector_avg_pe": None,           # will be filled by peer_comparison
        "oversubscription_rate": None,   # not available from scraper
        "proceeds_utilization": {},      # not available from scraper
        "net_profit_margin": None,       # not available from scraper
        "revenue_cagr_3yr": None,        # not available from scraper
        "shariah_compliant": None,       # not available from scraper
        "moratorium_period_years": 2.0,  # default for ACE
        "promoter_ownership_pct": None,  # not available from scraper
        "public_float_pct": None,        # not available from scraper
        "application_status": "Open",
        "listing_date": scraped.get("date", "TBC"),
        "source": scraped.get("source", "klse_screener"),
        "link": scraped.get("link", ""),
        "raw_data": scraped.get("raw_data", ""),
    }


def auto_scan_and_score(limit: int = 5) -> list[dict]:
    """
    Full pipeline: scrape → map → score → save.
    Returns list of scored IPOs.
    """
    from scoring_engine import calculate_alpha_score
    from peer_comparison import compare_ipo_to_sector, enhance_score_with_peers

    scraped = scrape_current_ipos(limit=limit)
    if not scraped:
        return []

    # Load existing scores to avoid duplicates
    existing = _load_scores()
    existing_names = {e.get("company_name", "").lower().strip() for e in existing}

    new_entries = []
    for s in scraped:
        ipo_input = map_scraped_to_ipo_input(s)
        name = ipo_input["company_name"].lower().strip()

        if name in existing_names:
            logger.info(f"Skipping duplicate: {ipo_input['company_name']}")
            continue

        # Score it
        try:
            result = calculate_alpha_score(ipo_input)
        except Exception as e:
            logger.warning(f"Scoring failed for {ipo_input.get('company_name')}: {e}")
            continue

        # Peer comparison
        try:
            peer = compare_ipo_to_sector(ipo_input)
            enhanced = enhance_score_with_peers(result, peer)
        except Exception as e:
            logger.warning(f"Peer comparison failed for {ipo_input.get('company_name')}: {e}")
            peer = {"comparison": {}, "valuation_summary": "", "peer_insights": []}
            enhanced = result

        entry = {
            "company_name": ipo_input["company_name"],
            "ticker": ipo_input.get("ticker", ""),
            "market": ipo_input["market"],
            "sector": ipo_input["sector"],
            "offer_price": ipo_input["offer_price"],
            "market_cap": ipo_input["market_cap"],
            "listing_date": ipo_input.get("listing_date", "TBC"),
            "source": ipo_input.get("source", ""),
            "link": ipo_input.get("link", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M"),
            **result,
            "peer_comparison": peer,
            "enhanced_score": enhanced,
        }
        new_entries.append(entry)

    # Merge with existing and save
    all_entries = new_entries + existing
    _save_scores(all_entries)

    return new_entries


def _load_scores() -> list[dict]:
    if SCORES_FILE.exists():
        try:
            with open(SCORES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_scores(data: list[dict]):
    SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Data Quality ────────────────────────────────────────────────────────────

def assess_data_quality(ipo_input: dict) -> str:
    """Score available data fields to tag quality level."""
    fields = {
        "pe_ratio": ipo_input.get("pe_ratio"),
        "sector_avg_pe": ipo_input.get("sector_avg_pe"),
        "oversubscription_rate": ipo_input.get("oversubscription_rate"),
        "net_profit_margin": ipo_input.get("net_profit_margin"),
        "revenue_cagr_3yr": ipo_input.get("revenue_cagr_3yr"),
        "proceeds_utilization": ipo_input.get("proceeds_utilization", {}),
        "shariah_compliant": ipo_input.get("shariah_compliant"),
        "promoter_ownership_pct": ipo_input.get("promoter_ownership_pct"),
        "public_float_pct": ipo_input.get("public_float_pct"),
    }
    # Count non-non-empty values
    filled = sum(1 for v in fields.values() if v is not None and v != {})
    if filled >= 5:
        return "HIGH"
    elif filled >= 2:
        return "MEDIUM"
    return "LOW"


def batch_scrape_all(limit: int = 100) -> list[dict]:
    """
    Scrape ALL IPOs from Bursa, score each, tag data quality, return list.
    Results NOT saved to file — pure in-memory for dashboard display.
    """
    from scoring_engine import calculate_alpha_score
    from peer_comparison import compare_ipo_to_sector, enhance_score_with_peers

    scraped = scrape_current_ipos(limit=limit)
    if not scraped:
        return []

    results = []
    for s in scraped:
        ipo_input = map_scraped_to_ipo_input(s)

        # Data quality assessment
        quality = assess_data_quality(ipo_input)

        try:
            result = calculate_alpha_score(ipo_input)
        except Exception as e:
            logger.warning(f"Scoring failed for {ipo_input.get('company_name')}: {e}")
            continue

        try:
            peer = compare_ipo_to_sector(ipo_input)
            enhanced = enhance_score_with_peers(result, peer)
        except Exception as e:
            logger.warning(f"Peer comparison failed: {e}")
            peer = {"comparison": {}, "valuation_summary": "", "peer_insights": []}
            enhanced = result

        entry = {
            "company_name": ipo_input["company_name"],
            "ticker": ipo_input.get("ticker", ""),
            "market": ipo_input["market"],
            "sector": ipo_input["sector"],
            "offer_price": ipo_input["offer_price"],
            "market_cap": ipo_input["market_cap"],
            "listing_date": ipo_input.get("listing_date", "TBC"),
            "link": ipo_input.get("link", ""),
            "source": ipo_input.get("source", "klse_screener"),
            "data_quality": quality,
            "timestamp": time.strftime("%Y-%m-%d %H:%M"),
            **result,
            "peer_comparison": peer,
            "enhanced_score": enhanced,
        }
        results.append(entry)

    # Sort by score descending
    results.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    return results


# ── Standalone test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Auto-scanning Bursa IPOs...")
    results = auto_scan_and_score(limit=5)
    print(f"\nScored {len(results)} new IPOs:")
    for r in results:
        print(f"  {r['company_name']} ({r.get('ticker','')}) — {r.get('market','')} — {r['total_score']}/100 — {r['verdict']}")
        print(f"    Link: {r.get('link','')}")
