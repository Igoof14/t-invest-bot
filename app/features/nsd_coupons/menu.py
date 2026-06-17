"""Секция меню «Купоны не пришли» для хаба «Уведомления»."""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from features.menu import MenuSection, back_to_hub_button, help_button, status_text

from .keyboards import create_coupon_alerts_keyboard
from .repository import NsdCouponAlertSettingsRepository

SECTION_KEY = "nsd_coupons"

SECTION_DESCRIPTION = (
    "<b>📉 Контроль выплаты купонов</b>\n\n"
    "Бот сверяет купонный календарь ваших облигаций с публикациями НРД и "
    "сообщит, если по бумаге в портфеле купон не поступил в НРД к плановой дате "
    "(задержка или технический дефолт эмитента)."
)

SECTION_HELP = (
    "Как это работает:\n"
    "• из календаря T-Invest бот знает плановые даты купонов ваших облигаций;\n"
    "• в день выплаты сверяет ленту НРД (nsddata.ru) по ISIN бумаги;\n"
    "• если публикации о выплате нет — присылает уведомление о неполученном "
    "купоне.\n\n"
    "Досрочная выплата засчитывается. Охват — рублёвые облигации (RU*), "
    "по которым НРД выступает депозитарием."
)


async def render(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Экран секции: тумблер подписки + «Как это работает» + «Назад»."""
    enabled = await NsdCouponAlertSettingsRepository.is_enabled(telegram_id)
    builder = create_coupon_alerts_keyboard(enabled)
    builder.row(help_button(SECTION_KEY))
    builder.row(back_to_hub_button())
    return SECTION_DESCRIPTION, builder.as_markup()


async def status_badge(telegram_id: int) -> str:
    """Бейдж для хаба: включено, если пользователь подписан."""
    enabled = await NsdCouponAlertSettingsRepository.is_enabled(telegram_id)
    return status_text(enabled)


SECTION = MenuSection(
    key=SECTION_KEY,
    title="Купоны не пришли",
    render=render,
    status_badge=status_badge,
    help_text=SECTION_HELP,
)
