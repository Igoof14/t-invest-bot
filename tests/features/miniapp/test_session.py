"""Тесты сессии мини-аппа."""

import time

import pytest
from features.miniapp.auth import MiniAppUser
from features.miniapp.session import SessionError, issue_session, verify_session

BOT_TOKEN = "123456:TEST-TOKEN"

USER = MiniAppUser(telegram_id=42, first_name="Иван", last_name="Петров", username="ivan")


def test_issued_session_verifies() -> None:
    """Выпущенный токен читается обратно вместе с профилем."""
    token, expires_at = issue_session(USER, BOT_TOKEN)

    user = verify_session(token, BOT_TOKEN)
    assert user == USER
    assert expires_at > time.time()


def test_tampered_payload_rejected() -> None:
    """Подменённый telegram_id ломает подпись — чужие настройки недоступны."""
    token, _ = issue_session(USER, BOT_TOKEN)
    payload, _, signature = token.partition(".")
    forged = f"{payload[:-1]}{'A' if payload[-1] != 'A' else 'B'}.{signature}"

    with pytest.raises(SessionError):
        verify_session(forged, BOT_TOKEN)


def test_other_bot_token_rejected() -> None:
    """Ключ подписи выведен из токена бота: чужой токен не читает сессию."""
    token, _ = issue_session(USER, BOT_TOKEN)

    with pytest.raises(SessionError):
        verify_session(token, "999:OTHER")


def test_expired_session_rejected() -> None:
    """Просроченная сессия отклоняется, хотя подпись сходится."""
    token, _ = issue_session(USER, BOT_TOKEN, ttl=-1)

    with pytest.raises(SessionError):
        verify_session(token, BOT_TOKEN)


def test_session_outlives_init_data_window() -> None:
    """Ради этого всё и затевалось: сессия живёт дольше суток.

    Telegram обновляет initData только при запуске страницы, а мини-апп при
    закрытии не выгружается — сутки жизни подписи не должны становиться
    сутками жизни доступа.
    """
    token, expires_at = issue_session(USER, BOT_TOKEN)

    assert expires_at - time.time() > 24 * 60 * 60
    assert verify_session(token, BOT_TOKEN).telegram_id == 42


@pytest.mark.parametrize(
    "token",
    ["", "без-точки", ".", "не-base64.не-base64", "eyJ0aWQiOjQyfQ.AAAA"],
    ids=["пусто", "без подписи", "пустые части", "мусор", "верная форма, чужая подпись"],
)
def test_malformed_token_rejected(token: str) -> None:
    """Любой непонятный токен — отказ, а не исключение наружу."""
    with pytest.raises(SessionError):
        verify_session(token, BOT_TOKEN)
