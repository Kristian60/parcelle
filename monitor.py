"""
Run all scrapers, generate HTML report, push to gh-pages, notify via Telegram.

Usage:
    python monitor.py                  # Run all scrapers
    python monitor.py --source lieu-dit  # Single source
    python monitor.py --dry-run        # Print hits only, no publish/notify
"""
import argparse
import subprocess
from db import init_db
from match import find_hits
from notify import notify_hits, notify_summary
from report import generate_report

from scrapers import lieu_dit, vin_de_table, domaine_brandis, bichel, theis_vine

SCRAPERS = {
    "lieu-dit": lieu_dit.scrape,
    "vin-de-table": vin_de_table.scrape,
    "domaine-brandis": domaine_brandis.scrape,
    "bichel": bichel.scrape,
    "theis-vine": theis_vine.scrape,
}

REPORT_URL = "https://kristian60.github.io/parcelle"


def push_report():
    """Commit and push docs/index.html to main (GitHub Pages serves from /docs)."""
    try:
        subprocess.run(["git", "add", "docs/"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "chore: update weekly report"], check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
        print(f"[OK] Report pushed → {REPORT_URL}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Git push failed: {e.stderr.decode()}")
        return False


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

    shops_scraped = len([s for s in active if any(h["source"] == s for h in all_hits)])

    if dry_run:
        print(f"\n--- DRY RUN: {len(all_hits)} total hits ---")
        for h in all_hits:
            print(f"  {h['matched_producer']} | {h['name']} | {h['source']} | {h.get('price', '')}")
        return

    # Generate HTML report
    generate_report(all_hits)

    # Push to GitHub Pages
    pushed = push_report()
    report_url = REPORT_URL if pushed else None

    # Send Telegram summary with link
    notify_summary(all_hits, shop_count=shops_scraped, report_url=report_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor wine shops for whitelist hits")
    parser.add_argument("--source", nargs="+", choices=list(SCRAPERS.keys()), help="Specific sources to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Print results, skip publish/notify")
    args = parser.parse_args()

    run(sources=args.source, dry_run=args.dry_run)
