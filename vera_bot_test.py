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
API_TOKEN = "8425551477:AAHfzN4dWpK2gE8Qo6hO152ozSvAqr71VuQ"

# 🔐 ID админов
ADMINS = [1077878777, 185307580, 1084846454, 878808566]

# 📦 SQLite база
conn = sqlite3.connect("vera.db")
conn.row_factory = sqlite3.Row
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
cursor.execute("PRAGMA table_info(bookings)")
columns = [col[1] for col in cursor.fetchall()]
if "notes" not in columns:
    cursor.execute("ALTER TABLE bookings ADD COLUMN notes TEXT")
conn.commit()

# ⚙️ FSM для бронирования
class BookingFSM(StatesGroup):
    fullname = State()
    phone = State()
    datetime = State()
    source = State()
    notes = State()


# ⚙️ FSM для редактирования бронирования
class EditBookingFSM(StatesGroup):
    fullname = State()
    phone = State()
    datetime = State()
    source = State()
    notes = State()

# 🤖 Бот
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())


# ========================== Клавиатуры ==========================
def main_menu_inline(is_admin: bool = False) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📅 Забронировать столик", callback_data="main_book")],
        [InlineKeyboardButton(text="📖 Посмотреть меню", callback_data="main_menu")],
        [InlineKeyboardButton(text="📸 Фотографии", callback_data="main_photos")],
        [InlineKeyboardButton(text="📞 Связаться с нами", callback_data="main_contact")],
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="⚙️ Админ меню", callback_data="main_admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def contact_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👩‍💼 Управляющая", url="https://t.me/AnnaBardo_nova")],
            [InlineKeyboardButton(text="👨‍🍳 Бариста", url="https://t.me/Arailon")],
            [InlineKeyboardButton(text="👨‍💻 Технический специалист", url="https://t.me/Arailon")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ]
    )


def admin_menu_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 Просмотр бронирований", callback_data="adm_view_bookings")],
            [InlineKeyboardButton(text="✏️ Изменить бронирование", callback_data="adm_edit_booking")],
            [InlineKeyboardButton(text="🗑 Удалить бронирование", callback_data="adm_delete_booking")],
            [InlineKeyboardButton(text="🍽 Меню (управление)", callback_data="adm_menu_manage")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
        ]
    )


# ========================== Хендлеры ==========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    is_admin = message.from_user.id in ADMINS
    await message.answer(
        "Добро пожаловать в кофейню <b>VERA</b>! ☕️\n\nВыберите действие из меню:",
        reply_markup=main_menu_inline(is_admin)
    )



# ----------- Гостевое меню -----------
@dp.message(F.text == "📞 Связаться с нами")
async def contact_us(message: types.Message):
    await message.answer("К кому хотите обратиться?", reply_markup=contact_kb())

@dp.callback_query(F.data == "main_contact")
async def contact_us_cb(call: types.CallbackQuery):
    await call.message.edit_text("К кому хотите обратиться?", reply_markup=contact_kb())

@dp.callback_query(F.data == "back_main")
async def back_main(call: types.CallbackQuery):
    is_admin = call.from_user.id in ADMINS
    await call.message.edit_text("🔙 Главное меню", reply_markup=main_menu_inline(is_admin))

@dp.callback_query(F.data == "menu_here")
async def show_menu_categories(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🥗 Еда", callback_data="menu_food")],
            [InlineKeyboardButton(text="🍹 Напитки", callback_data="menu_drinks")],
            [InlineKeyboardButton(text="🍰 Десерты", callback_data="menu_desserts")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ]
    )
    await call.message.edit_text("Выберите категорию меню:", reply_markup=kb)

@dp.message(F.text == "📖 Посмотреть меню")
async def view_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Посмотреть меню на сайте", url="https://veracoffeetea.com/?ysclid=mesnxzcdcm560404876")],
            [InlineKeyboardButton(text="📋 Посмотреть здесь", callback_data="menu_here")]
        ]
    )
    await message.answer("Выберите способ:", reply_markup=kb)

