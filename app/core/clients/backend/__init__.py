"""Клиенты бэкенда Bondelo (Cloud Run)."""

from .offers import OfferAccount, OfferItem, get_offers

__all__ = ["OfferAccount", "OfferItem", "get_offers"]
