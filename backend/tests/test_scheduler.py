import aiohttp
import pytest
from aiohttp import web

from app import scheduler
from app.config import Config
from app.mock_sources import ROUTES, build_mock_app
from app.parsers import SOURCES

from .conftest import FakeTelegramAPI


@pytest.fixture
async def mock_env(aiohttp_server):
    """Mock source server + config with every source URL overridden to it."""
    server = await aiohttp_server(build_mock_app())
    base = str(server.make_url("")).rstrip("/")
    overrides = {name: f"{base}/src/{name}" for name in ROUTES}
    overrides["telegram"] = f"{base}/tg/s/"
    config = Config(
        admin_id=100,
        telegram_channels=["freelancetaverna"],
        freelancehunt_token="fh-token",
        source_url_overrides=overrides,
    )
    async with aiohttp.ClientSession() as session:
        yield config, session


def test_source_url_resolution():
    config = Config(source_url_overrides={"fl_ru": "http://mock/fl"})
    assert scheduler.source_url(config, "fl_ru") == "http://mock/fl"
    assert scheduler.source_url(config, "kwork") == SOURCES["kwork"].url
    config2 = Config(source_url_overrides={"telegram": "http://mock/tg/s/"})
    assert (
        scheduler.source_url(config2, "telegram", "chan")
        == "http://mock/tg/s/chan"
    )


async def test_collect_every_source(mock_env):
    config, session = mock_env
    for name in SOURCES:
        items = await scheduler.collect_source(config, session, name)
        assert items, f"{name} returned no items"
        assert all(i.source for i in items)


async def test_run_cycle_delivers_matching_items(mock_env, db):
    config, session = mock_env
    db.add_user(1, "alice", 7)
    db.add_keywords(1, ["python"])
    api = FakeTelegramAPI()

    stats = await scheduler.run_cycle(config, session, db, api)

    assert all(entry["ok"] for entry in stats.values())
    assert len(api.sent) > 0
    assert all("python" in text.lower() for _, text, _ in api.sent)
    # second cycle: everything deduplicated, nothing re-sent
    api.sent.clear()
    stats2 = await scheduler.run_cycle(config, session, db, api)
    assert api.sent == []
    assert all(entry["sent"] == 0 for entry in stats2.values())


async def test_run_cycle_without_api_counts_only(mock_env, db):
    config, session = mock_env
    db.add_user(1, "alice", 7)
    stats = await scheduler.run_cycle(config, session, db, None, sources=["fl_ru"])
    assert stats["fl_ru"]["sent"] > 0


async def test_run_cycle_reports_broken_source(db):
    config = Config(source_url_overrides={"fl_ru": "http://127.0.0.1:1/x"})
    async with aiohttp.ClientSession() as session:
        stats = await scheduler.run_cycle(config, session, db, None, sources=["fl_ru"])
    assert stats["fl_ru"]["ok"] is False


async def test_deliver_respects_site_toggle_and_keywords(mock_env, db):
    config, session = mock_env
    db.add_user(1, "alice", 7)
    db.add_keywords(1, ["python"])
    db.toggle_site(1, "fl_ru")  # off
    stats = await scheduler.run_cycle(config, session, db, None, sources=["fl_ru"])
    assert stats["fl_ru"]["sent"] == 0

    db.add_user(2, "bob", 7)
    db.add_keywords(2, ["несуществующее_слово"])
    stats = await scheduler.run_cycle(config, session, db, None, sources=["kwork"])
    assert stats["kwork"]["sent"] == 0


async def test_deliver_continues_after_send_failure(mock_env, db):
    config, session = mock_env
    db.add_user(1, "blocked", 7)
    db.add_user(2, "ok", 7)
    api = FakeTelegramAPI(fail_for={1})
    stats = await scheduler.run_cycle(config, session, db, api, sources=["habr_freelance"])
    assert stats["habr_freelance"]["sent"] == 1
    assert {chat_id for chat_id, _, _ in api.sent} == {2}
