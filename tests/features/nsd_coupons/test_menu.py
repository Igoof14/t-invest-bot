"""Тесты секции меню «Купоны не пришли»."""

from __future__ import annotations

import pytest
from features.nsd_coupons.menu import SECTION, render, status_badge
from features.nsd_coupons.repository import NsdCouponAlertSettingsRepository

pytestmark = pytest.mark.usefixtures("patch_session_scope")


def test_section_metadata() -> None:
    assert SECTION.key == "nsd_coupons"
    assert SECTION.title
    assert SECTION.help_text


async def test_render_returns_text_and_keyboard() -> None:
    await NsdCouponAlertSettingsRepository.toggle(7)  # включаем

    text, markup = await render(7)

    assert "купон" in text.lower()
    # Тумблер + «как это работает» + «назад».
    assert len(markup.inline_keyboard) == 3
    assert "Включено" in markup.inline_keyboard[0][0].text


async def test_status_badge_reflects_subscription() -> None:
    badge_off = await status_badge(7)
    await NsdCouponAlertSettingsRepository.toggle(7)  # включаем
    badge_on = await status_badge(7)

    assert badge_off != badge_on
