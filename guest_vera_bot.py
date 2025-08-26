import re
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties


API_TOKEN = "YOUR_BOT_TOKEN"

# aiogram 3.7+ — parse_mode задаётся так:
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ---------- База данных ----------
def init_db():
    conn = sqlite3.connect("vera.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        fullname TEXT,
        datetime TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_booking(user_id: int, fullname: str, datetime_str: str):
    conn = sqlite3.connect("vera.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO bookings (user_id, fullname, datetime) VALUES (?, ?, ?)",
                   (user_id, fullname, datetime_str))
    conn.commit()
    conn.close()


# ---------- Главное меню ----------
def main_menu():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Забронировать столик")],
            [KeyboardButton(text="📖 Посмотреть меню")],
            [KeyboardButton(text="📸 Посмотреть фотографии")],
            [KeyboardButton(text="📞 Связаться с нами")]
        ],
        resize_keyboard=True
    )
    return kb


# ---------- /start ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать в кофейню <b>VERA</b>! ☕\nВыберите действие:",
        reply_markup=main_menu()
    )


# ---------- Бронирование ----------
@dp.message(F.text == "📅 Забронировать столик")
async def booking_start(message: types.Message):
    await message.answer("Введите дату и время бронирования (например: <i>12.09 18:30</i>):")


def normalize_datetime(text: str) -> str:
    """Форматируем дату и время в единый вид: ДД.ММ.ГГГГ ЧЧ:ММ"""
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


@dp.message()
async def handle_booking_input(message: types.Message):
    text = message.text.strip()
    normalized = normalize_datetime(text)

    if "??" not in normalized:  # если дата корректна
        fullname = message.from_user.full_name
        add_booking(message.from_user.id, fullname, normalized)
        await message.answer(
            f"Ваше бронирование: <b>{normalized}</b>\n"
            f"Спасибо, {fullname}! Мы свяжемся с вами для подтверждения ✅"
        )
    else:
        await message.answer("Не удалось распознать дату или время, попробуйте ещё раз.")


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


# ---------- Запуск ----------
async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())