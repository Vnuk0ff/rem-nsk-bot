import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

logging.basicConfig(level=logging.INFO)

TOKEN = "9255429964:AAGPJ8k9el502n_D8QX0SmpmJYvD5G-Pqmw"
ADMIN_ID = 6684594078

bot = Bot(token=TOKEN)



class RepairOrder(StatesGroup):
    waiting_for_brand = State()
    waiting_for_custom_brand = State()
    waiting_for_issues = State()
    waiting_for_description = State()
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_address = State()


BRANDS = [
    "LG",
    "Samsung",
    "Indesit",
    "Hotpoint Ariston",
    "Bosch",
    "Siemens",
    "Другие",
]
ISSUES = [
    "Шумит",
    "Не греет",
    "Не крутит",
    "Не сливает",
    "Трясется",
    "Не работают программы",
    "Не включается",
    "Другое",
]


# Постоянная клавиатура внизу экрана
def get_main_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Оставить заявку"), KeyboardButton(text="ℹ️ О нас")],
            [KeyboardButton(text="🔄 В начало")],
        ],
        resize_keyboard=True,
    )


def get_brands_keyboard():
    keyboard = []
    for brand in BRANDS:
        keyboard.append(
            [InlineKeyboardButton(text=brand, callback_data=f"brand_{brand}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_issues_keyboard(selected_issues):
    keyboard = []
    for issue in ISSUES:
        is_selected = issue in selected_issues
        text = f"✅ {issue}" if is_selected else issue
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=text, callback_data=f"issue_toggle_{issue}"
                )
            ]
        )
    if selected_issues:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="👉 Готово (продолжить)", callback_data="issues_done"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Обработка кнопки «О нас»
@router.message(F.text == "ℹ️ О нас")
async def cmd_about(message: Message, state: FSMContext):
    about_text = (
        "👨‍🔧 О мастере / Сервисный центр\n\n"
        "Здравствуйте! Я частный мастер по профессиональному ремонту и обслуживанию стиральных машин с многолетним опытом работы.\n\n"
        "📍 География работы: Весь город Новосибирск и пригород.\n"
        "⭐ Почему выбирают меня:\n"
        "• Выезд и диагностика — абсолютно бесплатно (при согласии на ремонт).\n"
        "• Ремонт любой сложности на дому у клиента в день обращения.\n"
        "• Честные цены без навязывания лишних услуг и оригинальные запчасти в наличии.\n"
        "• Гарантия на все виды работ.\n\n"
        "📞 Прямой контакт для связи:\n"
        "+7 (953) 804-30-48 (Николай)\n\n"
        "Нажмите «🛠 Оставить заявку» ниже, чтобы вызвать мастера!"
    )
    await message.answer(about_text, reply_markup=get_main_reply_keyboard())


# Обработка кнопки «В начало» или «Оставить заявку» из нижнего меню
@router.message(F.text.in_(["🔄 В начало", "🛠 Оставить заявку"]))
async def cmd_start_or_order(message: Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "👋 Здравствуйте!\n\n"
        "🛠 Служба ремонта и обслуживания стиральных машин\n"
        "📍 Работаем строго по городу Новосибирск и области.\n"
        "🎁 Выезд и диагностика — БЕСПЛАТНО!\n\n"
        "Пожалуйста, выберите марку вашей стиральной машины:"
    )
    await message.answer(
        welcome_text,
        reply_markup=get_brands_keyboard()
    )
    await message.answer(
        "👇 Меню управления:",
        reply_markup=get_main_reply_keyboard()
    )
    await state.set_state(RepairOrder.waiting_for_brand)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    welcome_text = (
        "👋 Здравствуйте!\n\n"
        "🛠 Служба ремонта и обслуживания стиральных машин\n"
        "📍 Работаем строго по городу Новосибирск и области.\n"
        "🎁 Выезд и диагностика — БЕСПЛАТНО!\n\n"
        "Пожалуйста, выберите марку вашей стиральной машины:"
    )
    await message.answer(welcome_text, reply_markup=get_brands_keyboard())
    await message.answer(
        "👇 Используйте кнопки меню внизу при необходимости:",
        reply_markup=get_main_reply_keyboard()
    )
    await state.set_state(RepairOrder.waiting_for_brand)


@router.callback_query(
    RepairOrder.waiting_for_brand, F.data.startswith("brand_")
)
async def process_brand(callback: CallbackQuery, state: FSMContext):
    brand = callback.data.split("_", 1)[1]
    if brand == "Другие":
        await callback.message.edit_text(
            "Пожалуйста, напишите марку вашей стиральной машины в ответном сообщении:"
        )
        await state.set_state(RepairOrder.waiting_for_custom_brand)
    else:
        await state.update_data(brand=brand, issues=[])
        await callback.message.edit_text(
            f"Выбрана марка: {brand}\n\n"
            "Что случилось со стиральной машиной? (Можно выбрать несколько вариантов):",
            reply_markup=get_issues_keyboard([]),
        )
        await state.set_state(RepairOrder.waiting_for_issues)
    await callback.answer()


@router.message(RepairOrder.waiting_for_custom_brand)
async def process_custom_brand(message: Message, state: FSMContext):
    brand = message.text.strip()
    await state.update_data(brand=brand, issues=[])
    await message.answer(
        f"Марка: {brand}\n\n"
        "Что случилось со стиральной машиной? (Можно выбрать несколько вариантов):",
        reply_markup=get_issues_keyboard([]),
    )
    await state.set_state(RepairOrder.waiting_for_issues)


