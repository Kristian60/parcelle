"""Scraper for lieu-dit.dk"""
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://lieu-dit.dk/en/shop/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WineCellarBot/1.0)"}


def scrape() -> list[dict]:
    products = []
    page = 1
    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}?paged={page}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("ul.products li.product")
        if not items:
            break

        for item in items:
            name_el = item.select_one(".woocommerce-loop-product__title")
            producer_el = item.select_one(".producer") or item.select_one(".brand")
            price_el = item.select_one(".price")
            link_el = item.select_one("a.woocommerce-loop-product__link")

            # Fallback: parse producer from description text
            desc_lines = [el.get_text(strip=True) for el in item.select("p, span") if el.get_text(strip=True)]

            products.append({
                "source": "lieu-dit",
                "name": name_el.get_text(strip=True) if name_el else "",
                "producer": producer_el.get_text(strip=True) if producer_el else (desc_lines[0] if desc_lines else ""),
                "price": price_el.get_text(strip=True) if price_el else "",
                "url": link_el["href"] if link_el else url,
            })

        # Check if there's a next page
        next_page = soup.select_one("a.next.page-numbers")
        if not next_page:
            break
        page += 1

    return products
