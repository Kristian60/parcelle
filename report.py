"""
Generate a static HTML report from the latest scrape results.
"""
from html import escape
from datetime import datetime
from collections import defaultdict
from notify import STYLE_EMOJI, get_restaurant_source, get_exact_wine_prices, fmt_price
from db import get_conn


def get_producer_styles(producer_name: str) -> list[str]:
    rows = get_conn().execute("""
        SELECT ps.style FROM producer_styles ps
        JOIN producers p ON p.id = ps.producer_id
        WHERE p.name = ?
    """, (producer_name,)).fetchall()
    return [r[0] for r in rows]


def build_html(hits: list[dict]) -> str:
    # Group by producer
    by_producer = defaultdict(list)
    for h in hits:
        by_producer[h["matched_producer"]].append(h)

    # Organise producers by style
    styled = defaultdict(list)
    unstyled = []
    for producer, wines in by_producer.items():
        styles = get_producer_styles(producer)
        has_exact = any(w.get("match_type") == "exact" for w in wines)
        info = {"wines": wines, "has_exact": has_exact, "style": styles[0] if styles else None}
        if styles:
            styled[styles[0]].append((producer, info))
        else:
            unstyled.append((producer, info))

    date_str = datetime.utcnow().strftime("%d %b %Y")
    total = len(by_producer)
    exact_count = sum(1 for wines in by_producer.values() if any(w.get("match_type") == "exact" for w in wines))

    def producer_card(producer: str, info: dict) -> str:
        wines = sorted(info["wines"], key=lambda w: (w.get("match_type") != "exact", float(w.get("price") or 9999)))
        rest_source = get_restaurant_source(producer)
        exact_rest = get_exact_wine_prices(producer, "")
        seen_rest = {}
        for r in exact_rest:
            key = (r["restaurant"], r["name"])
            if key not in seen_rest:
                seen_rest[key] = r

        badge = '<span class="badge exact">exact</span>' if info["has_exact"] else '<span class="badge producer">producer</span>'
        src_str = f'<span class="source">{escape(rest_source)}</span>' if rest_source else ""

        wine_rows = ""
        for w in wines:
            price = fmt_price(w.get("price"))
            rest_price_str = ""
            if w.get("match_type") == "exact":
                for r in seen_rest.values():
                    rp = fmt_price(r.get("price"))
                    rest_price_str = f'<span class="rest-price">{escape(r["restaurant"])} {rp}</span>'
                    break
            wine_rows += f"""
            <div class="wine-row">
              <a href="{w['url']}" target="_blank">{escape(w['name'])}</a>
              <span class="shop">{escape(w['source'])}</span>
              <span class="price">{price}</span>
              {rest_price_str}
            </div>"""

        return f"""
        <div class="producer-card">
          <div class="producer-header">
            <span class="producer-name">{escape(producer)}</span>
            {src_str}
            {badge}
          </div>
          <div class="wines">{wine_rows}
          </div>
        </div>"""

    sections = ""
    for style in STYLE_EMOJI:
        items = styled.get(style, [])
        if not items:
            continue
        cards = "".join(producer_card(p, i) for p, i in items)
        sections += f"""
      <section>
        <h2>{escape(style)}</h2>
        {cards}
      </section>"""

    if unstyled:
        cards = "".join(producer_card(p, i) for p, i in unstyled)
        sections += f"""
      <section>
        <h2>Other</h2>
        {cards}
      </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Parcelle — {date_str}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f9f7f4; color: #1a1a1a; max-width: 720px; margin: 0 auto; padding: 24px 16px 64px; }}
    header {{ padding: 32px 0 24px; border-bottom: 1px solid #e0dbd4; margin-bottom: 32px; }}
    header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }}
    header p {{ color: #666; font-size: 0.9rem; margin-top: 4px; }}
    section {{ margin-bottom: 40px; }}
    h2 {{ font-size: 0.75rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #999; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid #e8e4de; }}
    .producer-card {{ background: #fff; border: 1px solid #e8e4de; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; }}
    .producer-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }}
    .producer-name {{ font-weight: 600; font-size: 0.95rem; }}
    .source {{ font-size: 0.8rem; color: #888; }}
    .badge {{ font-size: 0.7rem; padding: 2px 7px; border-radius: 12px; font-weight: 500; margin-left: auto; }}
    .badge.exact {{ background: #f0f7ee; color: #3a7d2c; border: 1px solid #c3e6bb; }}
    .badge.producer {{ background: #f5f3ff; color: #5b4fcf; border: 1px solid #d4cffa; }}
    .wine-row {{ display: flex; align-items: baseline; gap: 8px; font-size: 0.88rem; padding: 4px 0; border-top: 1px solid #f2ede7; flex-wrap: wrap; }}
    .wine-row a {{ color: #1a1a1a; text-decoration: none; flex: 1; min-width: 160px; }}
    .wine-row a:hover {{ text-decoration: underline; }}
    .shop {{ color: #999; font-size: 0.8rem; }}
    .price {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
    .rest-price {{ font-size: 0.78rem; color: #aaa; }}
  </style>
</head>
<body>
  <header>
    <h1>Parcelle</h1>
    <p>{date_str} &middot; {exact_count} exact &middot; {total - exact_count} producer matches</p>
  </header>
  {sections}
</body>
</html>"""


def generate_report(hits: list[dict], output_path: str = "docs/index.html"):
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    html = build_html(hits)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"[OK] Report written to {output_path}")
    return output_path
