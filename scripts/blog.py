"""
Blog post pipeline — 3-agent system:
  1. Researcher — searches web + Reddit for real sources
  2. Writer — Claude writes SEO blog post from research
  3. Fact checker — validates claims before publishing
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent
POSTS_DIR = BASE_DIR / "site" / "posts"


def _slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def _search_duckduckgo(query, num_results=5):
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

        if title_tag and snippet_tag:
            results.append({
                "title": title_tag.get_text(strip=True),
                "snippet": snippet_tag.get_text(strip=True),
            })

    return results


def _search_reddit(query, subreddits=None):
    """Search Reddit for discussions."""
    results = []
    reddit_query = f"site:reddit.com {query}"

    if subreddits:
        for sub in subreddits[:3]:
            sub_results = _search_duckduckgo(f"site:reddit.com/r/{sub} {query}", num_results=3)
            results.extend(sub_results)

    results.extend(_search_duckduckgo(reddit_query, num_results=5))
    return results


# ── Agent 1: Researcher ─────────────────────────────────────────────────────

def research(title, niche):
    """
    Agent 1: Research the topic using web search + Reddit.
    Returns structured research for the writer.
    """
    # SERP research
    serp_results = _search_duckduckgo(f"{title} {niche}", num_results=5)
    serp_text = "\n".join(
        f"- {r['title']}: {r['snippet']}" for r in serp_results
    )

    # Reddit research
    subreddits_str = os.getenv("REDDIT_SUBREDDITS", "")
    subreddits = [s.strip() for s in subreddits_str.split(",") if s.strip()] if subreddits_str else None

    reddit_results = _search_reddit(title, subreddits=subreddits)
    reddit_text = "\n".join(
        f"- {r['title']}: {r['snippet']}" for r in reddit_results
    )

    return {
        "serp": serp_text or "No web results found.",
        "reddit": reddit_text or "No Reddit discussions found.",
        "num_sources": len(serp_results) + len(reddit_results),
    }


# ── Agent 2: Writer ─────────────────────────────────────────────────────────

def write(content, seo_data, research_data, episode_data=None):
    """
    Agent 2: Write the blog post using research and episode content.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY required for blog posts")

    client = anthropic.Anthropic(api_key=api_key)

    podcast_name = os.getenv("PODCAST_NAME", "")
    niche = os.getenv("PODCAST_NICHE", "")
    affiliate_link = os.getenv("AFFILIATE_LINK", "")
    categories_str = os.getenv("SITE_CATEGORIES", "")

    embed_html = ""
    if episode_data and episode_data.get("embed_html"):
        embed_html = episode_data["embed_html"]

    prompt = f"""You are a blog writer for a {niche} podcast. Write an SEO blog post.

Podcast: {podcast_name}
Episode title: {seo_data.get('title', content.get('title', ''))}
Episode description: {seo_data.get('description', '')}
Tags: {', '.join(seo_data.get('tags', []))}

Source content:
{content.get('body', '')[:2000]}

Web research (SERP):
{research_data.get('serp', 'None')}

Reddit discussions:
{research_data.get('reddit', 'None')}

{"Available categories: " + categories_str if categories_str else "Assign a category that best fits this content."}

Requirements:
- 800-1200 words
- Include a table of contents at the top (anchor links to H2s)
- Use H2 and H3 headings that are good for SEO
- Include a Pro Tip callout box (use <div class="pro-tip"> wrapper)
- Include a FAQ section (3-5 questions) at the bottom with <details> tags
- Write in a conversational, expert tone — not salesy
- Reference specific facts from the research above — don't make things up
- Include practical, actionable advice
{"- Include this CTA link naturally (once in the middle, once at the end): " + affiliate_link if affiliate_link else ""}
{"- Embed the podcast player near the top: " + embed_html if embed_html else ""}

Return a JSON object with:
- "html_content": the blog post as HTML (article body only, no <html>/<head>)
- "category": the category this post belongs to

Return ONLY valid JSON, no markdown fences."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    try:
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        result = json.loads(text)
        return {
            "html_content": result.get("html_content", text),
            "category": result.get("category", "General"),
        }
    except json.JSONDecodeError:
        return {"html_content": text, "category": "General"}


# ── Agent 3: Fact Checker (imported from fact_check.py) ──────────────────────

# ── Main Pipeline ────────────────────────────────────────────────────────────

def write_blog_post(content, seo_data, episode_data=None):
    """
    Run the full 3-agent blog pipeline:
    1. Research the topic
    2. Write the post
    3. Fact-check before publishing
    """
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    niche = os.getenv("PODCAST_NICHE", "")
    title = seo_data.get("title", content.get("title", ""))

    # Agent 1: Research
    research_data = research(title, niche)

    # Agent 2: Write
    write_result = write(content, seo_data, research_data, episode_data)
    html_content = write_result.get("html_content", "")
    category = write_result.get("category", "General")

    # Agent 3: Fact check
    try:
        from scripts.fact_check import fact_check
        fc_result = fact_check(html_content, niche, title=title)

        if not fc_result["passed"]:
            html_content = fc_result["corrected_html"]

        issues = fc_result.get("issues", [])
    except Exception:
        issues = []

    # Build the post
    slug = _slugify(title or "untitled")

    post = {
        "title": title,
        "slug": slug,
        "category": category,
        "meta_description": seo_data.get("description", ""),
        "tags": seo_data.get("tags", []),
        "html_content": html_content,
        "source_url": content.get("source_url", ""),
        "source_type": content.get("source_type", ""),
        "transistor_id": episode_data.get("id", "") if episode_data else "",
        "research_sources": research_data.get("num_sources", 0),
        "fact_check_issues": issues,
        "published_at": datetime.now().isoformat(),
    }

    post_path = POSTS_DIR / f"{slug}.json"
    post_path.write_text(json.dumps(post, indent=2))

    return {"slug": slug, "path": str(post_path), "category": category}
