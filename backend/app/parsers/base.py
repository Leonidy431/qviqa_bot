"""Shared parser primitives."""

from __future__ import annotations

import re
from dataclasses import dataclass

import feedparser


class ParserError(Exception):
    """Raised when a source payload cannot be understood."""


@dataclass
class Item:
    source: str
    id: str
    title: str
    url: str
    text: str = ""
    price: str = ""

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "text": self.text,
            "price": self.price,
        }


_TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(html: str) -> str:
    return " ".join(_TAG_RE.sub(" ", html).replace("&nbsp;", " ").split())


def parse_rss(source: str, payload: str) -> list[Item]:
    """Generic RSS/Atom feed parser used by several sources."""
    feed = feedparser.parse(payload)
    if feed.bozo and not feed.entries:
        raise ParserError(f"{source}: not a valid feed")
    items = []
    for entry in feed.entries:
        link = entry.get("link", "")
        if not link:
            continue
        items.append(
            Item(
                source=source,
                id=entry.get("id", link),
                title=strip_tags(entry.get("title", "")),
                url=link,
                text=strip_tags(entry.get("summary", "")),
            )
        )
    return items
