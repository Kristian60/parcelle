"""Scraper for theis-vine.dk (Shopify JSON API)"""
import requests

BASE_URL = "https://www.theis-vine.dk/collections/all/products.json"
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
            variant = p["variants"][0] if p.get("variants") else {}
            products.append({
                "source": "theis-vine",
                "name": p.get("title", ""),
                "producer": p.get("vendor", ""),
                "vintage": variant.get("option2") if str(variant.get("option2") or "").isdigit() else None,
                "price": str(int(float(variant["price"]))) if variant.get("price") else "",
                "currency": "DKK",
                "url": f"https://www.theis-vine.dk/products/{p.get('handle', '')}",
            })

        if len(data) < 250:
            break
        page += 1

    return products
