"""Тесты пула прокси для скрейпинга рейтингов."""

from __future__ import annotations

import pytest
from features.ratings import proxy_pool
from features.ratings.proxy_pool import ProxyRotator, load_proxies, normalize_proxy


def test_normalize_proxy_url_passthrough() -> None:
    assert normalize_proxy("socks5://h:1080") == "socks5://h:1080"


def test_normalize_proxy_host_port() -> None:
    assert normalize_proxy("1.2.3.4:8080") == "http://1.2.3.4:8080"


def test_normalize_proxy_with_credentials() -> None:
    assert normalize_proxy("1.2.3.4:8080:user:pass") == "http://user:pass@1.2.3.4:8080"


def test_normalize_proxy_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_proxy("a:b:c")


def test_load_proxies_empty_returns_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proxy_pool.config, "ratings_proxies", None, raising=False)
    monkeypatch.setattr(proxy_pool.config, "ratings_proxy", None, raising=False)
    assert load_proxies() == [None]


def test_load_proxies_parses_list_and_skips_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        proxy_pool.config,
        "ratings_proxies",
        "1.2.3.4:8080, http://h:3128\nbad:x:y",
        raising=False,
    )
    monkeypatch.setattr(proxy_pool.config, "ratings_proxy", None, raising=False)
    assert load_proxies() == ["http://1.2.3.4:8080", "http://h:3128"]


def test_rotator_round_robin() -> None:
    rotator = ProxyRotator(["a", "b"])
    assert [rotator.next() for _ in range(5)] == ["a", "b", "a", "b", "a"]


def test_rotator_empty_is_direct() -> None:
    rotator = ProxyRotator([])
    assert rotator.proxies == [None]
    assert rotator.next() is None
