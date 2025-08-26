import re
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

API_TOKEN = "YOUR_BOT_TOKEN"

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher()


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
    
    # Заменим все разделители на пробел
    text = re.sub(r"[\/\.:-]", " ", text)

    parts = text.split()
    date, time = None, None

    # Дата
    if len(parts) >= 2:
        date = parts[0]
        time = parts[1]
    elif len(parts) == 1:
        if ":" in parts[0] or len(parts[0]) in [4]:  # 1830 → 18:30
            time = parts[0]
        else:
            date = parts[0]

    # Формат времени
    if time:
        time = re.sub(r"(\d{1,2})(\d{2})", r"\1:\2", time) if time.isdigit() else time

    # Формат даты
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
    if any(word in message.text for word in ["забронировать", "стол", "место"]):
        return  # чтобы не ловило случайные сообщения

    normalized = normalize_datetime(message.text)
    if "??" not in normalized:
        await message.answer(f"Ваше бронирование: <b>{normalized}</b>\nМы свяжемся с вами для подтверждения ✅")
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())