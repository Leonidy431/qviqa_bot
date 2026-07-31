"""JSON-API sources: freelancehunt.com (API v2), freelancer.com, youdo.com."""

from __future__ import annotations

import json

from .base import Item, ParserError

FREELANCEHUNT_URL = "https://api.freelancehunt.com/v2/projects"
FREELANCER_COM_URL = (
    "https://www.freelancer.com/api/projects/0.1/projects/active/?limit=50&full_description=true"
)
YOUDO_URL = "https://youdo.com/api/tasks/tasksList/?list=all&page=1"


def _load_json(source: str, payload: str) -> dict:
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise ParserError(f"{source}: invalid JSON") from exc
    if not isinstance(data, dict):
        raise ParserError(f"{source}: unexpected JSON shape")
    return data


def parse_freelancehunt(payload: str) -> list[Item]:
    data = _load_json("freelancehunt", payload)
    items = []
    for row in data.get("data", []):
        attrs = row.get("attributes", {})
        budget = attrs.get("budget") or {}
        price = ""
        if budget.get("amount"):
            price = f"{budget['amount']} {budget.get('currency', '')}".strip()
        url = (row.get("links") or {}).get("self", {})
        web = url.get("web") if isinstance(url, dict) else ""
        items.append(
            Item(
                source="freelancehunt",
                id=str(row.get("id", "")),
                title=attrs.get("name", ""),
                url=web or f"https://freelancehunt.com/project/{row.get('id', '')}",
                text=attrs.get("description", "") or "",
                price=price,
            )
        )
    return items


def parse_freelancer_com(payload: str) -> list[Item]:
    data = _load_json("freelancer_com", payload)
    projects = (data.get("result") or {}).get("projects") or []
    items = []
    for row in projects:
        budget = row.get("budget") or {}
        price = ""
        if budget.get("minimum"):
            price = f"от {budget['minimum']} {row.get('currency', {}).get('code', '')}".strip()
        items.append(
            Item(
                source="freelancer_com",
                id=str(row.get("id", "")),
                title=row.get("title", ""),
                url="https://www.freelancer.com/projects/" + row.get("seo_url", ""),
                text=row.get("preview_description", "") or "",
                price=price,
            )
        )
    return items


def parse_youdo(payload: str) -> list[Item]:
    data = _load_json("youdo", payload)
    result = data.get("ResultObject") or {}
    items = []
    for row in result.get("Items") or []:
        price = str(row.get("PriceAmount") or "")
        items.append(
            Item(
                source="youdo",
                id=str(row.get("Id", "")),
                title=row.get("Name", ""),
                url=f"https://youdo.com/t{row.get('Id', '')}",
                text=row.get("Description", "") or "",
                price=(price + " ₽") if price else "",
            )
        )
    return items
