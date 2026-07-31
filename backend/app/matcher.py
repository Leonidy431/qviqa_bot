"""Keyword matching and message formatting (ports words_check / hashtag_format)."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[\wа-яё#+-]+", re.IGNORECASE | re.UNICODE)


def normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


def words_check(text: str, keywords: list[str]) -> list[str]:
    """Return the keywords found in *text* (substring match on normalized text).

    An empty keyword list means "match everything" — same as the original bot,
    where a user without filters received every project.
    """
    if not keywords:
        return ["*"]
    haystack = normalize(text)
    return [kw for kw in keywords if kw and normalize(kw) in haystack]


def hashtag_format(word: str) -> str:
    """Turn a keyword into a telegram-safe hashtag (port of hashtag_format)."""
    cleaned = re.sub(r"[^\wа-яё]+", "_", word.lower()).strip("_")
    return f"#{cleaned}" if cleaned else ""


def format_project(item, matched: list[str]) -> str:
    """Render one parsed project as a Telegram HTML message."""
    tags = " ".join(t for t in (hashtag_format(m) for m in matched if m != "*") if t)
    lines = [f"<b>{escape_html(item.title)}</b>"]
    if item.price:
        lines.append(f"💰 {escape_html(item.price)}")
    if item.text:
        snippet = item.text if len(item.text) <= 500 else item.text[:500] + "…"
        lines.append(escape_html(snippet))
    lines.append(item.url)
    lines.append(f"🌐 {item.source}" + (f"  {tags}" if tags else ""))
    return "\n\n".join(lines)


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
