from __future__ import annotations

import json
import urllib.error
import urllib.request

from buvis.pybase.adapters import console


def suggest_tags(text: str, model: str, url: str) -> list[str]:
    """Suggest tags for note text via ollama API.

    Args:
        text: Markdown content to suggest tags for.
        model: Ollama model name (e.g. "llama3.2:3b").
        url: Ollama base URL (e.g. "http://localhost:11434").

    Returns:
        List of suggested tag strings, or empty list on error.
    """
    prompt = (
        "Extract relevant tags from the following text. "
        "Return ONLY a JSON array of lowercase hyphenated tag strings, nothing else. "
        'Example: ["machine-learning", "python", "data-science"]\n\n'
        f"{text}"
    )

    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
    ).encode()

    req = urllib.request.Request(  # noqa: S310
        f"{url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            body = json.loads(resp.read())
    except (urllib.error.URLError, OSError, TimeoutError):
        console.warning("Could not reach ollama — skipping tag suggestion")
        return []

    response_text = body.get("response", "")

    try:
        tags = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON array from response
        start = response_text.find("[")
        end = response_text.rfind("]")
        if start != -1 and end != -1:
            try:
                tags = json.loads(response_text[start : end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []

    if not isinstance(tags, list):
        return []

    return [str(t) for t in tags if isinstance(t, str)]
