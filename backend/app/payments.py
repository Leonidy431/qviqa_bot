"""Subscription payments.

The original bot issued QIWI P2P invoices; QIWI shut down its wallet/P2P API
in 2024, so automatic invoicing is gone. The port keeps the subscription
model (test period + paid days) and routes payment through the admin:
the user gets payment instructions, the admin credits days via /grant.
"""

from __future__ import annotations

from .config import Config
from .db import Database


def payment_instructions(config: Config) -> str:
    return (
        f"💳 Подписка: {config.subscription_price} ₽/мес.\n\n"
        "QIWI P2P прекратил работу, поэтому оплата оформляется вручную:\n"
        f"напишите в поддержку {config.support} — после оплаты дни подписки "
        "будут начислены на ваш аккаунт."
    )


def grant_days(db: Database, user_id: int, days: int) -> int:
    """Credit subscription days (admin action, replaces add_balance)."""
    return db.grant_days(user_id, days)
