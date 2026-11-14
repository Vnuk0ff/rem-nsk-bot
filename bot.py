import asyncio
import logging
import os
import sqlite3
import html
from datetime import datetime, timedelta
from aiohttp import web

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# Конфигурация
TOKEN = "9255429964:AAFUMdzsDqgJs4Ie6NEnQfTSR9VOffz-WG0"
ADMIN_ID = 6684594078
CHANNEL_USERNAME = -1004465523357  # Числовой ID канала
CHANNEL_INVITE_LINK = "https://t.me/+HN5h7aaUEIc3YzQy"

DB_NAME = "service_bot.db"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            client_name TEXT,
            brand TEXT,
            fault TEXT,
            phone TEXT,
            district TEXT,
            status TEXT,
            created_at TEXT,
            master_name TEXT,
            cost TEXT,
            warranty_days TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_order_by_id(order_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_order_status_db(order_id: int, status: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

# ================= FSM STATES =================
class OrderState(StatesGroup):
    waiting_for_brand = State()
    waiting_for_fault = State()
    waiting_for_phone = State()
    waiting_for_district = State()

class ReviewState(StatesGroup):
    waiting_for_rating = State()
    waiting_for_text = State()
    waiting_for_photo = State()

class WarrantyState(StatesGroup):
    waiting_for_claim_text = State()

# ================= KEYBOARDS =================
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="📦 Мои заказы")],
        [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="ℹ️ О нас")]
    ],
    resize_keyboard=True
)

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="📦 Мои заказы")],
            [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="ℹ️ О нас")],
            [KeyboardButton(text="👑 Админ-панель")]
        ],
        resize_keyboard=True
    )

district_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Центральный"), KeyboardButton(text="Октябрьский")],
        [KeyboardButton(text="Ленинский"), KeyboardButton(text="Кировский")],
        [KeyboardButton(text="Советский"), KeyboardButton(text="Дзержинский")],
        [KeyboardButton(text="Калининский"), KeyboardButton(text="Другой / Пригород")],
        [KeyboardButton(text="🔙 В начало")]
    ],
    resize_keyboard=True
)

stars_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⭐"), KeyboardButton(text="⭐⭐"), KeyboardButton(text="⭐⭐⭐")],
        [KeyboardButton(text="⭐⭐⭐⭐"), KeyboardButton(text="⭐⭐⭐⭐⭐")],
        [KeyboardButton(text="🔙 В начало")]
    ],
    resize_keyboard=True
)

skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Пропустить фото")],
        [KeyboardButton(text="🔙 В начало")]
    ],
    resize_keyboard=True
)

# ================= CHANNEL CHECK =================
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception:
        return True

# ================= START / MENU =================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    is_subscribed = await check_subscription(message.from_user.id)
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard

    if not is_subscribed:
        sub_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_INVITE_LINK)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
        ])
        await message.answer(
            "👋 Здравствуйте! Чтобы пользоваться ботом, пожалуйста, подпишитесь на наш канал мастера.",
            reply_markup=sub_kb
        )
        return

    await message.answer(
        "👋 Добро пожаловать!\nЧастный мастер по ремонту стиральных машин в Новосибирске.\nВыберите нужный пункт меню:",
        reply_markup=kb
    )

@router.callback_query(F.data == "check_sub")
async def verify_subscription(callback: CallbackQuery, state: FSMContext):
    is_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        await callback.message.delete()
        kb = get_admin_keyboard() if callback.from_user.id == ADMIN_ID else main_keyboard
        await callback.message.answer("✅ Спасибо за подписку! Добро пожаловать.", reply_markup=kb)
    else:
        await callback.answer("❌ Вы еще не подписались на канал!", show_alert=True)

@router.message(F.text == "🔙 В начало")
async def cancel_to_start(message: Message, state: FSMContext):
    await state.clear()
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer("Главное меню:", reply_markup=kb)

