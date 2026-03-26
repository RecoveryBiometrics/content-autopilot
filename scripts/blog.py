"""
Blog post writer — uses Claude to write an SEO blog post for each episode.
"""

import json
import os
import re
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).parent.parent
POSTS_DIR = BASE_DIR / "site" / "posts"


def _slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


def write_blog_post(content, seo_data, episode_data=None):
    """
    Write an SEO blog post for an episode.

    Args:
        content: dict with 'title' and 'body'
        seo_data: dict with 'title', 'description', 'tags'
        episode_data: dict with transistor episode info (optional)

    Returns:
        dict with 'slug', 'path' keys
    """
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY required for blog posts")

    client = anthropic.Anthropic(api_key=api_key)

    podcast_name = os.getenv("PODCAST_NAME", "")
    niche = os.getenv("PODCAST_NICHE", "")
    affiliate_link = os.getenv("AFFILIATE_LINK", "")
    site_name = os.getenv("SITE_NAME", "")

    embed_html = ""
    if episode_data and episode_data.get("embed_html"):
        embed_html = episode_data["embed_html"]

    prompt = f"""Write an SEO blog post based on this podcast episode.

Podcast: {podcast_name}
Niche: {niche}
Episode title: {seo_data.get('title', content.get('title', ''))}
Episode description: {seo_data.get('description', '')}
Tags: {', '.join(seo_data.get('tags', []))}

Source content (first 3000 chars):
{content.get('body', '')[:3000]}

Requirements:
- 800-1200 words
- Include a table of contents at the top
- Use H2 and H3 headings
- Include a FAQ section (3-5 questions) at the bottom
- Write in a conversational, expert tone
- Include practical tips and actionable advice
{"- Include this CTA link naturally: " + affiliate_link if affiliate_link else ""}
{"- Embed the podcast player: " + embed_html if embed_html else ""}

Return the blog post as HTML (just the article body, no <html> or <head> tags).
Do NOT wrap in markdown fences."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    html_content = response.content[0].text.strip()

    # Remove markdown fences if present
    if html_content.startswith("```"):
        lines = html_content.split("\n")
        html_content = "\n".join(lines[1:-1])

    slug = _slugify(seo_data.get("title", content.get("title", "untitled")))

    post = {
        "title": seo_data.get("title", content.get("title", "")),
        "slug": slug,
        "meta_description": seo_data.get("description", ""),
        "tags": seo_data.get("tags", []),
        "html_content": html_content,
        "source_url": content.get("source_url", ""),
        "source_type": content.get("source_type", ""),
        "transistor_id": episode_data.get("id", "") if episode_data else "",
        "published_at": __import__("datetime").datetime.now().isoformat(),
    }

    post_path = POSTS_DIR / f"{slug}.json"
    post_path.write_text(json.dumps(post, indent=2))

    return {"slug": slug, "path": str(post_path)}
