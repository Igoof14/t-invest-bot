"""Мониторинг невыплаты купонов по данным НРД (nsddata.ru).

Сверяет купонный календарь T-Invest с публикациями НРД: если по облигации в
портфеле подписчика наступила плановая дата купона, а публикации о выплате в
ленте НРД нет — уведомляет держателя.
"""

from .handlers import router
from .service import NsdCouponService

__all__ = ["NsdCouponService", "router"]
