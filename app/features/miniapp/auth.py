"""Проверка подлинности запросов мини-аппа.

Мини-апп работает в браузере, а бэкенд принимает ``telegram_id`` прямо в пути и
не проверяет вызывающего. Единственное, что подтверждает личность пользователя, —
строка ``initData``, подписанная Telegram токеном бота: её и проверяем здесь, а
``telegram_id`` берём только из неё, никогда из тела запроса.

Алгоритм — стандартный для Telegram Mini Apps:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

logger = logging.getLogger(__name__)

# Соль секретного ключа, заданная Telegram.
_SECRET_SALT = b"WebAppData"

# Максимальный возраст подписи. Telegram сроком её не ограничивает, поэтому
# перехваченная строка иначе давала бы доступ к аккаунту бессрочно.
MAX_AGE_SECONDS = 24 * 60 * 60


class InitDataError(Exception):
    """`initData` отсутствует, просрочена или подписана неверно."""


@dataclass(frozen=True, slots=True)
class MiniAppUser:
    """Пользователь, подтверждённый подписью Telegram."""

    telegram_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


def _secret_key(bot_token: str) -> bytes:
    """Секретный ключ подписи — HMAC от токена бота с солью Telegram."""
    return hmac.new(_SECRET_SALT, bot_token.encode(), hashlib.sha256).digest()


def _check_signature(pairs: list[tuple[str, str]], received_hash: str, bot_token: str) -> None:
    """Сверяет подпись строки проверки.

    Raises:
        InitDataError: Подпись не совпала.

    """
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs))
    expected = hmac.new(
        _secret_key(bot_token), data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    # compare_digest, а не ==: сравнение за постоянное время не даёт подобрать
    # подпись по времени ответа.
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("подпись initData не совпала")


def _check_age(auth_date: str, max_age: int) -> None:
    """Проверяет свежесть подписи.

    Raises:
        InitDataError: `auth_date` отсутствует, нечитаем или просрочен.

    """
    try:
        issued_at = int(auth_date)
    except (TypeError, ValueError) as exc:
        raise InitDataError("некорректный auth_date") from exc

    age = time.time() - issued_at
    if age > max_age:
        raise InitDataError(f"initData просрочена ({int(age)} с)")


def _parse_user(raw_user: str | None) -> MiniAppUser:
    """Разбирает поле ``user`` initData.

    Raises:
        InitDataError: Поля нет или в нём нет идентификатора.

    """
    if not raw_user:
        raise InitDataError("в initData нет пользователя")
    try:
        payload: dict[str, object] = json.loads(raw_user)
    except ValueError as exc:
        raise InitDataError("не удалось разобрать пользователя initData") from exc

    telegram_id = payload.get("id")
    if not isinstance(telegram_id, int):
        raise InitDataError("в initData нет идентификатора пользователя")

    return MiniAppUser(
        telegram_id=telegram_id,
        first_name=_optional_str(payload.get("first_name")),
        last_name=_optional_str(payload.get("last_name")),
        username=_optional_str(payload.get("username")),
    )


def _optional_str(value: object) -> str | None:
    """Строковое поле профиля или ``None`` для всего остального."""
    return value if isinstance(value, str) else None


def parse_init_data(
    raw: str,
    bot_token: str,
    *,
    max_age: int = MAX_AGE_SECONDS,
) -> MiniAppUser:
    """Проверяет ``initData`` и возвращает пользователя из неё.

    Args:
        raw: Строка ``initData`` как её отдал Telegram, без изменений.
        bot_token: Токен бота — им Telegram подписывает данные.
        max_age: Допустимый возраст подписи в секундах.

    Returns:
        Пользователь, которому можно доверять.

    Raises:
        InitDataError: Строка пуста, просрочена или подписана неверно.

    """
    if not raw:
        raise InitDataError("пустая initData")

    # keep_blank_values: пустые поля участвуют в подписи наравне с остальными,
    # выбросив их, мы посчитали бы другой хэш.
    pairs = parse_qsl(raw, keep_blank_values=True)
    received_hash = next((value for key, value in pairs if key == "hash"), None)
    if not received_hash:
        raise InitDataError("в initData нет hash")

    # `signature` (Ed25519-подпись для сторонней валидации) Telegram добавляет
    # после расчёта `hash`, поэтому в строку проверки она не входит.
    signed = [(key, value) for key, value in pairs if key not in ("hash", "signature")]
    _check_signature(signed, received_hash, bot_token)

    fields = dict(signed)
    _check_age(fields.get("auth_date", ""), max_age)
    return _parse_user(fields.get("user"))
