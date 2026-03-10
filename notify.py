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
    "Jura": "🧀",
    "Loire": "🌸",
    "Burgundy": "🤍",
    "Beaujolais": "🍒",
    "Rhone": "🌑",
    "Germany/Austria": "🌿",
    "Spain": "🇪🇸",
    "California": "🌲",
    "Piedmont": "🏔️",
}


def get_exact_wine_prices(producer_name: str, wine_name: str = "") -> list[dict]:
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


def get_restaurant_source(producer: str) -> str:
    """Get the restaurant(s) that whitelisted this producer."""
    rows = get_conn().execute("""
        SELECT DISTINCT s.restaurant FROM sources s
        JOIN producer_sources ps ON ps.source_id = s.id
        JOIN producers p ON p.id = ps.producer_id
        WHERE p.name = ?
    """, (producer,)).fetchall()
    return ", ".join(r[0] for r in rows)


def fmt_price(p) -> str:
    try:
        return str(int(float(p)))
    except (TypeError, ValueError):
        return str(p) if p else "?"


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
        rest_source = get_restaurant_source(producer)
        src_str = f" <i>({escape(rest_source)})</i>" if rest_source else ""
        out = [f"\n<b>{escape(producer)}</b>{src_str}"]

        # Get restaurant prices for exact wine matching (dedupe)
        exact_rest = get_exact_wine_prices(producer, "")
        seen_rest = {}
        for r in exact_rest:
            key = (r["restaurant"], r["name"])
            if key not in seen_rest:
                seen_rest[key] = r

        # Sort by price asc, exact matches first, limit to 3
        sorted_wines = sorted(wines, key=lambda w: (w.get("match_type") != "exact", float(w.get("price") or 9999)))
        display_wines = sorted_wines[:3]

        for w in display_wines:
            price = fmt_price(w.get("price"))
            source = escape(w["source"])
            name = escape(w["name"])

            rest_price_str = ""
            if w.get("match_type") == "exact":
                for r in seen_rest.values():
                    rp = fmt_price(r.get("price"))
                    rest_price_str = f" <i>({escape(r['restaurant'])}, {rp})</i>"
                    break

            out.append(f"  <a href=\"{w['url']}\">{name}</a> — {source} {price}{rest_price_str}")

        if len(wines) > 3:
            out.append(f"  <i>+{len(wines) - 3} more wines</i>")

        return out

    MAX_PRODUCERS = 5

    # Styled sections
    for style in STYLE_EMOJI:
        items = styled.get(style, [])
        if not items:
            continue
        lines.append(f"\n<b>{escape(style)}</b>")
        for producer, info in items[:MAX_PRODUCERS]:
            lines.extend(format_producer(producer, info))
        if len(items) > MAX_PRODUCERS:
            lines.append(f"<i>+{len(items) - MAX_PRODUCERS} more</i>")

    # Discovery section
    if unstyled:
        lines.append(f"\n<b>Other</b>")
        for producer, info in unstyled[:MAX_PRODUCERS]:
            lines.extend(format_producer(producer, info))
        if len(unstyled) > MAX_PRODUCERS:
            lines.append(f"<i>+{len(unstyled) - MAX_PRODUCERS} more</i>")

    return "\n".join(lines)


def send_telegram(message: str):
    if not TELEGRAM_TOKEN:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Split at producer boundaries (\n<b>) to avoid cutting HTML mid-tag
    if len(message) <= 4000:
        chunks = [message]
    else:
        parts = message.split("\n<b>")
        chunks = []
        current = ""
        for i, part in enumerate(parts):
            section = ("" if i == 0 else "\n<b>") + part
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


def notify_summary(hits: list[dict], shop_count: int = 1, report_url: str = None):
    """Send a short Telegram summary with a link to the full HTML report."""
    from collections import Counter
    from match import find_hits

    by_producer = {}
    for h in hits:
        by_producer[h["matched_producer"]] = h

    total = len(by_producer)
    exact = sum(1 for h in by_producer.values() if h.get("match_type") == "exact")
    producer = total - exact

    from datetime import datetime
    date_str = datetime.utcnow().strftime("%d %b %Y")

    lines = [f"🍷 <b>Parcelle — {date_str}</b>"]
    lines.append(f"<i>{shop_count} shops · {exact} exact · {producer} producer matches</i>")

    if report_url:
        lines.append(f"\n<a href=\"{report_url}\">View full report →</a>")

    send_telegram("\n".join(lines))
