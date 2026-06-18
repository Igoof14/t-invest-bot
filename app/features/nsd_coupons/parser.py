"""Парсинг HTML ленты НРД: список новостей и карточка выплаты.

Список (поиск по ISIN) и карточка отдаются как HTML; здесь они разбираются в
доменные модели ``NsdNewsItem`` и ``NsdCardDetails`` с помощью BeautifulSoup.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup, Tag

from .schemas import NsdCardDetails, NsdNewsItem

logger = logging.getLogger(__name__)

# ISIN: 2 буквы кода страны + 10 буквенно-цифровых символов.
_ISIN_RE = re.compile(r"\b([A-Z]{2}[0-9A-Z]{10})\b")
# ИНН: 10 (юрлицо) или 12 (физлицо/ИП) цифр.
_INN_RE = re.compile(r"\b(\d{10}|\d{12})\b")
# Код типа КД в начале заголовка: "(INTR) ...".
_TYPE_RE = re.compile(r"^\(([A-Z]{3,5})\)")
# Ссылка на карточку: "/ru/news/view/12345".
_VIEW_ID_RE = re.compile(r"/ru/news/view/(\d+)")
# Дата публикации в списке: "16.06.2026".
_SHORT_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")

_RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}
_LONG_DATE_RE = re.compile(r"(\d{1,2})\s+([а-яё]+)\s+(\d{4})", re.IGNORECASE)


def _parse_short_date(text: str) -> date | None:
    """Парсит дату формата ``дд.мм.гггг`` из строки."""
    m = _SHORT_DATE_RE.search(text)
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    return date(year, month, day)


def _parse_long_date(text: str) -> date | None:
    """Парсит русскую дату формата ``19 июня 2026 г.`` из строки."""
    m = _LONG_DATE_RE.search(text)
    if not m:
        return None
    day, month_word, year = m.groups()
    month = _RU_MONTHS.get(month_word.lower())
    if month is None:
        return None
    return date(int(year), month, int(day))


def _parse_amount(text: str) -> float | None:
    """Парсит денежную сумму (``0.53``, ``1 647 440,01``) в число."""
    cleaned = text.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_from_title(title: str) -> tuple[str | None, str | None, str | None]:
    """Извлекает (issuer_name, inn, isin) из заголовка новости НРД.

    Реквизиты эмитента идут в скобках: ``(Эмитент, ИНН, ISIN, рег.номер)``.
    """
    isin_match = _ISIN_RE.search(title)
    isin = isin_match.group(1) if isin_match else None
    inn_match = _INN_RE.search(title)
    inn = inn_match.group(1) if inn_match else None

    issuer_name: str | None = None
    # Берём скобочную группу, содержащую ISIN, и первый её элемент — это эмитент.
    if isin:
        for group in re.findall(r"\(([^()]*)\)", title):
            if isin in group:
                issuer_name = group.split(",")[0].strip() or None
                break
    return issuer_name, inn, isin


def parse_listing(html: str) -> list[NsdNewsItem]:
    """Разбирает HTML списка новостей НРД в список ``NsdNewsItem``.

    Args:
        html: HTML страницы поиска новостей (``/ru/news?text=<ISIN>``).

    Returns:
        Список новостей; пустой, если новостей нет.

    """
    soup = BeautifulSoup(html, "html.parser")
    items: list[NsdNewsItem] = []
    for row in soup.select("div.news_list__item"):
        link = row.select_one("a.news_list__item__header__title")
        if link is None:
            continue
        href = link.get("href", "")
        id_match = _VIEW_ID_RE.search(href if isinstance(href, str) else "")
        if id_match is None:
            continue
        title = link.get_text(" ", strip=True)
        type_match = _TYPE_RE.search(title)
        date_node = row.select_one("div.news_list__item__date")
        published_at = (
            _parse_short_date(date_node.get_text(strip=True)) if date_node else None
        )
        issuer_name, inn, isin = _extract_from_title(title)
        items.append(
            NsdNewsItem(
                news_id=int(id_match.group(1)),
                news_type=type_match.group(1) if type_match else "",
                title=title,
                isin=isin,
                issuer_name=issuer_name,
                inn=inn,
                published_at=published_at,
            )
        )
    return items


def _find_label_cell(soup: BeautifulSoup, label: str) -> Tag | None:
    """Находит ячейку таблицы (``td``/``th``), содержащую указанную метку."""
    node = soup.find(string=re.compile(re.escape(label)))
    if node is None:
        return None
    parent = node.find_parent(["td", "th"])
    return parent if isinstance(parent, Tag) else None


def _value_beside(soup: BeautifulSoup, label: str) -> str | None:
    """Возвращает значение из соседней ячейки той же строки (раскладка «метка|значение»)."""
    cell = _find_label_cell(soup, label)
    if cell is None:
        return None
    sibling = cell.find_next_sibling(["td", "th"])
    return sibling.get_text(strip=True) if isinstance(sibling, Tag) else None


def _value_below(soup: BeautifulSoup, label: str) -> str | None:
    """Возвращает значение из строки-значений под строкой-заголовком.

    Метка стоит в строке заголовков; значение — в той же колонке ближайшей
    последующей непустой строки той же таблицы. Возвращает текст ячейки (может
    быть пустым → ``None``).
    """
    cell = _find_label_cell(soup, label)
    if cell is None:
        return None
    header_row = cell.find_parent("tr")
    table = cell.find_parent("table")
    if not isinstance(header_row, Tag) or not isinstance(table, Tag):
        return None
    header_cells = header_row.find_all(["td", "th"], recursive=False)
    try:
        col = header_cells.index(cell)
    except ValueError:
        return None

    rows = table.find_all("tr")
    start = rows.index(header_row) if header_row in rows else 0
    for row in rows[start + 1 :]:
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) > col:
            text = cells[col].get_text(strip=True)
            return text or None
    return None


def parse_card(html: str) -> NsdCardDetails:
    """Разбирает HTML карточки новости НРД в ``NsdCardDetails``.

    Args:
        html: HTML карточки (``/ru/news/view/<id>``).

    Returns:
        Детали выплаты: тип КД, плановая дата, дата поступления в НРД, сумма.

    """
    soup = BeautifulSoup(html, "html.parser")
    type_value = _value_beside(soup, "Код типа корпоративного действия")
    # Плановую дату берём из устойчивой пары «Дата КД (план.)» (есть во всех
    # раскладках); запасной вариант — колоночная «Дата выплаты плановая».
    planned = _value_beside(soup, "Дата КД (план.)") or _value_below(
        soup, "Дата выплаты плановая"
    )
    received = _value_below(soup, "Дата поступления в НРД денежных средств")
    # Сумму ищем под разными метками у разных эмитентов.
    amount = (
        _value_below(soup, "Размер денежных средств, подлежащих выплате на 1 ц.б.")
        or _value_beside(soup, "Размер купонного дохода")
    )
    return NsdCardDetails(
        news_type=type_value,
        planned_pay_date=_parse_long_date(planned) if planned else None,
        nsd_received_date=_parse_long_date(received) if received else None,
        amount_per_bond=_parse_amount(amount) if amount else None,
    )
