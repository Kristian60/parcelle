"""Scraper for domainebrandis.dk (age gate bypass via cookie)"""
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://domainebrandis.dk/shop/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WineCellarBot/1.0)"}
# Bypass age gate by setting the age-verified cookie
COOKIES = {"age_verified": "1", "woocommerce_age_verified": "yes"}


def scrape() -> list[dict]:
    products = []
    page = 1
    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        resp = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=15)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("ul.products li.product")
        if not items:
            break

        for item in items:
            name_el = item.select_one(".woocommerce-loop-product__title")
            price_el = item.select_one(".price")
            link_el = item.select_one("a")

            products.append({
                "source": "domaine-brandis",
                "name": name_el.get_text(strip=True) if name_el else "",
                "producer": "",  # Will be extracted from product name by matcher
                "price": price_el.get_text(strip=True) if price_el else "",
                "url": link_el["href"] if link_el else url,
            })

        next_page = soup.select_one("a.next.page-numbers")
        if not next_page:
            break
        page += 1

    return products
