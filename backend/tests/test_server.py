import json

import aiohttp
import pytest

from app.config import Config
from app.mock_sources import ROUTES, build_mock_app
from app.parsers import SOURCES
from app.server import build_app


@pytest.fixture
async def client(aiohttp_server, aiohttp_client, db):
    mock = await aiohttp_server(build_mock_app())
    base = str(mock.make_url("")).rstrip("/")
    overrides = {name: f"{base}/src/{name}" for name in ROUTES}
    overrides["telegram"] = f"{base}/tg/s/"
    config = Config(telegram_channels=["freelancetaverna"], source_url_overrides=overrides)
    session = aiohttp.ClientSession()
    app = build_app(config, db, session)
    test_client = await aiohttp_client(app)
    yield test_client
    await session.close()


async def test_health(client, db):
    db.add_user(1, "a", 7)
    resp = await client.get("/health")
    data = await resp.json()
    assert resp.status == 200
    assert data["status"] == "ok"
    assert data["users"] == 1


async def test_sources_listing(client):
    resp = await client.get("/api/sources")
    data = await resp.json()
    names = {s["name"] for s in data["sources"]}
    assert "fl_ru" in names and "telegram" in names
    assert data["dead_sources"]["freten.ru"]


async def test_parse_source(client):
    resp = await client.get("/api/parse/kwork")
    data = await resp.json()
    assert resp.status == 200
    assert data["ok"] is True and data["count"] == 2
    assert data["items"][0]["source"] == "kwork"


async def test_parse_source_limit(client):
    resp = await client.get("/api/parse/fl_ru?limit=1")
    data = await resp.json()
    assert data["count"] == 2 and len(data["items"]) == 1


async def test_parse_unknown_source(client):
    resp = await client.get("/api/parse/freten.ru")
    assert resp.status == 404
    data = await resp.json()
    assert data["dead"] == "сервис закрыт"


async def test_parse_broken_source(aiohttp_client, db):
    config = Config(source_url_overrides={"fl_ru": "http://127.0.0.1:1/x"})
    session = aiohttp.ClientSession()
    test_client = await aiohttp_client(build_app(config, db, session))
    resp = await test_client.get("/api/parse/fl_ru")
    assert resp.status == 502
    assert (await resp.json())["ok"] is False
    await session.close()


async def test_run_cycle_endpoint(client, db):
    db.add_user(1, "a", 7)
    resp = await client.post("/api/run-cycle")
    data = await resp.json()
    assert resp.status == 200
    assert data["cycle"]["fl_ru"]["ok"] is True
    assert data["cycle"]["fl_ru"]["sent"] > 0


async def _read_ndjson(resp):
    text = (await resp.text()).strip()
    return [json.loads(line) for line in text.split("\n") if line]


async def test_stream_all_items(client):
    resp = await client.get("/api/stream")
    assert resp.status == 200
    assert resp.headers["Content-Type"].startswith("application/x-ndjson")
    items = await _read_ndjson(resp)
    assert len(items) > 0
    assert all(i["matched_keywords"] == ["*"] for i in items)


async def test_stream_filters_by_keyword(client):
    resp = await client.get("/api/stream?keywords=python")
    items = await _read_ndjson(resp)
    assert items
    assert all(kw.lower() == "python" for i in items for kw in i["matched_keywords"])


async def test_stream_no_match_is_empty(client):
    resp = await client.get("/api/stream?keywords=совершенно_другое_слово")
    assert await _read_ndjson(resp) == []


async def test_stream_respects_limit(client):
    resp = await client.get("/api/stream?limit=1")
    assert len(await _read_ndjson(resp)) == 1


async def test_stream_invalid_limit_means_unlimited(client):
    resp = await client.get("/api/stream?limit=notanumber")
    assert len(await _read_ndjson(resp)) > 1


async def test_stream_skips_broken_sources(aiohttp_client, db):
    config = Config(source_url_overrides={name: "http://127.0.0.1:1/x" for name in SOURCES})
    session = aiohttp.ClientSession()
    test_client = await aiohttp_client(build_app(config, db, session))
    resp = await test_client.get("/api/stream")
    assert (await resp.text()).strip() == ""
    await session.close()


async def test_frontend_index_served(client):
    resp = await client.get("/")
    assert resp.status == 200
    assert "Qviqa" in await resp.text()


async def test_frontend_assets_served(client):
    resp = await client.get("/assets/app.js")
    assert resp.status == 200
    assert "appConfig" in await resp.text()
