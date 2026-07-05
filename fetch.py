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
from bs4 import BeautifulSoup

MAX_ITEMS_PER_SECTION = 12
REQUEST_TIMEOUT = 20
ARTICLE_FETCH_TIMEOUT = 8
SUMMARY_SENTENCES = 3
USER_AGENT = "dailyfeed-bot/1.0 (personal newsletter aggregator)"

STOPWORDS = set("""a about above after again against all am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have having
he her here hers herself him himself his how i if in into is it its itself just me more most my myself no nor
not now of off on once only or other our ours ourselves out over own same she should so some such than that the
their theirs them themselves then there these they this those through to too under until up very was we were
what when where which while who whom why will with would you your yours yourself yourselves said also new one
two using use used can may many much like get got make made says according""".split())

SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\u201c])')
WORD_RE = re.compile(r"[a-zA-Z']+")


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


def split_sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    sentences = SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def extractive_summary(text, max_sentences=SUMMARY_SENTENCES):
    """Pick the most information-dense sentences from `text` using word-frequency
    scoring (a lightweight relative of Luhn's summarization algorithm) — no ML
    model or API call required."""
    sentences = split_sentences(text)
    if not sentences:
        return ""
    if len(sentences) <= max_sentences:
        return clean_text(" ".join(sentences), limit=420)

    freq = {}
    for sent in sentences:
        for w in WORD_RE.findall(sent.lower()):
            if w in STOPWORDS or len(w) < 3:
                continue
            freq[w] = freq.get(w, 0) + 1
    if not freq:
        return clean_text(" ".join(sentences[:max_sentences]), limit=420)

    max_freq = max(freq.values())
    for w in freq:
        freq[w] /= max_freq

    scores = []
    for i, sent in enumerate(sentences):
        words = WORD_RE.findall(sent.lower())
        if not words:
            scores.append(0.0)
            continue
        score = sum(freq.get(w, 0) for w in words) / len(words)
        # slight lede bias -- opening sentences tend to carry the most context
        if i < 2:
            score *= 1.15
        scores.append(score)

    top_idx = sorted(
        sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences]
    )
    summary = " ".join(sentences[i] for i in top_idx)
    return clean_text(summary, limit=420)


def fetch_article_text(url):
    """Download a page and pull out its paragraph text, stripped of nav/ads/boilerplate."""
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=ARTICLE_FETCH_TIMEOUT) as resp:
            raw = resp.read()
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
            tag.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraphs = [p for p in paragraphs if len(p) > 40]  # drop short nav/caption fragments
        return " ".join(paragraphs)
    except Exception:
        return ""


def enrich_with_summary(item, max_sentences=SUMMARY_SENTENCES):
    """Fetch the full article and replace the RSS teaser with a real extractive summary.
    Falls back to whatever summary it already had if the fetch fails or the page is too thin."""
    article_text = fetch_article_text(item.get("url", ""))
    if len(article_text) > 300:
        summary = extractive_summary(article_text, max_sentences=max_sentences)
        if summary:
            item["summary"] = summary
    return item


def parse_date(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def fetch_rss(url, source_name, limit=MAX_ITEMS_PER_SECTION, summarize=True):
    """Generic RSS/Atom fetcher using feedparser. When summarize=True, visits each
    article and replaces the RSS teaser with a real extractive summary."""
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read()
        parsed = feedparser.parse(raw)
        for entry in parsed.entries[:limit]:
            item = {
                "title": clean_text(getattr(entry, "title", ""), 160),
                "url": getattr(entry, "link", ""),
                "summary": clean_text(
                    getattr(entry, "summary", "") or getattr(entry, "description", "")
                ),
                "source": source_name,
                "date": parse_date(entry),
            }
            if summarize:
                item = enrich_with_summary(item)
                time.sleep(0.3)  # be polite to the source's servers
            items.append(item)
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
            short_summary = extractive_summary(summary, max_sentences=2) or summary
            items.append({
                "title": title,
                "url": link,
                "summary": f"{author_str} — {short_summary}" if author_str else short_summary,
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
            link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            stats_line = f"{hit.get('points', 0)} points, {hit.get('num_comments', 0)} comments on Hacker News"
            item = {
                "title": clean_text(hit.get("title", ""), 160),
                "url": link,
                "summary": stats_line,
                "source": "Hacker News",
                "date": datetime.fromtimestamp(hit.get("created_at_i", time.time()), tz=timezone.utc).isoformat(),
            }
            article_text = fetch_article_text(link)
            if len(article_text) > 300:
                summary = extractive_summary(article_text)
                if summary:
                    item["summary"] = f"{summary} ({stats_line})"
            items.append(item)
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
