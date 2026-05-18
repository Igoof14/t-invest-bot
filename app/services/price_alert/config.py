"""Конфигурация политики уведомлений о ценах."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AlertPolicyConfig:
    """Параметры антиспам-политики и агрегации алертов.

    Все параметры — пользовательские настройки сервиса, а не пользователя
    Telegram. Меняются только при перезапуске приложения.
    """

    # Cooldown между алертами по одной бумаге (в часах).
    cooldown_hours: int = 4

    # Максимум алертов на пользователя в сутки.
    max_daily_alerts: int = 10

    # Если за один проход аномалий больше этого числа — отправляем сводку
    # вместо отдельных сообщений.
    aggregate_threshold: int = 3

    # Сколько показывать в сводке (по каждому уровню критичности).
    max_aggregated_per_severity: int = 5


DEFAULT_POLICY = AlertPolicyConfig()


@dataclass(frozen=True, slots=True)
class AlertThresholds:
    """Пороги пользователя для срабатывания алерта (в процентах изменения цены).

    Это domain-объект, не привязанный к ORM. Сервис создаёт его из
    ``PriceAlertSettings`` через :meth:`from_settings`.
    """

    drop_warning: float
    drop_critical: float
    rise_warning: float
    rise_critical: float

    @classmethod
    def from_settings(cls, settings: object) -> "AlertThresholds":
        """Собирает AlertThresholds из ORM-модели PriceAlertSettings."""
        return cls(
            drop_warning=settings.drop_warning_threshold,  # type: ignore[attr-defined]
            drop_critical=settings.drop_critical_threshold,  # type: ignore[attr-defined]
            rise_warning=settings.rise_warning_threshold,  # type: ignore[attr-defined]
            rise_critical=settings.rise_critical_threshold,  # type: ignore[attr-defined]
        )
