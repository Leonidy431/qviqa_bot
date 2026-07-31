"""Source registry.

Maps every source of the original BAS bot to its status in the port:
working parsers get an entry in SOURCES; dead or browser-bound sources are
documented in DEAD_SOURCES with the reason and the replacement.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import api_sources, html_sources, rss_sources
from .base import Item, ParserError  # noqa: F401  (re-exported)


@dataclass(frozen=True)
class Source:
    name: str
    title: str
    url: str
    parse: Callable[[str], list[Item]]
    needs_token: bool = False


SOURCES: dict[str, Source] = {
    s.name: s
    for s in [
        Source("fl_ru", "FL.ru", rss_sources.FL_RU_URL, rss_sources.parse_fl_ru),
        Source(
            "habr_freelance",
            "freelance.habr.com (быв. freelansim.ru)",
            rss_sources.HABR_URL,
            rss_sources.parse_habr,
        ),
        Source(
            "weblancer",
            "weblancer.net",
            rss_sources.WEBLANCER_URL,
            rss_sources.parse_weblancer,
        ),
        Source(
            "freelance_ru",
            "freelance.ru",
            rss_sources.FREELANCE_RU_URL,
            rss_sources.parse_freelance_ru,
        ),
        Source(
            "freelancehunt",
            "freelancehunt.com",
            api_sources.FREELANCEHUNT_URL,
            api_sources.parse_freelancehunt,
            needs_token=True,
        ),
        Source(
            "freelancer_com",
            "freelancer.com",
            api_sources.FREELANCER_COM_URL,
            api_sources.parse_freelancer_com,
        ),
        Source("youdo", "youdo.com", api_sources.YOUDO_URL, api_sources.parse_youdo),
        Source("kwork", "kwork.ru", html_sources.KWORK_URL, html_sources.parse_kwork),
        Source(
            "telegram",
            "Telegram-каналы (t.me/s)",
            html_sources.TELEGRAM_BASE,
            html_sources.parse_telegram_channel,
        ),
    ]
}

# Sources of the original bot that are NOT ported, and why.
DEAD_SOURCES: dict[str, str] = {
    "freten.ru": "сервис закрыт",
    "1clancer.ru": "сервис закрыт",
    "superlance.pro": "агрегатор закрыт",
    "fl-ru.com": "зеркало FL.ru не работает; используйте fl_ru",
    "freelansim.ru": "переехал на freelance.habr.com — см. habr_freelance",
    "freelancejob.ru": "нет машиночитаемой ленты, требуется браузер",
    "kadrof.ru": "нет машиночитаемой ленты, требуется браузер",
    "vk.com": "требует VK API токен и обход антибота; заменён на telegram",
    "telemetr.me": "антибот; заменён прямым чтением t.me/s — см. telegram",
    "tgstat.ru": "антибот; заменён прямым чтением t.me/s — см. telegram",
}
