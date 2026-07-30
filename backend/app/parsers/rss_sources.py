"""RSS-backed sources: FL.ru, freelance.habr.com (ex-freelansim.ru),
weblancer.net, freelance.ru.

The original BAS bot drove a full browser to scrape the HTML versions of
these boards; all four publish machine-readable feeds, so the port reads
those instead — no browser, no anti-bot arms race.
"""

from __future__ import annotations

from .base import Item, parse_rss

FL_RU_URL = "https://www.fl.ru/rss/all.xml"
HABR_URL = "https://freelance.habr.com/tasks/rss"
WEBLANCER_URL = "https://www.weblancer.net/rss/"
FREELANCE_RU_URL = "https://freelance.ru/rss/feed"


def parse_fl_ru(payload: str) -> list[Item]:
    return parse_rss("fl_ru", payload)


def parse_habr(payload: str) -> list[Item]:
    return parse_rss("habr_freelance", payload)


def parse_weblancer(payload: str) -> list[Item]:
    return parse_rss("weblancer", payload)


def parse_freelance_ru(payload: str) -> list[Item]:
    return parse_rss("freelance_ru", payload)
