"""Scraper for bichel.dk (Magento)"""
import requests
from bs4 import BeautifulSoup

# TODO: confirm correct category URLs — Bichel uses Magento
CATEGORY_URLS = [
    "https://bichel.dk/vin/roedvin",
    "https://bichel.dk/vin/hvidvin",
    "https://bichel.dk/vin/mousserende-vin",
    "https://bichel.dk/vin/orangevin",
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WineCellarBot/1.0)"}


def scrape() -> list[dict]:
    products = []
    for cat_url in CATEGORY_URLS:
        page = 1
        while True:
            url = cat_url if page == 1 else f"{cat_url}?p={page}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select(".product-item, .item.product")
            if not items:
                break

            for item in items:
                name_el = item.select_one(".product-item-name, .product-name")
                price_el = item.select_one(".price")
                link_el = item.select_one("a.product-item-link, a.product-name")

                products.append({
                    "source": "bichel",
                    "name": name_el.get_text(strip=True) if name_el else "",
                    "producer": "",  # Extracted from name by matcher
                    "price": price_el.get_text(strip=True) if price_el else "",
                    "url": link_el["href"] if link_el else url,
                })

            next_page = soup.select_one("a.action.next, li.pages-item-next a")
            if not next_page:
                break
            page += 1

    return products
