#!/usr/bin/env python3
"""
Static site builder — generates a blog from post JSON files.

Reads design config from .env (theme, accent color, font, logo).
Auto-discovers categories from published posts.
Generates: homepage, post pages, category pages, sitemap, robots.txt, llms.txt.

Usage:
  python3 site/build.py              # build the site
  python3 site/build.py --serve      # build + local preview server
"""

import argparse
import html
import json
import os
import re
import shutil
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

SITE_DIR = Path(__file__).parent
POSTS_DIR = SITE_DIR / "posts"
PUBLIC_DIR = SITE_DIR / "public"

# Config from .env
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")
SITE_NAME = os.getenv("SITE_NAME", "My Podcast Blog")
SITE_TAGLINE = os.getenv("SITE_TAGLINE", "")
AFFILIATE_LINK = os.getenv("AFFILIATE_LINK", "")
OG_IMAGE = os.getenv("OG_IMAGE_URL", "")
LOGO = os.getenv("SITE_LOGO", "")

# Design config
THEME = os.getenv("SITE_THEME", "dark")
ACCENT = os.getenv("SITE_ACCENT_COLOR", "#f59e0b")
FONT = os.getenv("SITE_FONT", "DM Sans")

# Derive colors from theme
if THEME == "dark":
    BG = "#07080a"
    SURFACE = "#111520"
    TEXT_PRIMARY = "#eef2ff"
    TEXT_SECONDARY = "#7c8aab"
    TEXT_MUTED = "#3d4a63"
    BORDER = "#1e2736"
else:
    BG = "#ffffff"
    SURFACE = "#f8f9fa"
    TEXT_PRIMARY = "#1a1a2e"
    TEXT_SECONDARY = "#555555"
    TEXT_MUTED = "#999999"
    BORDER = "#e0e0e0"

# Google Font URL
FONT_URL = f"https://fonts.googleapis.com/css2?family={FONT.replace(' ', '+')}:wght@400;700;800&display=swap"


def _slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80].strip("-")


# ── Load Posts ───────────────────────────────────────────────────────────────

def load_posts():
    """Load all post JSON files, sorted by date (newest first)."""
    posts = []
    if not POSTS_DIR.exists():
        return posts

    for f in POSTS_DIR.glob("*.json"):
        try:
            post = json.loads(f.read_text())
            post.setdefault("slug", f.stem)
            post.setdefault("category", "General")
            post.setdefault("published_at", "")
            post.setdefault("title", "Untitled")
            posts.append(post)
        except (json.JSONDecodeError, KeyError):
            continue

    posts.sort(key=lambda p: p.get("published_at", ""), reverse=True)
    return posts


def discover_categories(posts):
    """Auto-discover categories from posts. Returns list of {name, slug, count}."""
    cat_counts = {}
    for post in posts:
        cat = post.get("category", "General")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    categories = []
    for name, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        categories.append({
            "name": name,
            "slug": _slugify(name),
            "count": count,
        })

    return categories


# ── CSS ──────────────────────────────────────────────────────────────────────

