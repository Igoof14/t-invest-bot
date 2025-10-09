import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

from main import get_payment

# токен вашего бота
TOKEN = "8248723238:AAHN_nOUmeQ6t7tZg3iBEaesQ8Jvk4amgDc"

# создаём объекты бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()


# обработчик команды /start
@dp.message(Command(commands=["start"]))
async def start_handler(message: Message):
    await message.answer(get_payment(), parse_mode="HTML")


# функция для запуска бота
async def main():
    # запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
