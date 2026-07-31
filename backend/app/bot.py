"""Telegram command handling (ports commands_check / main_menu_keyboard / help /
add_words / add_del_site / get_user_info / change_status / add_balance)."""

from __future__ import annotations

import asyncio
import logging

from . import payments
from .config import Config
from .db import Database
from .parsers import SOURCES
from .telegram import TelegramAPI, TelegramError

log = logging.getLogger(__name__)

BTN_KEYWORDS = "🔑 Ключевые слова"
BTN_SITES = "🌐 Сайты"
BTN_PROFILE = "👤 Профиль"
BTN_PAY = "💳 Оплата"
BTN_PAUSE = "⏸ Пауза"
BTN_RESUME = "▶️ Возобновить"
BTN_HELP = "ℹ️ Помощь"

HELP_TEXT = (
    "Бот присылает новые фриланс-заказы по вашим ключевым словам.\n\n"
    "Команды:\n"
    "/add слово1, слово2 — добавить ключевые слова\n"
    "/del слово — удалить ключевое слово\n"
    "/words — список ключевых слов\n"
    "/sites — включить/выключить источники\n"
    "/site &lt;имя&gt; — переключить источник\n"
    "/pause и /resume — приостановить/возобновить рассылку\n"
    "/me — профиль и срок подписки\n"
    "/pay — оплата подписки\n"
)


def main_menu_keyboard() -> dict:
    return {
        "keyboard": [
            [{"text": BTN_KEYWORDS}, {"text": BTN_SITES}],
            [{"text": BTN_PROFILE}, {"text": BTN_PAY}],
            [{"text": BTN_PAUSE}, {"text": BTN_RESUME}],
            [{"text": BTN_HELP}],
        ],
        "resize_keyboard": True,
    }


