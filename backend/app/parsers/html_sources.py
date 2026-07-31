"""HTML-scraped sources: kwork.ru (embedded state JSON) and public
t.me/s/<channel> pages.

The t.me/s parser replaces three sources of the original bot at once —
telemetr.me, tgstat.ru and vk.com scraping of repost communities — which
all required a logged-in browser and anti-bot workarounds. Telegram's own
public preview pages expose the same messages as plain HTML.
"""

from __future__ import annotations

import json
import re

from .base import Item, ParserError, strip_tags

KWORK_URL = "https://kwork.ru/projects"
TELEGRAM_BASE = "https://t.me/s/"

_KWORK_STATE_RE = re.compile(r"window\.stateData\s*=\s*(\{.*?\});?\s*</script>", re.S)
_TG_MESSAGE_RE = re.compile(
    r'data-post="(?P<post>[^"]+)".*?'
    r"tgme_widget_message_text[^>]*>(?P<html>.*?)</div>",
    re.S,
)


def parse_kwork(payload: str) -> list[Item]:
    match = _KWORK_STATE_RE.search(payload)
    if not match:
        raise ParserError("kwork: stateData not found")
    try:
        state = json.loads(match.group(1))
    except ValueError as exc:
        raise ParserError("kwork: bad stateData JSON") from exc
    rows = ((state.get("wantsListData") or {}).get("pagination") or {}).get("data") or []
    items = []
    for row in rows:
        price = row.get("priceLimit") or ""
        items.append(
            Item(
                source="kwork",
                id=str(row.get("id", "")),
                title=strip_tags(str(row.get("name", ""))),
                url=f"https://kwork.ru/projects/{row.get('id', '')}",
                text=strip_tags(str(row.get("description", "") or "")),
                price=f"до {price} ₽" if price else "",
            )
        )
    return items


def parse_telegram_channel(payload: str) -> list[Item]:
    items = []
    for match in _TG_MESSAGE_RE.finditer(payload):
        post = match.group("post")
        text = strip_tags(match.group("html"))
        if not text:
            continue
        title = text if len(text) <= 80 else text[:80] + "…"
        items.append(
            Item(
                source="telegram",
                id=post,
                title=title,
                url=f"https://t.me/{post}",
                text=text,
            )
        )
    if not items and "tgme_widget_message" not in payload:
        raise ParserError("telegram: not a channel preview page")
    return items
