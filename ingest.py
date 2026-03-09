"""
Ingest a PDF wine list into the producer whitelist.

Usage:
    python ingest.py <path/to/winelist.pdf> --restaurant "Glassalen"
"""
import argparse
import sys
from pathlib import Path

from db import init_db, upsert_producer, add_source, link_producer_source, add_style
from extract import extract_producers


def ingest(pdf_path: str, restaurant: str):
    init_db()

    path = Path(pdf_path)
    if not path.exists():
        print(f"[ERROR] File not found: {pdf_path}")
        sys.exit(1)

    producers = extract_producers(str(path))
    if not producers:
        print("[WARNING] No producers found")
        return

    source_id = add_source(restaurant=restaurant, pdf_file=str(path.name))
    print(f"[*] Importing {len(producers)} producers from '{restaurant}'...")

    for p in producers:
        pid = upsert_producer(
            name=p["name"],
            region=p.get("region"),
            country=p.get("country"),
        )
        link_producer_source(pid, source_id)
        for style in p.get("styles", []):
            add_style(pid, style)

    print(f"[OK] Done. Run `python list.py` to see your producer whitelist.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a PDF wine list")
    parser.add_argument("pdf", help="Path to the wine list PDF")
    parser.add_argument("--restaurant", required=True, help="Restaurant name")
    args = parser.parse_args()

    ingest(args.pdf, args.restaurant)
