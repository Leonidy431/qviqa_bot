"""Entry point: dev HTTP server + (if BOT_TOKEN is set) bot polling and the
parse/deliver scheduler."""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiohttp import web

from . import scheduler
from .bot import Bot
from .config import Config
from .db import Database
from .server import build_app
from .telegram import TelegramAPI

log = logging.getLogger(__name__)


async def start(config: Config) -> tuple[web.AppRunner, list[asyncio.Task]]:
    session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=config.http_timeout)
    )
    db = Database(config.db_path)
    api = TelegramAPI(config.bot_token, session) if config.bot_token else None

    app = build_app(config, db, session, api)
    app["client_session"] = session
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.host, config.port)
    await site.start()
    log.info("dev server on http://%s:%s", config.host, config.port)

    tasks: list[asyncio.Task] = []
    if api is not None:
        bot = Bot(api, db, config)
        tasks.append(asyncio.create_task(bot.poll_forever()))
        tasks.append(
            asyncio.create_task(scheduler.loop_forever(config, session, db, api))
        )
        log.info("bot polling + scheduler started")
    else:
        log.warning("BOT_TOKEN not set — running dev server only")
    return runner, tasks


async def run() -> None:  # pragma: no cover - process lifetime wrapper
    logging.basicConfig(level=logging.INFO)
    config = Config.from_env()
    runner, tasks = await start(config)
    try:
        await asyncio.Event().wait()
    finally:
        for task in tasks:
            task.cancel()
        await runner.cleanup()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run())
