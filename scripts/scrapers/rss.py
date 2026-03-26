"""
RSS scraper — reads articles from an RSS/Atom feed.
"""

import json
import os
import re
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent.parent
CACHE_FILE = BASE_DIR / "data" / "rss-cache.json"
PUBLISHED_FILE = BASE_DIR / "data" / "published.json"


def _load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return []


def _save_cache(items):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(items, indent=2))


def _load_published_urls():
    if PUBLISHED_FILE.exists():
        published = json.loads(PUBLISHED_FILE.read_text())
        return {p.get("source", "") for p in published if p.get("source")}
    return set()


def _clean_html(html_content):
    """Strip HTML tags and return clean text."""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def build_cache():
    """Fetch and parse the RSS feed."""
    feed_url = os.getenv("RSS_FEED_URL", "")
    if not feed_url:
        return []

    feed = feedparser.parse(feed_url)

    items = []
    for entry in feed.entries:
        body = ""
        if hasattr(entry, "content") and entry.content:
            body = _clean_html(entry.content[0].get("value", ""))
        elif hasattr(entry, "summary"):
            body = _clean_html(entry.summary)

        items.append({
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "body": body,
            "processed": False,
        })

    _save_cache(items)
    return items


def _fetch_full_article(url):
    """If the RSS body is too short, try scraping the full page."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "PodcastPipeline/1.0"})
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup.find_all(["nav", "footer", "aside", "script", "style", "header"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main:
        return main.get_text(separator="\n", strip=True)

    return None


def get_next_item():
    """Get the next unprocessed RSS item."""
    cache = _load_cache()

    if not cache:
        cache = build_cache()

    if not cache:
        return None

    published_urls = _load_published_urls()

    for item in cache:
        url = item.get("url", "")
        if url not in published_urls and not item.get("processed"):
            body = item.get("body", "")

            # If body is too short, try fetching the full article
            if len(body) < 300 and url:
                full = _fetch_full_article(url)
                if full:
                    body = full

            if len(body) < 100:
                item["processed"] = True
                _save_cache(cache)
                continue

            item["processed"] = True
            _save_cache(cache)

            return {
                "title": item.get("title", ""),
                "body": body,
                "source_url": url,
                "source_type": "rss",
            }

    return None
