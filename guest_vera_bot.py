import re
import sqlite3
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


API_TOKEN = "YOUR_BOT_TOKEN"
ADMINS = [111111111, 222222222]  # сюда вставь Telegram ID админов

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())


# ---------- База данных ----------
def init_db():
    conn = sqlite3.connect("vera.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        fullname TEXT,
        phone TEXT,
        source TEXT,
        note TEXT,
        datetime TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_booking(user_id: int, fullname: str, phone: str, source: str, note: str, datetime_str: str):
    conn = sqlite3.connect("vera.db")
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO bookings (user_id, fullname, phone, source, note, datetime)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, fullname, phone, source, note, datetime_str))
    conn.commit()
    conn.close()

def get_bookings():
    conn = sqlite3.connect("vera.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, phone, datetime FROM bookings ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_booking(booking_id: int):
    conn = sqlite3.connect("vera.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()


# ---------- FSM ----------
class BookingFSM(StatesGroup):
    fullname = State()
    phone = State()
    source = State()
    note = State()
    datetime = State()


# ---------- Кнопки ----------
def main_menu(is_admin=False):
    kb = [
        [KeyboardButton(text="📅 Забронировать столик")],
        [KeyboardButton(text="📖 Посмотреть меню")],
        [KeyboardButton(text="📸 Посмотреть фотографии")],
        [KeyboardButton(text="📞 Связаться с нами")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ-меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def back_cancel_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⬅️ Назад"), KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )


# ---------- /start ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    is_admin = message.from_user.id in ADMINS
    await message.answer(
        "Добро пожаловать в кофейню <b>VERA</b>! ☕\n"
        "Для бронирования начнём с Вашего имени и фамилии.\n"
        "Пожалуйста, укажите, как к Вам обращаться:",
        reply_markup=back_cancel_kb()
    )
    await dp.fsm.set_state(message.chat.id, BookingFSM.fullname)


# ---------- FSM шаги ----------
@dp.message(BookingFSM.fullname)
async def process_fullname(message: types.Message, state: FSMContext):
    if message.text in ["❌ Отменить", "⬅️ Назад"]:
        await state.clear()
        await message.answer("Бронирование отменено.", reply_markup=main_menu(message.from_user.id in ADMINS))
        return
    await state.update_data(fullname=message.text)
    await message.answer("📱 Теперь введите номер телефона:", reply_markup=back_cancel_kb())
    await state.set_state(BookingFSM.phone)

@dp.message(BookingFSM.phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Бронирование отменено.", reply_markup=main_menu(message.from_user.id in ADMINS))
        return
    if message.text == "⬅️ Назад":
        await state.set_state(BookingFSM.fullname)
        await message.answer("Введите Ваше имя и фамилию:", reply_markup=back_cancel_kb())
        return
    await state.update_data(phone=message.text)
    await message.answer("🌐 Откуда вы узнали о нас?", reply_markup=back_cancel_kb())
    await state.set_state(BookingFSM.source)

@dp.message(BookingFSM.source)
async def process_source(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Бронирование отменено.", reply_markup=main_menu(message.from_user.id in ADMINS))
        return
    if message.text == "⬅️ Назад":
        await state.set_state(BookingFSM.phone)
        await message.answer("Введите номер телефона:", reply_markup=back_cancel_kb())
        return
    await state.update_data(source=message.text)
    await message.answer("📝 Добавьте примечание (например: количество гостей):", reply_markup=back_cancel_kb())
    await state.set_state(BookingFSM.note)

@dp.message(BookingFSM.note)
async def process_note(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Бронирование отменено.", reply_markup=main_menu(message.from_user.id in ADMINS))
        return
    if message.text == "⬅️ Назад":
        await state.set_state(BookingFSM.source)
        await message.answer("Откуда вы узнали о нас?", reply_markup=back_cancel_kb())
        return
    await state.update_data(note=message.text)
    await message.answer("📅 Введите дату и время бронирования (например: 12.09 18:30):", reply_markup=back_cancel_kb())
    await state.set_state(BookingFSM.datetime)


def normalize_datetime(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[\/\.:-]", " ", text)
    parts = text.split()
    date, time = None, None

    if len(parts) >= 2:
        date, time = parts[0], parts[1]
    elif len(parts) == 1:
        if ":" in parts[0] or len(parts[0]) in [4]:
            time = parts[0]
        else:
            date = parts[0]

    if time:
        time = re.sub(r"(\d{1,2})(\d{2})", r"\1:\2", time) if time.isdigit() else time

    if date:
        d = re.findall(r"\d+", date)
        if len(d) == 2:
            day, month = d
            date = f"{day.zfill(2)}.{month.zfill(2)}.2025"
        elif len(d) == 3:
            day, month, year = d
            date = f"{day.zfill(2)}.{month.zfill(2)}.{year}"

    return f"{date or '??.??.????'} {time or '??:??'}"


@dp.message(BookingFSM.datetime)
async def process_datetime(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer("Бронирование отменено.", reply_markup=main_menu(message.from_user.id in ADMINS))
        return
    if message.text == "⬅️ Назад":
        await state.set_state(BookingFSM.note)
        await message.answer("Введите примечание:", reply_markup=back_cancel_kb())
        return

    normalized = normalize_datetime(message.text)
    if "??" in normalized:
        await message.answer("Не удалось распознать дату или время, попробуйте ещё раз:")
        return

    data = await state.get_data()
    add_booking(
        message.from_user.id,
        data["fullname"],
        data["phone"],
        data["source"],
        data["note"],
        normalized
    )
    await state.clear()
    await message.answer(
        f"✅ Бронирование сохранено!\n\n"
        f"👤 {data['fullname']}\n"
        f"📱 {data['phone']}\n"
        f"🌐 {data['source']}\n"
        f"📝 {data['note']}\n"
        f"📅 {normalized}",
        reply_markup=main_menu(message.from_user.id in ADMINS)
    )


# ---------- Меню ----------
@dp.message(F.text == "📖 Посмотреть меню")
async def show_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Посмотреть меню на сайте", url="https://example.com")],
        [InlineKeyboardButton(text="📋 Посмотреть здесь", callback_data="menu_here")]
    ])
    await message.answer("Выберите способ просмотра меню:", reply_markup=kb)

@dp.callback_query(F.data == "menu_here")
async def menu_here(callback: types.CallbackQuery):
    await callback.message.answer("📋 Здесь позже появится меню.")


# ---------- Фотографии ----------
@dp.message(F.text == "📸 Посмотреть фотографии")
async def show_photos(message: types.Message):
    await message.answer("📸 Фотографии скоро будут добавлены.")


# ---------- Контакты ----------
@dp.message(F.text == "📞 Связаться с нами")
async def contacts(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👩 Управляющая", url="https://t.me/username1")],
        [InlineKeyboardButton(text="👨‍🦱 Бариста", url="https://t.me/username2")]
    ])
    await message.answer("К кому хотите обратиться?", reply_markup=kb)


# ---------- Админ меню ----------
@dp.message(F.text == "🛠 Админ-меню")
async def admin_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Просмотр бронирований")],
            [KeyboardButton(text="✏️ Изменить бронирование"), KeyboardButton(text="🗑 Удалить бронирование")],
            [KeyboardButton(text="⬅️ Назад в меню")]
        ],
        resize_keyboard=True
    )
    await message.answer("🛠 Админ-меню", reply_markup=kb)


@dp.message(F.text == "📋 Просмотр бронирований")
async def view_bookings(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    bookings = get_bookings()
    if not bookings:
        await message.answer("Пока нет бронирований.")
        return
    text = "\n".join([f"#{b[0]} 👤 {b[1]} 📱 {b[2]} 📅 {b[3]}" for b in bookings])
    await message.answer(text)


@dp.message(F.text == "🗑 Удалить бронирование")
async def delete_booking_start(message: types.Message):
    if message.from_user.id not in ADMINS:
        return
    await message.answer("Введите ID бронирования для удаления:")

@dp.message(lambda m: m.text.isdigit() and m.from_user.id in ADMINS)
async def delete_booking_admin(message: types.Message):
    booking_id = int(message.text)
    delete_booking(booking_id)
    await message.answer(f"Бронирование #{booking_id} удалено.")


# ---------- Запуск ----------
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    