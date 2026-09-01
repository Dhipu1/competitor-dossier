"""Calls the Gemini API to generate text.

Talking to the REST endpoint directly with `requests` rather than pulling in
an SDK: the request is a plain JSON POST, and keeping it visible makes it
obvious exactly what we send to the model and what it costs us in tokens.
"""

from typing import Optional

import requests

from config import require

MODEL = "gemini-3.6-flash"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiError(RuntimeError):
    pass


def generate(prompt: str, *, model: str = MODEL, timeout: int = 120) -> str:
    """Sends a prompt, returns the model's text response."""
    response = requests.post(
        ENDPOINT.format(model=model),
        params={"key": require("GEMINI_API_KEY")},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout,
    )

    if response.status_code != 200:
        raise GeminiError(f"Gemini returned {response.status_code}: {response.text[:400]}")

    payload = response.json()
    text = _first_text(payload)
    if text is None:
        raise GeminiError(f"No text in Gemini response: {str(payload)[:400]}")
    return text


def _first_text(payload: dict) -> Optional[str]:
    """Digs the generated text out of the response envelope."""
    for candidate in payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "text" in part:
                return part["text"]
    return None
