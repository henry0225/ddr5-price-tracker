"""Newegg 32GB DDR5 client.

Derived once from the live page: Newegg server-renders the listing with prices
embedded, so a single HTTP GET + parse is all we need — no browser, no HAR replay.
"""
import re
import requests

URL = "https://www.newegg.com/p/pl?d=32gb+ddr5+ram"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_CELL = re.compile(r'class="item-cell')
_TITLE = re.compile(r'<img[^>]*title="([^"]+)"')
_PRICE = re.compile(r'price-current[^>]*>.*?<strong>([\d,]+)</strong><sup>(\.\d{2})', re.S)


def fetch():
    """Return list of {price, title} for 32GB DDR5 kits on Newegg's first page."""
    html = requests.get(URL, headers=HEADERS, timeout=30).text
    rows = []
    for chunk in _CELL.split(html)[1:]:
        tm, pm = _TITLE.search(chunk), _PRICE.search(chunk)
        if not (tm and pm):
            continue
        title = tm.group(1).replace("&amp;", "&")
        if not (re.search(r"32\s*GB", title, re.I) and re.search(r"DDR5|PC5", title, re.I)):
            continue
        price = float(pm.group(1).replace(",", "") + pm.group(2))
        rows.append({"price": price, "title": title})
    return rows


if __name__ == "__main__":
    for r in sorted(fetch(), key=lambda x: x["price"]):
        print(f"${r['price']:8.2f}  {r['title'][:70]}")
