# Blog Deployment Guide

Your podcast pipeline can auto-generate a blog site. Here's how to set it up.

## Option 1: Cloudflare Pages (Recommended — Free)

1. Create a GitHub account if you don't have one: https://github.com
2. Create a new repository (private is fine)
3. Push this project to your repo
4. Go to https://dash.cloudflare.com → Pages → Create a project
5. Connect your GitHub repo
6. Set build settings:
   - Build command: `python3 site/build.py`
   - Build output directory: `site/public`
7. Deploy

To connect your domain:
1. In Cloudflare Pages → your project → Custom domains
2. Add your domain
3. Update your domain's nameservers to Cloudflare (they'll tell you which ones)

Every time the pipeline pushes new blog posts to GitHub, Cloudflare rebuilds your site automatically.

## Option 2: Run Locally

If you just want to preview the blog:

```bash
python3 site/build.py
# Open site/public/index.html in your browser
```

## Option 3: Any Static Host

The site generator outputs plain HTML to `site/public/`. You can host it anywhere:
- Netlify
- Vercel
- GitHub Pages
- Any web server

Just point the host at the `site/public/` directory.
