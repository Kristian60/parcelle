"""Scraper for vindetable.dk (Shopify JSON API)"""
import requests

BASE_URL = "https://vindetable.dk/collections/alle-vine/products.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WineCellarBot/1.0)"}


def scrape() -> list[dict]:
    products = []
    page = 1
    while True:
        resp = requests.get(BASE_URL, params={"limit": 250, "page": page}, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            break

        data = resp.json().get("products", [])
        if not data:
            break

        for p in data:
            products.append({
                "source": "vin-de-table",
                "name": p.get("title", ""),
                "producer": p.get("vendor", ""),
                "price": p["variants"][0]["price"] if p.get("variants") else "",
                "url": f"https://vindetable.dk/products/{p.get('handle', '')}",
            })

        if len(data) < 250:
            break
        page += 1

    return products
