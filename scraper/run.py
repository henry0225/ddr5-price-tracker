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

# Plausibility bounds for a 32GB DDR5 kit. Guards against spec text like "1.35V"
# being misread as a price, and against obvious junk / financing "$/mo" values.
PRICE_MIN, PRICE_MAX = 40.0, 2000.0


def summarize(rows):
    rows = [r for r in rows if PRICE_MIN <= r["price"] <= PRICE_MAX]
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

    for name, fetch in SOURCES.items():
        try:
            rows = fetch()
        except Exception as e:
            rows = []
            print(f"[{name}] error: {e}")
        s = summarize(rows) if rows else None
        if s:
            snapshot["sources"][name] = s
            print(f"[{name}] {s['count']} kits, cheapest ${s['cheapest']}")
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
