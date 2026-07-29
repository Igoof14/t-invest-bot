"""Доменные типы продуктовой аналитики: имена событий и направление."""

from enum import StrEnum


class Direction(StrEnum):
    """Направление события относительно бота."""

    IN = "in"
    """Пользователь что-то сделал: команда, кнопка, текст."""

    OUT = "out"
    """Бот что-то отправил: уведомление, рассылка."""


class EventName(StrEnum):
    """Канонический список продуктовых событий.

    Список сознательно короткий: новые сценарии описываются полями
    ``action`` и ``props``, а не новыми именами событий. Иначе воронки
    приходится переписывать при каждом изменении UI.
    """

    # --- Автоматические (пишет AnalyticsMiddleware) ---
    COMMAND = "command"
    """Слэш-команда. ``action`` — имя команды без слэша."""

    CALLBACK_CLICK = "callback_click"
    """Нажатие инлайн-кнопки. ``action`` — полный callback_data."""

    BUTTON_CLICK = "button_click"
    """Нажатие кнопки reply-клавиатуры. ``action`` — текст кнопки."""

    TEXT_MESSAGE = "text_message"
    """Произвольный текст. Сам текст не сохраняется — только его длина."""

    UPDATE_OTHER = "update_other"
    """Апдейт прочего типа (не сообщение и не callback). ``action`` — тип.

    Факт «хендлер не нашёлся» — это не отдельное событие, а props ``matched``:
    он есть у любого автоматического события.
    """

    # --- Явные: воронка онбординга ---
    BOT_START = "bot_start"
    """Вершина воронки. props: is_new_user, has_token, source."""

    ONBOARDING_STEP_SHOWN = "onboarding_step_shown"
    """Показан экран карусели онбординга. props: step."""

    ONBOARDING_CTA_CLICKED = "onboarding_cta_clicked"
    """Клик по финальной кнопке «Подключить портфель»."""

    ONBOARDING_MARKET_CHOSEN = "onboarding_market_chosen"
    """Выбран режим без токена — события по всему рынку.

    Вместе с ``ONBOARDING_CTA_CLICKED`` даёт разбивку финального шага по
    режимам: видно, сколько людей уходит в токен, а сколько — в рынок.
    """

    TOKEN_PROMPT_SHOWN = "token_prompt_shown"
    """Показана инструкция по получению токена. props: entry."""

    TOKEN_SUBMITTED = "token_submitted"
    """Пользователь отправил токен. props: valid."""

    TOKEN_CONNECTED = "token_connected"
    """Токен принят и сохранён — главная конверсия."""

    TOKEN_REMOVED = "token_removed"
    """Пользователь удалил токен."""

    BONDS_SYNCED = "bonds_synced"
    """Завершена синхронизация портфеля. props: count, ok."""

    # --- Явные: использование фич ---
    ALERT_TOGGLED = "alert_toggled"
    """Переключен алерт фичи. props: feature, enabled."""

    ALERT_SETTING_CHANGED = "alert_setting_changed"
    """Изменена настройка алерта. props: feature, field."""

    DATA_SCREEN_VIEWED = "data_screen_viewed"
    """Открыт экран с данными портфеля. props: screen, items, outcome."""

    # --- Явные: исходящие сообщения ---
    NOTIFICATION_SENT = "notification_sent"
    """Уведомление доставлено. props: kind, items."""

    NOTIFICATION_FAILED = "notification_failed"
    """Уведомление не доставлено. props: kind, reason."""

    BROADCAST_FINISHED = "broadcast_finished"
    """Завершена админская рассылка. props: delivered, blocked, failed."""
