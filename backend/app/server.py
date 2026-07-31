"""Dev/ops HTTP server: health, source registry, on-demand parsing, a live
NDJSON feed filtered by keywords, and the static frontend."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aiohttp import web

from . import __version__, fetcher, scheduler
from .matcher import words_check
from .parsers import DEAD_SOURCES, SOURCES, ParserError

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def build_app(config, db, session, api=None) -> web.Application:
    app = web.Application()
    app["config"] = config
    app["db"] = db
    app["session"] = session
    app["api"] = api
    app.add_routes(
        [
            web.get("/health", health),
            web.get("/api/sources", sources_handler),
            web.get("/api/parse/{source}", parse_handler),
            web.post("/api/run-cycle", run_cycle_handler),
            web.get("/api/stream", stream_handler),
            web.get("/", frontend_index),
            web.static("/assets", FRONTEND_DIR),
        ]
    )
    return app


async def health(request: web.Request) -> web.Response:
    db = request.app["db"]
    return web.json_response({"status": "ok", "version": __version__, **db.stats()})


async def sources_handler(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "sources": [
                {
                    "name": s.name,
                    "title": s.title,
                    "url": s.url,
                    "needs_token": s.needs_token,
                }
                for s in SOURCES.values()
            ],
            "dead_sources": DEAD_SOURCES,
        }
    )


async def parse_handler(request: web.Request) -> web.Response:
    name = request.match_info["source"]
    if name not in SOURCES:
        return web.json_response(
            {"error": f"unknown source '{name}'", "dead": DEAD_SOURCES.get(name)},
            status=404,
        )
    config = request.app["config"]
    try:
        items = await scheduler.collect_source(config, request.app["session"], name)
    except (fetcher.FetchError, ParserError) as exc:
        return web.json_response({"source": name, "ok": False, "error": str(exc)}, status=502)
    limit = int(request.query.get("limit", "10"))
    return web.json_response(
        {
            "source": name,
            "ok": True,
            "count": len(items),
            "items": [item.as_dict() for item in items[:limit]],
        }
    )


async def run_cycle_handler(request: web.Request) -> web.Response:
    stats = await scheduler.run_cycle(
        request.app["config"],
        request.app["session"],
        request.app["db"],
        request.app["api"],
    )
    return web.json_response({"cycle": stats})


async def _collect_for_stream(config, session, name: str) -> tuple[str, list]:
    try:
        return name, await scheduler.collect_source(config, session, name)
    except (fetcher.FetchError, ParserError):
        return name, []


async def stream_handler(request: web.Request) -> web.StreamResponse:
    """GET /api/stream?keywords=python,бот&limit=50

    Streams newline-delimited JSON: one line per matching project, across
    every source, as each source finishes fetching. Empty/absent `keywords`
    streams everything (same "*" semantics as the bot's own matcher).
    """
    keywords = [k.strip() for k in request.query.get("keywords", "").split(",") if k.strip()]
    try:
        limit = int(request.query.get("limit", "0"))
    except ValueError:
        limit = 0

    resp = web.StreamResponse(headers={"Content-Type": "application/x-ndjson; charset=utf-8"})
    await resp.prepare(request)

    config = request.app["config"]
    session = request.app["session"]
    sent = 0
    tasks = [asyncio.create_task(_collect_for_stream(config, session, name)) for name in SOURCES]
    for task in asyncio.as_completed(tasks):
        _name, items = await task
        for item in items:
            matched = words_check(f"{item.title} {item.text}", keywords)
            if not matched:
                continue
            payload = item.as_dict()
            payload["matched_keywords"] = matched
            await resp.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            sent += 1
            if limit and sent >= limit:
                for pending in tasks:
                    pending.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                await resp.write_eof()
                return resp
    await resp.write_eof()
    return resp


async def frontend_index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(FRONTEND_DIR / "index.html")
