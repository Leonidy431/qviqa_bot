from app.matcher import escape_html, format_project, hashtag_format, normalize, words_check
from app.parsers.base import Item


def test_normalize_strips_punctuation():
    assert normalize("Нужен, Python-разработчик!") == "нужен python-разработчик"


def test_words_check_empty_keywords_matches_all():
    assert words_check("любой текст", []) == ["*"]


def test_words_check_finds_keywords_case_insensitive():
    assert words_check("Требуется PYTHON разработчик", ["python", "java"]) == ["python"]


def test_words_check_no_match():
    assert words_check("верстка лендинга", ["python"]) == []


def test_words_check_skips_blank_keywords():
    assert words_check("python", ["", "python"]) == ["python"]


def test_hashtag_format():
    assert hashtag_format("Python бот") == "#python_бот"
    assert hashtag_format("!!!") == ""


def test_escape_html():
    assert escape_html("<b>&") == "&lt;b&gt;&amp;"


def test_format_project_full():
    item = Item(
        source="fl_ru",
        id="1",
        title="Бот <script>",
        url="https://example.com/1",
        text="x" * 600,
        price="30000 ₽",
    )
    text = format_project(item, ["бот"])
    assert "&lt;script&gt;" in text
    assert "30000 ₽" in text
    assert "…" in text  # long description trimmed
    assert "#бот" in text
    assert "https://example.com/1" in text


def test_format_project_minimal_and_star_match():
    item = Item(source="youdo", id="2", title="Заказ", url="u")
    text = format_project(item, ["*"])
    assert "💰" not in text
    assert "#" not in text
