"""
file for creating text-to-speech client using Elevenlabs.
Generates an mp3 for a line of agent dialogue and saves it under

"""
import os
import uuid
import requests

from app.config import settings
from app.logging_config import logger


class TTSError(Exception):
    pass


def synthesize_speech(text: str) -> str:
    """
    Returns a filename (relative to AUDIO_DIR) of the generated mp3.
    Raises TTSError on failure.
    """
    if not settings.ELEVENLABS_API_KEY:
        raise TTSError("ELEVENLABS_API_KEY is not configured")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": settings.ELEVENLABS_MODEL_ID,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"ElevenLabs TTS request failed: {e}")
        raise TTSError(str(e))

    os.makedirs(settings.AUDIO_DIR, exist_ok=True)
    filename = f"{uuid.uuid4()}.mp3"
    path = os.path.join(settings.AUDIO_DIR, filename)
    with open(path, "wb") as f:
        f.write(resp.content)
    return filename


def audio_url(filename: str) -> str:
    return f"{settings.PUBLIC_BASE_URL}/audio/{filename}"
