#!/usr/bin/env python3
"""
IPO Social Card Generator
Generates branded image cards + platform-optimized captions for any IPO.
No external API calls — fully local using Pillow.
"""

import json, os, textwrap
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ─── Paths ──────────────────────────────────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), 'ipo_scores.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'social')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Color Palette ──────────────────────────────────────────────────────────
BG_DARK      = (15, 23, 42)     # #0f172a
BG_CARD      = (30, 41, 59)     # #1e293b
WHITE        = (255, 255, 255)
GOLD         = (245, 176, 65)   # #f5b041 — exact gold
GREEN        = (34, 197, 94)    # #22c55e
RED          = (239, 68, 68)    # #ef4444
GRAY_TEXT    = (148, 163, 184)  # #94a3b8
LIGHT_GRAY   = (203, 213, 225)  # #cbd5e1
DARK_GRAY    = (100, 116, 139)  # #64748b
ACCENT_BLUE  = (56, 178, 172)   # #38b2ac
TRANSPARENT  = None

# ─── Font setup ─────────────────────────────────────────────────────────────
_FONT_CACHE = {}

def _font(name, size):
    """Load font with caching. Falls back to default if not found."""
    key = (name, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    paths = {
        'bold':   ['C:\\Windows\\Fonts\\arialbd.ttf', 'C:\\Windows\\Fonts\\arial.ttf', 'arialbd.ttf'],
        'regular': ['C:\\Windows\\Fonts\\arial.ttf', 'C:\\Windows\\Fonts\\verdana.ttf', 'arial.ttf'],
        'light':  ['C:\\Windows\\Fonts\\arial.ttf', 'C:\\Windows\\Fonts\\arial.ttf'],
    }
    font_name = name.lower()
    if font_name in paths:
        for p in paths[font_name]:
            try:
                f = ImageFont.truetype(p, size)
                _FONT_CACHE[key] = f
                return f
            except (IOError, OSError):
                continue
    try:
        f = ImageFont.truetype(name, size)
        _FONT_CACHE[key] = f
        return f
    except (IOError, OSError):
        _FONT_CACHE[key] = ImageFont.load_default()
        return _FONT_CACHE[key]

# ─── Drawing helpers ────────────────────────────────────────────────────────
def _draw_rounded_rect(draw, xy, radius, fill, outline=None):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline)

def _draw_badge(draw, center_x, y, text, color, font_size=22):
    """Draw a centered badge (e.g. BUY / NEUTRAL / AVOID)."""
    fnt = _font('bold', font_size)
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x = 24
    pad_y = 8
    bw = tw + pad_x * 2
    bh = th + pad_y * 2
    # Rounded rectangle behind badge
    bx = center_x - bw // 2
    by = y - bh // 2
    _draw_rounded_rect(draw, (bx, by, bx + bw, by + bh), 12, color + (40,))
    # Outline
    _draw_rounded_rect(draw, (bx, by, bx + bw, by + bh), 12, None, color)
    draw.text((center_x, y), text, fill=color, font=fnt, anchor='mm')
    return bh

def _truncate(text, max_w, font, draw):
    """Truncate text to fit max_w."""
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + '…', font=font) > max_w:
        text = text[:-1]
    return text + '…'

