"""Тесты парсинга страницы релиза рейтинга НРА."""

from __future__ import annotations

from datetime import date, datetime

from features.ratings.events import ReleaseStub
from features.ratings.rating_nra.parser import parse_release

_STUB = ReleaseStub(
    uid="44197",
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
    <tr><td>Сокращенное наименование объекта рейтинга</td><td>Новый Век</td></tr>
    <tr><td>Вид объекта рейтинга</td><td>Банк</td></tr>
    <tr><td>Идентификационный номер налогоплательщика (ИНН)</td><td>7744002652</td></tr>
    <tr><td>ISIN</td><td>RU000A105RV3, RU000A107DM8</td></tr>
    <tr><td>Дата публикации</td><td>03.06.2026</td></tr>
  </table>
</body></html>
"""


def test_parse_release_core_fields() -> None:
    event = parse_release(_HTML, _STUB)

    assert event is not None
    assert event.uid == "44197"
    assert event.inn == "7744002652"
    assert event.isins == ["RU000A105RV3", "RU000A107DM8"]
    assert event.entity_name == "Новый Век"
    assert event.rating_action == "Повышен"
    assert event.rating_value == "BBB|ru|"
    assert event.outlook == "Стабильный"
    assert event.publication_date == date(2026, 6, 3)


def test_parse_release_handles_empty() -> None:
    event = parse_release("<html><body>пусто</body></html>", _STUB)
    assert event is not None
    assert event.inn is None
    assert event.isins == []