@router.callback_query(
    RepairOrder.waiting_for_issues, F.data.startswith("issue_toggle_")
)
async def process_issues_toggle(callback: CallbackQuery, state: FSMContext):
    action = callback.data.replace("issue_toggle_", "")
    data = await state.get_data()
    selected_issues = data.get("issues", [])

    if action in selected_issues:
        selected_issues.remove(action)
    else:
        selected_issues.append(action)

    await state.update_data(issues=selected_issues)
    await callback.message.edit_reply_markup(
        reply_markup=get_issues_keyboard(selected_issues)
    )
    await callback.answer()


@router.callback_query(
    RepairOrder.waiting_for_issues, F.data == "issues_done"
)
async def process_issues_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_issues = data.get("issues", [])

    if not selected_issues:
        await callback.answer(
            "Выберите хотя бы одну причину!", show_alert=True
        )
        return

    issues_str = ", ".join(selected_issues)
    await state.update_data(issues_str=issues_str)
    await callback.message.edit_text(
        f"Выбранные проблемы: {issues_str}\n\n"
        "💬 Кратко опишите проблему своими словами (текстом или голосовым). Шаг можно пропустить.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить", callback_data="skip_description"
                    )
                ]
            ]
        ),
    )
    await state.set_state(RepairOrder.waiting_for_description)
    await callback.answer()


@router.callback_query(
    RepairOrder.waiting_for_description, F.data == "skip_description"
)
async def skip_description(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description="Не указано")
    await callback.message.edit_text(
        "📸 По желанию вы можете отправить фото стиральной машины.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить фото", callback_data="skip_photo"
                    )
                ]
            ]
        ),
    )
    await state.set_state(RepairOrder.waiting_for_photo)
    await callback.answer()


@router.message(
    RepairOrder.waiting_for_description,
    F.text | F.voice | F.audio | F.video_note,
)
async def process_description(message: Message, state: FSMContext):
    if message.text in ["ℹ️ О нас", "🔄 В начало", "🛠 Оставить заявку"]:
        return

    desc = message.text or "[Голосовое / медиа сообщение]"
    await state.update_data(description=desc)
    await message.answer(
        "📸 Отлично! Теперь по желанию вы можете отправить фото стиральной машины.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⏭ Пропустить фото", callback_data="skip_photo"
                    )
                ]
            ]
        ),
    )
    await state.set_state(RepairOrder.waiting_for_photo)


@router.message(RepairOrder.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo=photo_file_id)
    await message.answer("📝 Напишите, как к вам обращаться (Ваше имя):")
    await state.set_state(RepairOrder.waiting_for_name)


@router.callback_query(
    RepairOrder.waiting_for_photo, F.data == "skip_photo"
)
async def skip_photo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(photo=None)
    await callback.message.edit_text(
        "📝 Напишите, как к вам обращаться (Ваше имя):"
    )
    await state.set_state(RepairOrder.waiting_for_name)
    await callback.answer()


@router.message(RepairOrder.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    if message.text in ["ℹ️ О нас", "🔄 В начало", "🛠 Оставить заявку"]:
        return
    await state.update_data(name=message.text.strip())
    await message.answer(
        "📞 Укажите ваш номер телефона для связи с мастером:"
    )
    await state.set_state(RepairOrder.waiting_for_phone)


@router.message(RepairOrder.waiting_for_phone, F.text)
async def process_phone(message: Message, state: FSMContext):
    if message.text in ["ℹ️ О нас", "🔄 В начало", "🛠 Оставить заявку"]:
        return
    await state.update_data(phone=message.text.strip())
    await message.answer(
        "📍 Укажите ваш адрес (улица, дом, квартира / район):"
    )
    await state.set_state(RepairOrder.waiting_for_address)


@router.message(RepairOrder.waiting_for_address, F.text)
async def process_address(message: Message, state: FSMContext):
    if message.text in ["ℹ️ О нас", "🔄 В начало", "🛠 Оставить заявку"]:
        return
    await state.update_data(address=message.text.strip())
    data = await state.get_data()

    admin_notification = (
        "🚨 НОВАЯ ЗАЯВКА НА РЕМОНТ! 🚨\n\n"
        f"🏷 Марка: {data.get('brand')}\n"
        f"⚙️ Проблема: {data.get('issues_str')}\n"
        f"💬 Описание: {data.get('description')}\n"
        f"👤 Имя: {data.get('name')}\n"
        f"📞 Телефон: <code>{data.get('phone')}</code>\n"
        f"📍 Адрес: {data.get('address')}"
    )

    photo = data.get("photo")
    if photo:
        await bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo,
            caption=admin_notification,
            parse_mode="HTML",
        )
    else:
        await bot.send_message(
            chat_id=ADMIN_ID, text=admin_notification, parse_mode="HTML"
        )

    summary = (
        "✅ Заявка успешно принята!\n\n"
        f"🏷 Марка: {data.get('brand')}\n"
        f"⚙️ Проблема: {data.get('issues_str')}\n"
        f"💬 Описание: {data.get('description')}\n"
        f"👤 Имя: {data.get('name')}\n"
        f"📞 Телефон: {data.get('phone')}\n"
        f"📍 Адрес: {data.get('address')}\n\n"
        "🛠 Мастер свяжется с вами в ближайшее время.\n"
        "⚠️ Если этого не произошло, свяжитесь с ним напрямую по телефону: +7 (953) 804-30-48"
    )

    await message.answer(summary, reply_markup=get_main_reply_keyboard())
    await state.clear()


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
