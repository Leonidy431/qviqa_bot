import aiohttp
import pytest
from aiohttp import web

from app import fetcher


async def make_server(aiohttp_server, handler):
    app = web.Application()
    app.router.add_get("/", handler)
    return await aiohttp_server(app)


async def test_fetch_ok(aiohttp_server):
    async def handler(request):
        assert "Mozilla" in request.headers["User-Agent"]
        return web.Response(text="payload")

    server = await make_server(aiohttp_server, handler)
    async with aiohttp.ClientSession() as session:
        assert await fetcher.fetch(session, str(server.make_url("/"))) == "payload"


async def test_fetch_custom_headers(aiohttp_server):
    async def handler(request):
        return web.Response(text=request.headers.get("Authorization", ""))

    server = await make_server(aiohttp_server, handler)
    async with aiohttp.ClientSession() as session:
        body = await fetcher.fetch(
            session, str(server.make_url("/")), headers={"Authorization": "Bearer t"}
        )
    assert body == "Bearer t"


async def test_fetch_http_error_no_retries(aiohttp_server):
    async def handler(request):
        return web.Response(status=500)

    server = await make_server(aiohttp_server, handler)
    async with aiohttp.ClientSession() as session:
        with pytest.raises(fetcher.FetchError):
            await fetcher.fetch(session, str(server.make_url("/")))


async def test_fetch_retries_then_succeeds(aiohttp_server):
    calls = {"n": 0}

    async def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return web.Response(status=503)
        return web.Response(text="ok")

    server = await make_server(aiohttp_server, handler)
    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    async with aiohttp.ClientSession() as session:
        body = await fetcher.fetch(session, str(server.make_url("/")), retries=3, _sleep=fake_sleep)
    assert body == "ok"
    assert delays == [2, 4]


async def test_fetch_retries_exhausted(aiohttp_server):
    async def handler(request):
        return web.Response(status=503)

    server = await make_server(aiohttp_server, handler)

    async def fake_sleep(seconds):
        pass

    async with aiohttp.ClientSession() as session:
        with pytest.raises(fetcher.FetchError):
            await fetcher.fetch(session, str(server.make_url("/")), retries=5, _sleep=fake_sleep)


async def test_fetch_connection_error():
    async with aiohttp.ClientSession() as session:
        with pytest.raises(fetcher.FetchError):
            await fetcher.fetch(session, "http://127.0.0.1:1/nope")
