"""Брокеры, чьи токены умеет хранить бэкенд.

Единая точка правды для бота, HTTP API мини-аппа и клиента бэкенда — значения
совпадают с `Broker` в `bondelo-backend` (`app/users/models.py`) и с типом
`Broker` во фронтенде мини-аппа (`shared/api/types.ts`).
"""

from enum import StrEnum


class Broker(StrEnum):
    """Код брокера, как его хранит бэкенд."""

    TINVEST = "tinvest"
    FINAM = "finam"
    BCS = "bcs"
