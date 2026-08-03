"""Сессия мини-аппа: подписанный токен вместо initData на каждом запросе.

Зачем это нужно. ``initData`` — разовое доказательство личности при входе, и
проверка возраста (:data:`.auth.MAX_AGE_SECONDS`) для него уместна: перехваченная
строка иначе давала бы доступ бессрочно. Но Telegram выдаёт её только при
запуске страницы, а мини-апп при закрытии не выгружается — клиент возобновляет
тот же webview со старой строкой. Через сутки все запросы начинали получать 401,
и вылечить это можно было только полной выгрузкой Telegram.

Поэтому подпись обменивается на сессию один раз, а дальше живёт она: срок жизни
сессии больше не привязан к тому, когда Telegram последний раз перезапускал
страницу.

Формат — ``<payload>.<подпись>``, payload в base64url от JSON. Полноценный JWT
не нужен: читает токен только этот же сервис, а лишняя зависимость ради заголовка
с алгоритмом себя не окупает.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .auth import MiniAppUser

# Срок жизни сессии. Отсчитывается от выпуска и продлевается на каждом обмене
# (см. ручку ``POST /miniapp/api/session``).
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60

# Отделяет ключ подписи сессий от самого токена бота: даже зная один HMAC,
# нельзя подписать данные для другого назначения.
_KEY_CONTEXT = b"miniapp-session"


class SessionError(Exception):
    """Токен сессии повреждён, подписан не нами или просрочен."""


def _key(bot_token: str) -> bytes:
    """Ключ подписи сессий.

    Выводится из токена бота, а не из отдельной переменной окружения: одним
    секретом меньше в конфигурации Cloud Run. Побочный эффект намеренный —
    ротация токена бота разом гасит все выданные сессии.
    """
    return hmac.new(_KEY_CONTEXT, bot_token.encode(), hashlib.sha256).digest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    # Паддинг обрезан при кодировании: base64 требует длину, кратную четырём.
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_session(
    user: MiniAppUser, bot_token: str, *, ttl: int = SESSION_TTL_SECONDS
) -> tuple[str, int]:
    """Выпускает токен сессии для подтверждённого пользователя.

    Имя и username кладём внутрь токена, а не перезапрашиваем: они уже пришли
    подписанными в ``initData``, а ``GET /miniapp/api/me`` передаёт их в
    регистрацию — без них она затёрла бы данные пустыми значениями.

    Args:
        user: Пользователь, чью личность уже подтвердила подпись Telegram.
        bot_token: Токен бота, из которого выводится ключ подписи.
        ttl: Срок жизни токена в секундах.

    Returns:
        Пара «токен, момент истечения (unix-время)».

    """
    expires_at = int(time.time()) + ttl
    payload = {
        "tid": user.telegram_id,
        "fn": user.first_name,
        "ln": user.last_name,
        "un": user.username,
        "exp": expires_at,
    }
    encoded = _b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    signature = hmac.new(_key(bot_token), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{_b64encode(signature)}", expires_at


def verify_session(token: str, bot_token: str) -> MiniAppUser:
    """Проверяет токен сессии и возвращает пользователя из него.

    Args:
        token: Значение из заголовка ``Authorization: Bearer <token>``.
        bot_token: Токен бота, из которого выводится ключ подписи.

    Returns:
        Пользователь, которому можно доверять.

    Raises:
        SessionError: Токен пуст, повреждён, подписан не нами или просрочен.

    """
    if not token:
        raise SessionError("пустой токен сессии")

    encoded, separator, signature = token.partition(".")
    if not separator:
        raise SessionError("токен сессии без подписи")

    expected = hmac.new(_key(bot_token), encoded.encode(), hashlib.sha256).digest()
    try:
        provided = _b64decode(signature)
    except (ValueError, TypeError) as exc:
        raise SessionError("подпись сессии не разобрана") from exc
    # compare_digest, а не ==: сравнение по первому различию выдаёт подпись по
    # времени ответа.
    if not hmac.compare_digest(expected, provided):
        raise SessionError("подпись сессии не совпала")

    payload = _decode_payload(encoded)

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        raise SessionError("в сессии нет срока действия")
    if time.time() > expires_at:
        raise SessionError("сессия просрочена")

    telegram_id = payload.get("tid")
    if not isinstance(telegram_id, int):
        raise SessionError("в сессии нет пользователя")

    return MiniAppUser(
        telegram_id=telegram_id,
        first_name=_optional_str(payload.get("fn")),
        last_name=_optional_str(payload.get("ln")),
        username=_optional_str(payload.get("un")),
    )


def _optional_str(value: object) -> str | None:
    """Необязательное строковое поле токена.

    Имя и username — украшение профиля, а не право доступа: если в токене
    оказалось что-то другое, честнее показать пустоту, чем отказать во входе.
    """
    return value if isinstance(value, str) else None


def _decode_payload(encoded: str) -> dict[str, object]:
    """Разбирает payload токена.

    Подпись к этому моменту уже сошлась, поэтому испорченный payload означает не
    подделку, а сбой — но наружу это всё равно один и тот же отказ.

    Raises:
        SessionError: Payload не разбирается.

    """
    try:
        payload: object = json.loads(_b64decode(encoded))
    except (ValueError, TypeError) as exc:
        raise SessionError("тело сессии не разобрано") from exc

    if not isinstance(payload, dict):
        raise SessionError("тело сессии не объект")
    fields: dict[str, object] = payload
    return fields
