"""Dev runner: starts the mock source server (:9001) and the backend (:8000)
with all source URLs pointed at the mocks — full parse pipeline without
egress to the real freelance sites.

    python dev_run.py
"""

import asyncio
import logging

from aiohttp import web

from app.config import Config
from app.main import start
from app.mock_sources import ROUTES, build_mock_app

MOCK_PORT = 9001


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mock_runner = web.AppRunner(build_mock_app())
    await mock_runner.setup()
    await web.TCPSite(mock_runner, "127.0.0.1", MOCK_PORT).start()
    logging.info("mock sources on http://127.0.0.1:%s", MOCK_PORT)

    base = f"http://127.0.0.1:{MOCK_PORT}"
    overrides = {name: f"{base}/src/{name}" for name in ROUTES}
    overrides["telegram"] = f"{base}/tg/s/"
    config = Config.from_env()
    config.source_url_overrides = {**overrides, **config.source_url_overrides}
    if not config.telegram_channels:
        config.telegram_channels = ["freelancetaverna"]

    runner, tasks = await start(config)
    try:
        await asyncio.Event().wait()
    finally:
        for task in tasks:
            task.cancel()
        await runner.cleanup()
        await mock_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
