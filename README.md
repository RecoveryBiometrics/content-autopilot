# Podcast Pipeline

Turn any content into a fully automated podcast (and blog) with AI.

**Website articles, YouTube videos, RSS feeds, or just topics** → NotebookLM generates natural-sounding podcast audio → auto-published to Spotify, Apple Podcasts, Amazon Music.

Optionally generates SEO blog posts for each episode too.

## What It Does

1. **Pulls your content** — scrapes your website, reads your YouTube transcripts, parses your RSS feed, or researches topics you provide
2. **Generates podcast audio** — NotebookLM creates a conversation between two hosts about your content
3. **Writes SEO metadata** — Claude AI writes titles, descriptions, and tags
4. **Transcribes the audio** — Gemini transcribes for accessibility and SEO
5. **Publishes the podcast** — uploads to Transistor.fm, which distributes to all platforms
6. **Writes a blog post** (optional) — Claude writes an SEO blog post and publishes to your site

Runs on autopilot once set up. Or run manually whenever you want.

## Quick Start

```bash
git clone https://github.com/RecoveryBiometrics/content-autopilot.git
cd content-autopilot
python3 setup.py
```

The setup wizard walks you through everything step by step.

## Requirements

- **Python 3.10+**
- **Google account** — for NotebookLM (generates the audio)
- **Transistor.fm account** — $19/month, hosts your podcast
- **Anthropic API key** — for Claude AI (SEO writing, ~$0.03/day)
- **Gemini API key** (optional) — for transcription (~$0.05/day)

## Usage

```bash
# Run one episode
python3 run.py

# Run a full batch (up to your daily limit)
python3 run.py --batch

# Run on a specific topic
python3 run.py --topic "How to train a puppy"

# Start the automatic scheduler (runs every 25 hours)
python3 scheduler.py
```

## Monthly Cost

| Service | Cost |
|---------|------|
| Transistor.fm | $19/month |
| NotebookLM (free tier) | Free (3 episodes/day) |
| NotebookLM Plus | $20/month (20 episodes/day) |
| Claude AI (SEO) | ~$1/month |
| Gemini (transcription) | ~$1.50/month |
| Cloudflare Pages (blog) | Free |
| **Total (free tier)** | **~$21.50/month** |
| **Total (Plus)** | **~$41.50/month** |

## Project Structure

```
podcast-pipeline/
├── setup.py              ← interactive setup wizard
├── run.py                ← run one episode or a batch
├── scheduler.py          ← automatic daily runs
├── requirements.txt
├── .env.template         ← config template (copy to .env)
├── scripts/
│   ├── scrapers/
│   │   ├── web.py        ← scrapes websites
│   │   ├── youtube.py    ← pulls YouTube transcripts
│   │   ├── rss.py        ← reads RSS feeds
│   │   └── manual.py     ← researches topics from scratch
│   ├── notebooklm.py     ← generates podcast audio
│   ├── seo.py            ← writes SEO metadata (Claude)
│   ├── upload.py         ← uploads to Transistor.fm
│   ├── transcribe.py     ← transcribes audio (Gemini)
│   └── blog.py           ← writes blog posts (Claude)
├── data/
│   ├── topics.json       ← manual topics list
│   └── published.json    ← log of all published episodes
└── site/
    └── build.py          ← static site generator for blog
```

## Want This Done For You?

Don't want to set it up yourself? We'll build and run your entire podcast + blog pipeline for you.

[Get in touch](https://reiamplifi.com/dc)

## License

MIT
