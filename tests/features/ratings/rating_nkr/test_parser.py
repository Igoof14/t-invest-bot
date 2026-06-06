"""Тесты парсинга листинга и страниц релизов НКР."""

from __future__ import annotations

from datetime import date

from features.ratings.rating_nkr.parser import parse_listing, parse_release

_LISTING = """
<table><tbody>
  <tr>
    <td><a href="/ratings/press-releases/Acron-RA-220126/" class="blue-link">
      НКР подтвердило кредитный рейтинг ПАО «Акрон» на уровне AA.ru, прогноз — стабильный
    </a></td>
    <td><span class="mt-descr">Нефинансовые</span></td>
  </tr>
  <tr>
    <td><a href="/ratings/press-releases/VZVT-RA-050626/" class="blue-link">
      НКР снизило кредитный рейтинг ВЗВТ с B+.ru до CC.ru, прогноз — негативный
    </a></td>
  </tr>
  <tr><td><a href="/ratings/press-releases/" class="blue-link">Все пресс-релизы</a></td></tr>
</tbody></table>
"""

_DETAIL = """
<html><body>
  <h1>НКР подтвердило кредитный рейтинг ПАО «Акрон» на уровне AA.ru, прогноз — стабильный</h1>
  <p class="npr-l-p">Идентификационный номер налогоплательщика (ИНН) рейтингуемого лица 5321029508</p>
  <p class="npr-l-p">Выпуск облигаций ISIN RU000A105RV3</p>
  <div class="similar"><a href="/ratings/press-releases/Other-RA-1/" class="blue-link">
    Другой выпуск (RU000AOTHER1)</a></div>
</body></html>
"""


def test_parse_listing_extracts_release_rows() -> None:
    stubs = parse_listing(_LISTING)

    assert [s.uid for s in stubs] == ["Acron-RA-220126", "VZVT-RA-050626"]
    assert stubs[0].url == "https://ratings.ru/ratings/press-releases/Acron-RA-220126/"
    assert "Акрон" in stubs[0].title


def test_parse_release_extracts_fields() -> None:
    stub = parse_listing(_LISTING)[0]
    event = parse_release(_DETAIL, stub)

    assert event is not None
    assert event.inn == "5321029508"
    assert event.isins == ["RU000A105RV3"]
    assert event.rating_action == "Подтверждён"
    assert event.rating_value == "AA.ru"
    assert event.outlook == "Стабильный"
    assert event.entity_name == "Акрон"
    assert event.publication_date == date(2026, 1, 22)  # из slug -220126


_WITHDRAWN_DETAIL = """
<html><body>
  <span class="npr-r-hdr">Структура рейтинга:</span>
  <ul class="npr-r-ul">
    <li><span class="npr-r-u-l">Рейтинг</span><span class="npr-r-u-r">рейтинг отозван</span></li>
    <li><span class="npr-r-u-l">Прогноз</span><span class="npr-r-u-r">прогноз отозван</span></li>
  </ul>
  <p class="npr-l-p">Идентификационный номер налогоплательщика (ИНН) рейтингуемого лица 7700000123</p>
</body></html>
"""

_WITHDRAWN_LISTING = """
<table><tbody><tr><td>
  <a href="/ratings/press-releases/Omega-RA-020626/" class="blue-link">
    НКР отозвало кредитный рейтинг ООО «Омега» и прогноз по нему без подтверждения
  </a></td></tr></tbody></table>
"""


def test_parse_release_withdrawn_from_structure_block() -> None:
    stub = parse_listing(_WITHDRAWN_LISTING)[0]
    event = parse_release(_WITHDRAWN_DETAIL, stub)

    assert event is not None
    assert event.rating_action == "Отозван"
    assert event.rating_value is None  # «рейтинг отозван» → нет значения
    assert event.outlook is None  # «прогноз отозван» → нет прогноза
    assert event.inn == "7700000123"
    assert event.entity_name == "Омега"


def test_parse_release_value_outlook_from_structure_block() -> None:
    listing = """
    <table><tbody><tr><td><a href="/ratings/press-releases/Acron-RA-220126/" class="blue-link">
      НКР подтвердило рейтинг</a></td></tr></tbody></table>
    """
    detail = """
    <html><body><ul class="npr-r-ul">
      <li><span class="npr-r-u-l">ОСК</span><span class="npr-r-u-r">aa.ru</span></li>
      <li><span class="npr-r-u-l">Рейтинг</span><span class="npr-r-u-r">AA.ru</span></li>
      <li><span class="npr-r-u-l">Прогноз</span><span class="npr-r-u-r">стабильный</span></li>
    </ul></body></html>
    """
    event = parse_release(detail, parse_listing(listing)[0])

    assert event is not None
    assert event.rating_value == "AA.ru"  # из строки «Рейтинг», не «ОСК»
    assert event.outlook == "Стабильный"


def test_parse_release_downgrade_takes_new_value() -> None:
    stub = parse_listing(_LISTING)[1]  # ВЗВТ: «с B+.ru до CC.ru»
    event = parse_release("<html><body>нет инн</body></html>", stub)

    assert event is not None
    assert event.rating_action == "Понижен"
    assert event.rating_value == "CC.ru"  # новое значение (последнее)
    assert event.outlook == "Негативный"