class Bot:
    def __init__(self, api: TelegramAPI, db: Database, config: Config):
        self.api = api
        self.db = db
        self.config = config

    async def handle_update(self, update: dict) -> None:
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        user_id = chat.get("id")
        text = (message.get("text") or "").strip()
        if not user_id or not text:
            return
        try:
            await self._dispatch(user_id, message, text)
        except TelegramError:
            log.exception("failed to handle update for %s", user_id)

    # Button presses carry no args and map 1:1 onto a slash command — resolve
    # them to a canonical command up front so the rest of dispatch only ever
    # deals with one shape (AUTONOMY_PROTOCOL.md #15/#71: single lookup table
    # instead of a long branch chain — keeps this under the complexity limit
    # in ruff.toml, C901 max-complexity=12).
    _BUTTON_COMMANDS = {
        BTN_HELP: "/help",
        BTN_KEYWORDS: "/words",
        BTN_SITES: "/sites",
        BTN_PROFILE: "/me",
        BTN_PAY: "/pay",
        BTN_PAUSE: "/pause",
        BTN_RESUME: "/resume",
    }

    # command -> handler method name; every handler has the uniform signature
    # (self, user_id, args) so the table can dispatch without special-casing.
    _HANDLERS = {
        "/help": "_cmd_help",
        "/add": "_cmd_add",
        "/del": "_cmd_del",
        "/words": "_cmd_words",
        "/sites": "_cmd_sites",
        "/site": "_cmd_site",
        "/pause": "_cmd_pause",
        "/resume": "_cmd_resume",
        "/me": "_cmd_me",
        "/pay": "_cmd_pay",
        "/grant": "_cmd_grant",
        "/stats": "_cmd_stats",
    }

    async def _dispatch(self, user_id: int, message: dict, text: str) -> None:
        if text in self._BUTTON_COMMANDS:
            command, args = self._BUTTON_COMMANDS[text], ""
        else:
            command, _, args = text.partition(" ")
            args = args.strip()

        if command == "/start":
            await self._cmd_start(user_id, message)
            return

        handler_name = self._HANDLERS.get(command)
        if handler_name is None:
            await self.api.send_message(user_id, "Не понимаю. /help — список команд.")
            return
        await getattr(self, handler_name)(user_id, args)

    async def _cmd_start(self, user_id: int, message: dict) -> None:
        username = (message.get("from") or {}).get("username", "") or ""
        is_new = self.db.add_user(user_id, username, self.config.test_period_days)
        if is_new:
            greeting = (
                "👋 Добро пожаловать! Вам активирован тестовый период "
                f"на {self.config.test_period_days} дн.\n\n{HELP_TEXT}"
            )
            if self.config.admin_id:
                await self.api.send_message(
                    self.config.admin_id,
                    f"🆕 Новый пользователь: {user_id} @{username}",
                )
        else:
            greeting = "С возвращением! /help — список команд."
        await self.api.send_message(user_id, greeting, main_menu_keyboard())

    async def _cmd_add(self, user_id: int, args: str) -> None:
        words = [w for w in (p.strip() for p in args.split(",")) if w]
        if not words:
            await self.api.send_message(user_id, "Формат: /add слово1, слово2")
            return
        added = self.db.add_keywords(user_id, words)
        await self.api.send_message(user_id, f"✅ Добавлено слов: {added}")

    async def _cmd_del(self, user_id: int, args: str) -> None:
        if args and self.db.del_keyword(user_id, args):
            await self.api.send_message(user_id, f"🗑 Удалено: {args}")
        else:
            await self.api.send_message(user_id, "Такого слова нет. /words — список.")

    async def _cmd_help(self, user_id: int, args: str) -> None:
        await self.api.send_message(user_id, HELP_TEXT)

    async def _cmd_pause(self, user_id: int, args: str) -> None:
        self.db.set_active(user_id, False)
        await self.api.send_message(user_id, "⏸ Рассылка приостановлена.")

    async def _cmd_resume(self, user_id: int, args: str) -> None:
        self.db.set_active(user_id, True)
        await self.api.send_message(user_id, "▶️ Рассылка возобновлена.")

    async def _cmd_pay(self, user_id: int, args: str) -> None:
        await self.api.send_message(user_id, payments.payment_instructions(self.config))

    async def _cmd_words(self, user_id: int, args: str) -> None:
        words = self.db.keywords(user_id)
        if words:
            text = "🔑 Ваши ключевые слова:\n" + "\n".join(f"• {w}" for w in words)
        else:
            text = "Ключевых слов нет — вы получаете все заказы. /add — добавить."
        await self.api.send_message(user_id, text)

    async def _cmd_sites(self, user_id: int, args: str) -> None:
        lines = ["🌐 Источники (переключить: /site имя):"]
        for name, source in SOURCES.items():
            mark = "✅" if self.db.site_enabled(user_id, name) else "❌"
            lines.append(f"{mark} {name} — {source.title}")
        await self.api.send_message(user_id, "\n".join(lines))

    async def _cmd_site(self, user_id: int, args: str) -> None:
        if args not in SOURCES:
            await self.api.send_message(user_id, "Нет такого источника. /sites — список.")
            return
        enabled = self.db.toggle_site(user_id, args)
        state = "включён ✅" if enabled else "выключен ❌"
        await self.api.send_message(user_id, f"Источник {args} {state}.")

    async def _cmd_me(self, user_id: int, args: str) -> None:
        row = self.db.get_user(user_id)
        if row is None:
            await self.api.send_message(user_id, "Вы не зарегистрированы. /start")
            return
        import datetime

        until = datetime.datetime.fromtimestamp(row["paid_until"], tz=datetime.UTC).strftime(
            "%d.%m.%Y"
        )
        status = "активна ✅" if self.db.is_subscribed(user_id) else "истекла ❌"
        paused = "" if row["active"] else "\n⏸ Рассылка на паузе."
        await self.api.send_message(
            user_id,
            f"👤 ID: {user_id}\nПодписка: {status} (до {until}){paused}",
        )

    async def _cmd_grant(self, user_id: int, args: str) -> None:
        if user_id != self.config.admin_id:
            await self.api.send_message(user_id, "Команда доступна только администратору.")
            return
        try:
            target_str, days_str = args.split()
            target, days = int(target_str), int(days_str)
        except ValueError:
            await self.api.send_message(user_id, "Формат: /grant user_id days")
            return
        payments.grant_days(self.db, target, days)
        await self.api.send_message(user_id, f"✅ Начислено {days} дн. пользователю {target}")
        await self.api.send_message(target, f"💳 Вам начислено {days} дн. подписки.")

    async def _cmd_stats(self, user_id: int, args: str) -> None:
        if user_id != self.config.admin_id:
            await self.api.send_message(user_id, "Команда доступна только администратору.")
            return
        stats = self.db.stats()
        await self.api.send_message(
            user_id,
            f"📊 Пользователей: {stats['users']}, активных подписок: {stats['active']}",
        )

    async def poll_forever(self) -> None:  # pragma: no cover - infinite loop wrapper
        while True:
            await self.poll_once()
            await asyncio.sleep(self.config.bot_poll_delay)

    async def poll_once(self) -> None:
        try:
            updates = await self.api.get_updates()
        except TelegramError:
            log.exception("getUpdates failed")
            return
        for update in updates:
            await self.handle_update(update)
