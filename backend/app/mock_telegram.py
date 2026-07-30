"""Local stand-in for the Telegram Bot API.

api.telegram.org is not reachable from this sandbox's egress policy, so to
prove the bot's send/poll pipeline actually works over real HTTP (not just
in-process against a Python fake), dev_run.py points TelegramAPI at this
server instead. It implements the same two methods the bot uses
(sendMessage, getUpdates) plus /debug/* helpers to inject fake incoming
messages and inspect what the bot sent — exactly mirroring what a real
Telegram chat would do.
"""

from __future__ import annotations

from aiohttp import web


def build_mock_telegram_app() -> web.Application:
    app = web.Application()
    # A plain dict nested under one Application key, mutated in place —
    # reassigning Application keys after startup is deprecated in aiohttp.
    state = {"updates": [], "sent": [], "next_update_id": 1}
    app["state"] = state

    async def bot_method(request: web.Request) -> web.Response:
        method = request.match_info["method"]
        payload = await request.json()
        if method == "sendMessage":
            state["sent"].append(payload)
            return web.json_response({"ok": True, "result": {"message_id": len(state["sent"])}})
        if method == "getUpdates":
            updates, state["updates"] = state["updates"], []
            return web.json_response({"ok": True, "result": updates})
        return web.json_response({"ok": False, "description": f"unsupported method {method}"})

    async def push_update(request: web.Request) -> web.Response:
        """Debug helper: simulate a user sending a message to the bot."""
        body = await request.json()
        update = {
            "update_id": state["next_update_id"],
            "message": {
                "chat": {"id": body["chat_id"]},
                "from": {"username": body.get("username", "dev")},
                "text": body["text"],
            },
        }
        state["next_update_id"] += 1
        state["updates"].append(update)
        return web.json_response({"ok": True, "update_id": update["update_id"]})

    async def list_sent(request: web.Request) -> web.Response:
        return web.json_response({"sent": state["sent"]})

    app.add_routes(
        [
            web.post("/bot{token}/{method}", bot_method),
            web.post("/debug/push", push_update),
            web.get("/debug/sent", list_sent),
        ]
    )
    return app
