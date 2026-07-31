"""End-to-end proof the bot works: real HTTP against a Telegram-Bot-API-
shaped server (api.telegram.org itself is unreachable from this sandbox),
and real HTTP against mock freelance sources — the exact code paths used in
production, just pointed at local stand-ins instead of the real services.
"""

import aiohttp

from app import scheduler
from app.bot import Bot
from app.config import Config
from app.mock_sources import ROUTES, build_mock_app
from app.mock_telegram import build_mock_telegram_app
from app.telegram import TelegramAPI


async def test_bot_command_sequence_over_real_http(aiohttp_server, db, config):
    telegram_server = await aiohttp_server(build_mock_telegram_app())
    base = str(telegram_server.make_url("")).rstrip("/")

    async with aiohttp.ClientSession() as session:
        api = TelegramAPI("DEV:token", session, base=base)
        bot = Bot(api, db, config)

        async def push(chat_id, text):
            async with session.post(
                f"{base}/debug/push",
                json={"chat_id": chat_id, "text": text, "username": "tester"},
            ):
                pass

        await push(555, "/start")
        await bot.poll_once()
        await push(555, "/add python, дизайн")
        await bot.poll_once()
        await push(555, "/words")
        await bot.poll_once()

        async with session.get(f"{base}/debug/sent") as resp:
            sent = (await resp.json())["sent"]

    texts = [m["text"] for m in sent]
    assert any("Добро пожаловать" in t for t in texts)
    assert any("Добавлено слов: 2" in t for t in texts)
    assert any("python" in t and "дизайн" in t for t in texts)
    assert db.get_user(555) is not None
    assert db.keywords(555) == ["python", "дизайн"]


async def test_full_pipeline_parses_and_delivers_over_http(aiohttp_server, db):
    sources_server = await aiohttp_server(build_mock_app())
    telegram_server = await aiohttp_server(build_mock_telegram_app())

    src_base = str(sources_server.make_url("")).rstrip("/")
    tg_base = str(telegram_server.make_url("")).rstrip("/")

    overrides = {name: f"{src_base}/src/{name}" for name in ROUTES}
    overrides["telegram"] = f"{src_base}/tg/s/"
    config = Config(telegram_channels=["freelancetaverna"], source_url_overrides=overrides)

    db.add_user(1, "alice", 7)
    db.add_keywords(1, ["python"])

    async with aiohttp.ClientSession() as session:
        api = TelegramAPI("DEV:token", session, base=tg_base)
        stats = await scheduler.run_cycle(config, session, db, api)

        async with session.get(f"{tg_base}/debug/sent") as resp:
            sent = (await resp.json())["sent"]

    assert any(entry["ok"] for entry in stats.values())
    assert len(sent) > 0
    assert all("python" in m["text"].lower() for m in sent)
    assert all(m["chat_id"] == 1 for m in sent)
