"""
Match scraped products against the producer whitelist.
Uses fuzzy matching to handle name variations (e.g. "Domaine Leflaive" vs "Leflaive").
"""
from difflib import SequenceMatcher
from db import get_conn


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.strip().lower()).ratio()


def get_whitelisted_producers() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.id, p.name, p.region, p.country,
                   GROUP_CONCAT(DISTINCT ps.style) AS styles
            FROM producers p
            LEFT JOIN producer_styles ps ON ps.producer_id = p.id
            GROUP BY p.id
        """).fetchall()
    return [dict(r) for r in rows]


def find_match(product_name: str, product_producer: str, whitelist: list[dict], threshold=0.75) -> dict | None:
    """
    Try to match a scraped product to a whitelisted producer.
    Checks both the producer field and the product name (some sites embed producer in name).
    """
    search_text = f"{product_producer} {product_name}".strip()

    best_match = None
    best_score = 0.0

    for producer in whitelist:
        wl_name = producer["name"]

        # Direct substring check (fast path)
        if wl_name.lower() in search_text.lower():
            return producer

        # Fuzzy match on producer field
        score = _similarity(wl_name, product_producer) if product_producer else 0
        # Also try matching producer name against product name
        score = max(score, _similarity(wl_name, product_name))

        if score > best_score:
            best_score = score
            best_match = producer

    if best_score >= threshold:
        return best_match
    return None


def find_hits(products: list[dict]) -> list[dict]:
    """Return products that match whitelisted producers, with match info attached."""
    whitelist = get_whitelisted_producers()
    hits = []
    for product in products:
        match = find_match(product["name"], product.get("producer", ""), whitelist)
        if match:
            hits.append({**product, "matched_producer": match["name"], "styles": match.get("styles", "")})
    return hits
