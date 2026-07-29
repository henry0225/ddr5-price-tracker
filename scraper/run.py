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


def summarize(rows):
    prices = sorted(r["price"] for r in rows)
    cheapest_kit = min(rows, key=lambda r: r["price"])
    return {
        "cheapest": prices[0],
        "median": round(statistics.median(prices), 2),
        "count": len(prices),
        "cheapest_title": cheapest_kit["title"],
        "kits": sorted(rows, key=lambda r: r["price"])[:10],
    }


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snapshot = {"updated": now, "unit": "USD, 32GB (2x16GB) DDR5 kit", "sources": {}}

    for name, fetch in SOURCES.items():
        try:
            rows = fetch()
        except Exception as e:
            rows = []
            print(f"[{name}] error: {e}")
        if rows:
            snapshot["sources"][name] = summarize(rows)
            print(f"[{name}] {len(rows)} kits, cheapest ${snapshot['sources'][name]['cheapest']}")
        else:
            snapshot["sources"][name] = {"cheapest": None, "median": None, "count": 0, "kits": []}
            print(f"[{name}] no data (blocked or empty)")

    avail = [s["cheapest"] for s in snapshot["sources"].values() if s["cheapest"]]
    snapshot["best_price"] = min(avail) if avail else None

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