@dp.callback_query(F.data == "menu_food")
async def show_food(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🥪 Тост с ветчиной и сыром", callback_data="item_1")],
            [InlineKeyboardButton(text="🥗 Veggie Bowl", callback_data="item_2")],
            [InlineKeyboardButton(text="🥪 Кето-бейгл", callback_data="item_3")],
            [InlineKeyboardButton(text="🥪 Бриошь с пастрами", callback_data="item_4")],
            [InlineKeyboardButton(text="🥪 Кето-гранола", callback_data="item_5")],
            [InlineKeyboardButton(text="🥪 Скрэмбл", callback_data="item_6")],
            [InlineKeyboardButton(text="🥪 Бриошь с пастрами", callback_data="item_7")],
            [InlineKeyboardButton(text="🥪 Кето-Чизкейк", callback_data="item_8")],
            [InlineKeyboardButton(text="🥪 Куриная грудка су-вид", callback_data="item_9")],
            [InlineKeyboardButton(text="🥪 Бургер 3 вида сыра", callback_data="item_10")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_here")]
        ]
    )
    await call.message.edit_text("🥗 <b>Еда</b>:", reply_markup=kb)

@dp.message(F.text == "📸 Фотографии")
async def view_photos(message: types.Message):
    await message.answer("📸 Фотографии появятся здесь позже!")

@dp.callback_query(F.data == "main_photos")
async def main_photos_cb(call: types.CallbackQuery):
    await call.message.edit_text("📸 Фотографии появятся здесь позже!", reply_markup=main_menu_inline(call.from_user.id in ADMINS))

# ----------- Бронирование -----------
@dp.message(F.text == "📅 Забронировать столик")
async def booking_start(message: types.Message, state: FSMContext):
    await message.answer("Давайте знакомиться! Введите Ваше имя и фамилию:")
    await state.set_state(BookingFSM.fullname)


@dp.message(BookingFSM.fullname)
async def booking_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await message.answer("📞 Введите номер телефона:")
    await state.set_state(BookingFSM.phone)


@dp.message(BookingFSM.phone)
async def booking_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("📅 Когда планируете нас посетить? (например: 28.08 15:30):")
    await state.set_state(BookingFSM.datetime)


@dp.message(BookingFSM.datetime)
async def booking_datetime(message: types.Message, state: FSMContext):
    await state.update_data(datetime=message.text)
    await message.answer("📌 Откуда узнали о нас? (Instagram, друзья и т.п.):")
    await state.set_state(BookingFSM.source)


@dp.message(BookingFSM.source)
async def booking_source(message: types.Message, state: FSMContext):
    await state.update_data(source=message.text)
    await message.answer("📝 Ваши пожелания:")
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

    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"🌿 <b>Новое бронирование!</b> 🌿\n\n"
                f"👤 {fullname}\n"
                f"📞 {phone}\n"
                f"📅 {datetime_val}\n"
                f"📌 {source}\n"
                f"📝 {notes}"
            )
        except Exception as e:
            print(f"Не удалось отправить админу {admin_id}: {e}")

    await state.clear()


# ----------- Админ меню -----------
@dp.message(F.text == "⚙ Админ меню")
async def admin_menu(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У вас нет доступа")
    await message.answer("⚙ Админ меню", reply_markup=admin_menu_kb())

@dp.callback_query(F.data == "main_admin")
async def main_admin_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        return await call.answer("⛔️ Нет доступа", show_alert=True)
    await call.message.edit_text("⚙️ Админ меню", reply_markup=admin_menu_inline())


@dp.message(F.data == "m")
async def view_bookings_cb(call: types.CallbackQuery):
    cursor.execute("SELECT * FROM bookings")
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📭 Пока нет бронирований.")

    for row in rows:
        text = (
            f"🔖 ID: {row['id']}\n"
            f"👤 {row['fullname']}\n"
            f"📞 {row['phone']}\n"
            f"📅 {row['datetime']}\n"
            f"📌 {row['source']}\n"
            f"📝 {row['notes']}"
        )
        await message.answer(text)




# ----------- Изменение бронирования -----------
@dp.message(F.text == "✏ Изменить бронирование")
async def edit_booking(message: types.Message):
    cursor.execute("SELECT id, fullname, datetime FROM bookings")
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("📭 Нет бронирований для изменения.")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{r['id']} | {r['fullname']} ({r['datetime']})", callback_data=f"edit_{r['id']}")] for r in rows
        ]
    )
    await message.answer("Выберите бронирование для изменения:", reply_markup=kb)


