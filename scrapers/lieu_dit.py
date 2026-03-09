"""Scraper for lieu-dit.dk"""
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://lieu-dit.dk/en/shop/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WineCellarBot/1.0)"}


def scrape() -> list[dict]:
    products = []
    page = 1
    while True:
        url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        # Products are in <li class="flex flex-col relative"> inside ul.ld-products
        items = soup.select("ul.ld-products li")
        if not items:
            break

        for item in items:
            texts = [t.strip() for t in item.stripped_strings]
            if len(texts) < 2:
                continue

            # Structure: [wine_name, producer, region_country, wine_type, price]
            title = texts[0]
            vintage_match = re.match(r"^(\d{4})\s+(.+)", title)
            vintage = vintage_match.group(1) if vintage_match else None
            wine_name = vintage_match.group(2) if vintage_match else title

            producer = texts[1] if len(texts) > 1 else ""
            region_country = texts[2] if len(texts) > 2 else ""

            region, country = "", ""
            if "," in region_country:
                parts = region_country.split(",", 1)
                region = parts[0].strip()
                country = parts[1].strip()

            # Price: find text matching "NNN,NN DKK" or "NNN.NNN,NN DKK"
            price_clean = ""
            full_text = " ".join(texts)
            m = re.search(r"([\d.]+),\d{2}\s*DKK", full_text)
            if m:
                price_clean = m.group(1).replace(".", "")

            link_el = item.select_one("a")
            url_product = link_el["href"] if link_el and link_el.get("href") else BASE_URL

            products.append({
                "source": "lieu-dit",
                "name": wine_name,
                "producer": producer,
                "vintage": vintage,
                "region": region,
                "country": country,
                "price": price_clean,
                "currency": "DKK",
                "url": url_product,
            })

        page += 1

    return products
