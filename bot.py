import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = "9255429964:AAGPJ8k9el502n_D8QX0SmpmJYvD5G-Pqmw"
ADMIN_ID = 6684594078

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

class RepairOrder(StatesGroup):
    waiting_for_brand = State()
    waiting_for_custom_brand = State()
    waiting_for_issue = State()
    waiting_for_photo = State()
    waiting_for_contact = State()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="ℹ️ О нас")],
        [KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

# Клавиатура с популярными брендами
brands_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="LG"), KeyboardButton(text="Samsung"), KeyboardButton(text="Bosch")],
        [KeyboardButton(text="Indesit"), KeyboardButton(text="Ariston"), KeyboardButton(text="Candy")],
        [KeyboardButton(text="✍️ Другая марка"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Пропустить фото")],
        [KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Здравствуйте! Я бот-помощник частного мастера по ремонту стиральных машин в Новосибирске.\n\n"
        "Выберите нужный пункт в меню ниже:",
        reply_markup=main_keyboard
    )

@router.message(F.text == "🔄 В начало")
async def go_start(message: Message, state: FSMContext):
    await cmd_start(message, state)

@router.message(F.text == "ℹ️ О нас")
async def about_us(message: Message):
    await message.answer(
        "🛠 Частный мастер по ремонту стиральных машин\n\n"
        "• Работаем по всему Новосибирску\n"
        "• Быстрый выезд и диагностика\n"
        "• Гарантия на все виды работ\n\n"
        "Нажмите «🛠 Оставить заявку», чтобы вызвать мастера.",
        reply_markup=main_keyboard
    )

@router.message(F.text == "🛠 Оставить заявку")
async def start_order(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_brand)
    await message.answer(
        "Выберите марку вашей стиральной машины из списка или нажмите «✍️ Другая марка»:",
        reply_markup=brands_keyboard
    )

@router.message(RepairOrder.waiting_for_brand, F.text == "✍️ Другая марка")
async def custom_brand_prompt(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_custom_brand)
    await message.answer("Введите марку вашей стиральной машины вручную:", reply_markup=ReplyKeyboardRemove())

@router.message(RepairOrder.waiting_for_brand)
async def process_brand_choice(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    
    await state.update_data(brand=message.text)
    await state.set_state(RepairOrder.waiting_for_issue)
    await message.answer("Опишите коротко проблему (например: не отжимает, не греет воду, шумит при стирке):", reply_markup=ReplyKeyboardRemove())

@router.message(RepairOrder.waiting_for_custom_brand)
async def process_custom_brand(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    
    await state.update_data(brand=message.text)
    await state.set_state(RepairOrder.waiting_for_issue)
    await message.answer("Опишите коротко проблему (например: не отжимает, не греет воду, шумит при стирке):", reply_markup=ReplyKeyboardRemove())

@router.message(RepairOrder.waiting_for_issue)
async def process_issue(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(issue=message.text)
    await state.set_state(RepairOrder.waiting_for_photo)
    await message.answer(
        "Если есть возможность, отправьте фото поломки или панели машины (или нажмите «Пропустить фото»):",
        reply_markup=skip_keyboard
    )

@router.message(RepairOrder.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(RepairOrder.waiting_for_contact)
    await message.answer("Пожалуйста, укажите ваш номер телефона или контакт для связи:", reply_markup=ReplyKeyboardRemove())

@router.message(RepairOrder.waiting_for_photo, F.text == "Пропустить фото")
async def skip_photo(message: Message, state: FSMContext):
    await state.update_data(photo=None)
    await state.set_state(RepairOrder.waiting_for_contact)
    await message.answer("Пожалуйста, укажите ваш номер телефона или контакт для связи:", reply_markup=ReplyKeyboardRemove())

@router.message(RepairOrder.waiting_for_photo)
async def wrong_photo_format(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await message.answer("Пожалуйста, отправьте фотографию или нажмите «Пропустить фото».")

@router.message(RepairOrder.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    
    data = await state.get_data()
    brand = data.get("brand")
    issue = data.get("issue")
    photo = data.get("photo")
    contact = message.text
    
    user = message.from_user
    username = f"@{user.username}" if user.username else "нет username"

    admin_text = (
        f"🚨 Новая заявка на ремонт!\n\n"
        f"🏷 Марка: {brand}\n"
        f"⚠️ Проблема: {issue}\n"
        f"📞 Контакт: {contact}\n"
        f"👤 Клиент: {user.first_name} ({username})"
    )

    try:
        if photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=admin_text)
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text)
    except Exception as e:
        logging.error(f"Failed to send order to admin: {e}")

    await message.answer(
        "Спасибо! Ваша заявка принята. Мастер свяжется с вами в ближайшее время.",
        reply_markup=main_keyboard
    )
    await state.clear()

dp.include_router(router)

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
