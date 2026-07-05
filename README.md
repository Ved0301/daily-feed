# Daily Feed

A personal, auto-updating newsletter site: arXiv papers, OpenAI/Google Research/DeepMind
posts, TechCrunch startup news, The Verge, and top Hacker News stories — refreshed every
morning with no server to maintain.

**How it works**
- `fetch.py` pulls from all sources and writes `data.json`
- A GitHub Actions workflow (`.github/workflows/update.yml`) runs `fetch.py` on a daily
  schedule, commits the new `data.json`, and redeploys
- `index.html` / `style.css` / `app.js` is a plain static site that reads `data.json` —
  hosted free on GitHub Pages

Total cost: $0/month.

---

## 1. Put this on GitHub

1. Create a new **public** repo on github.com (e.g. `daily-feed`).
2. Upload all the files in this folder to it (or, if you have `git` locally):
   ```bash
   cd dailyfeed
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/daily-feed.git
   git push -u origin main
   ```

## 2. Turn on GitHub Pages

1. In your repo: **Settings → Pages**
2. Under "Build and deployment", set **Source** to **GitHub Actions**.
3. That's it — the workflow already includes the deploy step.

## 3. Run it once by hand

The scheduled cron won't fire until its next scheduled time, so trigger it manually the
first time:

1. Go to the **Actions** tab in your repo
2. Click **Update daily feed** → **Run workflow** → **Run workflow**
3. Wait ~30 seconds, then check the **Settings → Pages** tab for your live URL
   (something like `https://YOUR_USERNAME.github.io/daily-feed/`)

Your site is now live and will refresh itself every day at 07:00 UTC.

## 4. Customize

- **Schedule**: edit the `cron:` line in `.github/workflows/update.yml`
  ([crontab.guru](https://crontab.guru) helps with the syntax). Times are UTC.
- **Sources**: edit the `fetch_rss(...)` calls at the bottom of `fetch.py`. Any RSS/Atom
  feed works — swap in Anthropic's blog, MIT Technology Review, VentureBeat, etc.
- **arXiv categories**: change `categories=("cs.AI", "cs.LG", "cs.CL")` in `fetch.py` to
  any arXiv category (e.g. add `cs.CV` for computer vision, `stat.ML`).
- **Hacker News threshold**: `min_points=150` in `fetch_hn()` controls how "front-page-y"
  a story must be to show up — lower it to see more, raise it to see less.
- **Design**: `style.css` holds every color/type/spacing decision as CSS variables at the
  top — tweak `--ink`, `--paper`, `--muted` to adjust the palette without touching layout.
- **Issue number**: `LAUNCH_DATE` in `app.js` sets what "Issue No. 001" corresponds to.

## 5. Run the fetcher locally (optional, for testing)

```bash
pip install -r requirements.txt
python fetch.py
```

This overwrites `data.json` with fresh results — open `index.html` directly in a browser
to preview (or run `python -m http.server` in this folder and visit `localhost:8000`).

## Notes

- A source occasionally changing its RSS URL or rate-limiting is the most common failure
  mode — `fetch.py` is written so one source failing doesn't break the others (it logs a
  warning and moves on).
- If a section looks stale, check the **Actions** tab for the latest run's logs — the
  fetcher prints how many items it got from each source.
