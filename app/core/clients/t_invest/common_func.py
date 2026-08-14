"""Дополнительные функции для работы с T-Invest API."""


def to_float(value) -> float:
    """Конвертирует в float."""
    return value.units + value.nano / 1e9
