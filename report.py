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

    # Organise producers by area
    styled = defaultdict(list)
    unstyled = []
    for producer, wines in by_producer.items():
        styles = get_producer_styles(producer)
        has_exact = any(w.get("match_type") == "exact" for w in wines)
        min_price = min((float(w.get("price") or 9999) for w in wines), default=9999)
        info = {
            "wines": wines,
            "has_exact": has_exact,
            "style": styles[0] if styles else None,
            "min_price": int(min_price) if min_price < 9999 else 9999,
        }
        if styles:
            styled[styles[0]].append((producer, info))
        else:
            unstyled.append((producer, info))

    date_str = datetime.utcnow().strftime("%d %b %Y")
    total = len(by_producer)
    exact_count = sum(1 for wines in by_producer.values() if any(w.get("match_type") == "exact" for w in wines))

    # Collect all areas present in results
    present_areas = [a for a in STYLE_EMOJI if a in styled]
    if unstyled:
        present_areas.append("Other")

    def producer_card(producer: str, info: dict, area: str) -> str:
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
            price_raw = fmt_price(w.get("price"))
            rest_price_str = ""
            if w.get("match_type") == "exact":
                for r in seen_rest.values():
                    rp = fmt_price(r.get("price"))
                    rest_price_str = f'<span class="rest-price">{escape(r["restaurant"])} {rp}</span>'
                    break
            wine_rows += f"""
            <div class="wine-row" data-price="{price_raw}">
              <a href="{w['url']}" target="_blank">{escape(w['name'])}</a>
              <span class="shop">{escape(w['source'])}</span>
              <span class="price">{price_raw}</span>
              {rest_price_str}
            </div>"""

        area_attr = escape(area)
        return f"""
        <div class="producer-card" data-area="{area_attr}" data-min-price="{info['min_price']}">
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
        cards = "".join(producer_card(p, i, style) for p, i in items)
        sections += f"""
      <section data-area="{escape(style)}">
        <h2>{escape(style)}</h2>
        {cards}
      </section>"""

    if unstyled:
        cards = "".join(producer_card(p, i, "Other") for p, i in unstyled)
        sections += f"""
      <section data-area="Other">
        <h2>Other</h2>
        {cards}
      </section>"""

    area_buttons = "".join(
        f'<button class="area-btn active" data-area="{escape(a)}">{escape(a)}</button>'
        for a in present_areas
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Parcelle — {date_str}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f9f7f4; color: #1a1a1a; max-width: 760px; margin: 0 auto; padding: 24px 16px 64px; }}
    header {{ padding: 32px 0 20px; border-bottom: 1px solid #e0dbd4; margin-bottom: 24px; }}
    header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }}
    header p {{ color: #666; font-size: 0.9rem; margin-top: 4px; }}

    /* Filter bar */
    .filters {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 28px; padding-bottom: 20px; border-bottom: 1px solid #e8e4de; }}
    .area-btn {{
      font-size: 0.78rem; padding: 4px 10px; border-radius: 20px; border: 1px solid #d0cac2;
      background: #fff; color: #555; cursor: pointer; transition: all 0.15s;
    }}
    .area-btn.active {{ background: #1a1a1a; color: #fff; border-color: #1a1a1a; }}
    .price-filter {{ display: flex; align-items: center; gap: 6px; margin-left: auto; font-size: 0.82rem; color: #555; }}
    .price-filter input {{
      width: 70px; padding: 4px 8px; border: 1px solid #d0cac2; border-radius: 6px;
      font-size: 0.82rem; background: #fff;
    }}
    #result-count {{ font-size: 0.8rem; color: #999; width: 100%; }}

    section {{ margin-bottom: 36px; }}
    h2 {{ font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #999; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid #e8e4de; }}
    .producer-card {{ background: #fff; border: 1px solid #e8e4de; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px; }}
    .producer-card.hidden {{ display: none; }}
    .producer-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }}
    .producer-name {{ font-weight: 600; font-size: 0.95rem; }}
    .source {{ font-size: 0.8rem; color: #888; }}
    .badge {{ font-size: 0.7rem; padding: 2px 7px; border-radius: 12px; font-weight: 500; margin-left: auto; white-space: nowrap; }}
    .badge.exact {{ background: #f0f7ee; color: #3a7d2c; border: 1px solid #c3e6bb; }}
    .badge.producer {{ background: #f5f3ff; color: #5b4fcf; border: 1px solid #d4cffa; }}
    .wine-row {{ display: flex; align-items: baseline; gap: 8px; font-size: 0.88rem; padding: 4px 0; border-top: 1px solid #f2ede7; flex-wrap: wrap; }}
    .wine-row.hidden {{ display: none; }}
    .wine-row a {{ color: #1a1a1a; text-decoration: none; flex: 1; min-width: 160px; }}
    .wine-row a:hover {{ text-decoration: underline; }}
    .shop {{ color: #999; font-size: 0.8rem; }}
    .price {{ font-weight: 600; font-variant-numeric: tabular-nums; }}
    .rest-price {{ font-size: 0.78rem; color: #aaa; }}
    section.hidden {{ display: none; }}
  </style>
</head>
<body>
  <header>
    <h1>Parcelle</h1>
    <p>{date_str} &middot; {exact_count} exact &middot; {total - exact_count} producer matches</p>
  </header>

  <div class="filters">
    {area_buttons}
    <div class="price-filter">
      Max price <input type="number" id="max-price" placeholder="any" min="0" step="50">
    </div>
    <div id="result-count"></div>
  </div>

  {sections}

  <script>
    const activeAreas = new Set({list(present_areas)!r});
    let maxPrice = Infinity;

    function applyFilters() {{
      let visible = 0;
      document.querySelectorAll('.producer-card').forEach(card => {{
        const area = card.dataset.area;
        const minPrice = parseInt(card.dataset.minPrice);
        const areaOk = activeAreas.has(area);
        const priceOk = minPrice <= maxPrice;
        const show = areaOk && priceOk;
        card.classList.toggle('hidden', !show);
        if (show) visible++;
      }});

      // Hide empty sections
      document.querySelectorAll('section').forEach(sec => {{
        const hasVisible = sec.querySelectorAll('.producer-card:not(.hidden)').length > 0;
        sec.classList.toggle('hidden', !hasVisible);
      }});

      document.getElementById('result-count').textContent =
        visible === 0 ? 'No matches' : visible + ' producer' + (visible !== 1 ? 's' : '');
    }}

    document.querySelectorAll('.area-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const area = btn.dataset.area;
        if (activeAreas.has(area)) {{
          activeAreas.delete(area);
          btn.classList.remove('active');
        }} else {{
          activeAreas.add(area);
          btn.classList.add('active');
        }}
        applyFilters();
      }});
    }});

    document.getElementById('max-price').addEventListener('input', e => {{
      const val = parseInt(e.target.value);
      maxPrice = isNaN(val) ? Infinity : val;
      applyFilters();
    }});

    applyFilters();
  </script>
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
