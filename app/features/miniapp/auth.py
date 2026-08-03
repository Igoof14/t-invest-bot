"""Проверка подлинности запросов мини-аппа.

Мини-апп работает в браузере, а бэкенд принимает ``telegram_id`` прямо в пути и
не проверяет вызывающего. Единственное, что подтверждает личность пользователя, —
строка ``initData``, подписанная Telegram токеном бота: её и проверяем здесь, а
``telegram_id`` берём только из неё, никогда из тела запроса.

Саму подпись считает aiogram (:func:`safe_parse_webapp_init_data`) — он уже
зависимость бота и следует за спецификацией Telegram. Своя реализация здесь была
и оказалась неверной: она исключала из строки проверки поле ``signature``, а это
правило другого способа проверки — стороннего, по Ed25519, без токена бота. При
проверке токеном исключается только ``hash``, и современные клиенты, всегда
присылающие ``signature``, получали отказ.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from aiogram.utils.web_app import WebAppInitData, safe_parse_webapp_init_data

logger = logging.getLogger(__name__)

# Максимальный возраст подписи. Telegram сроком её не ограничивает, поэтому
# перехваченная строка иначе давала бы доступ к аккаунту бессрочно.
MAX_AGE_SECONDS = 24 * 60 * 60

# Предел для обмена подписи на сессию — он же вход.
#
# Отдельный и заметно больший, потому что суток на входе не хватает на практике:
# Telegram отдаёт мини-аппу подпись, выданную при первом запуске, и не обновляет
# её ни при повторном открытии, ни после перезагрузки устройства. В логах видно,
# как возраст растёт по часам и не сбрасывается неделями — с пределом в сутки
# пользователь просто не может войти и починить это самостоятельно.
#
# Размен осознанный: подпись остаётся криптографически верной и личность
# подтверждает, а возраст ограничивает только окно, в котором перехваченную
# строку можно предъявить повторно. Здесь это окно — месяц вместо суток.
LOGIN_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


class InitDataError(Exception):
    """`initData` отсутствует, просрочена или подписана неверно."""


@dataclass(frozen=True, slots=True)
class MiniAppUser:
    """Пользователь, подтверждённый подписью Telegram."""

    telegram_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


def _check_age(data: WebAppInitData, max_age: int) -> None:
    """Проверяет свежесть подписи.

    Возраст aiogram не проверяет: для него initData валидна, пока сходится
    подпись, то есть вечно.

    Raises:
        InitDataError: Подпись старше допустимого.

    """
    age = time.time() - data.auth_date.timestamp()
    if age > max_age:
        raise InitDataError(f"initData просрочена ({int(age)} с)")


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

    try:
        data = safe_parse_webapp_init_data(bot_token, raw)
    except ValueError as exc:
        # Сюда же попадает разбор строки: невалидный query string, отсутствие
        # `hash`, несовпадение подписи. Наружу причину не детализируем — для
        # клиента это один и тот же отказ.
        raise InitDataError("подпись initData не совпала") from exc

    _check_age(data, max_age)

    if data.user is None:
        raise InitDataError("в initData нет пользователя")

    return MiniAppUser(
        telegram_id=data.user.id,
        first_name=data.user.first_name,
        last_name=data.user.last_name,
        username=data.user.username,
    )
