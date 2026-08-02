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
_HREFS = re.compile(r'href="(https://www\.newegg\.com/[^"]+)"')
# Non-product Newegg links to skip; the product page is the first href left.
_SKIP = ("/d/", "/BrandStore/", "/pl?", "/p/pl", "/Todays-Deals")


def _product_link(chunk):
    for h in _HREFS.findall(chunk):
        if not any(x in h for x in _SKIP):
            return h
    return URL


def fetch():
    """Return deduped list of {price, title, url} for 32GB DDR5 kits (page 1).

    The same product can appear twice (main grid + a sponsored/combo strip, the
    latter with no product link); dedupe by title, preferring the linked entry.
    """
    html = requests.get(URL, headers=HEADERS, timeout=30).text
    by_title = {}
    for chunk in _CELL.split(html)[1:]:
        tm, pm = _TITLE.search(chunk), _PRICE.search(chunk)
        if not (tm and pm):
            continue
        title = tm.group(1).replace("&amp;", "&")
        if not (re.search(r"32\s*GB", title, re.I) and re.search(r"DDR5|PC5", title, re.I)):
            continue
        price = float(pm.group(1).replace(",", "") + pm.group(2))
        url = _product_link(chunk)
        row = {"price": price, "title": title, "url": url}
        prev = by_title.get(title)
        # Keep the entry that has a real product link; else the cheaper one.
        if prev is None or (url != URL and prev["url"] == URL) or price < prev["price"]:
            by_title[title] = row
    return list(by_title.values())


if __name__ == "__main__":
    for r in sorted(fetch(), key=lambda x: x["price"]):
        print(f"${r['price']:8.2f}  {r['title'][:70]}")
