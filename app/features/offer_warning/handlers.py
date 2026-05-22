import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from .enums import OfferCallbackData
from .repository import OfferSettingsRepository
from .schemas import OfferWarningCallbackData

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == OfferCallbackData.OFFER_TOGGLE.value)
async def handle_toggle_alerts(callback: CallbackQuery) -> None:
    """Обработчик включения/выключения мониторинга цен."""
    try:
        telegram_id = callback.from_user.id
        new_state = await OfferSettingsRepository.toggle_alerts(telegram_id)
        settings = await OfferSettingsRepository.get_or_create(telegram_id)

        status_text = "включен" if new_state else "выключен"
        message_text = (
            f"<b>Мониторинг цен облигаций</b>\n\n"
            f"Получайте уведомления при значительных изменениях цен "
            f"облигаций в вашем портфеле.\n\n"
            f"Статус: <b>{status_text}</b>"
        )
        if new_state:
            message_text += f"\n\n<b>Текущие пороги:</b>\n\nПадение:\n"

        # builder = KeyboardHelper.create_price_alerts_keyboard(new_state)

        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(
                message_text,
                # reply_markup=builder.as_markup(),
                parse_mode="HTML",
            )

        await callback.answer("Уведомления " + ("включены" if new_state else "выключены"))

    except Exception as e:
        logger.error(f"Ошибка при переключении уведомлений: {e}")
        await callback.answer("Произошла ошибка")
