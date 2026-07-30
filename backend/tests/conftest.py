from pathlib import Path

import pytest

from app.config import Config
from app.db import Database

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def config():
    return Config(admin_id=100, test_period_days=7, subscription_price=250)


class FakeTelegramAPI:
    """Records outgoing messages instead of hitting the Telegram API."""

    def __init__(self, updates=None, fail_for=()):
        self.sent: list[tuple[int, str, dict | None]] = []
        self.updates = list(updates or [])
        self.fail_for = set(fail_for)

    async def send_message(self, chat_id, text, reply_markup=None):
        if chat_id in self.fail_for:
            from app.telegram import TelegramError

            raise TelegramError("blocked")
        self.sent.append((chat_id, text, reply_markup))
        return {"message_id": len(self.sent)}

    async def get_updates(self, timeout: int = 30):
        updates, self.updates = self.updates, []
        return updates


@pytest.fixture
def fake_api():
    return FakeTelegramAPI()
