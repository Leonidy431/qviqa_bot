import aiohttp
import pytest
from aiohttp import web

from app.telegram import TelegramAPI, TelegramError


async def make_bot_server(aiohttp_server, responses):
    """responses: dict method -> callable(payload) -> dict"""
    received = []

    async def handler(request):
        method = request.match_info["method"]
        payload = await request.json()
        received.append((method, payload))
        return web.json_response(responses[method](payload))

    app = web.Application()
    app.router.add_post("/bot{token}/{method}", handler)
    server = await aiohttp_server(app)
    return server, received


async def test_send_message(aiohttp_server):
    server, received = await make_bot_server(
        aiohttp_server, {"sendMessage": lambda p: {"ok": True, "result": {"message_id": 7}}}
    )
    async with aiohttp.ClientSession() as session:
        api = TelegramAPI("TOKEN", session, base=str(server.make_url("")).rstrip("/"))
        result = await api.send_message(42, "привет", {"keyboard": []})
    assert result == {"message_id": 7}
    method, payload = received[0]
    assert method == "sendMessage"
    assert payload["chat_id"] == 42
    assert payload["parse_mode"] == "HTML"
    assert "keyboard" in payload["reply_markup"]


async def test_send_message_without_markup(aiohttp_server):
    server, received = await make_bot_server(
        aiohttp_server, {"sendMessage": lambda p: {"ok": True, "result": {}}}
    )
    async with aiohttp.ClientSession() as session:
        api = TelegramAPI("TOKEN", session, base=str(server.make_url("")).rstrip("/"))
        await api.send_message(42, "hi")
    assert "reply_markup" not in received[0][1]


async def test_api_error(aiohttp_server):
    server, _ = await make_bot_server(
        aiohttp_server,
        {"sendMessage": lambda p: {"ok": False, "description": "chat not found"}},
    )
    async with aiohttp.ClientSession() as session:
        api = TelegramAPI("TOKEN", session, base=str(server.make_url("")).rstrip("/"))
        with pytest.raises(TelegramError, match="chat not found"):
            await api.send_message(1, "x")


async def test_get_updates_advances_offset(aiohttp_server):
    batches = [
        {"ok": True, "result": [{"update_id": 10, "message": {}}]},
        {"ok": True, "result": []},
    ]
    calls = []

    def respond(payload):
        calls.append(payload)
        return batches[len(calls) - 1]

    server, _ = await make_bot_server(aiohttp_server, {"getUpdates": respond})
    async with aiohttp.ClientSession() as session:
        api = TelegramAPI("TOKEN", session, base=str(server.make_url("")).rstrip("/"))
        first = await api.get_updates()
        second = await api.get_updates()
    assert len(first) == 1 and second == []
    assert calls[0]["offset"] == 0
    assert calls[1]["offset"] == 11
