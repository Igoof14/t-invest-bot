from dataclasses import dataclass
from enum import Enum


class AlertSeverity(Enum):
    """Уровень критичности алерта."""

    WARNING = "warning"
    CRITICAL = "critical"


class AlertDirection(Enum):
    """Направление изменения цены."""

    DROP = "drop"
    RISE = "rise"


class AlertType(Enum):
    """Тип алерта = направление + уровень критичности."""

    DROP_WARNING = "drop_warning"
    DROP_CRITICAL = "drop_critical"
    RISE_WARNING = "rise_warning"
    RISE_CRITICAL = "rise_critical"

    @property
    def severity(self) -> AlertSeverity:
        """Возвращает уровень критичности алерта."""
        if self in (AlertType.DROP_CRITICAL, AlertType.RISE_CRITICAL):
            return AlertSeverity.CRITICAL
        return AlertSeverity.WARNING

    @property
    def direction(self) -> AlertDirection:
        """Возвращает направление изменения цены."""
        if self in (AlertType.DROP_WARNING, AlertType.DROP_CRITICAL):
            return AlertDirection.DROP
        return AlertDirection.RISE

    @property
    def is_critical(self) -> bool:
        """True, если уровень критичности CRITICAL."""
        return self.severity is AlertSeverity.CRITICAL

    @property
    def is_drop(self) -> bool:
        """True, если направление DROP."""
        return self.direction is AlertDirection.DROP

    @classmethod
    def from_parts(cls, direction: AlertDirection, severity: AlertSeverity) -> "AlertType":
        """Собирает AlertType из направления и уровня критичности."""
        return cls(f"{direction.value}_{severity.value}")


@dataclass(frozen=True, slots=True)
class PriceAnomaly:
    """Аномальное изменение цены облигации, требующее уведомления.

    Цены — в процентах от номинала (стандартная котировка облигаций).
    """

    isin: str
    name: str
    price_pct: float
    prev_close_pct: float
    change_pct: float
    alert_type: AlertType

    @property
    def severity(self) -> AlertSeverity:
        """Уровень критичности аномалии."""
        return self.alert_type.severity

    @property
    def direction(self) -> AlertDirection:
        """Направление изменения цены."""
        return self.alert_type.direction

    @property
    def is_critical(self) -> bool:
        """True, если аномалия критическая."""
        return self.alert_type.is_critical

    @property
    def is_drop(self) -> bool:
        """True, если цена упала."""
        return self.alert_type.is_drop
