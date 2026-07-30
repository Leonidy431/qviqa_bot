"""Dev/ops HTTP server: health, source registry, on-demand parsing."""

from __future__ import annotations

from aiohttp import web

from . import __version__, fetcher, scheduler
from .parsers import DEAD_SOURCES, SOURCES, ParserError


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
        ]
    )
    return app


async def health(request: web.Request) -> web.Response:
    db = request.app["db"]
    return web.json_response(
        {"status": "ok", "version": __version__, **db.stats()}
    )


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
