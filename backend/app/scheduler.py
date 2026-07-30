"""Periodic parsing + delivery (ports parse_sites / send_project / clear_links)."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from . import fetcher
from .config import Config
from .db import Database
from .matcher import format_project, words_check
from .parsers import SOURCES, Item, ParserError
from .telegram import TelegramAPI, TelegramError

log = logging.getLogger(__name__)


def source_url(config: Config, name: str, channel: str | None = None) -> str:
    """Resolve a source URL, honoring SOURCE_URL_* overrides (used by the
    dev fixture server) and per-channel telegram URLs."""
    base = config.source_url_overrides.get(name) or SOURCES[name].url
    if name == "telegram" and channel:
        return base.rstrip("/") + "/" + channel
    return base


async def collect_source(
    config: Config, session: aiohttp.ClientSession, name: str
) -> list[Item]:
    """Fetch and parse one source; telegram fans out over configured channels."""
    source = SOURCES[name]
    headers = {}
    if name == "freelancehunt" and config.freelancehunt_token:
        headers["Authorization"] = f"Bearer {config.freelancehunt_token}"

    if name == "telegram":
        items: list[Item] = []
        for channel in config.telegram_channels:
            payload = await fetcher.fetch(
                session, source_url(config, name, channel), headers=headers
            )
            items.extend(source.parse(payload))
        return items

    payload = await fetcher.fetch(session, source_url(config, name), headers=headers)
    return source.parse(payload)


async def run_cycle(
    config: Config,
    session: aiohttp.ClientSession,
    db: Database,
    api: TelegramAPI | None,
    sources: list[str] | None = None,
) -> dict:
    """One parse-and-deliver pass. Returns per-source stats for the dev API."""
    stats: dict[str, dict] = {}
    users = db.active_users()
    for name in sources or list(SOURCES):
        try:
            items = await collect_source(config, session, name)
            sent = 0
            for item in items:
                sent += await deliver(db, api, users, item)
            stats[name] = {"ok": True, "items": len(items), "sent": sent}
        except (fetcher.FetchError, ParserError) as exc:
            log.warning("source %s failed: %s", name, exc)
            stats[name] = {"ok": False, "error": str(exc)}
    return stats


async def deliver(db: Database, api: TelegramAPI | None, users, item: Item) -> int:
    sent = 0
    for user in users:
        user_id = user["user_id"]
        if not db.site_enabled(user_id, item.source):
            continue
        matched = words_check(f"{item.title} {item.text}", db.keywords(user_id))
        if not matched:
            continue
        if not db.mark_sent(user_id, item.key):
            continue
        if api is not None:
            try:
                await api.send_message(user_id, format_project(item, matched))
            except TelegramError:
                log.exception("send to %s failed", user_id)
                continue
        sent += 1
    return sent


async def loop_forever(
    config: Config, session: aiohttp.ClientSession, db: Database, api: TelegramAPI | None
) -> None:  # pragma: no cover - infinite loop wrapper
    while True:
        await run_cycle(config, session, db, api)
        db.purge_sent()
        await asyncio.sleep(max(config.poll_interval, 1.0))
