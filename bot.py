import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.markdown import hlink

from pyairtable import Table
from datetime import datetime

from config import BOT_TOKEN, AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, ADMINS

# Логирование
logging.basicConfig(level=logging.INFO)

# Airtable
table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

# Бот
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Состояния
class Form(StatesGroup):
    waiting_for_email = State()
    waiting_for_fullname = State()
    waiting_for_knowledge_choice = State()


@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    contact_button = KeyboardButton(text="📱 Отправить номер", request_contact=True)
    kb = ReplyKeyboardMarkup(keyboard=[[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Привет 👋\n\nПеред тем как вступить в канал, оставь, пожалуйста, номер телефона:", reply_markup=kb)


@dp.message(F.contact)
async def get_contact(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer("Теперь введи свой email:")
    await state.set_state(Form.waiting_for_email)


@dp.message(Form.waiting_for_email)
async def get_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text)
    await message.answer("Как вас зовут? Напишите имя и фамилию:")
    await state.set_state(Form.waiting_for_fullname)


@dp.message(Form.waiting_for_fullname)
async def get_fullname(message: Message, state: FSMContext):
    await state.update_data(fullname=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Для себя", callback_data="self")],
        [InlineKeyboardButton(text="📗 Для себя и других", callback_data="both")],
        [InlineKeyboardButton(text="👀 Просто наблюдать", callback_data="observe")]
    ])

    await message.answer("Вы хотите религиозные знания:", reply_markup=keyboard)
    await state.set_state(Form.waiting_for_knowledge_choice)


@dp.callback_query(Form.waiting_for_knowledge_choice)
async def process_choice(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.answer()

    choice_map = {
        "self": "Получать для себя и внедрять их",
        "both": "Получать, внедрять и передавать другим",
        "observe": "Хочу пока просто понаблюдать"
    }

    full_data = {
        "Telegram ID": str(callback.from_user.id),
        "Username": callback.from_user.username or "",
        "Phone": data.get("phone"),
        "Email": data.get("email"),
        "Full Name": data.get("fullname"),
        "Knowledge Intention": choice_map.get(callback.data),
        "Registered At": datetime.now().isoformat()
    }

    table.create(full_data)

    await callback.message.answer(
        "✅ Спасибо! Теперь можешь перейти в наш канал:\n" +
        hlink("👉 Перейти в канал", "https://t.me/dialogistiny_official"),
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()


@dp.message(F.text.startswith("/sendall"))
async def send_all(message: Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У вас нет прав для этой команды.")

    text = message.text.replace("/sendall", "").strip()
    if not text:
        return await message.answer("⚠️ Введите текст рассылки. Пример:\n/sendall Привет, это рассылка!")

    records = table.all()
    success = 0

    for record in records:
        user_id = record['fields'].get("Telegram ID")
        if user_id:
            try:
                await bot.send_message(chat_id=int(user_id), text=text)
                success += 1
            except Exception as e:
                logging.warning(f"Не удалось отправить {user_id}: {e}")

    await message.answer(f"✅ Рассылка завершена. Отправлено {success} сообщений.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))