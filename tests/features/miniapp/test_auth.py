"""Тесты проверки подписи initData."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from features.miniapp.auth import InitDataError, parse_init_data

BOT_TOKEN = "123456:TEST-TOKEN"


def make_init_data(
    *,
    token: str = BOT_TOKEN,
    auth_date: int | None = None,
    user: dict | None = None,
    extra: dict | None = None,
    corrupt_hash: bool = False,
) -> str:
    """Собирает подписанную initData, как это делает Telegram."""
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAH-test",
        "user": json.dumps(
            user if user is not None else {"id": 42, "first_name": "Иван", "username": "ivan"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    fields.update(extra or {})

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if corrupt_hash:
        signature = "0" * len(signature)

    return urlencode({**fields, "hash": signature})


def test_valid_init_data_returns_user() -> None:
    """Корректная подпись — пользователь из поля user."""
    user = parse_init_data(make_init_data(), BOT_TOKEN)
    assert user.telegram_id == 42
    assert user.first_name == "Иван"
    assert user.username == "ivan"


def test_signature_field_participates_in_check() -> None:
    """Поле signature входит в строку проверки наравне с остальными.

    Его исключают только при сторонней проверке по Ed25519, без токена бота.
    Клиенты Telegram присылают signature всегда, так что выбросив его, мы
    отклоняли бы вообще все настоящие запросы.
    """
    raw = make_init_data(extra={"signature": "Ed25519-подпись"})
    assert parse_init_data(raw, BOT_TOKEN).telegram_id == 42


def test_field_appended_after_signing_rejected() -> None:
    """Дописанное к готовой строке поле ломает проверку, а не игнорируется."""
    raw = make_init_data() + "&is_premium=true"
    with pytest.raises(InitDataError):
        parse_init_data(raw, BOT_TOKEN)


def test_forged_hash_rejected() -> None:
    """Подделанный hash не проходит."""
    with pytest.raises(InitDataError):
        parse_init_data(make_init_data(corrupt_hash=True), BOT_TOKEN)


def test_other_bot_token_rejected() -> None:
    """Подпись чужим токеном не проходит."""
    with pytest.raises(InitDataError):
        parse_init_data(make_init_data(token="999:OTHER"), BOT_TOKEN)


def test_tampered_user_rejected() -> None:
    """Подменённый telegram_id ломает подпись — чужие настройки недоступны."""
    raw = make_init_data().replace("42", "43")
    with pytest.raises(InitDataError):
        parse_init_data(raw, BOT_TOKEN)


def test_expired_init_data_rejected() -> None:
    """Просроченная подпись отклоняется: перехваченная строка не вечна."""
    stale = int(time.time()) - 48 * 60 * 60
    with pytest.raises(InitDataError):
        parse_init_data(make_init_data(auth_date=stale), BOT_TOKEN)


def test_empty_init_data_rejected() -> None:
    """Пустая строка — не пользователь."""
    with pytest.raises(InitDataError):
        parse_init_data("", BOT_TOKEN)


def test_missing_hash_rejected() -> None:
    """Без hash проверять нечего."""
    with pytest.raises(InitDataError):
        parse_init_data("auth_date=1&user=%7B%22id%22%3A1%7D", BOT_TOKEN)


def test_user_without_id_rejected() -> None:
    """Подпись верна, но пользователя в ней нет."""
    with pytest.raises(InitDataError):
        parse_init_data(make_init_data(user={"first_name": "Без id"}), BOT_TOKEN)
