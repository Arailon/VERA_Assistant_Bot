import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# 🔑 Токен
API_TOKEN = "8425551477:AAHkLE1-90-AefcRnr0IVV9jgOgVHomhVD4"

# 🔐 ID админов
ADMINS = [1077878777]

# 📦 SQLite база
conn = sqlite3.connect("vera.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT,
    phone TEXT,
    datetime TEXT,
    source TEXT,
    notes TEXT
)
""")
conn.commit()

# ⚙️ FSM для бронирования
class BookingFSM(StatesGroup):
    fullname = State()
    phone = State()
    datetime = State()
    source = State()
    notes = State()

# 🤖 Бот
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())


# ========================== Клавиатуры ==========================
def main_menu(is_admin=False):
    kb = [
        [KeyboardButton(text="📅 Забронировать столик")],
        [KeyboardButton(text="📖 Посмотреть меню")],
        [KeyboardButton(text="📸 Фотографии")],
        [KeyboardButton(text="📞 Связаться с нами")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙ Админ меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def contact_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👩‍💼 Управляющая", url="https://t.me/AnnaBardo_nova")],
            [KeyboardButton(text="👨‍🍳 Бариста", url="https://t.me/Arailon")],
            [KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )


def admin_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 Просмотр бронирований")],
            [KeyboardButton(text="✏ Изменить бронирование"), KeyboardButton(text="🗑 Удалить бронирование")],
            [KeyboardButton(text="🔙 Назад в меню")]
        ],
        resize_keyboard=True
    )


# ========================== Хендлеры ==========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    is_admin = message.from_user.id in ADMINS
    await message.answer(
        "Добро пожаловать в кофейню <b>VERA</b>! ☕\n\nВыберите действие из меню:",
        reply_markup=main_menu(is_admin)
    )


# ----------- Гостевое меню -----------
@dp.message(F.text == "📞 Связаться с нами")
async def contact_us(message: types.Message):
    await message.answer("К кому хотите обратиться?", reply_markup=contact_kb())


@dp.message(F.text == "📖 Посмотреть меню")
async def view_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Посмотреть меню на сайте", url="https://example.com")],
            [InlineKeyboardButton(text="📋 Посмотреть здесь", callback_data="menu_here")]
        ]
    )
    await message.answer("Выберите способ:", reply_markup=kb)


@dp.message(F.text == "📸 Фотографии")
async def view_photos(message: types.Message):
    await message.answer("📸 Фотографии появятся здесь позже!")


# ----------- Бронирование -----------
@dp.message(F.text == "📅 Забронировать столик")
async def booking_start(message: types.Message, state: FSMContext):
    await message.answer("Введите Ваше имя и фамилию:")
    await state.set_state(BookingFSM.fullname)


@dp.message(BookingFSM.fullname)
async def booking_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("📞 Введите номер телефона:")
    await state.set_state(BookingFSM.phone)


@dp.message(BookingFSM.phone)
async def booking_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("📅 Введите дату и время (например: 28.08.2025 15:30):")
    await state.set_state(BookingFSM.datetime)


@dp.message(BookingFSM.datetime)
async def booking_datetime(message: types.Message, state: FSMContext):
    await state.update_data(datetime=message.text)
    await message.answer("📌 Укажите, откуда Вы узнали о нас (Instagram, друзья и т.п.):")
    await state.set_state(BookingFSM.source)


@dp.message(BookingFSM.source)
async def booking_source(message: types.Message, state: FSMContext):
    await state.update_data(source=message.text)
    await message.answer("📝 Добавьте заметки (или напишите - нет):")
    await state.set_state(BookingFSM.notes)


@dp.message(BookingFSM.notes)
async def booking_notes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fullname = data["fullname"]
    phone = data["phone"]
    datetime_val = data["datetime"]
    source = data["source"]
    notes = message.text

    cursor.execute("INSERT INTO bookings (fullname, phone, datetime, source, notes) VALUES (?, ?, ?, ?, ?)",
                   (fullname, phone, datetime_val, source, notes))
    conn.commit()

    await message.answer(
        f"✅ Бронирование сохранено!\n\n"
        f"👤 <b>{fullname}</b>\n"
        f"📞 {phone}\n"
        f"📅 {datetime_val}\n"
        f"📌 {source}\n"
        f"📝 {notes}"
    )

    await state.clear()


# ----------- Админ меню -----------
@dp.message(F.text == "⚙ Админ меню")
async def admin_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У вас нет доступа")
    await message.answer("⚙ Админ меню", reply_markup=admin_menu_kb())


@dp.message(F.text == "📖 Просмотр бронирований")
async def view_bookings(message: types.Message):
    cursor.execute("SELECT * FROM bookings")
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📭 Пока нет бронирований.")

    for row in rows:
        booking_id, fullname, phone, datetime_val, source, notes = row
        text = (
            f"🔖 ID: {booking_id}\n"
            f"👤 {fullname}\n"
            f"📞 {phone}\n"
            f"📅 {datetime_val}\n"
            f"📌 {source}\n"
            f"📝 {notes}"
        )
        await message.answer(text)


@dp.message(F.text == "✏ Изменить бронирование")
async def edit_booking(message: types.Message):
    cursor.execute("SELECT id, fullname, datetime FROM bookings")
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📭 Нет бронирований для изменения.")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{r[0]} | {r[1]} ({r[2]})", callback_data=f"edit_{r[0]}")] for r in rows
        ]
    )
    await message.answer("Выберите бронирование для изменения:", reply_markup=kb)


@dp.message(F.text == "🗑 Удалить бронирование")
async def delete_booking(message: types.Message):
    cursor.execute("SELECT id, fullname, datetime FROM bookings")
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📭 Нет бронирований для удаления.")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{r[0]} | {r[1]} ({r[2]})", callback_data=f"delete_{r[0]}")] for r in rows
        ]
    )
    await message.answer("Выберите бронирование для удаления:", reply_markup=kb)


@dp.callback_query(F.data.startswith("delete_"))
async def process_delete(call: types.CallbackQuery):
    booking_id = int(call.data.split("_")[1])
    cursor.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    await call.message.edit_text(f"❌ Бронирование ID {booking_id} удалено.")


# ----------- Назад в меню -----------
@dp.message(F.text == "🔙 Назад в меню")
async def back_to_menu(message: types.Message):
    is_admin = message.from_user.id in ADMINS
    await message.answer("🔙 Главное меню", reply_markup=main_menu(is_admin))


# ========================== RUN ==========================
async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
