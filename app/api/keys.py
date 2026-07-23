"""Ключи aiohttp-приложения, доступные обработчикам запросов.

Вынесены в отдельный модуль, чтобы feature-модули с роутами не
импортировали ``api.server`` (избегаем циклических импортов).
"""

from aiogram import Bot
from aiohttp import web

# Ключ доступа к экземпляру бота из обработчиков запросов.
BOT_KEY: web.AppKey[Bot] = web.AppKey("bot", Bot)
