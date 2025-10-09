import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from main import get_payment

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("bot_token"))


bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=["start"]))
async def start_handler(message: Message):
    await message.answer(get_payment(), parse_mode="HTML")


# функция для запуска бота
async def main():
    # запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