@router.message(F.text == "ℹ️ О нас")
async def about_us(message: Message):
    text = (
        "🛠 <b>Частный мастер по ремонту стиральных машин в Новосибирске</b>\n\n"
        "• Бесплатный выезд и диагностика\n"
        "• Гарантия на работы до 1 года\n"
        "• Оплата после проверки работы\n\n"
        "📞 Телефон: +7 (953) 804-30-48\n"
        "📢 Наш канал: @master_Vnukoff"
    )
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

@router.message(F.text == "💰 Прайс")
async def show_price(message: Message):
    text = (
        "💰 <b>Примерные цены на ремонт:</b>\n\n"
        "• Диагностика и выезд — <b>0 руб.</b> (при ремонте)\n"
        "• Замена сливного насоса — от 800 руб.\n"
        "• Замена ТЭНа — от 1000 руб.\n"
        "• Замена подшипников — от 2500 руб.\n"
        "• Ремонт модуля управления — от 1500 руб."
    )
    await message.answer(text, parse_mode="HTML")

# ================= ORDER CREATION FLOW =================
@router.message(F.text == "🛠 Оставить заявку")
async def start_order(message: Message, state: FSMContext):
    await state.set_state(OrderState.waiting_for_brand)
    await message.answer("📝 Введите марку вашей стиральной машины (например: Samsung, Bosch, LG):", reply_markup=ReplyKeyboardRemove())

@router.message(OrderState.waiting_for_brand)
async def process_brand(message: Message, state: FSMContext):
    await state.update_data(brand=message.text)
    await state.set_state(OrderState.waiting_for_fault)
    await message.answer("📝 Опишите кратко проблему (например: не сливает воду, шумит при отжиме):")

@router.message(OrderState.waiting_for_fault)
async def process_fault(message: Message, state: FSMContext):
    await state.update_data(fault=message.text)
    await state.set_state(OrderState.waiting_for_phone)
    
    phone_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("📞 Укажите ваш контактный телефон или нажмите кнопку ниже:", reply_markup=phone_kb)

