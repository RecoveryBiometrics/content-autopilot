"""
Web scraper — crawls a website and returns articles one at a time.
Supports full site crawl, section-only, and sitemap modes.
"""

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent.parent
CACHE_FILE = BASE_DIR / "data" / "articles-cache.json"
PUBLISHED_FILE = BASE_DIR / "data" / "published.json"


def _load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return []


def _save_cache(articles):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(articles, indent=2))


def _load_published_urls():
    if PUBLISHED_FILE.exists():
        published = json.loads(PUBLISHED_FILE.read_text())
        return {p.get("source", "") for p in published if p.get("source")}
    return set()


def _scrape_page(url):
    """Scrape a single page and extract the main content."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "PodcastPipeline/1.0"})
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove nav, footer, sidebar, scripts, styles
    for tag in soup.find_all(["nav", "footer", "aside", "script", "style", "header"]):
        tag.decompose()

    # Try to find the main content
    main = soup.find("main") or soup.find("article") or soup.find(role="main")
    if not main:
        main = soup.find("body")
    if not main:
        return None

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    body = main.get_text(separator="\n", strip=True)

    if len(body) < 100:
        return None

    return {
        "title": title,
        "body": body,
        "source_url": url,
        "source_type": "website",
    }


def _discover_from_sitemap(sitemap_url):
    """Parse a sitemap.xml and return all URLs."""
    try:
        resp = requests.get(sitemap_url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    urls = []
    try:
        root = ET.fromstring(resp.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Check for sitemap index
        for sitemap in root.findall(".//sm:sitemap/sm:loc", ns):
            urls.extend(_discover_from_sitemap(sitemap.text.strip()))

        # Get URLs
        for url in root.findall(".//sm:url/sm:loc", ns):
            urls.append(url.text.strip())
    except ET.ParseError:
        pass

    return urls


def _discover_from_crawl(base_url, section=None):
    """Crawl a site and discover article URLs."""
    start_url = base_url
    if section:
        start_url = urljoin(base_url, section)

    visited = set()
    to_visit = [start_url]
    found = []
    domain = urlparse(base_url).netloc

    while to_visit and len(visited) < 500:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "PodcastPipeline/1.0"})
            resp.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Check if this page has enough content to be an article
        main = soup.find("main") or soup.find("article") or soup.find("body")
        if main:
            text = main.get_text(strip=True)
            if len(text) > 300:
                found.append(url)

        # Find links to follow
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"]).split("#")[0].split("?")[0]
            parsed = urlparse(href)
            if parsed.netloc == domain and href not in visited:
                if section and not parsed.path.startswith(section):
                    continue
                to_visit.append(href)

    return found


def build_cache():
    """Discover all articles and cache them."""
    website_url = os.getenv("WEBSITE_URL", "")
    crawl_mode = os.getenv("WEBSITE_CRAWL_MODE", "full")
    sitemap_url = os.getenv("WEBSITE_SITEMAP_URL", "")
    section = os.getenv("WEBSITE_SECTION", "")

    if not website_url:
        return []

    if crawl_mode == "sitemap" and sitemap_url:
        urls = _discover_from_sitemap(sitemap_url)
    else:
        urls = _discover_from_crawl(website_url, section=section if crawl_mode == "section" else None)

    articles = [{"url": url, "scraped": False} for url in urls]
    _save_cache(articles)
    return articles


def get_next_article():
    """Get the next unprocessed article."""
    cache = _load_cache()

    if not cache:
        cache = build_cache()

    if not cache:
        return None

    published_urls = _load_published_urls()

    for article in cache:
        if article["url"] not in published_urls and not article.get("scraped"):
            content = _scrape_page(article["url"])
            if content:
                article["scraped"] = True
                _save_cache(cache)
                return content

    return None
