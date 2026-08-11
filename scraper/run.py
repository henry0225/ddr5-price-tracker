"""Daily orchestrator: scrape each retailer, write the snapshot the site reads,
and append one point per source to the history log."""
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import newegg
import browser

SITE = Path(__file__).resolve().parent.parent / "docs"
# newegg = reliable HTTP scrape; the rest are best-effort browser scrapes.
SOURCES = {
    "newegg": newegg.fetch,
    "amazon": lambda: browser.fetch("amazon"),
    "microcenter": lambda: browser.fetch("microcenter"),
    "bh": lambda: browser.fetch("bh"),
}

# Hard plausibility bounds for a 32GB DDR5 kit. Catches spec text like "1.35V".
PRICE_MIN, PRICE_MAX = 40.0, 2000.0
# A real kit's price won't be less than this fraction of the cross-retailer
# median. Catches fragment/financing mis-scrapes (e.g. B&H showing "$78" for a
# ~$120 kit) that clear the hard floor. Newegg's reliable prices anchor the
# median, and it auto-adjusts as the market moves.
OUTLIER_FRACTION = 0.5


def summarize(rows, floor):
    rows = [r for r in rows if floor <= r["price"] <= PRICE_MAX]
    if not rows:
        return None
    cheapest = min(rows, key=lambda r: r["price"])
    return {
        "cheapest": cheapest["price"],
        "median": round(statistics.median(r["price"] for r in rows), 2),
        "count": len(rows),
        "cheapest_title": cheapest["title"],
        "cheapest_url": cheapest.get("url"),
        "kits": sorted(rows, key=lambda r: r["price"])[:10],
    }


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snapshot = {"updated": now, "unit": "USD, 32GB (2x16GB) DDR5 kit", "sources": {}}

    # Pass 1: fetch every source's raw kits.
    raw = {}
    for name, fetch in SOURCES.items():
        try:
            raw[name] = fetch()
        except Exception as e:
            raw[name] = []
            print(f"[{name}] error: {e}")

    # Cross-retailer median (robust to a few bad points) sets a dynamic floor.
    all_prices = [r["price"] for rows in raw.values() for r in rows
                  if PRICE_MIN <= r["price"] <= PRICE_MAX]
    market_median = statistics.median(all_prices) if all_prices else 0
    floor = max(PRICE_MIN, OUTLIER_FRACTION * market_median)
    print(f"market median ${market_median:.2f} -> outlier floor ${floor:.2f}")

    # Pass 2: summarize each source against the dynamic floor.
    for name, rows in raw.items():
        s = summarize(rows, floor) if rows else None
        if s:
            snapshot["sources"][name] = s
            dropped = len([r for r in rows if PRICE_MIN <= r["price"] < floor])
            note = f" (dropped {dropped} low outlier(s))" if dropped else ""
            print(f"[{name}] {s['count']} kits, cheapest ${s['cheapest']}{note}")
        else:
            snapshot["sources"][name] = {"cheapest": None, "median": None, "count": 0, "kits": []}
            print(f"[{name}] no data (blocked or empty)")

    # Overall cheapest across sources, with the retailer + link to that kit.
    best = min(
        ((name, s) for name, s in snapshot["sources"].items() if s["cheapest"]),
        key=lambda kv: kv[1]["cheapest"], default=None,
    )
    if best:
        name, s = best
        snapshot.update(best_price=s["cheapest"], best_source=name,
                        best_title=s["cheapest_title"], best_url=s.get("cheapest_url"))
    else:
        snapshot["best_price"] = None

    SITE.mkdir(exist_ok=True)
    (SITE / "prices.json").write_text(json.dumps(snapshot, indent=2))

    hist_path = SITE / "history.json"
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    day = now[:10]
    history = [h for h in history if h["date"] != day]  # idempotent per day
    for name, s in snapshot["sources"].items():
        if s["cheapest"]:
            history.append({"date": day, "source": name, "cheapest": s["cheapest"], "median": s["median"]})
    history.sort(key=lambda h: (h["date"], h["source"]))
    hist_path.write_text(json.dumps(history, indent=2))
    print(f"best price today: ${snapshot['best_price']}")


if __name__ == "__main__":
    main()
