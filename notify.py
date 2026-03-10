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


def get_exact_wine_prices(producer_name: str, wine_name: str) -> list[dict]:
    """Get restaurant prices for a specific wine (for exact matches only)."""
    rows = get_conn().execute("""
        SELECT DISTINCT w.name, w.price, s.restaurant
        FROM wines w
        JOIN producers p ON p.id = w.producer_id
        JOIN sources s ON s.id = w.source_id
        WHERE p.name = ?
        ORDER BY CAST(w.price AS INTEGER)
        LIMIT 3
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
    # Group all wines by producer
    by_producer = defaultdict(list)
    for h in hits:
        by_producer[h["matched_producer"]].append(h)

    # For each producer, determine primary style and if any wine is exact match
    producer_info = {}
    for producer, wines in by_producer.items():
        styles = get_producer_styles(producer)
        has_exact = any(w.get("match_type") == "exact" for w in wines)
        producer_info[producer] = {
            "style": styles[0] if styles else None,
            "has_exact": has_exact,
            "wines": wines,
        }

    # Split into styled vs unstyled
    styled = defaultdict(list)
    unstyled = []
    for producer, info in producer_info.items():
        if info["style"]:
            styled[info["style"]].append((producer, info))
        else:
            unstyled.append((producer, info))

    total_producers = len(producer_info)
    exact_count = sum(1 for info in producer_info.values() if info["has_exact"])
    producer_count = total_producers - exact_count

    lines = [
        f"🍷 <b>Parcelle — Weekly Finds</b>",
        f"<i>{shop_count} shop{'s' if shop_count > 1 else ''} · {exact_count} exact · {producer_count} producer</i>",
    ]

    def format_producer(producer: str, info: dict) -> list[str]:
        wines = info["wines"]
        has_exact = info["has_exact"]
        icon = "🎯" if has_exact else "✓"
        out = [f"\n{icon} <b>{escape(producer)}</b>"]

        # Show each wine as a sub-item
        for w in wines:
            price = w.get("price", "?")
            source = escape(w["source"])
            name = escape(w["name"])
            line = f"  · <a href=\"{w['url']}\">{name} — {source} {price} DKK</a>"
            out.append(line)

        # Restaurant price only for exact matches
        if has_exact:
            rest = get_exact_wine_prices(producer, wines[0]["name"])
            if rest:
                # Dedupe restaurant entries
                seen_prices = set()
                rest_parts = []
                for r in rest:
                    key = (r["restaurant"], r["price"])
                    if key not in seen_prices:
                        seen_prices.add(key)
                        rest_parts.append(f"{escape(r['restaurant'])}: {r['price']} DKK")
                if rest_parts:
                    out.append(f"  <i>↳ Restaurant: {' / '.join(rest_parts)}</i>")

        return out

    MAX_PRODUCERS = 5

    # Styled sections
    for style in STYLE_EMOJI:
        items = styled.get(style, [])
        if not items:
            continue
        emoji = STYLE_EMOJI[style]
        lines.append(f"\n━━━━━━━━━━━━━━━")
        lines.append(f"{emoji} <b>{escape(style.upper())}</b>")
        for producer, info in items[:MAX_PRODUCERS]:
            lines.extend(format_producer(producer, info))
        if len(items) > MAX_PRODUCERS:
            lines.append(f"<i>  +{len(items) - MAX_PRODUCERS} more producers</i>")

    # Discovery section
    if unstyled:
        lines.append(f"\n━━━━━━━━━━━━━━━")
        lines.append(f"🔍 <b>OUTSIDE YOUR STYLES</b>")
        lines.append(f"<i>Trusted producers — explore at your own risk</i>")
        for producer, info in unstyled[:MAX_PRODUCERS]:
            lines.extend(format_producer(producer, info))
        if len(unstyled) > MAX_PRODUCERS:
            lines.append(f"<i>  +{len(unstyled) - MAX_PRODUCERS} more producers</i>")

    return "\n".join(lines)


def send_telegram(message: str):
    if not TELEGRAM_TOKEN:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Split on section dividers to avoid cutting HTML tags mid-tag
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
