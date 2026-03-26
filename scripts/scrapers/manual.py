"""
Manual topic source — uses topics from data/topics.json or CLI input.
Optionally researches each topic via web search before passing to NotebookLM.
"""

import json
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent.parent
TOPICS_FILE = BASE_DIR / "data" / "topics.json"
PUBLISHED_FILE = BASE_DIR / "data" / "published.json"


def _load_topics():
    if TOPICS_FILE.exists():
        return json.loads(TOPICS_FILE.read_text())
    return []


def _save_topics(topics):
    TOPICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOPICS_FILE.write_text(json.dumps(topics, indent=2))


def _load_published_titles():
    if PUBLISHED_FILE.exists():
        published = json.loads(PUBLISHED_FILE.read_text())
        return {p.get("title", "").lower() for p in published if p.get("title")}
    return set()


def _search_duckduckgo(query, num_results=5):
    """Search DuckDuckGo and return top results as research material."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "PodcastPipeline/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for result in soup.find_all("div", class_="result")[:num_results]:
        title_tag = result.find("a", class_="result__a")
        snippet_tag = result.find("a", class_="result__snippet")

        if title_tag and snippet_tag:
            results.append(f"- {title_tag.get_text(strip=True)}: {snippet_tag.get_text(strip=True)}")

    return "\n".join(results)


def research_topic(topic):
    """Research a topic and return content for NotebookLM."""
    research = _search_duckduckgo(topic)

    body = f"Topic: {topic}\n\n"
    if research:
        body += f"Research findings:\n{research}\n\n"
    body += f"Please create a comprehensive, engaging discussion about: {topic}"

    return {
        "title": topic,
        "body": body,
        "source_url": "",
        "source_type": "manual",
    }


def get_next_topic():
    """Get the next unprocessed topic from topics.json."""
    topics = _load_topics()
    if not topics:
        return None

    published_titles = _load_published_titles()

    for topic in topics:
        if isinstance(topic, str):
            title = topic
        elif isinstance(topic, dict):
            title = topic.get("title", topic.get("topic", ""))
        else:
            continue

        if title.lower() not in published_titles:
            return research_topic(title)

    return None