def site_css():
    return f"""
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: '{FONT}', sans-serif;
    font-size: 18px;
    line-height: 1.75;
    color: {TEXT_PRIMARY};
    background: {BG};
}}

a {{ color: {ACCENT}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

.container {{ max-width: 1100px; margin: 0 auto; padding: 0 24px; }}
.narrow {{ max-width: 780px; }}

/* Header */
header {{
    border-bottom: 1px solid {BORDER};
    padding: 20px 0;
}}
header .container {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
}}
.site-title {{
    font-size: 1.4rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    text-decoration: none;
}}
.site-title:hover {{ text-decoration: none; color: {ACCENT}; }}
nav a {{
    color: {TEXT_SECONDARY};
    margin-left: 24px;
    font-size: 0.9rem;
    font-weight: 700;
}}
nav a:hover {{ color: {ACCENT}; }}
.logo {{ height: 36px; margin-right: 12px; vertical-align: middle; }}

/* Hero */
.hero {{
    padding: 80px 0 60px;
    text-align: center;
}}
.hero h1 {{
    font-size: clamp(2rem, 4vw, 3.2rem);
    font-weight: 800;
    line-height: 1.15;
    letter-spacing: -0.5px;
    margin-bottom: 16px;
}}
.hero p {{
    font-size: 1.15rem;
    color: {TEXT_SECONDARY};
    max-width: 600px;
    margin: 0 auto;
}}

/* Post Cards */
.posts-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 28px;
    padding: 40px 0 60px;
}}
.post-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 28px;
    transition: border-color 0.2s;
}}
.post-card:hover {{ border-color: {ACCENT}; }}
.post-card h2 {{
    font-size: 1.15rem;
    font-weight: 800;
    margin-bottom: 8px;
    line-height: 1.3;
}}
.post-card h2 a {{ color: {TEXT_PRIMARY}; }}
.post-card h2 a:hover {{ color: {ACCENT}; text-decoration: none; }}
.post-card .meta {{
    font-size: 0.8rem;
    color: {TEXT_MUTED};
    margin-bottom: 12px;
}}
.post-card .category-badge {{
    display: inline-block;
    background: {ACCENT}22;
    color: {ACCENT};
    font-size: 0.75rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.post-card .excerpt {{
    color: {TEXT_SECONDARY};
    font-size: 0.95rem;
    line-height: 1.6;
}}

/* Single Post */
.post-content {{
    padding: 60px 0;
}}
.post-content h1 {{
    font-size: clamp(1.8rem, 3.5vw, 2.8rem);
    font-weight: 800;
    line-height: 1.15;
    letter-spacing: -0.5px;
    margin-bottom: 16px;
}}
.post-content .post-meta {{
    color: {TEXT_MUTED};
    font-size: 0.85rem;
    margin-bottom: 40px;
    padding-bottom: 24px;
    border-bottom: 1px solid {BORDER};
}}
.post-content h2 {{
    font-size: 1.5rem;
    font-weight: 800;
    margin: 40px 0 16px;
}}
.post-content h3 {{
    font-size: 1.2rem;
    font-weight: 700;
    margin: 32px 0 12px;
}}
.post-content p {{ margin-bottom: 16px; }}
.post-content ul, .post-content ol {{
    margin: 0 0 16px 24px;
}}
.post-content li {{ margin-bottom: 6px; }}
.post-content img {{
    max-width: 100%;
    border-radius: 8px;
    margin: 20px 0;
}}

/* Pro Tip box */
.pro-tip {{
    background: {ACCENT}11;
    border-left: 4px solid {ACCENT};
    padding: 20px 24px;
    border-radius: 0 8px 8px 0;
    margin: 24px 0;
}}
.pro-tip strong {{ color: {ACCENT}; }}

/* FAQ */
details {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 12px;
}}
details summary {{
    font-weight: 700;
    cursor: pointer;
    color: {TEXT_PRIMARY};
}}
details summary:hover {{ color: {ACCENT}; }}
details p {{ margin-top: 12px; color: {TEXT_SECONDARY}; }}

/* CTA Box */
.cta-box {{
    background: {SURFACE};
    border: 2px solid {ACCENT};
    border-radius: 12px;
    padding: 32px;
    text-align: center;
    margin: 40px 0;
}}
.cta-box a {{
    display: inline-block;
    background: {ACCENT};
    color: {BG};
    font-weight: 800;
    padding: 12px 32px;
    border-radius: 8px;
    margin-top: 12px;
    text-decoration: none;
}}
.cta-box a:hover {{ opacity: 0.9; text-decoration: none; }}

/* Category page */
.category-header {{
    padding: 60px 0 20px;
}}
.category-header h1 {{
    font-size: 2rem;
    font-weight: 800;
}}
.category-header p {{
    color: {TEXT_SECONDARY};
    margin-top: 8px;
}}

/* Footer */
footer {{
    border-top: 1px solid {BORDER};
    padding: 40px 0;
    text-align: center;
    color: {TEXT_MUTED};
    font-size: 0.85rem;
}}
footer a {{ color: {TEXT_SECONDARY}; }}

/* Responsive */
@media (max-width: 640px) {{
    .posts-grid {{ grid-template-columns: 1fr; }}
    .hero {{ padding: 48px 0 36px; }}
    header .container {{ flex-direction: column; text-align: center; }}
    nav a {{ margin: 0 12px; }}
}}
"""


# ── HTML Templates ───────────────────────────────────────────────────────────

def base_html(title, description, canonical, body, categories=None):
    """Wrap body content in the full HTML page template."""
    cats = categories or []

    nav_links = ""
    for c in cats[:6]:
        nav_links += f'<a href="/category/{c["slug"]}/">{c["name"]}</a>'

    logo_html = ""
    if LOGO:
        logo_html = f'<img src="{html.escape(LOGO)}" alt="{html.escape(SITE_NAME)}" class="logo">'

    og_img = f'<meta property="og:image" content="{html.escape(OG_IMAGE)}">' if OG_IMAGE else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description[:160])}">
