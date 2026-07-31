import pytest

from app.parsers import DEAD_SOURCES, SOURCES, ParserError
from app.parsers.api_sources import parse_freelancehunt, parse_freelancer_com, parse_youdo
from app.parsers.base import parse_rss, strip_tags
from app.parsers.html_sources import parse_kwork, parse_telegram_channel
from app.parsers.rss_sources import (
    parse_fl_ru,
    parse_freelance_ru,
    parse_habr,
    parse_weblancer,
)

from .conftest import load_fixture


def test_strip_tags():
    assert strip_tags("<p>привет&nbsp;<b>мир</b></p>") == "привет мир"


def test_registry_covers_all_original_sources():
    # 9 ported + 10 documented dead = 18 originals + habr rename
    assert len(SOURCES) == 9
    assert len(DEAD_SOURCES) == 10
    assert "freelansim.ru" in DEAD_SOURCES


def test_parse_fl_ru():
    items = parse_fl_ru(load_fixture("fl_ru.xml"))
    assert len(items) == 2
    assert items[0].source == "fl_ru"
    assert items[0].title == "Разработать Telegram бота для магазина"
    assert "30000" in items[0].text
    assert items[0].url.startswith("https://www.fl.ru/projects/5211001")
    assert items[0].key.startswith("fl_ru:")


def test_parse_habr():
    items = parse_habr(load_fixture("habr.xml"))
    assert len(items) == 1
    assert items[0].source == "habr_freelance"
    assert items[0].title == "Парсер данных на Python"


def test_parse_weblancer():
    items = parse_weblancer(load_fixture("weblancer.xml"))
    assert items[0].source == "weblancer"
    assert "Laravel" in items[0].title


def test_parse_freelance_ru():
    items = parse_freelance_ru(load_fixture("freelance_ru.xml"))
    assert items[0].source == "freelance_ru"
    assert items[0].url == "https://freelance.ru/project/design-app-987654"


def test_parse_rss_rejects_garbage():
    with pytest.raises(ParserError):
        parse_rss("fl_ru", "это не xml и не фид")


def test_parse_rss_skips_entries_without_link():
    payload = (
        '<?xml version="1.0"?><rss version="2.0"><channel>'
        "<item><title>без ссылки</title></item>"
        "</channel></rss>"
    )
    assert parse_rss("fl_ru", payload) == []


def test_parse_freelancehunt():
    items = parse_freelancehunt(load_fixture("freelancehunt.json"))
    assert len(items) == 2
    assert items[0].price == "5000 UAH"
    assert items[0].url == "https://freelancehunt.com/project/998877.html"
    # fallback URL when links.self.web is missing
    assert items[1].url == "https://freelancehunt.com/project/998878"
    assert items[1].price == ""


def test_parse_freelancer_com():
    items = parse_freelancer_com(load_fixture("freelancer_com.json"))
    assert items[0].price == "от 250 USD"
    assert items[0].url.endswith("Build-scraping-bot-Python")
    assert items[1].price == ""


def test_parse_youdo():
    items = parse_youdo(load_fixture("youdo.json"))
    assert items[0].price == "8000 ₽"
    assert items[0].url == "https://youdo.com/t12345678"
    assert items[1].price == ""


@pytest.mark.parametrize("parse", [parse_freelancehunt, parse_freelancer_com, parse_youdo])
def test_api_parsers_reject_invalid_json(parse):
    with pytest.raises(ParserError):
        parse("not json")


@pytest.mark.parametrize("parse", [parse_freelancehunt, parse_freelancer_com, parse_youdo])
def test_api_parsers_reject_non_object_json(parse):
    with pytest.raises(ParserError):
        parse("[1, 2, 3]")


@pytest.mark.parametrize("parse", [parse_freelancehunt, parse_freelancer_com, parse_youdo])
def test_api_parsers_tolerate_empty_payload(parse):
    assert parse("{}") == []


def test_parse_kwork():
    items = parse_kwork(load_fixture("kwork.html"))
    assert len(items) == 2
    assert items[0].title == "Нужен бот для Telegram"
    assert items[0].price == "до 12000 ₽"
    assert items[1].price == ""


def test_parse_kwork_missing_state():
    with pytest.raises(ParserError):
        parse_kwork("<html><body>ничего</body></html>")


def test_parse_kwork_bad_json():
    with pytest.raises(ParserError):
        parse_kwork("<script>window.stateData = {broken};</script>")


def test_parse_telegram_channel():
    items = parse_telegram_channel(load_fixture("telegram_channel.html"))
    assert len(items) == 2
    assert items[0].id == "freelancetaverna/48211"
    assert items[0].url == "https://t.me/freelancetaverna/48211"
    assert "python разработчик" in items[0].text
    assert items[0].title.endswith("…")  # long text truncated in title


def test_parse_telegram_channel_not_a_channel_page():
    with pytest.raises(ParserError):
        parse_telegram_channel("<html><body>404</body></html>")


def test_parse_telegram_channel_empty_history_is_ok():
    page = '<div class="tgme_widget_message" data-post="x/1"></div>'
    assert parse_telegram_channel(page) == []


def test_parse_telegram_channel_skips_blank_messages():
    page = (
        '<div class="tgme_widget_message" data-post="x/1">'
        '<div class="tgme_widget_message_text js-message_text">   </div></div>'
    )
    assert parse_telegram_channel(page) == []
