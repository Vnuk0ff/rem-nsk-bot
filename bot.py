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

class AdminWarrantyFill(StatesGroup):
    waiting_for_order_id = State()
    waiting_for_price = State()
    waiting_for_period = State()
    waiting_for_details = State()

# Главное меню клиента
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="📜 Мои заказы")],
        [KeyboardButton(text="💰 Прайс"), KeyboardButton(text="ℹ️ О нас")],
        [KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

# Админское меню (показывается только тебе в /start)
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
        [KeyboardButton(text="Пригород и область"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

brands_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="LG"), KeyboardButton(text="Samsung"), KeyboardButton(text="Bosch")],
        [KeyboardButton(text="Indesit"), KeyboardButton(text="Ariston"), KeyboardButton(text="Candy")],
        [KeyboardButton(text="✍️ Другая марка"), KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

issues_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚰 Не сливает / не набирает воду")],
        [KeyboardButton(text="🔄 Не крутит барабан / не отжимает")],
        [KeyboardButton(text="⚡️ Не включается / не греет воду")],
        [KeyboardButton(text="🔊 Сильно шумит / стучит / вибрирует")],
        [KeyboardButton(text="✍️ Своя проблема"), KeyboardButton(text="🔄 В начало")]
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

contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)],
        [KeyboardButton(text="🔄 В начало")]
    ],
    resize_keyboard=True
)

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
    """Считает сколько дней осталось до конца гарантии"""
    try:
        completed_date = datetime.strptime(completed_at_str, "%Y-%m-%d")
        # Парсим срок (поддерживаем «X месяцев» или «X год» или просто «365 дней»)
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

def get_admin_order_markup(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
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
    ])

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "Здравствуйте! Я бот-помощник частного мастера по ремонту стиральных машин в Новосибирске.\n\n"
        "Выберите нужный пункт в меню ниже:",
        reply_markup=kb
    )

@router.message(F.text == "🔄 В начало")
async def go_start(message: Message, state: FSMContext):
    await cmd_start(message, state)

@router.message(F.text == "ℹ️ О нас")
async def about_us(message: Message):
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "🛠 Частный мастер по ремонту стиральных машин\n\n"
        "• Работаем по всему Новосибирску и области\n"
        "• Быстрый выезд и диагностика\n"
        "• Гарантия на все виды работ\n\n"
        "📞 Телефон для связи: +7 953 804 3048\n"
        "💬 Написать мастеру лично: @za_russia_ru\n\n"
        "Нажмите «🛠 Оставить заявку», чтобы вызвать мастера.",
        reply_markup=kb
    )

@router.message(F.text == "💰 Прайс")
async def show_price(message: Message):
    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "💰 Прайс-лист на ремонт стиральных машин\n\n"
        "Здесь скоро появится актуальный прайс на услуги.\n"
        "По вопросам стоимости вы всегда можете проконсультироваться у мастера: @za_russia_ru",
        reply_markup=kb
    )

# --- ИСТОРИЯ ЗАКАЗОВ КЛИЕНТА (С ДИНАМИЧЕСКИМ ТАЛОНОМ) ---
@router.message(F.text == "📜 Мои заказы")
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
        
        # Если заказ выполнен и есть гарантия — рисуем интерактивный тапон с днями
        if status == "Оплачено / Выполнено" and completed_at:
            rem_days, total_days = calculate_warranty_days(completed_at, period)
            text += (
                f"\n📜 **ОФИЦИАЛЬНЫЙ ГАРАНТИЙНЫЙ ТАЛОН**\n"
                f"📅 Дата выдачи: {completed_at}\n"
                f"🛡 Срок гарантии: {period}\n"
                f"⏳ **Осталось дней гарантии: {rem_days} из {total_days} дн.**\n"
                f"🟢 Статус: Действует\n"
            )
        text += "-------------------------\n"
        await message.answer(text, parse_mode="Markdown")

