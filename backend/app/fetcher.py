"""HTTP layer: fetch source pages/feeds with retries (2s/4s/8s/16s per TZ)."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
RETRY_DELAYS = (2, 4, 8, 16)


class FetchError(Exception):
    pass


async def fetch(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict | None = None,
    retries: int = 0,
    _sleep=asyncio.sleep,
) -> str:
    """GET *url* and return the body text; retry with exponential backoff."""
    merged = {"User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with session.get(url, headers=merged) as resp:
                if resp.status >= 400:
                    raise FetchError(f"{url}: HTTP {resp.status}")
                return await resp.text()
        except (TimeoutError, aiohttp.ClientError, FetchError) as exc:
            last_error = exc
            if attempt < retries:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                log.warning("fetch %s failed (%s), retry in %ss", url, exc, delay)
                await _sleep(delay)
    raise FetchError(f"{url}: {last_error}") from last_error
