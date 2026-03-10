"""Send Telegram notifications for whitelist hits."""
import os
import requests
from html import escape
from collections import defaultdict
from db import get_conn

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8744489466")

STYLE_EMOJI = {
    "Champagne": "🥂",
    "Pet-nat": "🫧",
    "Orange": "🍊",
    "German/Austrian Riesling": "🌿",
    "German/Austrian Weissburgunder": "🌿",
    "Jura Chardonnay": "🧀",
    "Loire Chenin": "🌸",
    "Burgundy Chardonnay": "🤍",
    "North Rhone Syrah": "🌑",
    "Spanish Tempranillo": "🇪🇸",
    "American Cabernet": "🌲",
    "Loire Cabernet Franc": "🌿",
    "German Spatburgunder": "🍂",
    "Structured Burgundy/Beaujolais": "🔴",
    "Light Beaujolais": "🍒",
    "Piedmont Nebbiolo": "🏔️",
}


def get_restaurant_prices(producer_name: str) -> list[dict]:
    rows = get_conn().execute("""
        SELECT w.name, w.price, s.restaurant
        FROM wines w
        JOIN producers p ON p.id = w.producer_id
        JOIN sources s ON s.id = w.source_id
        WHERE p.name = ?
        ORDER BY CAST(w.price AS INTEGER)
        LIMIT 2
    """, (producer_name,)).fetchall()
    return [dict(r) for r in rows]


def get_producer_styles(producer_name: str) -> list[str]:
    rows = get_conn().execute("""
        SELECT ps.style FROM producer_styles ps
        JOIN producers p ON p.id = ps.producer_id
        WHERE p.name = ?
    """, (producer_name,)).fetchall()
    return [r[0] for r in rows]


def build_message(hits: list[dict], shop_count: int) -> str:
    # Dedupe by producer, keep cheapest retail price per producer
    seen = {}
    for h in hits:
        p = h["matched_producer"]
        if p not in seen or float(h.get("price") or 0) < float(seen[p].get("price") or 9999):
            seen[p] = h

    hits_deduped = list(seen.values())

    # Split into styled vs unstyled
    styled = defaultdict(list)
    unstyled = []

    for h in hits_deduped:
        styles = get_producer_styles(h["matched_producer"])
        if styles:
            for style in styles:
                styled[style].append(h)
                break  # primary style only
        else:
            unstyled.append(h)

    total = len(hits_deduped)
    exact_count = sum(1 for h in hits_deduped if h.get("match_type") == "exact")
    producer_count = total - exact_count
    lines = [
        f"🍷 <b>Parcelle — Weekly Finds</b>",
        f"<i>{shop_count} shop{'s' if shop_count > 1 else ''} · {exact_count} exact · {producer_count} producer</i>",
    ]

    def format_hit(h: dict) -> list[str]:
        rest = get_restaurant_prices(h["matched_producer"])
        rest_str = " / ".join([f"{r['restaurant']}: {r['price']} DKK" for r in rest]) if rest else None
        price = h.get("price", "?")
        match_icon = "🎯" if h.get("match_type") == "exact" else "✓"
        producer_esc = escape(h['matched_producer'])
        name_esc = escape(h['name'])
        source_esc = escape(h['source'])
        out = [f"\n{match_icon} <b>{producer_esc}</b> — {name_esc}"]
        out.append(f"↳ <a href=\"{h['url']}\">{source_esc} · {price} DKK</a>")
        if rest_str:
            out.append(f"↳ <i>{escape(rest_str)}</i>")
        return out

    MAX_PER_SECTION = 5

    # Styled sections
    for style in STYLE_EMOJI:
        items = styled.get(style, [])
        if not items:
            continue
        emoji = STYLE_EMOJI[style]
        lines.append(f"\n━━━━━━━━━━━━━━━")
        lines.append(f"{emoji} <b>{escape(style.upper())}</b>")
        for h in items[:MAX_PER_SECTION]:
            lines.extend(format_hit(h))
        if len(items) > MAX_PER_SECTION:
            lines.append(f"<i>+{len(items) - MAX_PER_SECTION} more</i>")

    # Discovery section (outside defined styles)
    if unstyled:
        lines.append(f"\n━━━━━━━━━━━━━━━")
        lines.append(f"🔍 <b>OUTSIDE YOUR STYLES</b>")
        lines.append(f"<i>Trusted producers — outside your defined styles</i>")
        for h in unstyled[:MAX_PER_SECTION]:
            lines.extend(format_hit(h))
        if len(unstyled) > MAX_PER_SECTION:
            lines.append(f"<i>+{len(unstyled) - MAX_PER_SECTION} more</i>")

    return "\n".join(lines)


def send_telegram(message: str):
    if not TELEGRAM_TOKEN:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Split on section dividers to avoid cutting HTML tags
    if len(message) <= 4000:
        chunks = [message]
    else:
        parts = message.split("\n━━━━━━━━━━━━━━━")
        chunks = []
        current = ""
        for i, part in enumerate(parts):
            section = ("" if i == 0 else "\n━━━━━━━━━━━━━━━") + part
            if len(current) + len(section) > 4000:
                if current:
                    chunks.append(current)
                current = section
            else:
                current += section
        if current:
            chunks.append(current)

    for chunk in chunks:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }, timeout=10)
        if resp.status_code != 200:
            print(f"[ERROR] Telegram: {resp.text}")


def notify_hits(hits: list[dict], shop_count: int = 1):
    if not hits:
        print("[INFO] No whitelist hits found")
        return
    message = build_message(hits, shop_count)
    send_telegram(message)
