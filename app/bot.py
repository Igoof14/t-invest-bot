import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from invest import get_payment

_ = load_dotenv(".env")
TOKEN = str(os.environ.get("bot_token"))


bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=["start"]))
async def start_handler(message: Message):
    """Start handler."""
    _ = await message.answer(get_payment(), parse_mode="HTML")


async def main():
    """Start the bot."""
    await dp.start_polling(bot)  # type: ignore[reportUnknownMemberType]


if __name__ == "__main__":
    asyncio.run(main())
