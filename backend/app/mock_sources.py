"""Dev fixture server: serves recorded source payloads so parsing can be
tested end-to-end without egress to the real freelance sites."""

from __future__ import annotations

from pathlib import Path

from aiohttp import web

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

ROUTES = {
    "fl_ru": "fl_ru.xml",
    "habr_freelance": "habr.xml",
    "weblancer": "weblancer.xml",
    "freelance_ru": "freelance_ru.xml",
    "freelancehunt": "freelancehunt.json",
    "freelancer_com": "freelancer_com.json",
    "youdo": "youdo.json",
    "kwork": "kwork.html",
}


def build_mock_app(fixtures_dir: Path = FIXTURES_DIR) -> web.Application:
    app = web.Application()
    app["fixtures"] = fixtures_dir

    async def serve(request: web.Request) -> web.Response:
        name = request.match_info["source"]
        filename = ROUTES.get(name)
        if not filename:
            raise web.HTTPNotFound(text=f"no fixture for {name}")
        return web.Response(text=(request.app["fixtures"] / filename).read_text(encoding="utf-8"))

    async def serve_telegram(request: web.Request) -> web.Response:
        return web.Response(
            text=(request.app["fixtures"] / "telegram_channel.html").read_text(encoding="utf-8")
        )

    app.add_routes(
        [
            web.get("/src/{source}", serve),
            web.get("/tg/s/{channel}", serve_telegram),
        ]
    )
    return app
