"""
Run all scrapers and notify on whitelist hits.

Usage:
    python monitor.py                  # Run all scrapers
    python monitor.py --source lieu-dit  # Single source
    python monitor.py --dry-run        # Print hits, no Telegram
"""
import argparse
from db import init_db
from match import find_hits
from notify import notify_hits

from scrapers import lieu_dit, vin_de_table, domaine_brandis, bichel

SCRAPERS = {
    "lieu-dit": lieu_dit.scrape,
    "vin-de-table": vin_de_table.scrape,
    "domaine-brandis": domaine_brandis.scrape,
    "bichel": bichel.scrape,
}


def run(sources=None, dry_run=False):
    init_db()
    active = {k: v for k, v in SCRAPERS.items() if not sources or k in sources}
    all_hits = []

    for name, scrape_fn in active.items():
        print(f"[*] Scraping {name}...")
        try:
            products = scrape_fn()
            print(f"[OK] {name}: {len(products)} products")
            hits = find_hits(products)
            if hits:
                print(f"[OK] {name}: {len(hits)} whitelist hits")
            all_hits.extend(hits)
        except Exception as e:
            print(f"[ERROR] {name}: {e}")

    if dry_run:
        print(f"\n--- DRY RUN: {len(all_hits)} total hits ---")
        for h in all_hits:
            print(f"  {h['matched_producer']} | {h['name']} | {h['source']} | {h.get('price', '')}")
    else:
        notify_hits(all_hits)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor wine shops for whitelist hits")
    parser.add_argument("--source", nargs="+", choices=list(SCRAPERS.keys()), help="Specific sources to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Print results, skip Telegram")
    args = parser.parse_args()

    run(sources=args.source, dry_run=args.dry_run)
