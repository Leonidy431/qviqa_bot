"""Runtime configuration, read from environment variables.

Mirrors the settings model of the original BAS project
("настройки 15.11.22.xml") minus dead services: QIWI P2P invoices are
discontinued upstream, so payments are manual (admin /grant).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass
class Config:
    bot_token: str = ""
    admin_id: int = 0
    support: str = "@Leonidy"
    test_period_days: int = 7
    subscription_price: int = 250
    poll_interval: float = 60.0
    http_timeout: float = 20.0
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "data/qviqa.sqlite3"
    freelancehunt_token: str = ""
    telegram_channels: list[str] = field(default_factory=list)
    source_url_overrides: dict[str, str] = field(default_factory=dict)
    telegram_api_base: str = ""
    bot_poll_delay: float = 1.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        env = dict(os.environ if env is None else env)
        overrides: dict[str, str] = {}
        for key, value in env.items():
            if key.startswith("SOURCE_URL_"):
                overrides[key.removeprefix("SOURCE_URL_").lower()] = value
        return cls(
            bot_token=env.get("BOT_TOKEN", ""),
            admin_id=int(env.get("ADMIN_ID", "0") or 0),
            support=env.get("SUPPORT", "@Leonidy"),
            test_period_days=int(env.get("TEST_PERIOD_DAYS", "7")),
            subscription_price=int(env.get("SUBSCRIPTION_PRICE", "250")),
            poll_interval=float(env.get("POLL_INTERVAL", "60")),
            http_timeout=float(env.get("HTTP_TIMEOUT", "20")),
            host=env.get("HOST", "0.0.0.0"),
            port=int(env.get("PORT", "8000")),
            db_path=env.get("DB_PATH", "data/qviqa.sqlite3"),
            freelancehunt_token=env.get("FREELANCEHUNT_TOKEN", ""),
            telegram_channels=_split_csv(env.get("TELEGRAM_CHANNELS", "")),
            source_url_overrides=overrides,
            telegram_api_base=env.get("TELEGRAM_API_BASE", ""),
            bot_poll_delay=float(env.get("BOT_POLL_DELAY", "1.0")),
        )
