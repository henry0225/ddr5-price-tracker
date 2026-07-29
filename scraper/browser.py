"""Best-effort browser scrapers for Cloudflare/anti-bot retailers.

Amazon, Micro Center and B&H all block scripted HTTP (Amazon 503s; MC and B&H
serve a Cloudflare "Just a moment..." JS challenge), so each needs a real
headless browser. On GitHub Actions' datacenter IPs these get challenged some
days — every fetch returns [] on any block rather than crashing the run. Newegg
(scraper/newegg.py) is the reliable backbone; these are bonus data when they work.

NOTE: the Micro Center and B&H selectors below could not be verified live (the
challenge blocks non-browser tools). If a site returns 0 kits in the workflow
logs despite the page loading, adjust its `card`/`title`/`price` selectors here.
Micro Center prices are also store-specific; without a selected store some items
show no price, which the price fallback simply skips.
"""
import re

# Each site: search url, selectors to try (first hit wins), and a page-content
# signature that means "blocked" -> return [].
SITES = {
    "amazon": {
        "url": "https://www.amazon.com/s?k=32gb+ddr5+ram+desktop",
        "card": ['div[data-component-type="s-search-result"]'],
        "title": ["h2 span", "h2"],
        "price": [".a-price .a-offscreen"],
        "blocked": r"captcha|api-services-support",
    },
    "microcenter": {
        "url": "https://www.microcenter.com/search/search_results.aspx?NTT=32gb+ddr5",
        "card": ["li.product_wrapper", ".product_wrapper", 'article[data-name]'],
        "title": ['a.productClickItemV2', '[data-name]', "h2 a", "h2"],
        "price": ['span[itemprop="price"]', "[data-price]", ".price"],
        "blocked": r"just a moment|cf-challenge",
    },
    "bh": {
        "url": "https://www.bhphotovideo.com/c/search?q=32gb+ddr5+ram",
        "card": ['[data-selenium="miniProductPageProduct"]', "[data-selenium=miniProductPage]"],
        "title": ['[data-selenium="miniProductPageProductName"]', "h3", "h2"],
        "price": ['[data-selenium="uppedDecimalPriceRegular"]', "[data-selenium^=price]", ".price_1DPoToKrLP8uWvruGqgtaY"],
        "blocked": r"just a moment|cf-challenge",
    },
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
PRICE_RE = re.compile(r"[\d,]+\.\d{2}")


def _first(card, selectors):
    for sel in selectors:
        try:
            el = card.query_selector(sel)
        except Exception:
            continue
        if el:
            return el
    return None


def fetch(site_key):
    """Scrape one configured site. Returns [{price, title}] or [] if blocked/empty."""
    cfg = SITES[site_key]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        try:
            page.goto(cfg["url"], timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3500)  # give Cloudflare's passive challenge time to clear
            if re.search(cfg["blocked"], page.content(), re.I):
                return []
            for sel in cfg["card"]:
                cards = page.query_selector_all(sel)
                if cards:
                    break
            else:
                cards = []
            for card in cards:
                t = _first(card, cfg["title"])
                pnode = _first(card, cfg["price"])
                title = (t.inner_text().strip() if t else "")
                blob = (pnode.inner_text() if pnode else "") or card.inner_text()
                if not (re.search(r"32\s*GB", title, re.I) and re.search(r"DDR5", title, re.I)):
                    continue
                m = PRICE_RE.search(blob)
                if m:
                    rows.append({"price": float(m.group(0).replace(",", "")), "title": title})
        except Exception:
            return rows
        finally:
            browser.close()
    return rows


if __name__ == "__main__":
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else "amazon"
    for r in sorted(fetch(key), key=lambda x: x["price"]):
        print(f"${r['price']:8.2f}  {r['title'][:70]}")
