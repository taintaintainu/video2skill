"""Shared HTTP transport policy for Video2Skill provider adapters."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


USER_AGENT = "video2skill/0.2.2"
RETRYABLE_STATUS = {408, 409, 425, 429}


class HTTPTransportError(RuntimeError):
    """An HTTP response that was not accepted by the provider adapter."""

    def __init__(
        self,
        status: int,
        url: str,
        body: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.url = url
        self.body = body
        self.headers = {key.casefold(): value for key, value in (headers or {}).items()}
        super().__init__(f"HTTP {status} {url}: {body[:4000]}")

    @property
    def retry_after(self) -> str | None:
        return self.headers.get("retry-after")


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Keep credentials from being replayed to a redirect target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
    timeout: int,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            **({"Content-Type": "application/json"} if data is not None else {}),
            **headers,
        },
    )
    try:
        opener = urllib.request.build_opener(RejectRedirects())
        with opener.open(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HTTPTransportError(
            exc.code,
            url,
            body,
            dict(exc.headers.items()) if exc.headers else None,
        ) from exc


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, HTTPTransportError):
        return exc.status in RETRYABLE_STATUS or 500 <= exc.status <= 599
    return isinstance(exc, (TimeoutError, urllib.error.URLError))


def retry_delay(exc: Exception, attempt: int, base: float) -> float:
    if isinstance(exc, HTTPTransportError) and exc.retry_after:
        try:
            return min(300.0, max(0.0, float(exc.retry_after)))
        except ValueError:
            pass
    return min(300.0, base * (2**attempt))
