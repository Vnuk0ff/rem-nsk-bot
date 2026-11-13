import asyncio
import logging
import os
import sqlite3
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

TOKEN = "9255429964:AAGPJ8k9el502n_D8QX0SmpmJYvD5G-Pqmw"
ADMIN_ID = 6684594078
CHANNEL_USERNAME = "@A_TOOLSx2"  # Юзернейм твоего канала для проверки подписки через API
CHANNEL_INVITE_LINK = "https://t.me/+HN5h7aaUEIc3YzQy"

DB_NAME = "service_bot.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            district TEXT,
            brand TEXT,
            issue TEXT,
            photo TEXT,
            contact TEXT,
            status TEXT DEFAULT 'Новая',
            price TEXT DEFAULT '',
            warranty_period TEXT DEFAULT '',
            work_details TEXT DEFAULT '',
            completed_at TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class RepairOrder(StatesGroup):
    waiting_for_district = State()
    waiting_for_brand = State()
    waiting_for_custom_brand = State()
    waiting_for_issue = State()
    waiting_for_custom_issue = State()
    waiting_for_photo = State()
    waiting_for_contact = State()
    preview_order = State()

class AdminWarrantyFill(StatesGroup):
    waiting_for_order_id = State()
    waiting_for_price = State()
    waiting_for_period = State()
    waiting_for_details = State()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="📜 Мои заказы")],
        [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="ℹ️ О нас")],
        [KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="📜 Мои заказы")],
            [KeyboardButton(text="📊 Управление заказами (Админ)")],
            [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="ℹ️ О нас")],
            [KeyboardButton(text="🔄 В начало")]
        ],
        resize_keyboard=True
    )

