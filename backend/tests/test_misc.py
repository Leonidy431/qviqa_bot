import asyncio

import aiohttp

from app import payments
from app.config import Config
from app.main import start
from app.mock_sources import build_mock_app


def test_config_defaults():
    config = Config.from_env(env={})
    assert config.bot_token == ""
    assert config.admin_id == 0
    assert config.test_period_days == 7
    assert config.telegram_channels == []
    assert config.source_url_overrides == {}


def test_config_from_env():
    config = Config.from_env(
        env={
            "BOT_TOKEN": "123:abc",
            "ADMIN_ID": "42",
            "TEST_PERIOD_DAYS": "3",
            "SUBSCRIPTION_PRICE": "500",
            "POLL_INTERVAL": "10",
            "PORT": "9000",
            "TELEGRAM_CHANNELS": "one, two,,three",
            "SOURCE_URL_FL_RU": "http://mock/fl",
            "FREELANCEHUNT_TOKEN": "fh",
        }
    )
    assert config.bot_token == "123:abc"
    assert config.admin_id == 42
    assert config.test_period_days == 3
    assert config.subscription_price == 500
    assert config.port == 9000
    assert config.telegram_channels == ["one", "two", "three"]
    assert config.source_url_overrides == {"fl_ru": "http://mock/fl"}
    assert config.freelancehunt_token == "fh"


def test_payment_instructions_mentions_support(config):
    text = payments.payment_instructions(config)
    assert "@Leonidy" in text and "250" in text


def test_grant_days_wrapper(db):
    assert payments.grant_days(db, 5, 10) > 0


async def test_mock_sources_unknown_fixture(aiohttp_client):
    client = await aiohttp_client(build_mock_app())
    resp = await client.get("/src/unknown")
    assert resp.status == 404


async def test_mock_sources_serves_fixture(aiohttp_client):
    client = await aiohttp_client(build_mock_app())
    resp = await client.get("/src/fl_ru")
    assert resp.status == 200
    assert "rss" in await resp.text()
    resp = await client.get("/tg/s/anychannel")
    assert "tgme_widget_message" in await resp.text()


async def test_main_start_server_only(tmp_path, unused_tcp_port):
    config = Config(port=unused_tcp_port, host="127.0.0.1", db_path=str(tmp_path / "d.sqlite3"))
    runner, tasks = await start(config)
    assert tasks == []
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://127.0.0.1:{unused_tcp_port}/health") as resp:
            assert (await resp.json())["status"] == "ok"
    await runner.cleanup()
    await runner.app["client_session"].close()


async def test_main_start_with_bot(tmp_path, unused_tcp_port):
    config = Config(
        port=unused_tcp_port,
        host="127.0.0.1",
        db_path=str(tmp_path / "d.sqlite3"),
        bot_token="123:abc",
        poll_interval=9999,
    )
    runner, tasks = await start(config)
    assert len(tasks) == 2
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await runner.cleanup()
    await runner.app["client_session"].close()


async def test_main_start_with_custom_telegram_api_base(tmp_path, unused_tcp_port):
    config = Config(
        port=unused_tcp_port,
        host="127.0.0.1",
        db_path=str(tmp_path / "d.sqlite3"),
        bot_token="123:abc",
        poll_interval=9999,
        telegram_api_base="http://127.0.0.1:1",  # unroutable; cancelled before use
    )
    runner, tasks = await start(config)
    assert len(tasks) == 2
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await runner.cleanup()
    await runner.app["client_session"].close()
