"""
YouTube scraper — pulls video transcripts from a YouTube channel.
Uses yt-dlp to list videos and extract transcripts.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
CACHE_FILE = BASE_DIR / "data" / "youtube-cache.json"
PUBLISHED_FILE = BASE_DIR / "data" / "published.json"


def _load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return []


def _save_cache(videos):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(videos, indent=2))


def _load_published_urls():
    if PUBLISHED_FILE.exists():
        published = json.loads(PUBLISHED_FILE.read_text())
        return {p.get("source", "") for p in published if p.get("source")}
    return set()


def build_cache():
    """List all videos from the configured YouTube channel."""
    channel_url = os.getenv("YOUTUBE_CHANNEL_URL", "")
    if not channel_url:
        return []

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "yt_dlp",
                "--flat-playlist",
                "--dump-json",
                "--no-warnings",
                channel_url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            videos.append({
                "id": data.get("id", ""),
                "title": data.get("title", ""),
                "url": data.get("url", f"https://www.youtube.com/watch?v={data.get('id', '')}"),
                "processed": False,
            })
        except json.JSONDecodeError:
            continue

    _save_cache(videos)
    return videos


def _get_transcript(video_url):
    """Download the transcript/subtitles for a video."""
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "yt_dlp",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--skip-download",
                "--sub-format", "vtt",
                "--print", "%(title)s",
                "-o", "-",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        title = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""

        # Try to get the subtitle file content
        sub_result = subprocess.run(
            [
                sys.executable, "-m", "yt_dlp",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--skip-download",
                "--sub-format", "txt",
                "--print-to-file", "%(subtitles.en.-1.data)s", "-",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        transcript = sub_result.stdout.strip() if sub_result.stdout else ""

        if not transcript:
            return None

        return {
            "title": title,
            "body": transcript,
            "source_url": video_url,
            "source_type": "youtube",
        }

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_next_video():
    """Get the next unprocessed video transcript."""
    cache = _load_cache()

    if not cache:
        cache = build_cache()

    if not cache:
        return None

    published_urls = _load_published_urls()

    for video in cache:
        url = video.get("url", "")
        if url not in published_urls and not video.get("processed"):
            content = _get_transcript(url)
            if content:
                video["processed"] = True
                _save_cache(cache)
                return content

    return None
