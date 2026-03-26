"""
SEO metadata writer — uses Claude to generate title, description, and tags.
"""

import json
import os

import anthropic


def write_seo(content, niche=""):
    """
    Generate SEO metadata for an episode.

    Args:
        content: dict with 'title' and 'body' keys
        niche: the podcast's niche/topic for context

    Returns:
        dict with 'title', 'description', 'tags' keys
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "title": content.get("title", ""),
            "description": content.get("body", "")[:200],
            "tags": [],
        }

    client = anthropic.Anthropic(api_key=api_key)

    podcast_name = os.getenv("PODCAST_NAME", "")
    affiliate_link = os.getenv("AFFILIATE_LINK", "")

    prompt = f"""Write SEO metadata for a podcast episode.

Podcast: {podcast_name}
Niche: {niche}
Original title: {content.get('title', '')}

Article content (first 2000 chars):
{content.get('body', '')[:2000]}

Return a JSON object with:
- "title": A compelling podcast episode title (50-70 chars). Don't start with "How to" every time.
- "description": Episode description for podcast apps (150-250 chars). Make people want to listen.
- "tags": Array of 5-8 relevant tags/keywords.

{"Include this link in the description: " + affiliate_link if affiliate_link else ""}

Return ONLY valid JSON, no markdown fences."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()

    # Parse JSON from response
    try:
        # Handle markdown fences if present
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "title": content.get("title", ""),
            "description": content.get("body", "")[:200],
            "tags": [],
        }
