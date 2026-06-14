"""Тесты парсинга и нормализации пула прокси."""

from __future__ import annotations

import pytest
from features.fns_monitoring import proxy_pool
from features.fns_monitoring.proxy_pool import load_proxies, normalize_proxy


def test_normalize_ip_port_user_pass() -> None:
    assert (
        normalize_proxy("85.142.81.192:63356:zqWPwa8t:KhRH5Sq1")
        == "http://zqWPwa8t:KhRH5Sq1@85.142.81.192:63356"
    )


def test_normalize_host_port() -> None:
    assert normalize_proxy("1.2.3.4:8080") == "http://1.2.3.4:8080"


def test_normalize_passthrough_url() -> None:
    url = "http://user:pass@1.2.3.4:8080"
    assert normalize_proxy(url) == url
    assert normalize_proxy("socks5://1.2.3.4:1080") == "socks5://1.2.3.4:1080"


def test_normalize_strips_whitespace() -> None:
    assert normalize_proxy("  1.2.3.4:8080  ") == "http://1.2.3.4:8080"


def test_normalize_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        normalize_proxy("not-a-proxy")
    with pytest.raises(ValueError):
        normalize_proxy("")


def test_load_proxies_empty_returns_direct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proxy_pool.config, "fns_proxies", None)
    monkeypatch.setattr(proxy_pool.config, "fns_proxy", None)
    assert load_proxies() == [None]


def test_load_proxies_falls_back_to_singular(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(proxy_pool.config, "fns_proxies", None)
    monkeypatch.setattr(proxy_pool.config, "fns_proxy", "1.2.3.4:8080")
    assert load_proxies() == ["http://1.2.3.4:8080"]


def test_load_proxies_parses_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        proxy_pool.config,
        "fns_proxies",
        "1.2.3.4:8080:u:p, 5.6.7.8:9090",
    )
    monkeypatch.setattr(proxy_pool.config, "fns_proxy", None)
    assert load_proxies() == [
        "http://u:p@1.2.3.4:8080",
        "http://5.6.7.8:9090",
    ]


def test_load_proxies_skips_bad_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        proxy_pool.config, "fns_proxies", "garbage, 5.6.7.8:9090"
    )
    monkeypatch.setattr(proxy_pool.config, "fns_proxy", None)
    assert load_proxies() == ["http://5.6.7.8:9090"]
