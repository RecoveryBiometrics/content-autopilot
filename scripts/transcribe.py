"""
Audio transcription — uses Google Gemini to transcribe podcast audio.
"""

import os

import google.generativeai as genai


def transcribe_audio(audio_path):
    """
    Transcribe an audio file using Gemini.

    Args:
        audio_path: path to the audio file

    Returns:
        transcript text string
    """
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_AI_API_KEY required for transcription")

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel("gemini-2.0-flash")

    audio_file = genai.upload_file(audio_path)

    response = model.generate_content(
        [
            "Transcribe this audio completely and accurately. "
            "Include speaker labels if there are multiple speakers. "
            "Return only the transcript text, no commentary.",
            audio_file,
        ]
    )

    # Clean up uploaded file
    try:
        audio_file.delete()
    except Exception:
        pass

    return response.text
