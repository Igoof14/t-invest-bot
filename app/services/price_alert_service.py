"""Сервис уведомлений об аномальных изменениях цен облигаций."""

import logging

from aiogram import Bot
from invest.price_monitor import (
    PriceAnomaly,
    detect_anomalies,
    get_portfolio_bond_prices,
    should_send_alert,
)
from storage import AlertStorage

logger = logging.getLogger(__name__)

# Максимум аномалий в одном сообщении перед агрегацией
MAX_ANOMALIES_BEFORE_AGGREGATE = 3


class PriceAlertService:
    """Сервис для мониторинга цен и отправки уведомлений."""

    @staticmethod
    async def check_price_anomalies(bot: Bot) -> None:
        """Основная задача scheduler - проверка цен для всех пользователей.

        Args:
            bot: Экземпляр бота для отправки сообщений

        """
        logger.info("Запуск проверки аномалий цен облигаций")

        # Получаем всех пользователей с включенными уведомлениями
        users = await AlertStorage.get_all_users_with_alerts_enabled()

        if not users:
            logger.info("Нет пользователей с включенными уведомлениями")
            return

        logger.info(f"Проверка цен для {len(users)} пользователей")

        for telegram_id in users:
            try:
                await PriceAlertService._check_user_portfolio(bot, telegram_id)
            except Exception as e:
                logger.error(f"Ошибка при проверке портфеля пользователя {telegram_id}: {e}")

        # Периодическая очистка старых данных
        await AlertStorage.cleanup_old_prices(days_to_keep=7)
        await AlertStorage.cleanup_old_alerts(days_to_keep=7)

        logger.info("Проверка аномалий цен завершена")

    @staticmethod
    async def _check_user_portfolio(bot: Bot, telegram_id: int) -> None:
        """Проверяет портфель одного пользователя на аномалии.

        Args:
            bot: Экземпляр бота
            telegram_id: ID пользователя в Telegram

        """
        # Получаем настройки пользователя
        settings = await AlertStorage.get_user_settings(telegram_id)
        if not settings or not settings.alerts_enabled:
            return

        # Получаем текущие цены
        current_prices = await get_portfolio_bond_prices(telegram_id)
        if not current_prices:
            logger.debug(f"Нет облигаций в портфеле пользователя {telegram_id}")
            return

        # Получаем предыдущие цены
        previous_prices = await AlertStorage.get_latest_prices(telegram_id)

        # Если есть предыдущие цены - ищем аномалии
        if previous_prices:
            anomalies = detect_anomalies(current_prices, previous_prices, settings)

            if anomalies:
                await PriceAlertService._send_alerts(bot, telegram_id, anomalies)

        # Сохраняем текущие цены
        price_data = [
            {
                "figi": p.figi,
                "ticker": p.ticker,
                "name": p.name,
                "price_percent": p.price_percent,
                "account_name": p.account_name,
            }
            for p in current_prices
        ]
        await AlertStorage.save_price_snapshot(telegram_id, price_data)

    @staticmethod
    async def _send_alerts(
        bot: Bot, telegram_id: int, anomalies: list[PriceAnomaly]
    ) -> None:
        """Отправляет уведомления об аномалиях.

        Args:
            bot: Экземпляр бота
            telegram_id: ID пользователя
            anomalies: Список аномалий для отправки

        """
        # Фильтруем аномалии по anti-spam правилам
        alerts_to_send: list[PriceAnomaly] = []
        for anomaly in anomalies:
            if await should_send_alert(telegram_id, anomaly):
                alerts_to_send.append(anomaly)

        if not alerts_to_send:
            return

        # Агрегация: если много аномалий - отправляем сводное сообщение
        if len(alerts_to_send) > MAX_ANOMALIES_BEFORE_AGGREGATE:
            await PriceAlertService._send_aggregated_alert(bot, telegram_id, alerts_to_send)
        else:
            for anomaly in alerts_to_send:
                await PriceAlertService._send_single_alert(bot, telegram_id, anomaly)

    @staticmethod
    async def _send_single_alert(
        bot: Bot, telegram_id: int, anomaly: PriceAnomaly
    ) -> None:
        """Отправляет одно уведомление об аномалии.

        Args:
            bot: Экземпляр бота
            telegram_id: ID пользователя
            anomaly: Информация об аномалии

        """
        message = PriceAlertService._format_alert_message(anomaly)

        try:
            await bot.send_message(telegram_id, message, parse_mode="HTML")

            # Записываем отправленный алерт
            await AlertStorage.record_sent_alert(
                telegram_id, anomaly.figi, anomaly.alert_type.value
            )

            logger.info(
                f"Отправлен алерт пользователю {telegram_id}: "
                f"{anomaly.ticker} {anomaly.alert_type.value}"
            )

        except Exception as e:
            logger.error(f"Ошибка при отправке алерта пользователю {telegram_id}: {e}")

    @staticmethod
    async def _send_aggregated_alert(
        bot: Bot, telegram_id: int, anomalies: list[PriceAnomaly]
    ) -> None:
        """Отправляет сводное сообщение о нескольких аномалиях.

        Args:
            bot: Экземпляр бота
            telegram_id: ID пользователя
            anomalies: Список аномалий

        """
        # Сортируем по критичности
        critical = [a for a in anomalies if "CRITICAL" in a.alert_type.name]
        warnings = [a for a in anomalies if "WARNING" in a.alert_type.name]

        # Формируем сводку
        lines = ["<b>Множественные изменения цен облигаций</b>\n"]

        if critical:
            lines.append(f"<b>Критических: {len(critical)}</b>")
            for a in critical[:5]:  # Показываем максимум 5
                direction = "[-]" if a.change_percent < 0 else "[+]"
                lines.append(
                    f"  {direction} <code>{a.ticker}</code>: {a.change_percent:+.1f}%"
                )

        if warnings:
            lines.append(f"\n<b>Предупреждений: {len(warnings)}</b>")
            for a in warnings[:5]:  # Показываем максимум 5
                direction = "[-]" if a.change_percent < 0 else "[+]"
                lines.append(
                    f"  {direction} <code>{a.ticker}</code>: {a.change_percent:+.1f}%"
                )

        if len(anomalies) > 10:
            lines.append(f"\n... и ещё {len(anomalies) - 10} изменений")

        lines.append("\n<i>Рекомендуем проверить портфель</i>")

        message = "\n".join(lines)

        try:
            await bot.send_message(telegram_id, message, parse_mode="HTML")

            # Записываем все алерты
            for anomaly in anomalies:
                await AlertStorage.record_sent_alert(
                    telegram_id, anomaly.figi, anomaly.alert_type.value
                )

            logger.info(
                f"Отправлен сводный алерт пользователю {telegram_id}: "
                f"{len(anomalies)} аномалий"
            )

        except Exception as e:
            logger.error(f"Ошибка при отправке сводного алерта пользователю {telegram_id}: {e}")

    @staticmethod
    def _format_alert_message(anomaly: PriceAnomaly) -> str:
        """Форматирует сообщение об аномалии.

        Args:
            anomaly: Информация об аномалии

        Returns:
            Отформатированное сообщение

        """
        is_critical = "CRITICAL" in anomaly.alert_type.name
        is_drop = anomaly.change_percent < 0

        # Заголовок
        if is_critical:
            if is_drop:
                header = "<b>КРИТИЧЕСКОЕ падение цены!</b>"
            else:
                header = "<b>КРИТИЧЕСКИЙ рост цены!</b>"
        else:
            header = "<b>Внимание: изменение цены облигации</b>"

        # Направление изменения
        direction_text = "упала" if is_drop else "выросла"

        # Основное сообщение
        lines = [
            header,
            "",
            f"<code>{anomaly.ticker}</code> {anomaly.name}",
            f"Цена {direction_text} на {anomaly.change_percent:+.1f}%",
            f"   Было: {anomaly.old_price:.2f}%  ->  Стало: {anomaly.new_price:.2f}%",
            "",
            f"Счёт: {anomaly.account_name}",
        ]

        # Рекомендация для критических
        if is_critical:
            lines.append("")
            lines.append("⚡ <i>Рекомендуем проверить новости эмитента</i>")

        return "\n".join(lines)
