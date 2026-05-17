"""
Bursa Malaysia IPO Scraper — Playwright + KLSE Screener.

Primary: KLSE Screener /v2/ipos (reliable, structured)
Secondary: KLSE Screener news (latest announcements)
"""

import json
import logging
import re
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

PAGE_TIMEOUT = 30000
DAYS = {'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'}
MONTHS = {'JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'}


async def get_current_ipos_async(limit: int = 3) -> list[dict]:
    """Scrape current IPO listings using Playwright."""
    from playwright.async_api import async_playwright

    ipos = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-gpu"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        ipos.extend(await _scrape_klse_ipos(context))
        ipos.extend(await _scrape_klse_news(context))

        await browser.close()

    # Deduplicate
    seen = set()
    unique = []
    for ipo in ipos:
        key = re.sub(r'\s+(berhad|bhd|holdings?)$', '', ipo["name"], flags=re.IGNORECASE).lower().strip()
        if key not in seen and key:
            seen.add(key)
            unique.append(ipo)

    unique.sort(key=lambda x: x.get("date", ""), reverse=True)
    return unique[:limit]


def get_current_ipos(limit: int = 3) -> list[dict]:
    return asyncio.run(get_current_ipos_async(limit))


async def _scrape_klse_ipos(context) -> list[dict]:
    """Scrape KLSE Screener /v2/ipos — structured IPO data."""
    ipos = []

    try:
        page = await context.new_page()
        await page.goto(
            "https://www.klsescreener.com/v2/ipos",
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )
        await page.wait_for_timeout(3000)

        text = await page.evaluate('() => document.body.innerText')
        ipos = _parse_klse_text(text)

        logger.info(f"KLSE IPOs: found {len(ipos)} entries")
        await page.close()

    except Exception as e:
        logger.warning(f"KLSE IPOs failed: {e}")

    return ipos


def _parse_klse_text(text: str) -> list[dict]:
    """Parse IPO entries from KLSE Screener page text."""
    ipos = []
    lines = text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Ticker: 2-6 uppercase, not a month/day
        if re.match(r'^[A-Z]{2,6}$', line) and line not in MONTHS and line not in DAYS:
            ticker = line
            if i + 1 < len(lines):
                name = lines[i + 1].strip()
                if len(name) > 5 and name not in DAYS:
                    ctx_lines = lines[i + 2:min(i + 15, len(lines))]
                    context = '\n'.join(ctx_lines)

                    board = "Unknown"
                    bm = re.search(r'(LEAP|ACE|Main)\s*Market', context)
                    if bm:
                        board = bm.group(0)

                    price = ""
                    for l in ctx_lines:
                        if re.match(r'^\d+\.\d+$', l.strip()):
                            price = l.strip()
                            break

                    sector = ""
                    sm = re.search(r'Sector:\s*(.+?)(?:\s+Sub\s)', context)
                    if sm:
                        sector = sm.group(1).strip()

                    sub_sector = ""
                    ss = re.search(r'Sub sector:\s*(.+)', context)
                    if ss:
                        sub_sector = ss.group(1).strip()

                    date = ""
                    for j, l in enumerate(ctx_lines):
                        if l.strip() in MONTHS and j + 2 < len(ctx_lines):
                            day_num = re.match(r'^\d{1,2}$', ctx_lines[j + 1].strip())
                            if day_num:
                                date = f"{l.strip()} {ctx_lines[j + 1].strip()}"
                                break

                    open_date = ""
                    om = re.search(r'Open:\s*(.+?)\s*Close:', context)
                    if om:
                        open_date = om.group(1).strip()

                    issue_size = ""
                    im = re.search(r'Issue Size:\s*([^\n]+)', context)
                    if im:
                        issue_size = im.group(1).strip()

                    ipos.append({
                        "name": name,
                        "ticker": ticker,
                        "code": "",
                        "board": board,
                        "price": price,
                        "pe": "",
                        "market_cap": "",
                        "date": date,
                        "sector": sector,
                        "sub_sector": sub_sector,
                        "issue_size": issue_size,
                        "open_date": open_date,
                        "source": "klse_screener",
                        "raw_data": f"{ticker} | {name} | {board} | RM{price} | {sector}",
                        "link": f"https://www.klsescreener.com/v2/stocks/{ticker.lower()}",
                    })
                    i += 2
                    continue
        i += 1

    return ipos


async def _scrape_klse_news(context) -> list[dict]:
    """Scrape KLSE Screener for IPO news."""
    ipos = []

    try:
        page = await context.new_page()
        await page.goto(
            "https://www.klsescreener.com/v2/news?q=IPO",
            wait_until='domcontentloaded',
            timeout=PAGE_TIMEOUT,
        )
        await page.wait_for_timeout(2000)

        text = await page.evaluate('() => document.body.innerText')

        for line in text.split('\n'):
            if 'ipo' in line.lower() and len(line) > 15:
                name = _extract_company_name(line)
                if name:
                    ipos.append({
                        "name": name, "ticker": "", "code": "",
                        "board": "Unknown", "price": "", "pe": "",
                        "market_cap": "", "date": "", "sector": "",
                        "sub_sector": "", "issue_size": "", "open_date": "",
                        "source": "klse_news",
                        "raw_data": line[:200], "link": "",
                        "news_context": line[:200],
                    })

        logger.info(f"KLSE News: found {len(ipos)} articles")
        await page.close()

    except Exception as e:
        logger.warning(f"KLSE News failed: {e}")

    return ipos


def _extract_company_name(text: str) -> str:
    m = re.search(
        r'([A-Z][A-Za-z\s&\-\']+?(?:Berhad|Bhd|Holdings?|Group|Resources|Ventures?))',
        text
    )
    return m.group(1).strip() if m else ""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ipos = asyncio.run(get_current_ipos_async(limit=5))
    for ipo in ipos:
        print(f"\n  {ipo.get('ticker','')} - {ipo['name']}")
        print(f"  Board: {ipo.get('board','?')}, Price: RM{ipo.get('price','?')}, Date: {ipo.get('date','?')}")
        print(f"  Sector: {ipo.get('sector','?')}, Source: {ipo.get('source','?')}")