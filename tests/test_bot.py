"""Тесты startup-хука webhook-сервиса."""

from unittest.mock import AsyncMock, MagicMock

import bot as bot_module
import pytest


def _patch_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Заглушает I/O-побочки ``on_startup`` (БД и команды бота)."""
    monkeypatch.setattr(bot_module.db_manager, "create_tables", AsyncMock())
    monkeypatch.setattr(bot_module.BotUtils, "set_commands", AsyncMock())
    monkeypatch.setattr(bot_module.BotUtils, "set_descriptions", AsyncMock())


async def test_on_startup_sets_webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    """``on_startup`` регистрирует webhook с полным URL и secret token."""
    _patch_side_effects(monkeypatch)
    monkeypatch.setattr(bot_module.config, "webhook_base_url", "https://svc.run.app")
    monkeypatch.setattr(bot_module.config, "webhook_path", "/webhook")
    monkeypatch.setattr(
        bot_module.config,
        "webhook_secret",
        MagicMock(get_secret_value=lambda: "sec"),
    )
    fake_bot = MagicMock()
    fake_bot.set_webhook = AsyncMock()

    await bot_module.on_startup(fake_bot)

    fake_bot.set_webhook.assert_awaited_once()
    kwargs = fake_bot.set_webhook.await_args.kwargs
    assert kwargs["url"] == "https://svc.run.app/webhook"
    assert kwargs["secret_token"] == "sec"
    assert kwargs["drop_pending_updates"] is True


async def test_on_startup_raises_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без публичного URL webhook'а startup падает с RuntimeError."""
    _patch_side_effects(monkeypatch)
    monkeypatch.setattr(bot_module.config, "webhook_base_url", None)
    fake_bot = MagicMock()
    fake_bot.set_webhook = AsyncMock()

    with pytest.raises(RuntimeError):
        await bot_module.on_startup(fake_bot)

    fake_bot.set_webhook.assert_not_awaited()
