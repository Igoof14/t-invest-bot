"""Тесты парсинга страницы релиза рейтинга НРА."""

from __future__ import annotations

from datetime import date, datetime

from features.rating_nra.parser import parse_release
from features.rating_nra.schemas import ReleaseStub

_STUB = ReleaseStub(
    post_id=44197,
    url="https://www.ra-national.ru/press_release/new-century-bank/44197/",
    title="НРА повысило кредитный рейтинг",
    modified=datetime(2026, 6, 3, 10, 8, 31),
)

_HTML = """
<html><body>
  <h3>НРА ПОВЫСИЛО кредитный рейтинг</h3>
  <span class="sample01">
    НРА повысило кредитный рейтинг до уровня BBB|ru|, прогноз «Стабильный».
  </span>
  <table>
    <tr><td>Полное наименование объекта рейтинга</td><td>ООО «Новый Век»</td></tr>
    <tr><td>Сокращенное наименование объекта рейтинга</td><td>Новый Век</td></tr>
    <tr><td>Вид объекта рейтинга</td><td>Банк</td></tr>
    <tr><td>Идентификационный номер налогоплательщика (ИНН)</td><td>7744002652</td></tr>
    <tr><td>ISIN</td><td>RU000A105RV3</td></tr>
    <tr><td>Дата публикации</td><td>03.06.2026</td></tr>
  </table>
</body></html>
"""


def test_parse_release_extracts_core_fields() -> None:
    event = parse_release(_HTML, _STUB)

    assert event is not None
    assert event.post_id == 44197
    assert event.inn == "7744002652"
    assert event.isins == ["RU000A105RV3"]
    assert event.entity_name == "Новый Век"
    assert event.entity_type == "Банк"
    assert event.rating_value == "BBB|ru|"
    assert event.outlook == "Стабильный"
    assert event.publication_date == date(2026, 6, 3)
    assert event.modified == datetime(2026, 6, 3, 10, 8, 31)


def test_parse_release_extracts_multiple_isins() -> None:
    # Рейтинг облигационного выпуска покрывает несколько серий.
    html = """
    <table>
      <tr><td>ISIN</td><td>RU000A103QL1, RU000A107DM8, RU000A108447</td></tr>
    </table>
    """
    event = parse_release(html, _STUB)

    assert event is not None
    assert event.isins == ["RU000A103QL1", "RU000A107DM8", "RU000A108447"]


def test_parse_release_dedupes_isins() -> None:
    html = """
    <table>
      <tr><td>ISIN</td><td>RU000A103QL1, RU000A103QL1</td></tr>
    </table>
    """
    event = parse_release(html, _STUB)

    assert event is not None
    assert event.isins == ["RU000A103QL1"]


def test_parse_release_detects_action_from_header() -> None:
    event = parse_release(_HTML, _STUB)

    assert event is not None
    assert event.rating_action == "Повышен"


def test_parse_release_detects_action_from_title() -> None:
    stub = _STUB.model_copy(update={"title": "НРА отозвало кредитный рейтинг"})
    event = parse_release("<html><body></body></html>", stub)

    assert event is not None
    assert event.rating_action == "Отозван"


def test_parse_release_falls_back_to_full_name() -> None:
    html = """
    <table>
      <tr><td>Полное наименование объекта рейтинга</td><td>ООО «Полное Имя»</td></tr>
      <tr><td>Идентификационный номер налогоплательщика (ИНН)</td><td>123</td></tr>
    </table>
    """
    event = parse_release(html, _STUB)

    assert event is not None
    assert event.entity_name == "ООО «Полное Имя»"


def test_parse_release_handles_missing_fields() -> None:
    event = parse_release("<html><body>пусто</body></html>", _STUB)

    assert event is not None
    assert event.inn is None
    assert event.isins == []
    assert event.rating_value is None
    assert event.outlook is None


def test_parse_release_cleans_na_values() -> None:
    html = """
    <table>
      <tr><td>Идентификационный номер налогоплательщика (ИНН)</td><td>не применимо</td></tr>
      <tr><td>ISIN</td><td>—</td></tr>
    </table>
    """
    event = parse_release(html, _STUB)

    assert event is not None
    assert event.inn is None
    assert event.isins == []
