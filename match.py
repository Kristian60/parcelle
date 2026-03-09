"""
Match scraped products against the producer whitelist.

Strategy (in order):
1. Exact match (case-insensitive)
2. All words of whitelist producer appear in product text (word-boundary safe)
3. Fuzzy ratio — only if producer name is long enough to avoid false positives
"""
import re
from db import get_conn


def _normalize(s: str) -> str:
    """Lowercase, strip accents roughly, remove punctuation."""
    s = s.lower().strip()
    # Common accent substitutions
    for a, b in [("é","e"),("è","e"),("ê","e"),("ë","e"),("à","a"),("â","a"),
                 ("ô","o"),("ù","u"),("û","u"),("ç","c"),("î","i"),("ï","i")]:
        s = s.replace(a, b)
    s = re.sub(r"[''`]", "", s)
    return s


def _words(s: str) -> list[str]:
    return re.findall(r"\b\w{3,}\b", _normalize(s))


def _exact_match(wl: str, text: str) -> bool:
    """Whitelist name appears verbatim as a whole phrase (word boundaries on both ends)."""
    pattern = rf"\b{re.escape(_normalize(wl))}\b"
    return bool(re.search(pattern, _normalize(text)))


def _word_match(wl: str, text: str, min_words: int = 2) -> bool:
    """
    All significant words (3+ chars) from the whitelist name
    appear as whole words in the text.
    Only used when the whitelist name has >= min_words significant words.
    """
    wl_words = _words(wl)
    if len(wl_words) < min_words:
        return False
    text_norm = _normalize(text)
    return all(re.search(rf"\b{re.escape(w)}\b", text_norm) for w in wl_words)


def _fuzzy_score(a: str, b: str) -> float:
    """Simple character-level overlap ratio — only used as last resort."""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _whole_word_match(wl: str, text: str) -> bool:
    """Whitelist name appears as a whole-word match (not inside a longer word)."""
    pattern = rf"\b{re.escape(_normalize(wl))}\b"
    return bool(re.search(pattern, _normalize(text)))


def match_producer(wl_name: str, product_name: str, product_producer: str) -> bool:
    search_combined = f"{product_producer} {product_name}"

    # Short names (≤5 chars): require exact whole-word match in producer field only
    if len(wl_name) <= 5:
        if product_producer:
            return _whole_word_match(wl_name, product_producer)
        return False

    # 1. Exact whole-word match in producer field
    if product_producer and _whole_word_match(wl_name, product_producer):
        return True

    # 2. Exact substring match in producer field
    if product_producer and _exact_match(wl_name, product_producer):
        return True

    # 3. All significant words match as whole words in producer field
    if product_producer and _word_match(wl_name, product_producer):
        return True

    # 4. Fuzzy — only for names 12+ chars to avoid false positives
    if len(wl_name) >= 12 and product_producer:
        score = _fuzzy_score(wl_name, product_producer)
        if score >= 0.88:
            return True

    return False


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


def find_hits(products: list[dict]) -> list[dict]:
    whitelist = get_whitelisted_producers()
    hits = []
    for product in products:
        for producer in whitelist:
            if match_producer(producer["name"], product["name"], product.get("producer", "")):
                hits.append({**product, "matched_producer": producer["name"], "styles": producer.get("styles", "")})
                break
    return hits
