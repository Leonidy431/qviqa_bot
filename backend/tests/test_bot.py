import pytest

from app.bot import BTN_HELP, BTN_KEYWORDS, Bot, main_menu_keyboard
from app.telegram import TelegramError

from .conftest import FakeTelegramAPI


def update(user_id, text, username="user"):
    return {
        "message": {
            "chat": {"id": user_id},
            "from": {"username": username},
            "text": text,
        }
    }


@pytest.fixture
def bot(fake_api, db, config):
    return Bot(fake_api, db, config)


def last_text(api):
    return api.sent[-1][1]


async def test_start_new_user_notifies_admin(bot, fake_api, db):
    await bot.handle_update(update(1, "/start", "alice"))
    assert db.get_user(1) is not None
    texts = [t for _, t, _ in fake_api.sent]
    assert any("Новый пользователь" in t for t in texts)
    assert any("тестовый период" in t for t in texts)
    assert fake_api.sent[-1][2] == main_menu_keyboard()


async def test_start_existing_user(bot, fake_api, db):
    db.add_user(1, "alice", 7)
    await bot.handle_update(update(1, "/start"))
    assert "С возвращением" in last_text(fake_api)


async def test_start_without_admin_configured(fake_api, db, config):
    config.admin_id = 0
    bot = Bot(fake_api, db, config)
    await bot.handle_update(update(1, "/start"))
    assert all(chat_id == 1 for chat_id, _, _ in fake_api.sent)


async def test_help_command_and_button(bot, fake_api):
    await bot.handle_update(update(1, "/help"))
    await bot.handle_update(update(1, BTN_HELP))
    assert all("/add" in t for _, t, _ in fake_api.sent)


async def test_add_and_list_and_delete_words(bot, fake_api, db):
    await bot.handle_update(update(1, "/add python, бот"))
    assert "Добавлено слов: 2" in last_text(fake_api)
    await bot.handle_update(update(1, "/words"))
    assert "python" in last_text(fake_api)
    await bot.handle_update(update(1, BTN_KEYWORDS))
    assert "бот" in last_text(fake_api)
    await bot.handle_update(update(1, "/del python"))
    assert "Удалено" in last_text(fake_api)
    await bot.handle_update(update(1, "/del python"))
    assert "Такого слова нет" in last_text(fake_api)


async def test_add_without_args(bot, fake_api):
    await bot.handle_update(update(1, "/add"))
    assert "Формат" in last_text(fake_api)


async def test_words_empty(bot, fake_api):
    await bot.handle_update(update(1, "/words"))
    assert "все заказы" in last_text(fake_api)


async def test_sites_listing_and_toggle(bot, fake_api, db):
    await bot.handle_update(update(1, "/sites"))
    assert "fl_ru" in last_text(fake_api)
    await bot.handle_update(update(1, "/site fl_ru"))
    assert "выключен" in last_text(fake_api)
    await bot.handle_update(update(1, "/sites"))
    assert "❌ fl_ru" in last_text(fake_api)
    await bot.handle_update(update(1, "/site fl_ru"))
    assert "включён" in last_text(fake_api)
    await bot.handle_update(update(1, "/site nosuch"))
    assert "Нет такого источника" in last_text(fake_api)


async def test_pause_resume(bot, fake_api, db):
    db.add_user(1, "a", 7)
    await bot.handle_update(update(1, "/pause"))
    assert db.get_user(1)["active"] == 0
    await bot.handle_update(update(1, "/resume"))
    assert db.get_user(1)["active"] == 1


async def test_me_registered_paused_and_unregistered(bot, fake_api, db):
    await bot.handle_update(update(1, "/me"))
    assert "не зарегистрированы" in last_text(fake_api)
    db.add_user(1, "a", 7)
    db.set_active(1, False)
    await bot.handle_update(update(1, "/me"))
    assert "активна ✅" in last_text(fake_api)
    assert "на паузе" in last_text(fake_api)


async def test_me_expired(bot, fake_api, db):
    db.add_user(1, "a", 0)
    await bot.handle_update(update(1, "/me"))
    assert "истекла ❌" in last_text(fake_api)


async def test_pay(bot, fake_api):
    await bot.handle_update(update(1, "/pay"))
    assert "250" in last_text(fake_api)
    assert "QIWI" in last_text(fake_api)


async def test_grant_requires_admin(bot, fake_api):
    await bot.handle_update(update(1, "/grant 2 30"))
    assert "только администратору" in last_text(fake_api)


async def test_grant_by_admin(bot, fake_api, db):
    db.add_user(2, "b", 0)
    await bot.handle_update(update(100, "/grant 2 30"))
    assert db.is_subscribed(2) is True
    assert any(chat_id == 2 for chat_id, _, _ in fake_api.sent)


async def test_grant_bad_args(bot, fake_api):
    await bot.handle_update(update(100, "/grant oops"))
    assert "Формат" in last_text(fake_api)


async def test_stats(bot, fake_api, db):
    db.add_user(1, "a", 7)
    await bot.handle_update(update(100, "/stats"))
    assert "Пользователей: 1" in last_text(fake_api)
    await bot.handle_update(update(1, "/stats"))
    assert "только администратору" in last_text(fake_api)


async def test_unknown_command(bot, fake_api):
    await bot.handle_update(update(1, "какой-то текст"))
    assert "Не понимаю" in last_text(fake_api)


async def test_ignores_updates_without_text_or_chat(bot, fake_api):
    await bot.handle_update({"message": {"chat": {"id": 1}}})
    await bot.handle_update({"message": {"text": "hi", "chat": {}}})
    await bot.handle_update({})
    assert fake_api.sent == []


async def test_handle_update_swallows_telegram_errors(db, config):
    api = FakeTelegramAPI(fail_for={1})
    bot = Bot(api, db, config)
    await bot.handle_update(update(1, "/help"))  # must not raise
    assert api.sent == []


async def test_poll_once_dispatches(db, config):
    api = FakeTelegramAPI(updates=[update(1, "/help")])
    bot = Bot(api, db, config)
    await bot.poll_once()
    assert len(api.sent) == 1


async def test_poll_once_survives_getupdates_error(db, config):
    class BrokenAPI(FakeTelegramAPI):
        async def get_updates(self, timeout: int = 30):
            raise TelegramError("network")

    bot = Bot(BrokenAPI(), db, config)
    await bot.poll_once()  # must not raise
