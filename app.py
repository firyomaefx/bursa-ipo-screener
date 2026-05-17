"""
Bursa Malaysia IPO Screener — Telegram Bot.

Button-based: /start → Search Now → Top 3 new IPOs analyzed.
Runs Playwright in subprocess to avoid event loop conflicts.
Uses MarkdownV2 with fancy card formatting.
Sends PDF report after analysis.
"""

import os
import json
import logging
import hashlib
import tempfile
import subprocess
import sys
import threading
import time
import concurrent.futures
from pathlib import Path

import requests as http_requests
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from llm_analyzer import analyze_ipo_data, format_analysis_as_markdown, format_summary
from pdf_report import generate_and_send_pdf

# ── Config ──────────────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "kimi-k2.5:cloud")
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "60"))
SEEN_DB = Path(os.path.join(tempfile.gettempdir(), "ipo_seen.json"))
BOT_DIR = Path(__file__).parent

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Telegram Messages ───────────────────────────────────────────────────────

WELCOME_MSG = (
    "🇲🇾 *Bursa IPO Screener*\n"
    "_Powered by Ollama AI × KLSE Screener_\n\n"
    "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
    "📡 *Live data* from KLSE Screener\n"
    "🤖 *AI analysis* via Ollama Cloud\n"
    "⚡ *Results* in \\~30–60 seconds\n\n"
    "▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n\n"
    "Choose an action below 👇"
)

SCANNING_MSG = (
    "🔍 *Initiating IPO Scan\\.\\.\\.*\n\n"
    "┌─────────────────────────┐\n"
    "│ 📡 Connecting to KLSE │\n"
    "│ 🧠 Loading Firdausbot │\n"
    "│ ⏳ ETA: 30–60 seconds │\n"
    "└─────────────────────────┘\n\n"
    "_Please wait while we fetch and analyse the top 3 IPOs for you\\._"
)


def _html(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    if text is None:
        return "N/A"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _send_telegram_md(text: str):
    """Send MarkdownV2 message to Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        http_requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


def _send_telegram_done():
    """Send completion message with Main Menu button."""
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        http_requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": (
                    "✅ *All done\\!*\n\n"
                    "Scan complete, PDF report delivered\\.\n\n"
                    "Tap below to return to main menu 👇"
                ),
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "🏠 Main Menu", "callback_data": "main_menu"}
                    ]]
                },
            },
            timeout=30,
        )
    except Exception as e:
        logger.error(f"Telegram done message failed: {e}")


def _send_telegram_html(text: str):
    """Send HTML message to Telegram (fallback)."""
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        http_requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


def _load_seen() -> dict:
    if SEEN_DB.exists():
        try:
            return json.loads(SEEN_DB.read_text())
        except Exception:
            pass
    return {}


def _save_seen(data: dict):
    SEEN_DB.write_text(json.dumps(data, indent=2))


def _key(name: str) -> str:
    return hashlib.md5(name.lower().strip().encode()).hexdigest()


# ── Scraper (subprocess) ────────────────────────────────────────────────────

def _scrape_ipos_subprocess(limit: int = 3) -> list:
    """Run Playwright scraper in subprocess to avoid asyncio conflicts."""
    script = f"""
import asyncio, json
from ipo_scraper import get_current_ipos_async
ipos = asyncio.run(get_current_ipos_async(limit={limit}))
print(json.dumps(ipos))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=90,
            cwd=str(BOT_DIR),
        )
        if result.returncode != 0:
            logger.error(f"Scraper failed: {result.stderr[:500]}")
            return []

        output = result.stdout
        start = output.find("[")
        if start == -1:
            logger.error(f"No JSON in scraper output: {output[:500]}")
            return []

        json_str = output[start:]
        ipos = json.loads(json_str)
        logger.info(f"Scraper returned {len(ipos)} IPOs")
        return ipos

    except subprocess.TimeoutExpired:
        logger.error("Scraper subprocess timed out")
        return []
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        return []


# ── Search Pipeline ──────────────────────────────────────────────────────────

def _run_search_pipeline():
    """Full pipeline: scrape → analyze → send to Telegram + PDF."""
    try:
        logger.info("Search pipeline started")

        ipos = _scrape_ipos_subprocess(limit=3)

        if not ipos:
            _send_telegram_md(
                "🔍 *No IPOs found right now\\.*\n\n"
                "Sources may be temporarily unavailable\\.\n"
                "Auto\\-monitor keeps checking every hour\\."
            )
            return

        all_analyses = []

        for i, ipo in enumerate(ipos, 1):
            name = ipo.get("name", "Unknown")

            try:
                analysis = analyze_ipo_data(ipo, model=LLM_MODEL, provider=LLM_PROVIDER)
                all_analyses.append(analysis)

                card = format_analysis_as_markdown(analysis)

                # Send in chunks if needed (Telegram limit 4096)
                if len(card) <= 4096:
                    _send_telegram_md(card)
                else:
                    _send_telegram_md(card[:4096])
                    time.sleep(1)
                    remaining = card[4096:]
                    for j in range(0, len(remaining), 4096):
                        _send_telegram_md(remaining[j:j+4096])
                        time.sleep(1)

            except Exception as e:
                logger.exception(f"Analysis failed for {name}")
                _send_telegram_html(
                    f"❌ <b>{name}</b>: Analysis failed - {str(e)[:80]}"
                )

            time.sleep(2)

        # Summary
        if all_analyses:
            summary = format_summary(all_analyses)
            _send_telegram_md(summary)

            # PDF report
            _send_telegram_md("📄 _Generating PDF report with charts\\.\\.\\._")
            try:
                generate_and_send_pdf(
                    analyses=all_analyses,
                    ipo_data_list=ipos,
                    chat_id=CHAT_ID,
                    bot_token=BOT_TOKEN,
                )
                logger.info("PDF report sent successfully")
            except Exception as e:
                logger.exception(f"PDF generation failed: {e}")
                _send_telegram_html(f"❌ PDF report failed: {str(e)[:80]}")

            # Completion message with Main Menu button
            _send_telegram_done()

    except Exception as e:
        logger.exception(f"Search pipeline failed: {e}")
        _send_telegram_html(f"❌ Search error: {str(e)[:150]}")