@dp.callback_query(F.data.startswith("edit_"))
async def process_edit(call: types.CallbackQuery, state: FSMContext):
    booking_id = int(call.data.split("_")[1])
    await state.update_data(edit_id=booking_id)

    # Загружаем текущие данные
    cursor.execute("SELECT * FROM bookings WHERE id=?", (booking_id,))
    row = cursor.fetchone()
    if not row:
        return await call.message.edit_text("❌ Бронирование не найдено.")

    await call.message.edit_text(
        f"✏ Изменение бронирования #{booking_id}\n\n"
        f"👤 {row['fullname']}\n"
        f"📞 {row['phone']}\n"
        f"📅 {row['datetime']}\n"
        f"📌 {row['source']}\n"
        f"📝 {row['notes']}\n\n"
        f"Отправьте новое <b>имя</b> (или напишите 'пропустить')"
    )
    await state.set_state(EditBookingFSM.fullname)


@dp.message(EditBookingFSM.fullname)
async def edit_fullname(message: types.Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data["edit_id"]

    if message.text.lower() != "пропустить":
        cursor.execute("UPDATE bookings SET fullname=? WHERE id=?", (message.text, booking_id))
        conn.commit()

    await message.answer("📞 Введите новый телефон (или 'пропустить'):")
    await state.set_state(EditBookingFSM.phone)


@dp.message(EditBookingFSM.phone)
async def edit_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data["edit_id"]

    if message.text.lower() != "пропустить":
        cursor.execute("UPDATE bookings SET phone=? WHERE id=?", (message.text, booking_id))
        conn.commit()

    await message.answer("📅 Введите новую дату и время (или 'пропустить'):")
    await state.set_state(EditBookingFSM.datetime)


@dp.message(EditBookingFSM.datetime)
async def edit_datetime(message: types.Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data["edit_id"]

    if message.text.lower() != "пропустить":
        cursor.execute("UPDATE bookings SET datetime=? WHERE id=?", (message.text, booking_id))
        conn.commit()

    await message.answer("📌 Введите новый источник (или 'пропустить'):")
    await state.set_state(EditBookingFSM.source)


@dp.message(EditBookingFSM.source)
async def edit_source(message: types.Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data["edit_id"]

    if message.text.lower() != "пропустить":
        cursor.execute("UPDATE bookings SET source=? WHERE id=?", (message.text, booking_id))
        conn.commit()

    await message.answer("📝 Введите новые заметки (или 'пропустить'):")
    await state.set_state(EditBookingFSM.notes)


@dp.message(EditBookingFSM.notes)
async def edit_notes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    booking_id = data["edit_id"]

    if message.text.lower() != "пропустить":
        cursor.execute("UPDATE bookings SET notes=? WHERE id=?", (message.text, booking_id))
        conn.commit()

    await message.answer(f"✅ Бронирование ID {booking_id} обновлено.")
    await state.clear()


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
async def back_to_menu_legacy(message: types.Message):
    # Оставляем для совместимости со старыми кнопками, можно удалить позже
    is_admin = message.from_user.id in ADMINS
    await message.answer("🔙 Главное меню", reply_markup=main_menu_inline(is_admin))

@dp.callback_query(F.data == "back_main")
async def back_main(call: types.CallbackQuery):
    is_admin = call.from_user.id in ADMINS
    await call.message.edit_text("🔙 Главное меню", reply_markup=main_menu_inline(is_admin))


# ========================== RUN ==========================
async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
