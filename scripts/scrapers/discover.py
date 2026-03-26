"""
Topic discovery engine — continuously finds new topics by searching
the web and Reddit for content in the user's niche.

Never repeats a topic that's already been covered.
"""

import json
import os
import re
import random
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent.parent
PUBLISHED_FILE = BASE_DIR / "data" / "published.json"
DISCOVERED_FILE = BASE_DIR / "data" / "discovered-topics.json"


def _load_published_titles():
    """Get all titles we've already covered."""
    if PUBLISHED_FILE.exists():
        published = json.loads(PUBLISHED_FILE.read_text())
        return {p.get("title", "").lower().strip() for p in published if p.get("title")}
    return set()


def _load_discovered():
    if DISCOVERED_FILE.exists():
        return json.loads(DISCOVERED_FILE.read_text())
    return []


def _save_discovered(topics):
    DISCOVERED_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISCOVERED_FILE.write_text(json.dumps(topics, indent=2))


def _search_duckduckgo(query, num_results=10):
    """Search DuckDuckGo and return results."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "PodcastPipeline/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for result in soup.find_all("div", class_="result")[:num_results]:
        title_tag = result.find("a", class_="result__a")
        snippet_tag = result.find("a", class_="result__snippet")
        url_tag = result.find("a", class_="result__url")

        if title_tag:
            results.append({
                "title": title_tag.get_text(strip=True),
                "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                "url": url_tag.get("href", "") if url_tag else "",
            })

    return results


def _search_reddit(query, subreddits=None, num_results=10):
    """Search Reddit for discussions and questions."""
    results = []

    # Search via DuckDuckGo with site:reddit.com
    reddit_query = f"site:reddit.com {query}"
    if subreddits:
        # Also search specific subreddits
        for sub in subreddits[:3]:
            sub_query = f"site:reddit.com/r/{sub} {query}"
            results.extend(_search_duckduckgo(sub_query, num_results=5))

    results.extend(_search_duckduckgo(reddit_query, num_results=num_results))

    return results


def _scrape_reddit_thread(url):
    """Try to scrape key points from a Reddit thread."""
    try:
        # Use old.reddit.com for simpler HTML
        url = url.replace("www.reddit.com", "old.reddit.com")
        resp = requests.get(
            url,
            headers={"User-Agent": "PodcastPipeline/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    comments = []
    for comment in soup.find_all("div", class_="md")[:10]:
        text = comment.get_text(strip=True)
        if len(text) > 50:
            comments.append(text[:500])

    return "\n\n".join(comments)


def _is_duplicate(title, published_titles):
    """Check if a topic is too similar to one we've already covered."""
    title_lower = title.lower().strip()

    if title_lower in published_titles:
        return True

    # Check for high word overlap
    title_words = set(title_lower.split())
    for pub_title in published_titles:
        pub_words = set(pub_title.split())
        if len(title_words) > 3 and len(pub_words) > 3:
            overlap = len(title_words & pub_words) / max(len(title_words), len(pub_words))
            if overlap > 0.7:
                return True

    return False


def discover_topics(niche, count=10, subreddits=None):
    """
    Discover new topics in the niche by searching the web and Reddit.

    Args:
        niche: the podcast's niche/topic
        count: how many new topics to find
        subreddits: list of subreddit names to search

    Returns:
        list of topic dicts with 'title', 'research', 'source_urls'
    """
    published_titles = _load_published_titles()
    discovered = _load_discovered()
    discovered_titles = {t.get("title", "").lower() for t in discovered}

    # Generate search queries based on the niche
    search_queries = [
        f"{niche} tips 2026",
        f"{niche} common mistakes",
        f"{niche} how to",
        f"{niche} best practices",
        f"{niche} beginners guide",
        f"what is {niche}",
        f"{niche} tools",
        f"{niche} trends",
        f"{niche} vs",
        f"{niche} FAQ",
        f"{niche} problems solutions",
        f"{niche} case study",
    ]

    # Shuffle so we don't always search the same queries
    random.shuffle(search_queries)

    new_topics = []

    for query in search_queries:
        if len(new_topics) >= count:
            break

        # Web search
        web_results = _search_duckduckgo(query, num_results=5)

        for result in web_results:
            title = result.get("title", "")
            if not title or len(title) < 10:
                continue

            if _is_duplicate(title, published_titles | discovered_titles):
                continue

            # Build research from the search result
            research = f"Source: {result.get('url', '')}\n"
            research += f"Summary: {result.get('snippet', '')}\n"

            new_topics.append({
                "title": title,
                "research": research,
                "source_urls": [result.get("url", "")],
                "source_type": "discovered",
                "discovered_via": "web_search",
                "query": query,
            })

            discovered_titles.add(title.lower())

            if len(new_topics) >= count:
                break

        # Reddit search
        if len(new_topics) < count:
            reddit_results = _search_reddit(query, subreddits=subreddits, num_results=5)

            for result in reddit_results:
                title = result.get("title", "")
                if not title or len(title) < 10:
                    continue

                if _is_duplicate(title, published_titles | discovered_titles):
                    continue

                research = f"Reddit discussion: {result.get('url', '')}\n"
                research += f"Context: {result.get('snippet', '')}\n"

                # Try to get more from the thread
                thread_url = result.get("url", "")
                if "reddit.com" in thread_url:
                    thread_content = _scrape_reddit_thread(thread_url)
                    if thread_content:
                        research += f"\nKey points from discussion:\n{thread_content[:1500]}\n"

                new_topics.append({
                    "title": title,
                    "research": research,
                    "source_urls": [result.get("url", "")],
                    "source_type": "discovered",
                    "discovered_via": "reddit",
                    "query": query,
                })

                discovered_titles.add(title.lower())

                if len(new_topics) >= count:
                    break

    # Save discovered topics
    discovered.extend(new_topics)
    _save_discovered(discovered)

    return new_topics


def get_next_discovered():
    """Get the next undiscovered topic, or discover new ones."""
    niche = os.getenv("PODCAST_NICHE", "")
    if not niche:
        return None

    # Check for unused discovered topics first
    discovered = _load_discovered()
    published_titles = _load_published_titles()

    for topic in discovered:
        if not _is_duplicate(topic.get("title", ""), published_titles):
            return {
                "title": topic["title"],
                "body": f"Topic: {topic['title']}\n\nResearch:\n{topic.get('research', '')}",
                "source_url": topic.get("source_urls", [""])[0],
                "source_type": "discovered",
                "research": topic.get("research", ""),
            }

    # Discover new topics
    subreddits_str = os.getenv("REDDIT_SUBREDDITS", "")
    subreddits = [s.strip() for s in subreddits_str.split(",") if s.strip()] if subreddits_str else None

    new_topics = discover_topics(niche, count=10, subreddits=subreddits)

    if new_topics:
        topic = new_topics[0]
        return {
            "title": topic["title"],
            "body": f"Topic: {topic['title']}\n\nResearch:\n{topic.get('research', '')}",
            "source_url": topic.get("source_urls", [""])[0],
            "source_type": "discovered",
            "research": topic.get("research", ""),
        }

    return None
