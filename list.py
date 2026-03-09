"""
List all producers in the whitelist.

Usage:
    python list.py
    python list.py --style "Burgundy Chardonnay"
    python list.py --country France
"""
import argparse
from rich.table import Table
from rich.console import Console
from db import init_db, list_producers


def main():
    parser = argparse.ArgumentParser(description="List whitelisted producers")
    parser.add_argument("--style", help="Filter by style")
    parser.add_argument("--country", help="Filter by country")
    args = parser.parse_args()

    init_db()
    producers = list_producers()

    if args.style:
        producers = [p for p in producers if p["styles"] and args.style.lower() in p["styles"].lower()]
    if args.country:
        producers = [p for p in producers if p["country"] and args.country.lower() in p["country"].lower()]

    console = Console()
    table = Table(title=f"Producer Whitelist ({len(producers)} producers)")
    table.add_column("Name", style="bold")
    table.add_column("Region")
    table.add_column("Country")
    table.add_column("Styles")
    table.add_column("Sources")

    for p in producers:
        table.add_row(
            p["name"],
            p["region"] or "",
            p["country"] or "",
            p["styles"] or "",
            p["restaurants"] or ""
        )

    console.print(table)


if __name__ == "__main__":
    main()