<link rel="canonical" href="{html.escape(canonical)}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description[:160])}">
<meta property="og:url" content="{html.escape(canonical)}">
<meta property="og:type" content="website">
{og_img}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{FONT_URL}" rel="stylesheet">
<style>{site_css()}</style>
</head>
<body>
<header>
<div class="container">
<a href="/" class="site-title">{logo_html}{html.escape(SITE_NAME)}</a>
<nav>{nav_links}</nav>
</div>
</header>
{body}
<footer>
<div class="container">
<p>&copy; {datetime.now().year} {html.escape(SITE_NAME)}. All rights reserved.</p>
</div>
</footer>
</body>
</html>"""


def build_homepage(posts, categories):
    """Build the homepage with hero and post grid."""
    cards = ""
    for post in posts[:30]:
        date_str = ""
        if post.get("published_at"):
            try:
                dt = datetime.fromisoformat(post["published_at"])
                date_str = dt.strftime("%b %d, %Y")
            except (ValueError, TypeError):
                pass

        excerpt = post.get("meta_description", "")[:150]
        cat = post.get("category", "General")
        cat_slug = _slugify(cat)

        cards += f"""
<div class="post-card">
  <a href="/category/{cat_slug}/" class="category-badge">{html.escape(cat)}</a>
  <h2><a href="/blog/{post['slug']}/">{html.escape(post['title'])}</a></h2>
  <div class="meta">{date_str}</div>
  <p class="excerpt">{html.escape(excerpt)}</p>
</div>"""

    tagline_html = f"<p>{html.escape(SITE_TAGLINE)}</p>" if SITE_TAGLINE else ""

    body = f"""
<div class="container">
<div class="hero">
  <h1>{html.escape(SITE_NAME)}</h1>
  {tagline_html}
</div>
<div class="posts-grid">
{cards}
</div>
</div>"""

    return base_html(
        title=f"{SITE_NAME} — {SITE_TAGLINE}" if SITE_TAGLINE else SITE_NAME,
        description=SITE_TAGLINE or f"Latest articles from {SITE_NAME}",
        canonical=SITE_URL or "/",
        body=body,
        categories=categories,
    )


def build_post_page(post, categories):
    """Build a single post page."""
    date_str = ""
    if post.get("published_at"):
        try:
            dt = datetime.fromisoformat(post["published_at"])
            date_str = dt.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            pass

    cat = post.get("category", "General")
    cat_slug = _slugify(cat)

    body = f"""
<div class="container narrow">
<article class="post-content">
  <a href="/category/{cat_slug}/" class="category-badge" style="margin-bottom:16px;display:inline-block">{html.escape(cat)}</a>
  <h1>{html.escape(post['title'])}</h1>
  <div class="post-meta">{date_str}</div>
  {post.get('html_content', '')}
</article>
</div>"""

    return base_html(
        title=f"{post['title']} — {SITE_NAME}",
        description=post.get("meta_description", ""),
        canonical=f"{SITE_URL}/blog/{post['slug']}/" if SITE_URL else f"/blog/{post['slug']}/",
        body=body,
        categories=categories,
    )


def build_category_page(category, posts, categories):
    """Build a category listing page."""
    cat_posts = [p for p in posts if _slugify(p.get("category", "General")) == category["slug"]]

    cards = ""
    for post in cat_posts:
        date_str = ""
        if post.get("published_at"):
            try:
                dt = datetime.fromisoformat(post["published_at"])
                date_str = dt.strftime("%b %d, %Y")
            except (ValueError, TypeError):
                pass

        excerpt = post.get("meta_description", "")[:150]

        cards += f"""
<div class="post-card">
  <h2><a href="/blog/{post['slug']}/">{html.escape(post['title'])}</a></h2>
  <div class="meta">{date_str}</div>
  <p class="excerpt">{html.escape(excerpt)}</p>
</div>"""

    body = f"""
<div class="container">
<div class="category-header">
  <h1>{html.escape(category['name'])}</h1>
  <p>{category['count']} article{'s' if category['count'] != 1 else ''}</p>
