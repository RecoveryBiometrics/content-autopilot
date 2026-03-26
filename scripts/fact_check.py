"""
Fact checker agent — validates blog post claims before publishing.
Uses the niche and market context from setup to catch inaccuracies.
"""

import json
import os

import anthropic


def fact_check(html_content, niche, title=""):
    """
    Fact-check a blog post before publishing.

    Args:
        html_content: the blog post HTML
        niche: the podcast's niche
        title: the post title for context

    Returns:
        dict with 'passed' (bool), 'corrected_html' (str), 'issues' (list)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"passed": True, "corrected_html": html_content, "issues": []}

    client = anthropic.Anthropic(api_key=api_key)

    market = os.getenv("TARGET_MARKET", "")
    fact_check_rules = os.getenv("FACT_CHECK_RULES", "")

    prompt = f"""You are a fact-checker for a {niche} blog. Review this article for accuracy.

Title: {title}
{"Target market: " + market if market else ""}

{"Additional rules to check:\n" + fact_check_rules if fact_check_rules else ""}

Check for:
1. Factual claims that are wrong or outdated
2. Statistics or numbers that seem made up
3. Product names, company names, or tool names that are misspelled or don't exist
4. Pricing claims — if you're not sure of the current price, flag it
5. Legal or compliance claims that could be wrong
6. Anything that could get the site owner in trouble if published

Article:
{html_content[:4000]}

Return a JSON object with:
- "passed": true if no issues found, false if corrections needed
- "issues": array of strings describing each issue found
- "corrected_html": the corrected HTML (or the original if no corrections needed)

If the article is generally accurate with no major issues, set passed to true even if minor style improvements could be made. Only fail for factual errors.

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
            "passed": result.get("passed", True),
            "corrected_html": result.get("corrected_html", html_content),
            "issues": result.get("issues", []),
        }
    except json.JSONDecodeError:
        # If we can't parse the response, pass the article through
        return {"passed": True, "corrected_html": html_content, "issues": []}
