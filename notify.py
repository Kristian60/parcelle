"""Send Telegram notifications for whitelist hits."""
import os
import requests
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
    lines = [
        f"🍷 <b>Parcelle — Weekly Finds</b>",
        f"<i>{shop_count} shop{'s' if shop_count > 1 else ''} · {total} match{'es' if total != 1 else ''}</i>",
    ]

    # Styled sections
    for style in STYLE_EMOJI:
        items = styled.get(style, [])
        if not items:
            continue
        emoji = STYLE_EMOJI[style]
        lines.append(f"\n━━━━━━━━━━━━━━━")
        lines.append(f"{emoji} <b>{style.upper()}</b>")
        for h in items:
            rest = get_restaurant_prices(h["matched_producer"])
            rest_str = " / ".join([f"{r['restaurant']}: {r['price']} DKK" for r in rest]) if rest else None
            price = h.get("price", "?")
            lines.append(f"\n<b>{h['matched_producer']}</b> — {h['name']}")
            lines.append(f"↳ <a href=\"{h['url']}\">{h['source']} · {price} DKK</a>")
            if rest_str:
                lines.append(f"↳ <i>{rest_str}</i>")

    # Discovery section (outside defined styles)
    if unstyled:
        lines.append(f"\n━━━━━━━━━━━━━━━")
        lines.append(f"🔍 <b>OUTSIDE YOUR STYLES</b>")
        lines.append(f"<i>Producers Levi trusted — outside your defined styles</i>")
        for h in unstyled:
            price = h.get("price", "?")
            lines.append(f"\n<b>{h['matched_producer']}</b> — {h['name']}")
            lines.append(f"↳ <a href=\"{h['url']}\">{h['source']} · {price} DKK</a>")

    return "\n".join(lines)


def send_telegram(message: str):
    if not TELEGRAM_TOKEN:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # Split if too long (Telegram limit 4096 chars)
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
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
