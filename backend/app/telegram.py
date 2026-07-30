"""Minimal Telegram Bot API client (raw HTTP, as in the original BAS bot)."""

from __future__ import annotations

import json
import logging

import aiohttp

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"


class TelegramError(Exception):
    pass


class TelegramAPI:
    def __init__(self, token: str, session: aiohttp.ClientSession, base: str = API_BASE):
        self.token = token
        self.session = session
        self.base = base
        self._offset = 0

    async def request(self, method: str, **params) -> dict | list:
        url = f"{self.base}/bot{self.token}/{method}"
        payload = {k: v for k, v in params.items() if v is not None}
        async with self.session.post(url, json=payload) as resp:
            data = await resp.json(content_type=None)
        if not isinstance(data, dict) or not data.get("ok"):
            description = data.get("description", "unknown") if isinstance(data, dict) else data
            raise TelegramError(f"{method}: {description}")
        return data["result"]

    async def send_message(
        self, chat_id: int, text: str, reply_markup: dict | None = None
    ) -> dict:
        return await self.request(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=json.dumps(reply_markup) if reply_markup else None,
        )

    async def get_updates(self, timeout: int = 30) -> list[dict]:
        updates = await self.request(
            "getUpdates", offset=self._offset, timeout=timeout,
            allowed_updates=["message"],
        )
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates
