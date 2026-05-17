"""
Bursa Malaysia IPO Auto-Discovery & Monitoring.

Scrapes official Bursa sources for new IPO listings,
downloads prospectuses, analyzes them, and notifies via Telegram.
"""

import os
import re
import json
import logging
import time
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Your Telegram user ID for notifications
LLM_MODEL = os.getenv("LLM_MODEL", "kimi-k2.5:cloud")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
MAX_PDF_SIZE_MB = int(os.getenv("MAX_PDF_SIZE_MB", "20"))
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "60"))  # How often to check

import tempfile
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", os.path.join(tempfile.gettempdir(), "ipo_pdfs")))
SEEN_DB = Path(os.path.join(tempfile.gettempdir(), "ipo_seen.json"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── IPO Sources ─────────────────────────────────────────────────────────────

# Bursa Malaysia official IPO page
BURSA_IPO_URL = "https://www.bursamalaysia.com/market_information/listings_directory/initial_public_offering"

# Bursa API endpoint for IPO listings (JSON)
BURSA_API_URL = "https://www.bursamalaysia.com/market_information/listings_directory/initial_public_offering?_=1"

# Alternative: Bursa announcements feed
BURSA_ANNOUNCEMENTS_URL = "https://www.bursamalaysia.com/market_information/announcements"

# SC (Securities Commission) Malaysia IPO disclosures
SC_IPO_URL = "https://www.sc.com.my/regulation/corporate-fund-raising/initial-public-offerings"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-MY,en;q=0.9",
}


def load_seen_ipos() -> dict:
    """Load previously seen IPOs to avoid re-processing."""
    if SEEN_DB.exists():
        try:
            return json.loads(SEEN_DB.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_seen_ipos(data: dict):
    """Persist seen IPOs to disk."""
    SEEN_DB.write_text(json.dumps(data, indent=2))


def _ipo_key(name: str) -> str:
    """Generate a unique key for an IPO by name."""
    return hashlib.md5(name.lower().strip().encode()).hexdigest()


# ── Scrapers ─────────────────────────────────────────────────────────────────

def scrape_bursa_ipos() -> list[dict]:
    """
    Scrape Bursa Malaysia IPO directory for current listings.
    Returns list of dicts: {name, board, status, prospectus_url, announcement_date}
    """
    ipos = []

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        # Try the main IPO page
        resp = session.get(BURSA_IPO_URL, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # Parse IPO entries from HTML
        # Bursa listing entries typically have this structure:
        # Company name | Board (Main/ACE) | Status | Prospectus link

        # Pattern 1: Look for IPO listing table rows
        # Bursa uses dynamic rendering, so we look for data attributes
        company_pattern = re.compile(
            r'<td[^>]*class="[^"]*company[^"]*"[^>]*>\s*'
            r'<a[^>]*href="(?P<url>[^"]*)"[^>]*>\s*'
            r'(?P<name>[^<]+)\s*</a>',
            re.IGNORECASE | re.DOTALL
        )

        # Pattern 2: Alternative — look for listing directory cards
        card_pattern = re.compile(
            r'data-company-name="(?P<name>[^"]+)"[^>]*'
            r'(?:data-board="(?P<board>[^"]+)")?[^>]*'
            r'data-status="(?P<status>[^"]+)"',
            re.IGNORECASE
        )

        # Pattern 3: Generic link patterns for prospectus PDFs
        pdf_link_pattern = re.compile(
            r'href="(?P<url>[^"]*prospectus[^"]*\.pdf)"[^>]*>'
            r'(?P<name>[^<]+)</a>',
            re.IGNORECASE
        )

        # Try card pattern first
        for match in card_pattern.finditer(html):
            name = match.group("name").strip()
            board = match.group("board") or "Unknown"
            status = match.group("status") or "Active"
            ipos.append({
                "name": name,
                "board": board,
                "status": status,
                "prospectus_url": "",
                "source": "bursa_directory",
            })

        # Try company pattern
        for match in company_pattern.finditer(html):
            name = match.group("name").strip()
            url = match.group("url").strip()
            if url and not url.startswith("http"):
                url = f"https://www.bursamalaysia.com{url}"
            ipos.append({
                "name": name,
                "board": "Unknown",
                "status": "Active",
                "prospectus_url": url,
                "source": "bursa_directory",
            })

        # Try PDF link pattern
        for match in pdf_link_pattern.finditer(html):
            url = match.group("url").strip()
            name = match.group("name").strip()
            if url and not url.startswith("http"):
                url = f"https://www.bursamalaysia.com{url}"
            ipos.append({
                "name": name,
                "board": "Unknown",
                "status": "Active",
                "prospectus_url": url,
                "source": "bursa_prospectus",
            })

        logger.info(f"Bursa directory: found {len(ipos)} IPO entries")

    except requests.RequestException as e:
        logger.warning(f"Failed to scrape Bursa IPO directory: {e}")

    return ipos


def scrape_bursa_announcements() -> list[dict]:
    """
    Scrape Bursa announcements for IPO-related filings.
    This catches new prospectus uploads, listing dates, etc.
    """
    ipos = []

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        resp = session.get(BURSA_ANNOUNCEMENTS_URL, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # Look for IPO-related announcements
        ipo_keywords = [
            "prospectus", "initial public offering", "IPO",
            "listing", "public issue", "offer for sale",
            "prospectus date", "listing by introduction",
        ]

        # Find announcement links that mention IPO keywords
        announcement_pattern = re.compile(
            r'<a[^>]*href="(?P<url>[^"]*)"[^>]*>\s*'
            r'(?P<title>[^<]*(?:' + "|".join(ipo_keywords) + r')[^<]*)\s*'
            r'</a>',
            re.IGNORECASE
        )

        for match in announcement_pattern.finditer(html):
            title = match.group("title").strip()
            url = match.group("url").strip()
            if url and not url.startswith("http"):
                url = f"https://www.bursamalaysia.com{url}"
            ipos.append({
                "name": title,
                "board": "Unknown",
                "status": "Announced",
                "prospectus_url": url,
                "source": "bursa_announcements",
            })

        logger.info(f"Bursa announcements: found {len(ipos)} IPO entries")

    except requests.RequestException as e:
        logger.warning(f"Failed to scrape Bursa announcements: {e}")

    return ipos


def scrape_sc_ipos() -> list[dict]:
    """Scrape Securities Commission Malaysia for new IPO approvals."""
    ipos = []

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        resp = session.get(SC_IPO_URL, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # SC lists approved IPOs
        # Look for company names and links
        sc_pattern = re.compile(
            r'<(?:td|li|div)[^>]*>\s*'
            r'(?:<a[^>]*href="(?P<url>[^"]*)"[^>]*>)?\s*'
            r'(?P<name>[A-Z][A-Za-z\s]+(?:Berhad|Bhd|Holdings?))\s*'
            r'(?:</a>)?\s*</',
            re.IGNORECASE
        )

        for match in sc_pattern.finditer(html):
            name = match.group("name").strip()
            url = match.group("url") or ""
            if url and not url.startswith("http"):
                url = f"https://www.sc.com.my{url}"
            ipos.append({
                "name": name,
                "board": "Unknown",
                "status": "SC Approved",
                "prospectus_url": url,
                "source": "sc_malaysia",
            })

        logger.info(f"SC Malaysia: found {len(ipos)} IPO entries")

    except requests.RequestException as e:
        logger.warning(f"Failed to scrape SC Malaysia: {e}")

    return ipos


def find_prospectus_pdf(company_name: str) -> Optional[str]:
    """
    Try to find the prospectus PDF URL for a given company.
    Searches Bursa document repository.
    """
    # Clean the name for search
    clean_name = re.sub(r'\s+(berhad|bhd|holdings?)$', '', company_name, flags=re.IGNORECASE)
    search_query = requests.utils.quote(f"{clean_name} prospectus site:bursamalaysia.com")

    try:
        # Search Bursa directly
        search_url = f"https://www.bursamalaysia.com/search?q={search_query}"
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(search_url, timeout=20)
        resp.raise_for_status()

        # Find PDF links in search results
        pdf_pattern = re.compile(
            r'href="([^"]*\.pdf[^"]*)"',
            re.IGNORECASE
        )
        for match in pdf_pattern.finditer(resp.text):
            url = match.group(1)
            if url and not url.startswith("http"):
                url = f"https://www.bursamalaysia.com{url}"
            if "prospectus" in url.lower() or "ipo" in url.lower():
                return url

    except Exception as e:
        logger.warning(f"Prospectus search failed for {company_name}: {e}")

    return None


def download_pdf(url: str, filename: str) -> Optional[Path]:
    """Download a PDF from URL to local disk."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DOWNLOAD_DIR / filename

    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(url, timeout=60, stream=True)
        resp.raise_for_status()

        # Check size
        content_length = int(resp.headers.get("content-length", 0))
        if content_length > MAX_PDF_SIZE_MB * 1024 * 1024:
            logger.warning(f"PDF too large: {content_length / 1024 / 1024:.1f}MB")
            return None

        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded: {file_path} ({file_path.stat().st_size / 1024:.0f}KB)")
        return file_path

    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return None


# ── Telegram Notification ────────────────────────────────────────────────────

def send_telegram_message(text: str, parse_mode: str = "MarkdownV2"):
    """Send a message to the configured Telegram chat."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


def _esc(text: str) -> str:
    """Escape for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text


# ── Main Monitoring Loop ────────────────────────────────────────────────────

def discover_new_ipos() -> list[dict]:
    """
    Run all scrapers and return new (unseen) IPOs.
    """
    all_ipos = []

    # Run all scrapers
    all_ipos.extend(scrape_bursa_ipos())
    all_ipos.extend(scrape_bursa_announcements())
    all_ipos.extend(scrape_sc_ipos())

    # Deduplicate by name
    seen_names = set()
    unique_ipos = []
    for ipo in all_ipos:
        key = _ipo_key(ipo["name"])
        if key not in seen_names:
            seen_names.add(key)
            unique_ipos.append(ipo)

    # Filter out already-processed IPOs
    seen_db = load_seen_ipos()
    new_ipos = []
    for ipo in unique_ipos:
        key = _ipo_key(ipo["name"])
        if key not in seen_db:
            new_ipos.append(ipo)

    logger.info(f"Discovered {len(unique_ipos)} total IPOs, {len(new_ipos)} new")
    return new_ipos


def process_new_ipo(ipo: dict):
    """
    Process a single new IPO: find prospectus, download, analyze, notify.
    """
    name = ipo["name"]
    logger.info(f"Processing new IPO: {name}")

    # Notify user about discovery
    board = ipo.get("board", "Unknown")
    status = ipo.get("status", "Active")
    source = ipo.get("source", "unknown")

    send_telegram_message(
        f"🆕 *New IPO Detected\\!*\n\n"
        f"*Company:* {_esc(name)}\n"
        f"*Board:* {_esc(board)}\n"
        f"*Status:* {_esc(status)}\n"
        f"*Source:* {_esc(source)}\n\n"
        f"🔍 Searching for prospectus\\.\\.\\.",
    )

    # Try to find and download prospectus
    pdf_url = ipo.get("prospectus_url")
    if not pdf_url:
        pdf_url = find_prospectus_pdf(name)

    if not pdf_url:
        send_telegram_message(
            f"⚠️ {_esc(name)}: Could not find prospectus PDF\\.\n"
            f"Will retry on next check\\.",
        )
        return

    # Download
    safe_filename = re.sub(r'[^\w\-.]', '_', name) + ".pdf"
    file_path = download_pdf(pdf_url, safe_filename)

    if not file_path:
        send_telegram_message(
            f"⚠️ {_esc(name)}: Prospectus download failed\\.",
        )
        return

    try:
        # Extract and analyze
        from pdf_processor import extract_prospectus_data
        from llm_analyzer import analyze_ipo, format_analysis_as_markdown

        send_telegram_message(
            f"📊 {_esc(name)}: Analyzing prospectus\\.\\.\\.\\n"
            f"This may take 30\\-60s\\.",
        )

        extracted = extract_prospectus_data(str(file_path))
        total_chars = sum(len(v) for v in extracted.values())

        if total_chars < 200:
            send_telegram_message(
                f"⚠️ {_esc(name)}: Prospectus text extraction failed\\. "
                f"May be scanned/image PDF\\.",
            )
            return

        analysis = analyze_ipo(extracted, model=LLM_MODEL, provider=LLM_PROVIDER)
        markdown_text = format_analysis_as_markdown(analysis)

        # Send analysis (split if needed)
        if len(markdown_text) <= 4096:
            send_telegram_message(markdown_text)
        else:
            send_telegram_message(markdown_text[:4096])
            remaining = markdown_text[4096:]
            for i in range(0, len(remaining), 4096):
                time.sleep(1)  # Rate limit
                send_telegram_message(remaining[i:i + 4096])

        # Mark as processed
        seen_db = load_seen_ipos()
        key = _ipo_key(name)
        seen_db[key] = {
            "name": name,
            "processed_at": datetime.now().isoformat(),
            "verdict": analysis.get("final_verdict", ""),
        }
        save_seen_ipos(seen_db)

        logger.info(f"Completed analysis for {name}")

    except Exception as e:
        logger.exception(f"Analysis failed for {name}: {e}")
        send_telegram_message(
            f"❌ {_esc(name)}: Analysis failed \\- {_esc(str(e)[:100])}\\.",
        )

    finally:
        # Cleanup
        if file_path and file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass


def run_monitor():
    """
    Main monitoring loop. Runs continuously, checking for new IPOs
    at the configured interval.
    """
    logger.info(f"Starting IPO monitor (checking every {CHECK_INTERVAL_MIN} min)")

    send_telegram_message(
        "🟢 *Bursa IPO Monitor Started\\!*\n\n"
        f"Checking every {CHECK_INTERVAL_MIN} minutes\n"
        "Sources:\n"
        "• Bursa Malaysia IPO Directory\n"
        "• Bursa Announcements\n"
        "• Securities Commission Malaysia",
    )

    while True:
        try:
            new_ipos = discover_new_ipos()

            for ipo in new_ipos:
                try:
                    process_new_ipo(ipo)
                except Exception as e:
                    logger.exception(f"Error processing {ipo['name']}: {e}")
                time.sleep(5)  # Rate limit between IPOs

        except Exception as e:
            logger.exception(f"Monitor loop error: {e}")

        # Wait before next check
        logger.info(f"Next check in {CHECK_INTERVAL_MIN} minutes")
        time.sleep(CHECK_INTERVAL_MIN * 60)


if __name__ == "__main__":
    import sys
    if "--discover" in sys.argv:
        # One-shot discovery mode
        ipos = discover_new_ipos()
        for ipo in ipos:
            print(f"  {ipo['name']} [{ipo['board']}] - {ipo['source']}")
    elif "--process" in sys.argv:
        # Process a specific IPO by name
        name = " ".join(sys.argv[sys.argv.index("--process") + 1:])
        process_new_ipo({"name": name, "board": "Unknown", "status": "Manual"})
    else:
        # Continuous monitoring
        run_monitor()