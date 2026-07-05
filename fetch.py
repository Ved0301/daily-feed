#!/usr/bin/env python3
"""
Fetches the latest tech/AI research, lab announcements, startup news,
and Hacker News stories, and writes them all to data.json.

Run manually with:  python fetch.py
Runs automatically every day via .github/workflows/update.yml
"""

import json
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import feedparser

MAX_ITEMS_PER_SECTION = 12
REQUEST_TIMEOUT = 20
USER_AGENT = "dailyfeed-bot/1.0 (personal newsletter aggregator)"


def log(msg):
    print(f"[fetch] {msg}")


def clean_text(text, limit=220):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def parse_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def fetch_rss(url, source_name, limit=MAX_ITEMS_PER_SECTION):
    """Generic RSS/Atom fetcher using feedparser."""
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read()
        parsed = feedparser.parse(raw)
        for entry in parsed.entries[:limit]:
            items.append({
                "title": clean_text(getattr(entry, "title", ""), 160),
                "url": getattr(entry, "link", ""),
                "summary": clean_text(
                    getattr(entry, "summary", "") or getattr(entry, "description", "")
                ),
                "source": source_name,
                "date": parse_date(entry),
            })
        log(f"{source_name}: fetched {len(items)} items")
    except Exception as e:
        log(f"{source_name}: FAILED ({e})")
    return items


def fetch_arxiv(categories=("cs.AI", "cs.LG", "cs.CL"), limit=MAX_ITEMS_PER_SECTION):
    """Fetch recent papers from arXiv's public API."""
    items = []
    query = "+OR+".join(f"cat:{c}" for c in categories)
    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query={query}&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw)
        for entry in root.findall("atom:entry", ns):
            title = clean_text(entry.findtext("atom:title", default="", namespaces=ns), 160)
            summary = clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
            link = ""
            for l in entry.findall("atom:link", ns):
                if l.get("rel") == "alternate" or link == "":
                    link = l.get("href", "")
            published = entry.findtext("atom:published", default="", namespaces=ns)
            authors = [
                a.findtext("atom:name", default="", namespaces=ns)
                for a in entry.findall("atom:author", ns)
            ]
            author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
            items.append({
                "title": title,
                "url": link,
                "summary": f"{author_str} — {summary}" if author_str else summary,
                "source": "arXiv",
                "date": published or datetime.now(timezone.utc).isoformat(),
            })
        log(f"arXiv: fetched {len(items)} items")
    except Exception as e:
        log(f"arXiv: FAILED ({e})")
    return items


def fetch_hn(limit=MAX_ITEMS_PER_SECTION, min_points=150):
    """Fetch top Hacker News stories from the last day via the Algolia API."""
    items = []
    try:
        url = (
            "http://hn.algolia.com/api/v1/search_by_date?"
            f"tags=story&numericFilters=points>{min_points},created_at_i>{int(time.time()) - 86400 * 2}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
        hits = sorted(data.get("hits", []), key=lambda h: h.get("points", 0), reverse=True)
        for hit in hits[:limit]:
            items.append({
                "title": clean_text(hit.get("title", ""), 160),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                "summary": f"{hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments on Hacker News",
                "source": "Hacker News",
                "date": datetime.fromtimestamp(hit.get("created_at_i", time.time()), tz=timezone.utc).isoformat(),
            })
        log(f"Hacker News: fetched {len(items)} items")
    except Exception as e:
        log(f"Hacker News: FAILED ({e})")
    return items


def dedupe_and_sort(items):
    seen = set()
    out = []
    for it in items:
        key = it["url"] or it["title"]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def main():
    log("Starting fetch run…")

    research = fetch_arxiv()

    labs = (
        fetch_rss("https://openai.com/news/rss.xml", "OpenAI")
        + fetch_rss("https://research.google/blog/rss/", "Google Research")
        + fetch_rss("https://deepmind.google/blog/rss.xml", "Google DeepMind")
    )

    startups = fetch_rss("https://techcrunch.com/feed/", "TechCrunch")

    wider_tech = (
        fetch_rss("https://www.theverge.com/rss/index.xml", "The Verge")
        + fetch_hn()
    )

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": {
            "research":   dedupe_and_sort(research)[:MAX_ITEMS_PER_SECTION],
            "labs":       dedupe_and_sort(labs)[:MAX_ITEMS_PER_SECTION],
            "startups":   dedupe_and_sort(startups)[:MAX_ITEMS_PER_SECTION],
            "wider_tech": dedupe_and_sort(wider_tech)[:MAX_ITEMS_PER_SECTION],
        },
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in data["sections"].values())
    log(f"Done. Wrote {total} items to data.json")


if __name__ == "__main__":
    main()
