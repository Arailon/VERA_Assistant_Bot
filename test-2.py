import asyncio
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 🔑 Токен
API_TOKEN = "YOUR_TOKEN"

# 🔐 Уровни доступа
ROLE_GUEST = "guest"
ROLE_STAFF = "staff"
ROLE_ADMIN = "admin"

# 📦 SQLite база
conn = sqlite3.connect("vera.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Таблицы
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    role TEXT DEFAULT 'guest'
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT,
    phone TEXT,
    datetime TEXT,
    source TEXT,
    notes TEXT,
    user_id INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    price REAL DEFAULT 0,
    category TEXT DEFAULT 'Еда',
    is_active INTEGER DEFAULT 1
)
""")
conn.commit()

# FSM
class BookingFSM(StatesGroup):
    fullname = State()
    phone = State()
    datetime = State()
    source = State()
    notes = State()

class EditMenuFSM(StatesGroup):
    waiting_field = State()
    waiting_value = State()

# 🤖 Бот
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

# ========================== Помощники ==========================
def get_role(user_id: int) -> str:
    cursor.execute("SELECT role FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row["role"] if row else ROLE_GUEST

def set_role(user_id: int, role: str):
    cursor.execute("INSERT OR REPLACE INTO users(user_id, role) VALUES(?, ?)", (user_id, role))
    conn.commit()

# ========================== Кнопки ==========================
def main_menu_inline(role: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📅 Забронировать столик", callback_data="main_book")],
        [InlineKeyboardButton(text="📖 Посмотреть меню", callback_data="main_menu")],
        [InlineKeyboardButton(text="📞 Связаться с нами", callback_data="main_contact")],
    ]
    if role in (ROLE_STAFF, ROLE_ADMIN):
        kb.append([InlineKeyboardButton(text="🍽 Меню (управление)", callback_data="adm_menu_manage")])
    if role == ROLE_ADMIN:
        kb.append([InlineKeyboardButton(text="⚙️ Админ меню", callback_data="main_admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_menu_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Просмотр бронирований", callback_data="adm_view_bookings")],
        [InlineKeyboardButton(text="👤 Назначить роль", callback_data="adm_roles")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])

# ========================== START ==========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    role = get_role(message.from_user.id)
    if role == ROLE_GUEST:
        set_role(message.from_user.id, ROLE_GUEST)
    await message.answer(
        "Добро пожаловать в кофейню <b>VERA</b>! ☕️\n\nВыберите действие:",
        reply_markup=main_menu_inline(role)
    )

# ========================== Меню ==========================
@dp.callback_query(F.data == "main_menu")
async def menu_choice(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Посмотреть на сайте", url="https://veracoffeetea.com")],
            [InlineKeyboardButton(text="📋 Посмотреть здесь", callback_data="menu_here")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ]
    )
    await call.message.edit_text("Выберите способ просмотра меню:", reply_markup=kb)

@dp.callback_query(F.data == "menu_here")
async def menu_here(call: types.CallbackQuery):
    cursor.execute("SELECT DISTINCT category FROM menu_items WHERE is_active=1")
    cats = [r["category"] for r in cursor.fetchall()]
    if not cats:
        return await call.message.edit_text("Пока нет блюд.", reply_markup=main_menu_inline(get_role(call.from_user.id)))
    kb = [[InlineKeyboardButton(text=cat, callback_data=f"menu_cat_{cat}")] for cat in cats]
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    await call.message.edit_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ========================== Бронирования ==========================
async def validate_datetime(input_text: str) -> tuple[bool, str]:
    try:
        dt = datetime.strptime(input_text, "%d.%m %H:%M")
        dt = dt.replace(year=datetime.now().year)
    except ValueError:
        return False, "⛔ Неверный формат даты. Введите как: 28.08 15:30"

    now = datetime.now()
    if dt < now:
        return False, "⛔ Выберите дату позже текущей."
    if not (8 <= dt.hour < 21):
        return False, "⛔ Мы принимаем брони только с 08:00 до 21:00."
    return True, dt.isoformat()

@dp.message(BookingFSM.datetime)
async def booking_datetime(message: types.Message, state: FSMContext):
    ok, res = await validate_datetime(message.text)
    if not ok:
        return await message.answer(res)
    await state.update_data(datetime=res)
    await state.set_state(BookingFSM.source)
    await message.answer("📌 Откуда узнали о нас?")

# ========================== Напоминания ==========================
async def remind_booking():
    now = datetime.now()
    cursor.execute("SELECT * FROM bookings")
    for row in cursor.fetchall():
        try:
            dt = datetime.fromisoformat(row["datetime"])
            if dt - timedelta(hours=1) < now < dt - timedelta(minutes=59):
                await bot.send_message(row["user_id"], f"⏰ Напоминание! Ваше бронирование через час:\n\n👤 {row['fullname']}\n📅 {row['datetime']}")
        except:
            pass

async def morning_digest():
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM bookings WHERE datetime LIKE ?", (f"{today}%",))
    rows = cursor.fetchall()
    if not rows:
        return
    text = "📋 Список гостей на сегодня:\n\n"
    text += "\n\n".join([f"👤 {r['fullname']} — {r['datetime']}" for r in rows])
    # Отправляем только админам
    cursor.execute("SELECT user_id FROM users WHERE role='admin'")
    for u in cursor.fetchall():
        await bot.send_message(u["user_id"], text)

# ========================== Админ меню ==========================
@dp.callback_query(F.data == "main_admin")
async def admin_panel(call: types.CallbackQuery):
    if get_role(call.from_user.id) != ROLE_ADMIN:
        return await call.answer("⛔ Нет доступа", show_alert=True)
    await call.message.edit_text("⚙️ Админ меню", reply_markup=admin_menu_inline())

@dp.callback_query(F.data == "adm_roles")
async def adm_roles(call: types.CallbackQuery):
    if get_role(call.from_user.id) != ROLE_ADMIN:
        return await call.answer("⛔ Нет доступа", show_alert=True)
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    text = "Пользователи и их роли:\n\n"
    for r in rows:
        text += f"{r['user_id']} — {r['role']}\n"
    await call.message.edit_text(text)

# ========================== RUN ==========================
async def main():
    print("🤖 Бот запущен...")
    scheduler.add_job(remind_booking, "interval", minutes=1)
    scheduler.add_job(morning_digest, "cron", hour=7, minute=50)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())