# ─── Card Generator ────────────────────────────────────────────────────────
def make_card(ipo, platform='telegram', size=None):
    """
    Generate a branded IPO social card.
    
    Args:
        ipo: dict with IPO data
        platform: 'tiktok', 'facebook', 'threads', 'telegram'
        size: optional (w, h) override
    
    Returns:
        PIL Image of the card
    """
    # Platform sizes
    sizes = {
        'tiktok':   (1080, 1920),
        'facebook': (1200, 630),
        'threads':  (1080, 1080),
        'telegram': (1080, 1080),
    }
    w, h = size or sizes.get(platform, (1080, 1080))
    
    img = Image.new('RGB', (w, h), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    s = ipo
    cn = s.get('company_name', 'Unknown')
    ticker = s.get('ticker', '')
    score = s.get('alpha_score', 0) or s.get('total_score', 0)
    verdict = s.get('verdict', 'N/A')
    pe = s.get('pe_ratio', '—')
    margin = s.get('net_margin_pct', '—')
    cagr = s.get('revenue_cagr_pct', '—')
    oversub = s.get('oversubscription_pct', '—')
    shariah = s.get('shariah_compliant', False)
    market = s.get('market', 'ACE')
    sector = s.get('sector', 'General')
    
    verdict_color = GREEN if verdict == 'BUY' else (GOLD if verdict == 'NEUTRAL' else RED)
    is_portrait = h > w
    
    # Responsive sizing
    base = min(w, h)
    padding = int(base * 0.045)
    
    # ── Header bar ──────────────────────────────────────────────────────
    header_h = int(base * 0.1)
    _draw_rounded_rect(draw, (padding, padding, w - padding, padding + header_h),
                       12, BG_CARD)
    # Golden dot
    dot_r = 8
    draw.ellipse([padding + 20 - dot_r, padding + header_h//2 - dot_r,
                  padding + 20 + dot_r, padding + header_h//2 + dot_r],
                 fill=GOLD)
    # Title
    title_fnt = _font('bold', max(14, int(base * 0.032)))
    title_txt = "🚀  IPO ALPHA SCREENER"
    draw.text((padding + 38, padding + header_h // 2), title_txt,
              fill=GOLD, font=title_fnt, anchor='lm')
    
    # ── Company name (centered, large) ──────────────────────────────────
    name_area_y = padding + header_h + int(base * 0.06)
    name_fnt = _font('bold', max(24, int(base * 0.075)))
    name_max_w = w - padding * 4
    company_display = _truncate(cn.upper(), name_max_w, name_fnt, draw)
    draw.text((w // 2, name_area_y), company_display, fill=WHITE,
              font=name_fnt, anchor='mm')
    
    # Ticker below name
    ticker_y = name_area_y + int(base * 0.055)
    if ticker:
        tick_fnt = _font('light', max(14, int(base * 0.033)))
        draw.text((w // 2, ticker_y), ticker, fill=GRAY_TEXT, font=tick_fnt, anchor='mm')
    
    # ── Verdict badge + Score ───────────────────────────────────────────
    badge_y = ticker_y + int(base * 0.08)
    _draw_badge(draw, w // 2, badge_y, verdict, verdict_color, max(18, int(base * 0.04)))
    
    # Score number
    score_y = badge_y + int(base * 0.09)
    score_fnt = _font('bold', max(36, int(base * 0.095)))
    draw.text((w // 2, score_y), f'{score:.0f}', fill=verdict_color,
              font=score_fnt, anchor='mm')
    # Score label
    score_label_y = score_y + int(base * 0.045)
    sl_fnt = _font('regular', max(11, int(base * 0.026)))
    draw.text((w // 2, score_label_y), '/ 100', fill=GRAY_TEXT, font=sl_fnt, anchor='mm')
    
    # ── Metrics card ────────────────────────────────────────────────────
    card_y = score_label_y + int(base * 0.06)
    card_pad = int(base * 0.06)
    card_w = w - padding * 3
    card_h = int((base * 0.38) if is_portrait else (base * 0.5))
    card_x = padding + (w - padding * 2 - card_w) // 2
    _draw_rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h),
                       16, BG_CARD)
    
    # Metrics layout
    metrics_fnt = _font('bold', max(11, int(base * 0.024)))
    val_fnt = _font('bold', max(12, int(base * 0.028)))
    
    def _metric_row(idx, label, value, color=WHITE):
        """Draw a metric row inside the card."""
        row_h = card_h // 6
        y = card_y + 8 + idx * row_h
        x_l = card_x + 22
        x_r = card_x + card_w - 22
        draw.text((x_l, y + row_h // 2), label, fill=GRAY_TEXT, font=metrics_fnt, anchor='lm')
        draw.text((x_r, y + row_h // 2), str(value), fill=color, font=val_fnt, anchor='rm')
        # Divider
        if idx < 5:
            dy = y + row_h
            draw.line([(x_l, dy), (x_r, dy)], fill=DARK_GRAY, width=1)
    
    pe_str = f'{pe:.1f}x' if isinstance(pe, (int, float)) else '—'
    margin_str = f'{margin:.1f}%' if isinstance(margin, (int, float)) else '—'
    cagr_str = f'{cagr:.1f}%' if isinstance(cagr, (int, float)) else '—'
    over_str = f'{oversub:.1f}x' if isinstance(oversub, (int, float)) else '—'
    shariah_str = '✅ Compliant' if shariah else ('❌ Non-Compliant' if shariah is False else '❓ Unknown')
    
    _metric_row(0, 'P/E Ratio', pe_str, LIGHT_GRAY)
    _metric_row(1, 'Net Margin', margin_str, GREEN if isinstance(margin, (int, float)) and margin > 10 else LIGHT_GRAY)
    _metric_row(2, 'Rev Growth', cagr_str, GREEN if isinstance(cagr, (int, float)) and cagr > 10 else LIGHT_GRAY)
    _metric_row(3, 'Oversub', over_str, ACCENT_BLUE)
    _metric_row(4, 'Shariah', shariah_str, GREEN if shariah else LIGHT_GRAY)
    
    # ── Market badge ────────────────────────────────────────────────────
    mkt_h = int(base * 0.04)
    mkt_y = card_y + card_h + int(base * 0.03)
    mkt_str = f'{market} · {sector}'
    mkt_fnt = _font('light', max(10, int(base * 0.022)))
    draw.text((w // 2, mkt_y), mkt_str, fill=DARK_GRAY, font=mkt_fnt, anchor='mm')
    
    # ── Footer ──────────────────────────────────────────────────────────
    footer_y = h - padding - int(base * 0.025)
    foot_fnt = _font('light', max(10, int(base * 0.022)))
    # Divider line
    divider_y = footer_y - int(base * 0.055)
    draw.line([(padding + 30, divider_y), (w - padding - 30, divider_y)],
              fill=DARK_GRAY, width=1)
    draw.text((w // 2, footer_y), 'bursa-ipo-screener.streamlit.app',
              fill=DARK_GRAY, font=foot_fnt, anchor='mm')
    
    # ── Shariah indicator (top-right corner) ────────────────────────────
    if shariah:
        s_label = "✅ SHARIAH" if is_portrait else "S"
        s_fnt = _font('bold', max(10, int(base * 0.024)))
        sx = w - padding - 16
        sy = padding + header_h // 2
        draw.text((sx, sy), s_label, fill=GREEN, font=s_fnt, anchor='rm')
    
    return img


# ─── Caption Generator ──────────────────────────────────────────────────────
def make_captions(ipo):
    """Generate platform-optimized caption texts for an IPO."""
    s = ipo
    cn = s.get('company_name', 'Unknown')
    ticker = s.get('ticker', '')
    score = s.get('alpha_score', 0) or s.get('total_score', 0)
    verdict = s.get('verdict', 'N/A')
    pe = s.get('pe_ratio', '—')
    margin = s.get('net_margin_pct', '—')
    cagr = s.get('revenue_cagr_pct', '—')
    oversub = s.get('oversubscription_pct', '—')
    shariah = '✅ Shariah-compliant' if s.get('shariah_compliant') else 'Non-Shariah'
    market = s.get('market', 'ACE')
    sector = s.get('sector', 'General')
    link = 'https://bursa-ipo-screener.streamlit.app'
    
    pe_str = f'{pe:.1f}x' if isinstance(pe, (int, float)) else 'N/A'
    margin_str = f'{margin:.1f}%' if isinstance(margin, (int, float)) else 'N/A'
    cagr_str = f'{cagr:.1f}%' if isinstance(cagr, (int, float)) else 'N/A'
    over_str = f'{oversub:.1f}x' if isinstance(oversub, (int, float)) else 'N/A'
    
    url = f'{link}?ticker={ticker}' if ticker else link
    score_str = f'{score:.0f}/100'
    
    emoji_map = {'BUY': '🔥', 'NEUTRAL': '⚖️', 'AVOID': '⚠️'}
    emoji = emoji_map.get(verdict, '📊')
    
    # ── TikTok ──────────────────────────────────────────────────────────
    tiktok = (
        f"{emoji} HOT IPO ALERT!\n\n"
        f"{cn} ({ticker}) just hit the market with an Alpha Score of "
        f"{score_str} — that's a {verdict}!\n\n"
        f"📊 Key numbers:\n"
        f"▸ P/E: {pe_str}\n"
        f"▸ Net Margin: {margin_str}\n"
        f"▸ Revenue Growth: {cagr_str}\n"
        f"▸ Oversubscription: {over_str}\n"
        f"{shariah}\n\n"
        f"Full report → {url}\n\n"
        f"#{'IPO'.lower()} #{'BursaMalaysia'.lower()} #{'StockMarket'.lower()} "
        f"#{'Investing'.lower()} #{cn.replace(' ', '').lower()}"
    )
    
    # ── Facebook ────────────────────────────────────────────────────────
    facebook = (
        f"📊 Is {cn} the Next Big IPO on Bursa Malaysia?\n\n"
        f"We ran {cn} through our Alpha Screener and here's what we found:\n\n"
        f"🏆 Alpha Score: {score_str} → {verdict}\n\n"
        f"Key metrics at a glance:\n"
        f"• P/E Ratio: {pe_str} (sector comparison available)\n"
        f"• Net Profit Margin: {margin_str}\n"
        f"• Revenue CAGR (3yr): {cagr_str}\n"
        f"• Oversubscription Rate: {over_str}\n"
        f"• {shariah}\n\n"
        f"Listing on Bursa Malaysia {market} in the {sector} space.\n\n"
        f"→ Check the full analysis and 30-page PDF report at:\n"
        f"{url}\n\n"
        f"#IPOAlerts #BursaMalaysia #InvestmentIdeas #{sector.replace('/', '')}"
    )
    
    # ── Threads ──────────────────────────────────────────────────────────
    threads = (
        f"{emoji} {cn} IPO'd with {score_str} — my take: {verdict}\n\n"
        f"The numbers: PE {pe_str} | Margin {margin_str} | "
        f"CAGR {cagr_str} | Oversub {over_str}\n\n"
        f"{shariah} | {market} Market | {sector}\n\n"
        f"What do you think — is this one to watch? 👇\n\n"
        f"Full analysis → {url}"
    )
    
    # ── Telegram ────────────────────────────────────────────────────────
    telegram = (
        f"🚀 IPO SPOTLIGHT\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🇲🇾 {cn} ({ticker})\n"
        f"📊 Alpha Score: {score_str}\n"
        f"🎯 Verdict: {verdict}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 P/E: {pe_str}\n"
        f"💰 Net Margin: {margin_str}\n"
        f"📈 Rev CAGR: {cagr_str}\n"
        f"👥 Oversub: {over_str}\n"
        f"🕌 {shariah}\n"
        f"🏛️ {market} · {sector}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📄 Full report → {url}"
    )
    
    return {
        'tiktok': tiktok,
        'facebook': facebook,
        'threads': threads,
        'telegram': telegram,
    }


# ─── Batch Generation ───────────────────────────────────────────────────────
def batch_all(output_dir=None):
    """Generate social cards + captions for ALL IPOs in the database."""
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    with open(DATA_FILE) as f:
        data = json.load(f)
    
    results = []
    for ipo in data:
        cn = ipo.get('company_name', 'Unknown')
        ticker = ipo.get('ticker', '')
        safe_name = ticker or cn.replace(' ', '_')
        
        try:
            # Generate caption file
            caps = make_captions(ipo)
            cap_path = os.path.join(output_dir, f'{safe_name}_captions.txt')
            with open(cap_path, 'w', encoding='utf-8') as f:
                for plat, text in caps.items():
                    f.write(f'─── {plat.upper()} ───\n')
                    f.write(text)
                    f.write('\n\n')
            
            # Generate card images (telegram/square default)
            img = make_card(ipo, 'telegram')
            img_path = os.path.join(output_dir, f'{safe_name}_card.png')
            img.save(img_path, quality=92)
            
            results.append((cn, ticker, 'OK'))
        except Exception as e:
            results.append((cn, ticker, f'ERROR: {e}'))
    
    return results


def daily_spotlight(output_dir=None):
    """
    Generate a card + caption for the highest-scoring IPO that hasn't
    been posted today. Creates a 'daily_spolight' marker file.
    """
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    with open(DATA_FILE) as f:
        data = json.load(f)
    
    today = datetime.now().strftime('%Y-%m-%d')
    marker_file = os.path.join(output_dir, f'.daily_{today}')
    posted_file = os.path.join(output_dir, '.posted_spotlights.txt')
    
    # Read previously posted
    posted = set()
    if os.path.exists(posted_file):
        with open(posted_file) as f:
            posted = set(line.strip() for line in f if line.strip())
    
    # Sort by score descending, pick first un-posted
    scored = sorted(data, key=lambda d: d.get('alpha_score', 0) or d.get('total_score', 0), reverse=True)
    pick = None
    for ipo in scored:
        ticker = ipo.get('ticker', '')
        if ticker and ticker not in posted:
            pick = ipo
            break
    if not pick and scored:
        pick = scored[0]  # repeat if all posted
    
    if not pick:
        return None, 'No IPOs in database'
    
    # Generate
    cn = pick.get('company_name', '')
    ticker = pick.get('ticker', '')
    safe_name = ticker or cn.replace(' ', '_')
    
    caps = make_captions(pick)
    cap_path = os.path.join(output_dir, f'{safe_name}_captions.txt')
    with open(cap_path, 'w', encoding='utf-8') as f:
        for plat, text in caps.items():
            f.write(f'─── {plat.upper()} ───\n')
            f.write(text)
            f.write('\n\n')
    
    img = make_card(pick, 'telegram')
    img_path = os.path.join(output_dir, f'{safe_name}_card.png')
    img.save(img_path, quality=92)
    
    # Write marker
    with open(marker_file, 'w') as f:
        f.write(f'{ticker}|{cn}|{datetime.now().isoformat()}')
    
    # Mark as posted
    with open(posted_file, 'a') as f:
        f.write(f'{ticker}\n')
    
    return {
        'ticker': ticker,
        'company': cn,
        'score': pick.get('alpha_score', 0),
        'card': str(img_path),
        'captions': str(cap_path),
    }, None


# ─── CLI ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else 'spotlight'
    
    if mode == 'batch':
        r = batch_all()
        ok = [x for x in r if x[2] == 'OK']
        fail = [x for x in r if x[2] != 'OK']
        print(f'Batch complete: {len(ok)} OK, {len(fail)} failed')
        for f in fail:
            print(f'  ✗ {f[0]} ({f[1]}): {f[2]}')
    elif mode == 'spotlight':
        result, err = daily_spotlight()
        if err:
            print(f'Error: {err}')
        else:
            print(f'Daily spotlight: {result["company"]} ({result["ticker"]}) — Score {result["score"]:.0f}')
            print(f'  Card: {result["card"]}')
            print(f'  Captions: {result["captions"]}')
    elif mode in ('tiktok', 'facebook', 'threads', 'telegram'):
        # Single card for given ticker
        ticker = sys.argv[2] if len(sys.argv) > 2 else None
        with open(DATA_FILE) as f:
            data = json.load(f)
        if not ticker:
            ipo = data[0]
        else:
            ipo = next(
                (d for d in data
                 if ticker.upper() in (d.get('ticker', '') or '').upper()
                 or ticker.lower() in (d.get('company_name', '') or '').lower()),
                data[0]
            )
        cn = ipo.get('company_name', 'Unknown')
        safe = ipo.get('ticker', '') or cn.replace(' ', '_')
        img = make_card(ipo, mode)
        path = os.path.join(OUTPUT_DIR, f'{safe}_card_{mode}.png')
        img.save(path, quality=92)
        print(f'Card saved: {path}')
        caps = make_captions(ipo)
        print(f'\n─── Caption ({mode}) ───')
        print(caps.get(mode, caps['telegram']))
    else:
        print('Usage: python social_generator.py <batch|spotlight|tiktok|facebook|threads|telegram> [ticker]')
