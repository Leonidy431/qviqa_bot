"""Dev runner: mock source server (:9001), mock Telegram server (:9002), and
the backend (:8000) wired to both — full pipeline (parsing, keyword
matching, bot command dispatch, delivery) exercised over real HTTP without
any external network access (api.telegram.org and the freelance sites are
both unreachable from this sandbox's egress policy).

    python dev_run.py

Then, e.g.:
    curl "localhost:8000/api/stream?keywords=python"
    curl -X POST localhost:9002/debug/push \
         -H 'content-type: application/json' \
         -d '{"chat_id": 555, "text": "/start", "username": "tester"}'
    curl localhost:9002/debug/sent
"""

import asyncio
import logging

from aiohttp import web

from app.config import Config
from app.main import start
from app.mock_sources import ROUTES, build_mock_app
from app.mock_telegram import build_mock_telegram_app

MOCK_SOURCES_PORT = 9001
MOCK_TELEGRAM_PORT = 9002


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    sources_runner = web.AppRunner(build_mock_app())
    await sources_runner.setup()
    await web.TCPSite(sources_runner, "127.0.0.1", MOCK_SOURCES_PORT).start()
    logging.info("mock sources on http://127.0.0.1:%s", MOCK_SOURCES_PORT)

    telegram_runner = web.AppRunner(build_mock_telegram_app())
    await telegram_runner.setup()
    await web.TCPSite(telegram_runner, "127.0.0.1", MOCK_TELEGRAM_PORT).start()
    logging.info("mock telegram on http://127.0.0.1:%s", MOCK_TELEGRAM_PORT)

    src_base = f"http://127.0.0.1:{MOCK_SOURCES_PORT}"
    overrides = {name: f"{src_base}/src/{name}" for name in ROUTES}
    overrides["telegram"] = f"{src_base}/tg/s/"

    config = Config.from_env()
    config.source_url_overrides = {**overrides, **config.source_url_overrides}
    if not config.telegram_channels:
        config.telegram_channels = ["freelancetaverna"]
    if not config.bot_token:
        config.bot_token = "DEV:mock-token"
    if not config.telegram_api_base:
        config.telegram_api_base = f"http://127.0.0.1:{MOCK_TELEGRAM_PORT}"

    runner, tasks = await start(config)
    try:
        await asyncio.Event().wait()
    finally:
        for task in tasks:
            task.cancel()
        await runner.cleanup()
        await sources_runner.cleanup()
        await telegram_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
