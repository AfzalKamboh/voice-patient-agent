"""
file for creating client of Ollama Cloud, running the open-source `gpt-oss` model.
"""
import json
import requests
from typing import List, Dict, Any

from app.config import settings
from app.logging_config import logger


class LLMError(Exception):
    pass


def chat_json(messages: List[Dict[str, str]], timeout: int = 20) -> Dict[str, Any]:
    """
    Calls the gpt-oss model via Ollama Cloud and returns the parsed JSON
    object the model was instructed to produce. Raises LLMError on any
    failure (network, non-2xx, unparsable JSON) so callers can fall back
    gracefully instead of leaving the caller in silence.
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    headers = {"Content-Type": "application/json"}
    if settings.OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"

    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.3},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()
        content = body.get("message", {}).get("content", "")
        return _parse_json_lenient(content)
    except requests.RequestException as e:
        logger.error(f"Ollama Cloud request failed: {e}")
        raise LLMError(str(e))
    except (ValueError, KeyError) as e:
        logger.error(f"Failed to parse Ollama Cloud response: {e}")
        raise LLMError(str(e))


def _parse_json_lenient(content: str) -> Dict[str, Any]:
    content = content.strip()
    # gpt-oss occasionally wraps JSON in markdown fences despite format=json
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # last resort: grab the outermost {...}
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            return json.loads(content[start:end + 1])
        raise