# --- АДМИН-ПАНЕЛЬ: ФИЛЬТРАЦИЯ ЗАКАЗОВ ПО СТАТУСАМ ---
@router.message(F.text == "📊 Управление заказами (Админ)")
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
        markup = get_admin_order_markup(o_id)
        await callback.message.answer(text, reply_markup=markup, parse_mode="Markdown")
    await callback.answer()

# --- ЛОГИКА СОЗДАНИЯ ЗАЯВКИ ---
@router.message(F.text == "🛠 Оставить заявку")
async def start_order(message: Message, state: FSMContext):
    await state.set_state(RepairOrder.waiting_for_district)
    await message.answer("Выберите ваш район города (или область):", reply_markup=districts_keyboard)

@router.message(RepairOrder.waiting_for_district)
async def process_district(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(district=message.text)
    await state.set_state(RepairOrder.waiting_for_brand)
    await message.answer("Выберите марку вашей стиральной машины из списка или нажмите «✍️ Другая марка»:", reply_markup=brands_keyboard)

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
    await message.answer("Выберите проблему из списка или нажмите «✍️ Своя проблема»:", reply_markup=issues_keyboard)

@router.message(RepairOrder.waiting_for_custom_brand)
async def process_custom_brand(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(brand=message.text)
    await state.set_state(RepairOrder.waiting_for_issue)
    await message.answer("Выберите проблему из списка или нажмите «✍️ Своя проблема»:", reply_markup=issues_keyboard)

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
    await message.answer("Если есть возможность, отправьте фото поломки или панели машины (или нажмите «Пропустить фото»):", reply_markup=skip_keyboard)

@router.message(RepairOrder.waiting_for_custom_issue)
async def process_custom_issue(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    await state.update_data(issue=message.text)
    await state.set_state(RepairOrder.waiting_for_photo)
    await message.answer("Если есть возможность, отправьте фото поломки или панели машины (или нажмите «Пропустить фото»):", reply_markup=skip_keyboard)

@router.message(RepairOrder.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(RepairOrder.waiting_for_contact)
    await message.answer("Пожалуйста, поделитесь контактом в один клик или введите номер телефона вручную:", reply_markup=contact_keyboard)

@router.message(RepairOrder.waiting_for_photo, F.text == "Пропустить фото")
async def skip_photo(message: Message, state: FSMContext):
    await state.update_data(photo=None)
    await state.set_state(RepairOrder.waiting_for_contact)
    await message.answer("Пожалуйста, поделитесь контактом в один клик или введите номер телефона вручную:", reply_markup=contact_keyboard)

@router.message(RepairOrder.waiting_for_contact, F.contact)
async def process_contact_button(message: Message, state: FSMContext):
    contact = message.contact.phone_number
    await finalize_order(message, state, contact)

@router.message(RepairOrder.waiting_for_contact)
async def process_contact_text(message: Message, state: FSMContext):
    if message.text == "🔄 В начало":
        await cmd_start(message, state)
        return
    contact = message.text
    await finalize_order(message, state, contact)

async def finalize_order(message: Message, state: FSMContext, contact: str):
    data = await state.get_data()
    district = data.get("district")
    brand = data.get("brand")
    issue = data.get("issue")
    photo = data.get("photo")
    
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

    admin_markup = get_admin_order_markup(order_id)

    try:
        if photo:
            await bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=admin_text, reply_markup=admin_markup)
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_markup)
    except Exception as e:
        logging.error(f"Failed to send order to admin: {e}")

    kb = get_admin_keyboard() if message.from_user.id == ADMIN_ID else main_keyboard
    await message.answer(
        "Спасибо! Ваша заявка принята. Мастер свяжется с вами в ближайшее время, если этого не произошло позвоните по телефону +7 953 804 3048",
        reply_markup=kb
    )
    await state.clear()

@router.callback_query(F.data.startswith("status_"))
async def
