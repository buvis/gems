"""Stdlib-only ntfy requests with header-safe titles and optional Basic auth."""

from __future__ import annotations

import base64
import urllib.error
import urllib.request

__all__ = ["build_ntfy_request", "send_ntfy"]

_USER_AGENT = "buvis-gems/ntfy"


def _header_safe(value: str) -> str:
    if "\r" not in value and "\n" not in value:
        try:
            value.encode("latin-1")
        except UnicodeEncodeError:
            pass
        else:
            return value
    token = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f"=?UTF-8?B?{token}?="


def build_ntfy_request(url: str, topic: str, title: str, message: str, credentials: str = "") -> urllib.request.Request:
    headers = {"Title": _header_safe(title), "Tags": "computer", "User-Agent": _USER_AGENT}
    if credentials:
        token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return urllib.request.Request(
        f"{url.rstrip('/')}/{topic}", data=message.encode("utf-8"), headers=headers, method="POST"
    )


def send_ntfy(
    url: str, topic: str, title: str, message: str, *, credentials: str = "", timeout: float = 5.0
) -> str | None:
    """POST ``message`` to ``url/topic``; return None on success, else the reason."""
    try:
        request = build_ntfy_request(url, topic, title, message, credentials)
        with urllib.request.urlopen(request, timeout=timeout):
            return None
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"
