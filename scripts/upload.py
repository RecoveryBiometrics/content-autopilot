"""
Transistor.fm uploader — uploads audio and publishes episodes.
"""

import json
import os
from datetime import datetime, timedelta

import requests


def _authorize_upload(api_key, filename):
    """Get an authorized upload URL from Transistor."""
    resp = requests.get(
        "https://api.transistor.fm/v1/episodes/authorize_upload",
        params={"filename": filename},
        headers={"x-api-key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["attributes"]


def _upload_audio(upload_url, audio_path, content_type="audio/mpeg"):
    """Upload the audio file to the authorized URL."""
    with open(audio_path, "rb") as f:
        resp = requests.put(
            upload_url,
            data=f,
            headers={"Content-Type": content_type},
            timeout=300,
        )
        resp.raise_for_status()


def upload_episode(audio_path, title, description="", tags=None, transcript=""):
    """
    Upload an episode to Transistor.fm.

    Args:
        audio_path: path to the audio file
        title: episode title
        description: episode description (HTML ok)
        tags: list of tag strings
        transcript: episode transcript text

    Returns:
        dict with 'id', 'share_url' keys
    """
    api_key = os.getenv("TRANSISTOR_API_KEY")
    show_id = os.getenv("TRANSISTOR_SHOW_ID")

    if not api_key or not show_id:
        raise ValueError("TRANSISTOR_API_KEY and TRANSISTOR_SHOW_ID required in .env")

    filename = os.path.basename(audio_path)

    # Step 1: Get authorized upload URL
    upload_data = _authorize_upload(api_key, filename)
    upload_url = upload_data["upload_url"]
    audio_url = upload_data["content_url"]

    # Step 2: Upload the audio
    _upload_audio(upload_url, audio_path)

    # Step 3: Create the episode
    episode_data = {
        "episode": {
            "show_id": int(show_id),
            "title": title,
            "summary": description,
            "audio_url": audio_url,
            "status": "published",
        }
    }

    if tags:
        episode_data["episode"]["tags"] = ", ".join(tags)

    if transcript:
        episode_data["episode"]["transcript_text"] = transcript

    resp = requests.post(
        "https://api.transistor.fm/v1/episodes",
        json=episode_data,
        headers={"x-api-key": api_key},
        timeout=30,
    )
    resp.raise_for_status()

    result = resp.json()
    ep = result["data"]

    return {
        "id": ep["id"],
        "share_url": ep.get("attributes", {}).get("share_url", ""),
        "embed_html": ep.get("attributes", {}).get("embed_html", ""),
    }
