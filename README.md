# 32GB DDR5 Price Tracker

A daily-updated, hosted-anywhere dashboard for the live price of 32GB (2×16GB) DDR5 RAM.

## How it works

The efficient version of "an agent browses sites every day": an agent derived the
client **once**, and the daily job is now a plain deterministic script — no LLM,
no browser for Newegg.

```
GitHub Actions (free daily cron)
  └─ scraper/run.py
       ├─ newegg.py  → HTTP GET, parse prices embedded in the page (reliable)
       └─ amazon.py  → headless browser, best-effort (Amazon blocks datacenter IPs)
       └─ writes docs/prices.json + appends docs/history.json, commits back
GitHub Pages (free static hosting)
  └─ docs/index.html → reads the JSON, shows cheapest + median + history chart
```

- **Newegg** is the reliable backbone: prices are server-rendered into the page, so
  one HTTP request per day gets them. No anti-bot wall.
- **Amazon** blocks scripted requests, so it's scraped via headless Chromium and may
  return no data on days it serves a CAPTCHA to GitHub's datacenter IP. When that
  happens the site shows "no data today" for Amazon; the run still succeeds.

## Deploy (one time)

1. Create a GitHub repo and push this folder:
   ```bash
   cd ddr5-price-tracker
   git init && git add . && git commit -m "init"
   gh repo create ddr5-price-tracker --public --source=. --push
   ```
2. **Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/docs`
   (GitHub Pages only serves from `/` or `/docs`). Live at
   `https://<you>.github.io/ddr5-price-tracker/`.
3. **Actions tab** → run *Daily price scrape* once (`workflow_dispatch`) to populate data.
   After that it runs itself daily and commits fresh prices.

## Run locally

```bash
pip install -r requirements.txt
python -m playwright install chromium   # only needed for Amazon
python scraper/run.py                    # writes docs/prices.json + history.json
open docs/index.html
```

## Customize

- **What's tracked**: edit the search URL / filters in `scraper/newegg.py` and
  `scraper/amazon.py` (currently "32GB DDR5", filtered to titles containing 32GB + DDR5).
- **Add retailers** (Micro Center, B&H scrape cleanly like Newegg): add a `fetch()`
  module and register it in `SOURCES` in `scraper/run.py`.
- **Schedule**: change the `cron` in `.github/workflows/daily.yml`.
