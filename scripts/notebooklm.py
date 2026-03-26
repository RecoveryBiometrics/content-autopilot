"""
NotebookLM audio generator — creates podcast-style audio from content.
"""

import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
AUDIO_DIR = BASE_DIR / "data" / "audio"


def generate_audio(content):
    """
    Generate podcast audio from content using NotebookLM.

    Args:
        content: dict with 'title' and 'body' keys

    Returns:
        dict with 'audio_path' key, or None on failure
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from notebooklm import NotebookLM
    except ImportError:
        raise ImportError(
            "notebooklm-py not installed. Run: pip install notebooklm-py"
        )

    # Check for storage state (authentication)
    storage_state = BASE_DIR / "storage_state.json"
    if not storage_state.exists():
        raise FileNotFoundError(
            "NotebookLM not authenticated. Run: python3 -m notebooklm login"
        )

    client = NotebookLM()

    # Create a notebook with the content
    title = content.get("title", "Untitled")
    body = content.get("body", "")

    # Write content to a temp file for NotebookLM to use as a source
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(f"{title}\n\n{body}")
        source_path = f.name

    try:
        # Create notebook and generate audio
        notebook = client.create_notebook(title=title)
        notebook.add_source(source_path)
        audio = notebook.generate_audio()

        # Save audio file
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:80]
        audio_path = str(AUDIO_DIR / f"{safe_title}.mp4")
        audio.save(audio_path)

        # Clean up notebook
        try:
            notebook.delete()
        except Exception:
            pass

        return {"audio_path": audio_path}

    except Exception as e:
        raise RuntimeError(f"NotebookLM generation failed: {e}")

    finally:
        # Clean up temp file
        try:
            os.unlink(source_path)
        except OSError:
            pass
