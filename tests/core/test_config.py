"""Тесты загрузки настроек webhook в ``Settings``."""

from __future__ import annotations

from core.config import Settings


def _settings(**overrides: object) -> Settings:
    """Создаёт ``Settings`` без чтения .env, с обязательным ``bot_token``."""
    defaults: dict[str, object] = {"bot_token": "test-token"}
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type]


def test_webhook_defaults_when_base_url_missing() -> None:
    settings = _settings()

    assert settings.webhook_path == "/webhook"
    assert settings.webhook_base_url is None
    assert settings.webhook_url is None


def test_webhook_url_joins_base_and_path() -> None:
    settings = _settings(
        webhook_base_url="https://svc.run.app",
        webhook_path="/webhook",
    )

    assert settings.webhook_url == "https://svc.run.app/webhook"


def test_webhook_url_normalizes_slashes() -> None:
    settings = _settings(
        webhook_base_url="https://svc.run.app/",
        webhook_path="hook/secret",
    )

    assert settings.webhook_url == "https://svc.run.app/hook/secret"


def test_webhook_secret_is_secret() -> None:
    settings = _settings(webhook_secret="s3cret")

    assert settings.webhook_secret is not None
    assert settings.webhook_secret.get_secret_value() == "s3cret"
    assert "s3cret" not in repr(settings.webhook_secret)


def test_api_port_defaults_to_8080() -> None:
    assert _settings().api_port == 8080


def test_api_port_reads_cloud_run_port_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("PORT", "9000")

    assert _settings().api_port == 9000