# ── Telegram Handlers ───────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start — main menu."""
    keyboard = [
        [InlineKeyboardButton("🔍 Search Top 3 IPOs Now", callback_data="search_now")],
        [InlineKeyboardButton("📊 Auto-Monitor Status", callback_data="monitor_status"),
         InlineKeyboardButton("📋 Tracked IPOs", callback_data="tracked_ipos")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        WELCOME_MSG,
        parse_mode="MarkdownV2",
        reply_markup=reply_markup,
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses."""
    query = update.callback_query
    logger.info(f"Callback received: {query.data}")
    await query.answer()

    if query.data == "search_now":
        logger.info("Search now button pressed — starting pipeline")
        await query.edit_message_text(
            SCANNING_MSG,
            parse_mode="MarkdownV2",
        )
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        pool.submit(_run_search_pipeline)
        logger.info("Search pipeline submitted to thread pool")

    elif query.data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("🔍 Search Top 3 IPOs Now", callback_data="search_now")],
            [InlineKeyboardButton("📊 Auto-Monitor Status", callback_data="monitor_status"),
             InlineKeyboardButton("📋 Tracked IPOs", callback_data="tracked_ipos")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            WELCOME_MSG,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup,
        )

    elif query.data == "tracked_ipos":
        seen = _load_seen()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ])
        if not seen:
            await query.edit_message_text(
                "📋 <b>No tracked IPOs yet</b>\n\n"
                "The auto-monitor scans every 60 minutes for new IPOs.\n"
                "When it finds one, it sends analysis to you and saves it here.",
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            lines = "📋 <b>Tracked IPOs</b>\n\n"
            for k, v in seen.items():
                name = _html(v.get("name", "Unknown"))
                verdict = _html(v.get("verdict", ""))
                lines += f"• <b>{name}</b>\n  <i>{verdict}</i>\n\n"
            lines += f"\nTotal: {len(seen)} IPOs tracked"
            try:
                await query.edit_message_text(
                    lines,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
            except Exception as e:
                logger.error(f"tracked_ipos send failed: {e}")
                # Fallback: simpler message
                await query.edit_message_text(
                    f"📋 {len(seen)} IPOs tracked. Check chat for details.",
                    parse_mode="HTML",
                    reply_markup=kb,
                )

    elif query.data == "monitor_status":
        seen = _load_seen()
        count = len(seen)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Tracked IPOs", callback_data="tracked_ipos"),
             InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ])
        await query.edit_message_text(
            f"📊 <b>Auto-Monitor Status</b>\n\n"
            f"✅ Running in background\n"
            f"⏱ Interval: every {CHECK_INTERVAL_MIN} min\n"
            f"📋 IPOs tracked: {count}\n\n"
            f"New IPO alerts sent automatically.",
            parse_mode="HTML",
            reply_markup=kb,
        )


# ── Background Auto-Monitor ────────────────────────────────────────────────

def _monitor_loop():
    """Background thread: auto-discover and analyze new IPOs."""
    time.sleep(15)
    logger.info(f"Auto-monitor started (every {CHECK_INTERVAL_MIN} min)")

    while True:
        try:
            ipos = _scrape_ipos_subprocess(limit=5)
            seen = _load_seen()

            for ipo in ipos:
                k = _key(ipo["name"])
                if k not in seen:
                    name = ipo.get("name", "Unknown")
                    logger.info(f"Monitor: new IPO - {name}")

                    try:
                        analysis = analyze_ipo_data(ipo, model=LLM_MODEL, provider=LLM_PROVIDER)
                        card = format_analysis_as_markdown(analysis)
                        _send_telegram_md(f"🆕 *New IPO Detected\\!*\n\n{card}")
                        seen[k] = {"name": name, "verdict": analysis.get("final_verdict", "")}
                        _save_seen(seen)
                    except Exception as e:
                        logger.exception(f"Monitor: analysis failed for {name}")
                        _send_telegram_html(f"🆕 <b>New IPO:</b> {name}\n❌ Analysis failed")
                        seen[k] = {"name": name, "verdict": "failed"}
                        _save_seen(seen)

                    time.sleep(5)

        except Exception as e:
            logger.exception(f"Monitor loop error: {e}")

        time.sleep(CHECK_INTERVAL_MIN * 60)


# ── Startup ──────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set. Check your .env file.")

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))

    async def post_init(app):
        await app.bot.set_my_commands([
            BotCommand("start", "🇲🇾 IPO Screener"),
        ])

    application.post_init = post_init

    # Background monitor
    monitor = threading.Thread(target=_monitor_loop, daemon=True)
    monitor.start()

    logger.info("Starting bot (polling mode)")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    main()