districts_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Центральный"), KeyboardButton(text="Железнодорожный")],
        [KeyboardButton(text="Заельцовский"), KeyboardButton(text="Октябрьский")],
        [KeyboardButton(text="Советский"), KeyboardButton(text="Ленинский")],
        [KeyboardButton(text="Кировский"), KeyboardButton(text="Дзержинский")],
        [KeyboardButton(text="Калининский"), KeyboardButton(text="Первомайский")],
        [KeyboardButton(text="Пригород и область")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

brands_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="LG"), KeyboardButton(text="Samsung"), KeyboardButton(text="Bosch")],
        [KeyboardButton(text="Indesit"), KeyboardButton(text="Ariston"), KeyboardButton(text="Candy")],
        [KeyboardButton(text="✍️ Другая марка")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

issues_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚰 Не сливает / не набирает воду")],
        [KeyboardButton(text="🔄 Не крутит барабан / не отжимает")],
        [KeyboardButton(text="⚡️ Не включается / не греет воду")],
        [KeyboardButton(text="🔊 Сильно шумит / стучит / вибрирует")],
        [KeyboardButton(text="✍️ Своя проблема")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Пропустить фото")],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

async def check_subscription(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True  # Админу подписка не нужна
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
    return False

def get_sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал мастера", url=CHANNEL_INVITE_LINK)],
        [InlineKeyboardButton(text="✅ Я подписался(ась)", callback_data="check_sub")]
    ])

def save_order(user_id, user_name, district, brand, issue, photo, contact):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO orders (user_id, user_name, district, brand, issue, photo, contact)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, user_name, district, brand, issue, photo, contact))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_user_orders(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, brand, issue, status, price, warranty_period, work_details, completed_at FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_orders_by_status(status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_name, district, brand, issue, contact, price FROM orders WHERE status = ? ORDER BY id DESC', (status,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_order_by_id(order_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, user_name, district, brand, issue, photo, contact, status, price, warranty_period, work_details, completed_at FROM orders WHERE id = ?', (order_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def update_order_warranty(order_id, price, period, details):
    today_str = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE orders 
        SET price = ?, warranty_period = ?, work_details = ?, status = 'Ожидает оплаты', completed_at = ?
        WHERE id = ?
    ''', (price, period, details, today_str, order_id))
    conn.commit()
    conn.close()

def calculate_warranty_days(completed_at_str, period_str):
    try:
        completed_date = datetime.strptime(completed_at_str, "%Y-%m-%d")
        days_total = 365
        if "месяц" in period_str:
            months = int(''.join(filter(str.isdigit, period_str)) or 1)
            days_total = months * 30
        elif "год" in period_str:
            years = int(''.join(filter(str.isdigit, period_str)) or 1)
            days_total = years * 365
        elif "дн" in period_str or "день" in period_str:
            days_total = int(''.join(filter(str.isdigit, period_str)) or 365)
            
        expiry_date = completed_date + timedelta(days=days_total)
        remaining_days = (expiry_date - datetime.now()).days
        return max(0, remaining_days), days_total
    except Exception:
        return 365, 365

def get_admin_order_markup(order_id, status=""):
    buttons = [
        [
            InlineKeyboardButton(text="📞 Созвон", callback_data=f"status_{order_id}_Созвон"),
            InlineKeyboardButton(text="🛠 В работе", callback_data=f"status_{order_id}_В работе")
        ],
        [
            InlineKeyboardButton(text="⚠️ Не ответ", callback_data=f"status_{order_id}_Не ответ"),
            InlineKeyboardButton(text="🟢 Готов", callback_data=f"status_{order_id}_Готов")
        ],
        [
            InlineKeyboardButton(text="📋 Выписать гарантию / счет", callback_data=f"fill_warranty_{order_id}")
        ]
    ]
    if status in ["Готов", "Оплачено / Выполнено"]:
        buttons.append([InlineKeyboardButton(text="📜 Посмотреть гарантию", callback_data=f"admin_view_warranty_{order_id}")])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    if not await check_subscription(message.from_user.id):
        await message.answer(
            "👋 **Добро пожаловать!**\n\n"
            f"Чтобы пользоваться ботом, пожалуйста, подпишитесь на [наш канал мастера]({CHANNEL_INVITE_LINK}). "
            "Так вы точно не потеряетесь — здесь всегда можно связаться с мастером напрямую, найти полезные советы по уходу за техникой и быть в курсе всех новостей.\n\n"
            "Как подпишетесь — нажмите кнопку ниже 👇",
            reply_markup=get_sub_keyboard(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return

    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "Здравствуйте! Я бот-помощник частного мастера по ремонту стиральных машин в Новосибирске.\n\n"
        "Выберите нужный пункт в меню ниже:",
        reply_markup=kb
    )

@router.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery, state: FSMContext):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        kb = get_admin_keyboard() if callback.from_user.id == ADMIN_ID else main_keyboard
        await callback.message.answer(
            "✅ Спасибо за подписку! Рады видеть вас.\n\nВыберите нужный пункт в меню ниже:",
            reply_markup=kb
        )
    else:
        await callback.answer("❌ Вы еще не подписались на канал. Пожалуйста, подпишитесь, чтобы продолжить!", show_alert=True)

# Главный барьер: проверка подписки перед выполнением любых текстовых команд
@router.message()
async def global_sub_check(message: Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        await message.answer(
            "⚠️ **Для использования бота необходима подписка на канал!**\n\n"
            f"Пожалуйста, подпишитесь на [наш канал мастера]({CHANNEL_INVITE_LINK}), чтобы продолжить работу с ботом:",
            reply_markup=get_sub_keyboard(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return

    text = message.text
    if text == "🔄 В начало":
        await cmd_start(message, state)
    elif text == "ℹ️ О нас":
        await about_us(message)
    elif text == "💰 Прайс":
        await show_price(message)
    elif text == "📜 Мои заказы":
        await show_user_orders(message)
    elif text == "📊 Управление заказами (Админ)":
        await admin_orders_menu(message)
    elif text == "🛠 Оставить заявку":
        await start_order(message, state)
    else:
        current_state = await state.get_state()
        if current_state:
            return
        else:
            kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
            await message.answer("Пожалуйста, воспользуйтесь кнопками меню:", reply_markup=kb)

async def about_us(message: Message):
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "🛠 Частный мастер по ремонту бытовой техники\n\n"
        "• Работаем по всему Новосибирску и области\n"
        "• Быстрый выезд и диагностика\n"
        "• Официальная гарантия на все виды работ\n\n"
        "📞 Телефон для связи: +7 953 804 3048\n"
        "💬 Написать мастеру лично: @za_russia_ru\n\n"
        "Нажмите «🛠 Оставить заявку», чтобы вызвать мастера.",
        reply_markup=kb
    )

async def show_price(message: Message):
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "💰 Прайс-лист на ремонт техники\n\n"
        "Здесь скоро появится актуальный прайс на услуги.\n"
        "По вопросам стоимости вы всегда можете проконсультироваться у мастера: @za_russia_ru",
        reply_markup=kb
    )

async def show_user_orders(message: Message):
    orders = get_user_orders(message.from_user.id)
    if not orders:
        kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
        await message.answer("У вас пока нет активных или выполненных заказов.", reply_markup=kb)
        return

    for order in orders:
        o_id, brand, issue, status, price, period, details, completed_at = order
        
        text = (
            f"🔹 **Заказ №{o_id}**\n"
            f"🏷 Марка: {brand}\n"
            f"⚠️ Проблема: {issue}\n"
            f"📌 Статус: **{status}**\n"
        )
        if price:
            text += f"💰 Сумма: {price} руб.\n"
            text += f"🔧 Работы: {details}\n"
        
        markup = None
        if status == "Оплачено / Выполнено" and completed_at:
            rem_days, total_days = calculate_warranty_days(completed_at, period)
            text += (
                f"\n📜 **ОФИЦИАЛЬНЫЙ ГАРАНТИЙНЫЙ ТАЛОН**\n"
                f"📅 Дата выдачи: {completed_at}\n"
                f"🛡 Срок гарантии: {period}\n"
                f"⏳ **Осталось дней гарантии: {rem_days} из {total_days} дн.**\n"
                f"🟢 Статус: Действует\n"
            )
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛡 Обратиться по гарантии", callback_data=f"warranty_claim_{o_id}")],
                [InlineKeyboardButton(text="🛠 Создать новую заявку", callback_data="new_order_from_history")]
            ])
        
        text += "-------------------------\n"
        if markup:
            await message.answer(text, reply_markup=markup, parse_mode="Markdown")
        else:
            await message.answer(text, parse_mode="Markdown")

@router.callback_query(F.data.startswith("warranty_claim_"))
async def warranty_claim_callback(callback: CallbackQuery):
    order_id = callback.data.split("_")[2]
    order = get_order_by_id(order_id)
    user = callback.from_user
    
    completed_date = order[12]
    period = order[10]
    rem_days, total_days = calculate_warranty_days(completed_date, period)

    admin_claim_text = (
        f"🚨 **ОБРАЩЕНИЕ ПО ГАРАНТИИ!**\n\n"
        f"🆔 Заказ №{order_id}\n"
        f"👤 Клиент: {user.first_name} (@{user.username if user.username else 'нет'})\n"
        f"📞 Контакт: {order[7]}\n"
        f"🏷 Марка: {order[4]}\n"
        f"🔧 Выполненные ранее работы: {order[11]}\n"
        f"🛡 Срок гарантии: {period} (Осталось дней: {rem_days} из {total_days})"
    )
    
    confirm_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить получение (связаться)", callback_data=f"confirm_claim_{order_id}_{user.id}")]
    ])

    try:
        await bot.send_message(chat_id=ADMIN_ID, text=admin_claim_text, reply_markup=confirm_markup, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed to send warranty claim to admin: {e}")

    await callback.message.edit_text(
        text=callback.message.text + "\n\n⏳ **Запрос по гарантии отправлен мастеру!** Ожидайте, мастер свяжется с вами.",
        parse_mode="Markdown"
    )
    await callback.answer("Запрос по гарантии отправлен!")

@router.callback_query(F.data.startswith("confirm_claim_"))
async def admin_confirm_claim(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    parts = callback.data.split("_")
    order_id = parts[2]
    user_id = int(parts[3])

    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"🟢 **Мастер успешно уведомлен о вашем обращении по гарантии (Заказ №{order_id})!**\nОн свяжется с вами в ближайшее время.",
            parse_mode="Markdown"
        )
        await callback.message.edit_text(text=callback.message.text + "\n\n✅ Уведомление клиенту отправлено!")
    except Exception as e:
        await callback.message.answer(f"Не удалось отправить уведомление клиенту: {e}")

    await callback.answer("Подтверждено!")

@router.callback_query(F.data == "new_order_from_history")
async def callback_new_order(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Давайте оформим новую заявку.")
    await start_order_by_callback(callback.message, state)
    await callback.answer()

async def start_order_by_callback(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_district)
    await message.answer("Шаг 1 из 5: Выберите ваш район города (или область):", reply_markup=districts_keyboard)

async def admin_orders_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Созвон", callback_data="adm_list_Созвон"),
         InlineKeyboardButton(text="🛠 В работе", callback_data="adm_list_В работе")],
        [InlineKeyboardButton(text="⚠️ Не ответ", callback_data="adm_list_Не ответ"),
         InlineKeyboardButton(text="🟢 Готов", callback_data="adm_list_Готов")],
        [InlineKeyboardButton(text="⏳ Ожидает оплаты", callback_data="adm_list_Ожидает оплаты"),
         InlineKeyboardButton(text="✅ Оплачено", callback_data="adm_list_Оплачено / Выполнено")]
    ])
    await message.answer("📊 Выберите статус заказов, которые хотите просмотреть:", reply_markup=markup)

@router.callback_query(F.data.startswith("adm_list_"))
async def admin_show_status_list(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    status = callback.data.replace("adm_list_", "")
    orders = get_orders_by_status(status)
    
    if not orders:
        await callback.message.answer(f"📭 Нет заказов со статусом: *{status}*", parse_mode="Markdown")
        await callback.answer()
        return

    await callback.message.answer(f"📋 **Список заказов со статусом: {status}**", parse_mode="Markdown")
    for o in orders:
        o_id, u_name, district, brand, issue, contact, price = o
        text = (
            f"🆔 **Заказ №{o_id}**\n"
            f"👤 Клиент: {u_name} ({contact})\n"
            f"📍 Район: {district}\n"
            f"🏷 {brand} | ⚠️ {issue}\n"
        )
        markup = get_admin_order_markup(o_id, status)
        await callback.message.answer(text, reply_markup=markup, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_view_warranty_"))
async def admin_view_warranty(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    order_id = callback.data.split("_")[3]
    order = get_order_by_id(order_id)
    
    completed_date = order[12] if order[12] else datetime.now().strftime("%Y-%m-%d")
    period = order[10] if order[10] else "1 год"
    rem_days, total_days = calculate_warranty_days(completed_date, period)

    client_str = str(order[2]) + " (" + str(order[7]) + ")"
    warranty_ticket = (
        "📜 **ГАРАНТИЙНЫЙ ТАЛОН (Копия для мастера)**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Заказ №: {order_id}\n"
        f"Клиент: {client_str}\n"
        f"Марка: {order[4]}\n"
        f"Работы: {order[11]}\n"
        f"Сумма: {order[9]} руб.\n"
        f"📅 Дата выдачи: {completed_date}\n"
        f"🛡 Срок гарантии: {period}\n"
        f"⏳ **Осталось дней: {rem_days} из {total_days} дн.**\n"
        f"Статус: {order[8]}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    await callback.message.answer(warranty_ticket, parse_mode="Markdown")
    await callback.answer()

async def start_order(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_district)
    await message.answer("Шаг 1 из 5: Выберите ваш район города (или область):", reply_markup=districts_keyboard)

@router.message(RepairOrder.waiting_for_district, F.text == "⬅️ Назад")
async def back_to_start(message: Message, state: FSMContext):
    await cmd_start(message, state)

@router.message(RepairOrder.waiting_for_district)
async def process_district(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(district=message.text)
    await state.set_state(RepairOrder.waiting_for_brand)
    await message.answer("Шаг 2 из 5: Выберите марку вашей стиральной машины из списка или нажмите «✍️ Другая марка»:", reply_markup=brands_keyboard)

@router.message(RepairOrder.waiting_for_brand, F.text == "⬅️ Назад")
async def back_to_district(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_district)
    await message.answer("Шаг 1 из 5: Выберите ваш район города (или область):", reply_markup=districts_keyboard)

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
    await message.answer("Шаг 3 из 5: Выберите проблему из списка или нажмите «✍️ Своя проблема»:", reply_markup=issues_keyboard)

@router.message(RepairOrder.waiting_for_custom_brand, F.text == "⬅️ Назад")
async def back_to_brand(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_brand)
    await message.answer("Шаг 2 из 5: Выберите марку вашей стиральной машины:", reply_markup=brands_keyboard)

@router.message(RepairOrder.waiting_for_custom_brand)
async def process_custom_brand(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(brand=message.text)
    await state.set_state(RepairOrder.waiting_for_issue)
    await message.answer("Шаг 3 из 5: Выберите проблему из списка или нажмите «✍️ Своя проблема»:", reply_markup=issues_keyboard)

@router.message(RepairOrder.waiting_for_issue, F.text == "⬅️ Назад")
async def back_to_brand_choice(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_brand)
    await message.answer("Шаг 2 из 5: Выберите марку вашей стиральной машины:", reply_markup=brands_keyboard)

@router.message(RepairOrder.waiting_for_issue, F.text == "✍️ Своя проблема")
async def custom_issue_prompt(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_custom_issue)
    await message.answer("Опишите проблему своими словами:", reply_markup=ReplyKeyboardRemove())

@router.message(RepairOrder.waiting_for_issue)
async def process_issue_choice(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(issue=message.text)
    await state.set_state(RepairOrder.waiting_for_photo)
    await message.answer("Шаг 4 из 5: Если есть возможность, отправьте фото поломки или панели машины (или нажмите «Пропустить фото»):", reply_markup=skip_keyboard)

@router.message(RepairOrder.waiting_for_custom_issue, F.text == "⬅️ Назад")
async def back_to_issue_choice(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_issue)
    await message.answer("Шаг 3 из 5: Выберите проблему из списка:", reply_markup=issues_keyboard)

@router.message(RepairOrder.waiting_for_custom_issue)
async def process_custom_issue(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(issue=message.text)
    await state.set_state(RepairOrder.waiting_for_photo)
    await message.answer("Шаг 4 из 5: Если есть возможность, отправьте фото поломки или панели машины (или нажмите «Пропустить фото»):", reply_markup=skip_keyboard)

@router.message(RepairOrder.waiting_for_photo, F.text == "⬅️ Назад")
async def back_to_issue(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_issue)
    await message.answer("Шаг 3 из 5: Выберите проблему из списка:", reply_markup=issues_keyboard)

@router.message(RepairOrder.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(RepairOrder.waiting_for_contact)
    await message.answer("Шаг 5 из 5: Пожалуйста, поделитесь контактом в один клик или введите номер телефона вручную:", reply_markup=contact_keyboard)

@router.message(RepairOrder.waiting_for_photo, F.text == "Пропустить фото")
async def skip_photo(message: Message, state: FSMContext):
    await state.update_data(photo=None)
    await state.set_state(RepairOrder.waiting_for_contact)
    await message.answer("Шаг 5 из 5: Пожалуйста, поделитесь контактом в один клик или введите номер телефона вручную:", reply_markup=contact_keyboard)

@router.message(RepairOrder.waiting_for_contact, F.text == "⬅️ Назад")
async def back_to_photo(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_photo)
    await message.answer("Шаг 4 из 5: Отправьте фото или нажмите «Пропустить фото»:", reply_markup=skip_keyboard)

@router.message(RepairOrder.waiting_for_contact, F.contact)
async def process_contact_button(message: Message, state: FSMContext):
    contact = message.contact.phone_number
    await state.update_data(contact=contact)
    await show_preview(message, state)

@router.message(RepairOrder.waiting_for_contact)
async def process_contact_text(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    contact = message.text
    await state.update_data(contact=contact)
    await show_preview(message, state)

async def show_preview(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.preview_order)
    data = await state.get_data()
    
    preview_text = (
        f"📋 **Проверьте вашу заявку:**\n\n"
        f"📍 Район: {data.get('district')}\n"
        f"🏷 Марка: {data.get('brand')}\n"
        f"⚠️ Проблема: {data.get('issue')}\n"
        f"📞 Телефон: {data.get('contact')}\n"
        f"📷 Фото: {'Прикреплено' if data.get('photo') else 'Не прикреплено'}\n\n"
        f"Всё верно?"
    )
    
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Все верно / Отправить"), KeyboardButton(text="❌ Изменить данные")]
        ],
        resize_keyboard=True
    )
    
    if data.get("photo"):
        await message.answer_photo(photo=data.get("photo"), caption=preview_text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer(text=preview_text, reply_markup=markup, parse_mode="Markdown")

@router.message(RepairOrder.preview_order, F.text == "❌ Изменить данные")
async def restart_order_from_preview(message: Message, state: FSMContext):
    await start_order(message, state)

@router.message(RepairOrder.preview_order, F.text == "✅ Все верно / Отправить")
async def confirm_and_send_order(message: Message, state: FSMContext):
    data = await state.get_data()
    district = data.get("district")
    brand = data.get("brand")
    issue = data.get("issue")
    photo = data.get("photo")
    contact = data.get("contact")
    
    user = message.from_user
    username = f"@{user.username}" if user.username else "нет username"

    order_id = save_order(user.id, user.first_name, district, brand, issue, photo, contact)

    admin_text = (
        f"🚨 Новая заявка №{order_id}!\n\n"
        f"📍 Район: {district}\n"
        f"🏷 Марка: {brand}\n"
        f"⚠️ Проблема: {issue}\n"
        f"📞 Контакт: {contact}\n"
        f"👤 Клиент: {user.first_name} ({username})\n\n"
        f"📌 Статус: Новая"
    )

    admin_markup = get_admin_order_markup(order_id, "Новая")

    try:
        if photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=admin_text, reply_markup=admin_markup)
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_markup)
    except Exception as e:
        logging.error(f"Failed to send order to admin: {e}")

    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "Спасибо! Ваша заявка успешно отправлена мастеру. Он свяжется с вами в ближайшее время!",
        reply_markup=kb
    )
    await state.clear()

@router.callback_query(F.data.startswith("status_"))
async def change_status_callback(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    _, order_id, new_status = callback.data.split("_")
    update_order_status(order_id, new_status)
    
    old_text = callback.message.caption if callback.message.photo else callback.message.text
    base_text = old_text.split("📌 Статус:")[0].strip() if "📌 Статус:" in old_text else old_text.strip()
    
    new_admin_text = f"{base_text}\n\n📌 Статус: {new_status}"
    admin_markup = get_admin_order_markup(order_id, new_status)

    if callback.message.photo:
        await callback.message.edit_caption(caption=new_admin_text, reply_markup=admin_markup)
    else:
        await callback.message.edit_text(text=new_admin_text, reply_markup=admin_markup)
        
    await callback.answer(f"Статус изменен на: {new_status}")

@router.callback_query(F.data.startswith("fill_warranty_"))
async def start_fill_warranty(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    order_id = callback.data.split("_")[2]
    await state.update_data(warranty_order_id=order_id)
    await state.set_state(AdminWarrantyFill.waiting_for_price)
    await callback.message.answer(f"Заполнение гарантии для заказа №{order_id}.\nВведите итоговую стоимость ремонта (руб):")
    await callback.answer()

@router.message(AdminWarrantyFill.waiting_for_price)
async def process_warranty_price(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(price=message.text)
    await state.set_state(AdminWarrantyFill.waiting_for_period)
    await message.answer("Укажите срок гарантии (например: 6 месяцев, 1 год, 365 дней):")

@router.message(AdminWarrantyFill.waiting_for_period)
async def process_warranty_period(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(period=message.text)
    await state.set_state(AdminWarrantyFill.waiting_for_details)
    await message.answer("Опишите выполненные работы (например: Замена сливного насоса):")

@router.message(AdminWarrantyFill.waiting_for_details)
async def process_warranty_details(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    order_id = data.get("warranty_order_id")
    price = data.get("price")
    period = data.get("period")
    details = message.text

    update_order_warranty(order_id, price, period, details)
    order = get_order_by_id(order_id)
    user_id = order[1]

    client_payment_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Наличными / Переводом на месте", callback_data=f"pay_cash_{order_id}")],
        [InlineKeyboardButton(text="📤 Я оплатил (сообщить мастеру)", callback_data=f"notify_master_{order_id}")]
    ])

    bill_text = (
        f"🧾 **Счет и гарантия по заказу №{order_id}**\n\n"
        f"🔧 Выполненные работы: {details}\n"
        f"🛡 Срок гарантии: {period}\n"
        f"💰 К оплате: **{price} руб.**\n\n"
        f"💳 **Оплата по СБП:**\n"
        f"• Банк получателя: **Альфа-Банк**\n"
        f"• Получатель: **Ольга В.**\n"
        f"• Номер телефона (нажмите для копирования):\n"
        f"`+79538043048`\n"
        f"• Сумма: `{price} руб.`\n\n"
        f"После оплаты нажмите кнопку ниже 👇"
    )

    try:
        await bot.send_message(chat_id=user_id, text=bill_text, reply_markup=client_payment_markup, parse_mode="Markdown")
        await message.answer(f"✅ Счет и гарантия успешно отправлены клиенту по заказу №{order_id}!")
    except Exception as e:
        await message.answer(f"Ошибка при отправке клиенту: {e}")

    await state.clear()

@router.callback_query(F.data.startswith("pay_cash_"))
async def client_chose_cash(callback: CallbackQuery):
    order_id = callback.data.split("_")[2]
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Сообщить мастеру об оплате", callback_data=f"notify_master_{order_id}")]
    ])
    await callback.message.edit_text(
        text=f"💵 Вы выбрали оплату наличными или переводом мастеру на месте.\n\nПосле расчета нажмите кнопку ниже:",
        reply_markup=markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith("notify_master_"))
async def notify_master(callback: CallbackQuery):
    order_id = callback.data.split("_")[2]
    order = get_order_by_id(order_id)
    
    await callback.message.edit_text(text="⏳ Ожидайте подтверждения оплаты мастером. После проверки вам придет официальный гарантийный талон.")
    
    admin_confirm_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить получение денег", callback_data=f"admin_confirm_pay_{order_id}")]
    ])
    
    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🔔 **Клиент сообщил об оплате по заказу №{order_id}**\nСумма: {order[9]} руб.\nПроверьте поступление и подтвердите оплату:",
        reply_markup=admin_confirm_markup,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_confirm_pay_"))
async def admin_confirm_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    order_id = callback.data.split("_")[3]
    order = get_order_by_id(order_id)
    user_id = order[1]
    
    update_order_status(order_id, "Оплачено / Выполнено")
    completed_date = order[12]
    period = order[10]
    rem_days, total_days = calculate_warranty_days(completed_date, period)

    warranty_ticket = (
        f"📜 **ОФИЦИАЛЬНЫЙ ЭЛЕКТРОННЫЙ ГАРАНТИЙНЫЙ ТАЛОН**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Заказ №: {order_id}\n"
        f"Марка: {order[4]}\n"
        f"Работы: {order[11]}\n"
        f"Сумма: {order[9]} руб.\n"
        f"📅 Дата выдачи: {completed_date}\n"
        f"🛡 Срок гарантии: {period}\n"
        f"⏳ **Осталось дней гарантии: {rem_days} из {total_days} дн.**\n"
        f"Статус: 🟢 ОПЛАЧЕНО И ПОДТВЕРЖДЕНО\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Мастер: Николай (+7 953 804 3048)\n"
        f"Сохраните этот талон. По вопросам гарантии обращайтесь в бот."
    )

    try:
        await bot.send_message(chat_id=user_id, text=warranty_ticket, parse_mode="Markdown")
        await callback.message.edit_text(text=callback.message.text + "\n\n✅ Оплата подтверждена, гарантийный талон выслан клиенту!")
    except Exception as e:
        await callback.message.answer(f"Ошибка отправки талона клиенту: {e}")
        
    await callback.answer("Оплата подтверждена!")

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
