import pytest

from app.mock_telegram import build_mock_telegram_app


@pytest.fixture
async def client(aiohttp_client):
    return await aiohttp_client(build_mock_telegram_app())


async def test_send_message_recorded(client):
    resp = await client.post("/botTOKEN/sendMessage", json={"chat_id": 1, "text": "hi"})
    data = await resp.json()
    assert data["ok"] is True and data["result"]["message_id"] == 1

    sent = await (await client.get("/debug/sent")).json()
    assert sent["sent"][0]["text"] == "hi"


async def test_get_updates_empty_then_after_push(client):
    resp = await client.post("/botTOKEN/getUpdates", json={"offset": 0, "timeout": 30})
    assert (await resp.json())["result"] == []

    push = await client.post(
        "/debug/push", json={"chat_id": 5, "text": "/start", "username": "dev"}
    )
    push_data = await push.json()
    assert push_data == {"ok": True, "update_id": 1}

    resp2 = await client.post("/botTOKEN/getUpdates", json={"offset": 0, "timeout": 30})
    data2 = (await resp2.json())["result"]
    assert len(data2) == 1
    assert data2[0]["message"]["text"] == "/start"
    assert data2[0]["message"]["chat"]["id"] == 5
    assert data2[0]["message"]["from"]["username"] == "dev"

    # queue drained after read
    resp3 = await client.post("/botTOKEN/getUpdates", json={"offset": 0, "timeout": 30})
    assert (await resp3.json())["result"] == []


async def test_push_update_default_username(client):
    await client.post("/debug/push", json={"chat_id": 7, "text": "hi"})
    data = (await (await client.post("/botTOKEN/getUpdates", json={})).json())["result"]
    assert data[0]["message"]["from"]["username"] == "dev"


async def test_unsupported_method(client):
    resp = await client.post("/botTOKEN/unknownMethod", json={})
    data = await resp.json()
    assert data == {"ok": False, "description": "unsupported method unknownMethod"}
