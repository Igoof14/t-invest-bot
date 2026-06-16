"""Тесты вспомогательной логики клиента НРД (без сети/браузера)."""

from __future__ import annotations

from features.nsd_coupons.client import to_playwright_proxy


def test_proxy_none_returns_none() -> None:
    assert to_playwright_proxy(None) is None
    assert to_playwright_proxy("") is None


def test_proxy_with_credentials() -> None:
    assert to_playwright_proxy("http://user:pass@1.2.3.4:8080") == {
        "server": "http://1.2.3.4:8080",
        "username": "user",
        "password": "pass",
    }


def test_proxy_without_credentials() -> None:
    assert to_playwright_proxy("http://1.2.3.4:8080") == {"server": "http://1.2.3.4:8080"}


def test_proxy_preserves_scheme() -> None:
    assert to_playwright_proxy("socks5://1.2.3.4:1080") == {
        "server": "socks5://1.2.3.4:1080"
    }
