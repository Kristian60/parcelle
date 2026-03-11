"""
Cellar management — 120 bottle parametric collection.
20 slots × 6 bottles (2 entry / 2 mid / 2 premium).
"""
from db import get_conn, init_db

SLOTS = [
    # id, name, category, area, entry_max, mid_max
    (1,  "Champagne",               "Sparkling", "Champagne",          600,  1200),
    (2,  "Pét-nat / Crémant",       "Sparkling", None,                 200,   400),
    (3,  "Jura White",              "White",     "Jura",               300,   600),
    (4,  "Loire Chenin",            "White",     "Loire",              250,   500),
    (5,  "Burgundy White",          "White",     "Burgundy",           400,   900),
    (6,  "Germany/Austria Riesling","White",     "Germany/Austria",    250,   500),
    (7,  "Germany/Austria Pinot",   "White",     "Germany/Austria",    200,   400),
    (8,  "Rhône White",             "White",     "Rhone",              250,   500),
    (9,  "Spain White",             "White",     "Spain",              200,   400),
    (10, "Italy White",             "White",     None,                 250,   500),
    (11, "Jura Red",                "Red",       "Jura",               300,   600),
    (12, "Loire Red",               "Red",       "Loire",              200,   450),
    (13, "Burgundy Red",            "Red",       "Burgundy",           400,   900),
    (14, "Beaujolais",              "Red",       "Beaujolais",         200,   400),
    (15, "Rhône Red",               "Red",       "Rhone",              250,   550),
    (16, "Bordeaux",                "Red",       "Bordeaux",           350,   800),
    (17, "Piedmont Nebbiolo",       "Red",       "Piedmont",           400,   900),
    (18, "Piedmont Barbera/Dolcetto","Red",      "Piedmont",           200,   400),
    (19, "Spain Red",               "Red",       "Spain",              200,   450),
    (20, "California Red",          "Red",       "California",         350,   800),
]


def seed_slots():
    """Insert slot definitions if not already present."""
    conn = get_conn()
    existing = conn.execute("SELECT COUNT(*) FROM cellar_slots").fetchone()[0]
    if existing >= 20:
        return
    conn.executemany("""
        INSERT OR IGNORE INTO cellar_slots
            (id, name, category, area, entry_max, mid_max)
        VALUES (?, ?, ?, ?, ?, ?)
    """, SLOTS)
    conn.commit()
    print(f"[OK] Seeded {len(SLOTS)} cellar slots")


def get_tier(price: int, entry_max: int, mid_max: int) -> str:
    if price <= entry_max:
        return "entry"
    elif price <= mid_max:
        return "mid"
    return "premium"


def get_status() -> list[dict]:
    """Return all slots with bottle counts and gaps."""
    conn = get_conn()
    slots = conn.execute("SELECT * FROM cellar_slots ORDER BY id").fetchall()
    result = []
    for s in slots:
        bottles = conn.execute("""
            SELECT tier, COUNT(*) as count FROM cellar_bottles
            WHERE slot_id = ? GROUP BY tier
        """, (s["id"],)).fetchall()
        counts = {b["tier"]: b["count"] for b in bottles}
        entry  = counts.get("entry", 0)
        mid    = counts.get("mid", 0)
        premium = counts.get("premium", 0)
        total  = entry + mid + premium
        result.append({
            "id": s["id"],
            "name": s["name"],
            "category": s["category"],
            "area": s["area"],
            "entry_max": s["entry_max"],
            "mid_max": s["mid_max"],
            "entry": entry,   "target_entry": s["target_entry"],
            "mid": mid,       "target_mid": s["target_mid"],
            "premium": premium, "target_premium": s["target_premium"],
            "total": total,   "target_total": s["target_entry"] + s["target_mid"] + s["target_premium"],
        })
    return result


def add_bottle(slot_id: int, producer: str, wine_name: str,
               price: int, vintage: str = None, shop: str = None, notes: str = None):
    """Record a bottle purchase into a cellar slot."""
    conn = get_conn()
    slot = conn.execute("SELECT * FROM cellar_slots WHERE id = ?", (slot_id,)).fetchone()
    if not slot:
        raise ValueError(f"No slot with id {slot_id}")
    tier = get_tier(price, slot["entry_max"], slot["mid_max"])
    conn.execute("""
        INSERT INTO cellar_bottles (slot_id, producer, wine_name, vintage, price, tier, shop, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (slot_id, producer, wine_name, vintage, price, tier, shop, notes))
    conn.commit()
    print(f"[OK] Added {producer} — {wine_name} ({vintage or '?'}) · {price} DKK · {tier} → {slot['name']}")
    return tier


def get_open_slots() -> list[dict]:
    """Return slots that still have room, by tier."""
    status = get_status()
    open_slots = []
    for s in status:
        gaps = {}
        if s["entry"] < s["target_entry"]:
            gaps["entry"] = s["target_entry"] - s["entry"]
        if s["mid"] < s["target_mid"]:
            gaps["mid"] = s["target_mid"] - s["mid"]
        if s["premium"] < s["target_premium"]:
            gaps["premium"] = s["target_premium"] - s["premium"]
        if gaps:
            open_slots.append({**s, "gaps": gaps})
    return open_slots


def tag_hit_with_slot(hit: dict) -> dict:
    """Add slot_id and tier to a scrape hit if it matches an open slot."""
    price = int(float(hit.get("price") or 0))
    if price == 0:
        return hit

    conn = get_conn()
    # Get producer area tags
    producer = hit.get("matched_producer", "")
    areas = [r[0] for r in conn.execute("""
        SELECT ps.style FROM producer_styles ps
        JOIN producers p ON p.id = ps.producer_id
        WHERE p.name = ?
    """, (producer,)).fetchall()]

    open_slots = get_open_slots()
    for slot in open_slots:
        if slot["area"] and slot["area"] not in areas:
            continue
        tier = get_tier(price, slot["entry_max"], slot["mid_max"])
        if slot["gaps"].get(tier, 0) > 0:
            hit = {**hit, "slot_id": slot["id"], "slot_name": slot["name"], "slot_tier": tier}
            break

    return hit


if __name__ == "__main__":
    init_db()
    seed_slots()
    print("\nCellar status:")
    for s in get_status():
        bar = f"{s['total']}/{s['target_total']}"
        tiers = f"E:{s['entry']}/{s['target_entry']} M:{s['mid']}/{s['target_mid']} P:{s['premium']}/{s['target_premium']}"
        print(f"  [{s['id']:2}] {s['name']:<28} {bar:>5}  {tiers}")