</div>
<div class="posts-grid">
{cards}
</div>
</div>"""

    return base_html(
        title=f"{category['name']} — {SITE_NAME}",
        description=f"{category['name']} articles and guides from {SITE_NAME}",
        canonical=f"{SITE_URL}/category/{category['slug']}/" if SITE_URL else f"/category/{category['slug']}/",
        body=body,
        categories=categories,
    )


def build_sitemap(posts, categories):
    """Generate sitemap.xml."""
    urls = []

    # Homepage
    if SITE_URL:
        urls.append(f"  <url><loc>{SITE_URL}/</loc><priority>1.0</priority></url>")

        # Posts
        for post in posts:
            urls.append(f"  <url><loc>{SITE_URL}/blog/{post['slug']}/</loc></url>")

        # Categories
        for cat in categories:
            urls.append(f"  <url><loc>{SITE_URL}/category/{cat['slug']}/</loc></url>")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


def build_robots():
    """Generate robots.txt."""
    sitemap_line = f"Sitemap: {SITE_URL}/sitemap.xml" if SITE_URL else ""
    return f"""User-agent: *
Allow: /

{sitemap_line}"""


def build_llms_txt(posts):
    """Generate llms.txt for AI model discoverability."""
    lines = [f"# {SITE_NAME}", ""]
    if SITE_TAGLINE:
        lines.append(f"> {SITE_TAGLINE}")
        lines.append("")

    lines.append("## Articles")
    lines.append("")

    for post in posts:
        url = f"{SITE_URL}/blog/{post['slug']}/" if SITE_URL else f"/blog/{post['slug']}/"
        lines.append(f"- [{post['title']}]({url})")

    return "\n".join(lines)


# ── Build ────────────────────────────────────────────────────────────────────

def build():
    """Build the entire site."""
    print(f"  Building site: {SITE_NAME}")

    # Load posts
    posts = load_posts()
    print(f"  Found {len(posts)} posts")

    if not posts:
        print("  No posts found in site/posts/ — nothing to build.")
        return

    # Discover categories
    categories = discover_categories(posts)
    print(f"  Categories: {', '.join(c['name'] for c in categories)}")

    # Clean public directory
    if PUBLIC_DIR.exists():
        shutil.rmtree(PUBLIC_DIR)
    PUBLIC_DIR.mkdir(parents=True)

    # Homepage
    (PUBLIC_DIR / "index.html").write_text(build_homepage(posts, categories))
    print("  Built: index.html")

    # Post pages
    blog_dir = PUBLIC_DIR / "blog"
    for post in posts:
        post_dir = blog_dir / post["slug"]
        post_dir.mkdir(parents=True, exist_ok=True)
        (post_dir / "index.html").write_text(build_post_page(post, categories))
    print(f"  Built: {len(posts)} post pages")

    # Category pages
    cat_dir = PUBLIC_DIR / "category"
    for cat in categories:
        c_dir = cat_dir / cat["slug"]
        c_dir.mkdir(parents=True, exist_ok=True)
        (c_dir / "index.html").write_text(build_category_page(cat, posts, categories))
    print(f"  Built: {len(categories)} category pages")

    # Sitemap
    (PUBLIC_DIR / "sitemap.xml").write_text(build_sitemap(posts, categories))
    print("  Built: sitemap.xml")

    # Robots.txt
    (PUBLIC_DIR / "robots.txt").write_text(build_robots())
    print("  Built: robots.txt")

    # llms.txt
    (PUBLIC_DIR / "llms.txt").write_text(build_llms_txt(posts))
    print("  Built: llms.txt")

    # Copy logo if it's a local file
    if LOGO and os.path.isfile(LOGO):
        shutil.copy2(LOGO, PUBLIC_DIR / os.path.basename(LOGO))
        print(f"  Copied: {os.path.basename(LOGO)}")

    print(f"\n  Site built to site/public/ ({len(posts)} posts, {len(categories)} categories)")


def serve():
    """Start a local preview server."""
    if not PUBLIC_DIR.exists():
        build()

    os.chdir(str(PUBLIC_DIR))
    port = 8000
    print(f"\n  Serving at http://localhost:{port}")
    print("  Press Ctrl+C to stop.\n")
    httpd = HTTPServer(("", port), SimpleHTTPRequestHandler)
    httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Build the blog site")
    parser.add_argument("--serve", action="store_true", help="Build and start local preview")
    args = parser.parse_args()

    build()

    if args.serve:
        serve()


if __name__ == "__main__":
    main()