@router.message(OrderState.waiting_for_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await state.set_state(OrderState.waiting_for_district)
    await message.answer("📍 Выберите ваш район в Новосибирске:", reply_markup=district_keyboard)

@router.message(OrderState.waiting_for_phone)
async def process_phone_text(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderState.waiting_for_district)
    await message.answer("📍 Выберите ваш район в Новосибирске:", reply_markup=district_keyboard)

@router.message(OrderState.waiting_for_district)
async def process_district(message: Message, state: FSMContext):
    district = message.text
    data = await state.get_data()
    
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (user_id, username, client_name, brand, fault, phone, district, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user.id, username, user.first_name, data["brand"], data["fault"], data["phone"], district, "Создана", datetime.now().strftime("%Y-%m-%d %H:%M")))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    kb = get_admin_keyboard() if user.id == ADMIN_ID else main_keyboard
    await message.answer(f"✅ <b>Заявка №{order_id} успешно оформлена!</b>\nМастер свяжется с вами в ближайшее время.", reply_markup=kb, parse_mode="HTML")
    
    admin_text = (
        f"🚨 <b>НОВАЯ ЗАЯВКА №{order_id}</b>\n\n"
        f"👤 Клиент: {username} (ID: {user.id})\n"
        f"🏷 Марка: {data['brand']}\n"
        f"⚠️ Поломка: {data['fault']}\n"
        f"📞 Телефон: {data['phone']}\n"
        f"📍 Район: {district}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception:
        pass

    await state.clear()

# ================= USER ORDERS =================
@router.message(F.text == "📦 Мои заказы")
async def show_user_orders(message: Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand, status, created_at FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (message.from_user.id,))
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await message.answer("У вас пока нет активных заказов.")
        return

    text = "📦 <b>Ваши последние заказы:</b>\n\n"
    for o in orders:
        text += f"🔹 <b>Заявка №{o[0]}</b>\n🏷 Техника: {o[1]}\n📊 Статус: {o[2]}\n📅 Дата: {o[3]}\n\n"
    
    await message.answer(text, parse_mode="HTML")

# ================= REVIEW SUBMISSION FLOW =================
async def publish_review_to_channel(message: Message, state: FSMContext):
    logging.info("[REVIEW] Начало публикации отзыва в канал...")
    data = await state.get_data()
    order_id = data.get("review_order_id")
    order = get_order_by_id(order_id) if order_id else None
    
    user = message.from_user
    username_str = f"@{user.username}" if user.username else html.escape(user.first_name or "Клиент")
    
    brand = html.escape(order[4]) if (order and order[4]) else "Не указана"
    rating = html.escape(data.get("rating") or "⭐⭐⭐⭐⭐")
    review_text = html.escape(data.get("review_text") or "")
    photo_id = data.get("review_photo")

    channel_post = (
        f"💬 <b>НОВЫЙ ОТЗЫВ О РАБОТЕ МАСТЕРА</b>\n\n"
        f"👤 Клиент: {username_str}\n"
        f"🏷 Техника: {brand}\n"
        f"⭐ Оценка: {rating}\n\n"
        f"📝 «{review_text}»\n\n"
        f"🛠 Частный ремонт бытовой техники в Новосибирске"
    )

    kb = get_admin_keyboard() if user.id == ADMIN_ID else main_keyboard

    try:
        if photo_id:
            await bot.send_photo(chat_id=CHANNEL_USERNAME, photo=photo_id, caption=channel_post, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=CHANNEL_USERNAME, text=channel_post, parse_mode="HTML", disable_web_page_preview=True)
        
        logging.info("[REVIEW] Отзыв успешно опубликован в канал!")
        await message.answer("🌟 <b>Спасибо большое за ваш отзыв!</b> Он успешно опубликован в нашем канале.", reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        err_msg = str(e)
        logging.error(f"[REVIEW] Ошибка при публикации отзыва в канал: {err_msg}")
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ <b>ОШИБКА ПУБЛИКАЦИИ В КАНАЛ:</b>\n<code>{html.escape(err_msg)}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        await message.answer("🌟 Спасибо за ваш отзыв!", reply_markup=kb)

    await state.clear()

@router.callback_query(F.data.startswith("rate_"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])
    await state.update_data(review_order_id=order_id)
    await state.set_state(ReviewState.waiting_for_rating)
    
    await callback.message.answer(
        "Шаг 1 из 3: Пожалуйста, выберите оценку на клавиатуре снизу:",
        reply_markup=stars_keyboard
    )
    await callback.answer()

@router.message(ReviewState.waiting_for_rating, F.text.in_(["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]))
async def review_receive_rating(message: Message, state: FSMContext):
    await state.update_data(rating=message.text)
    await state.set_state(ReviewState.waiting_for_text)
    await message.answer(
        f"Вы выбрали оценку: {message.text}\n\nШаг 2 из 3: Напишите пару слов о проведенном ремонте:",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(ReviewState.waiting_for_text)
async def review_receive_text(message: Message, state: FSMContext):
    await state.update_data(review_text=message.text)
    await state.set_state(ReviewState.waiting_for_photo)
    await message.answer(
        "Шаг 3 из 3: Прикрепите фото отремонтированной техники (или нажмите «Пропустить фото»):",
        reply_markup=skip_keyboard
    )

@router.message(ReviewState.waiting_for_photo, F.text == "Пропустить фото")
async def review_skip_photo(message: Message, state: FSMContext):
    await state.update_data(review_photo=None)
    await publish_review_to_channel(message, state)

@router.message(ReviewState.waiting_for_photo, F.photo)
async def review_receive_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(review_photo=photo_id)
    await publish_review_to_channel(message, state)

# ================= WARRANTY CLAIM FLOW =================
@router.callback_query(F.data.startswith("warranty_"))
async def start_warranty_claim(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])
    await state.update_data(warranty_order_id=order_id)
    await state.set_state(WarrantyState.waiting_for_claim_text)
    await callback.message.answer("Опишите вашу проблему по гарантии:", reply_markup=ReplyKeyboardRemove())
    await callback.answer()

@router.message(WarrantyState.waiting_for_claim_text)
async def process_warranty_claim(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("warranty_order_id")
    order = get_order_by_id(order_id)
    
    user = message.from_user
    kb = get_admin_keyboard() if user.id == ADMIN_ID else main_keyboard
    
    await message.answer("✅ Ваше обращение по гарантии принято! Мастер свяжется с вами в ближайшее время.", reply_markup=kb)
    
    admin_text = (
        f"🚨 <b>ГАРАНТИЙНОЕ ОБРАЩЕНИЕ ПО ЗАЯВКЕ №{order_id}</b>\n\n"
        f"👤 Клиент: @{user.username or user.first_name} (ID: {user.id})\n"
        f"📞 Телефон: {order[6] if order else 'Не указан'}\n"
        f"📝 Проблема: {message.text}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception:
        pass
        
    await state.clear()

# ================= ADMIN PANEL =================
@router.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, brand, client_name, phone, status FROM orders WHERE status != 'ОПЛАЧЕНО И ПОДТВЕРЖДЕНО' ORDER BY id DESC LIMIT 5")
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await message.answer("👑 Панель администратора\n\nНет активных необработанных заявок.")
        return

    for o in orders:
        text = (
            f"📋 <b>Заявка №{o[0]}</b>\n"
            f"👤 Клиент: {o[2]} ({o[3]})\n"
            f"🏷 Техника: {o[1]}\n"
            f"📊 Статус: {o[4]}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Заполнить гарантийный талон", callback_data=f"admin_fill_{o[0]}")]
        ])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("admin_fill_"))
async def admin_fill_ticket(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    order_id = int(callback.data.split("_")[2])
    order = get_order_by_id(order_id)
    
    master_name = "Николай"
    cost = "2500"
    warranty_days = "365"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET master_name = ?, cost = ?, warranty_days = ?, status = ? WHERE id = ?", 
                   (master_name, cost, warranty_days, "ОПЛАЧЕНО И ПОДТВЕРЖДЕНО", order_id))
    conn.commit()
    conn.close()

    ticket_text = (
        f"📄 <b>ЭЛЕКТРОННЫЙ ГАРАНТИЙНЫЙ ТАЛОН №{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 Марка: {order[4]}\n"
        f"🛠 Выполненные работы: Ремонт и замена узла\n"
        f"💵 Стоимость: {cost} руб.\n"
        f"📅 Дата выдачи: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"⏳ Срок гарантии: {warranty_days} дн.\n"
        f"🟢 Статус: ОПЛАЧЕНО И ПОДТВЕРЖДЕНО\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Мастер: Николай (+7 953 804 3048)\n"
        f"Сохраните этот талон. По вопросам гарантии обращайтесь в бот."
    )

    ticket_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡 Обратиться по гарантии", callback_data=f"warranty_{order_id}")],
        [InlineKeyboardButton(text="⭐ Оценить работу мастера", callback_data=f"rate_{order_id}")]
    ])

    try:
        await bot.send_message(order[1], ticket_text, parse_mode="HTML", reply_markup=ticket_kb)
    except Exception as e:
        logging.error(f"Не удалось отправить талон клиенту: {e}")

    await callback.message.answer(f"✅ Гарантийный талон для заявки №{order_id} успешно сформирован и отправлен клиенту!")
    await callback.answer()

# ================= WEB SERVER FOR RENDER =================
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ================= MAIN =================
async def main():
    init_db()
    dp.include_router(router)
    
    asyncio.create_task(web_server())
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
