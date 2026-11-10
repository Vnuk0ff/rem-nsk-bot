import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "9255461947:AAH3i9H9oZqD_7K5O9O_JYvd5Gi47aCq2M8" # Твой токен
ADMIN_ID = 6684594078 # Твой ID

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# Клавиатура меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="ℹ️ О нас")],
        [KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Здравствуйте! Я бот-помощник частного мастера по ремонту стиральных машин в Новосибирске.\n\n"
        "Выберите нужный пункт в меню ниже:",
        reply_markup=main_keyboard
    )

@router.message(F.text == "ℹ️ О нас")
async def about_us(message: Message):
    await message.answer(
        "🛠 **Частный мастер по ремонту стиральных машин**\n\n"
        "• Работаем по всему Новосибирску\n"
        "• Быстрый выезд и диагностика\n"
        "• Гарантия на все виды работ\n\n"
        "Нажмите «🛠 Оставить заявку», чтобы вызвать мастера.",
        reply_markup=main_keyboard
    )

@router.message(F.text == "🔄 В начало")
async def go_start(message: Message):
    await cmd_start(message)

dp.include_router(router)

# --- Функция для обмана Render (чтобы веб-сервис держал порт) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render передает порт через системную переменную PORT, по умолчанию берем 10000
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

async def main():
    logging.basicConfig(level=logging.INFO)
    # Запускаем веб-сервер для Render и поллинг бота одновременно
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
