import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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

# Таблица бронирований
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
# Таблица меню
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

# seed menu (если пусто)
cursor.execute("SELECT COUNT(*) AS c FROM menu_items")
if cursor.fetchone()["c"] == 0:
    items = [
        ("Тост с ветчиной и сыром", "Хрустящий тост с ветчиной и плавленым сыром", 290, "Еда"),
        ("Veggie Bowl", "Овощной боул с соусом", 350, "Еда"),
        ("Кето-бейгл", "Низкоуглеводный бейгл", 320, "Еда"),
        ("Бриошь с пастрами", "Нежная бриошь с пастрами", 420, "Еда"),
    ]
    cursor.executemany("INSERT INTO menu_items(title, description, price, category) VALUES(?,?,?,?)", items)
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

# ⚙️ FSM для редактирования меню
class EditMenuFSM(StatesGroup):
    waiting_field = State()
    waiting_value = State()

# 🤖 Бот
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# ========================== Inline клавиатуры ==========================
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

def contact_kb() -> InlineKeyboardMarkup:
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
            [InlineKeyboardButton(text="🍽 Меню (управление)", callback_data="adm_menu_manage")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
        ]
    )

def bookings_item_kb(bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit_{bid}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"askdel_{bid}")
        ]
    ])

def confirm_del_kb(bid: int, return_to: str = None) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_{bid}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data=return_to or "adm_view_bookings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# Навигационные кнопки для бронирования
BOOK_ORDER = ["fullname", "phone", "datetime", "source", "notes"]
PREV = {step: (BOOK_ORDER[i-1] if i > 0 else None) for i, step in enumerate(BOOK_ORDER)}

def nav_kb(step: str, allow_skip: bool = False) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text="⬅ Назад", callback_data=f"book_back_{step}")]
    if allow_skip:
        row.append(InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"book_skip_{step}"))
    kb = [row, [InlineKeyboardButton(text="❌ Отмена", callback_data="book_cancel")]]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ========================== Помощники ==========================
async def _ask_step(message_or_call, state: FSMContext, step: str):
    prompts = {
        "fullname": "Давайте знакомиться! Введите Ваше имя и фамилию:",
        "phone": "📞 Введите номер телефона:",
        "datetime": "📅 Когда планируете нас посетить? (например: 28.08 15:30):",
        "source": "📌 Откуда узнали о нас? (Instagram, друзья и т.п.):",
        "notes": "📝 Ваши пожелания:",
    }
    allow_skip = step in ("source", "notes")
    await state.set_state(getattr(BookingFSM, step))
    text = prompts[step]
    kb = nav_kb(step, allow_skip=allow_skip)

    if isinstance(message_or_call, types.CallbackQuery):
        await message_or_call.message.edit_text(text, reply_markup=kb)
    else:
        await message_or_call.answer(text, reply_markup=kb)

async def _save_booking_and_finish(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    fullname = data.get("fullname", "")
    phone = data.get("phone", "")
    datetime_val = data.get("datetime", "")
    source = data.get("source", "")
    notes = data.get("notes", "")

    cursor.execute(
        "INSERT INTO bookings (fullname, phone, datetime, source, notes) VALUES (?, ?, ?, ?, ?)",
        (fullname, phone, datetime_val, source, notes)
    )
    conn.commit()

    text = (f"✅ Бронирование сохранено!\n\n"
            f"👤 <b>{fullname}</b>\n"
            f"📞 {phone}\n"
            f"📅 {datetime_val}\n"
            f"📌 {source}\n"
            f"📝 {notes}")

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, reply_markup=main_menu_inline(event.from_user.id in ADMINS))
    else:
        await event.answer(text)
        await event.answer("🔙 Главное меню", reply_markup=main_menu_inline(event.from_user.id in ADMINS))

    # Уведомляем админов
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

# ========================== Хендлеры ==========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    is_admin = message.from_user.id in ADMINS
    await message.answer(
        "Добро пожаловать в кофейню <b>VERA</b>! ☕️\n\nВыберите действие из меню:",
        reply_markup=main_menu_inline(is_admin)
    )

# ---------- Главное меню / контакты / фото ----------
@dp.callback_query(F.data == "main_contact")
async def contact_us_cb(call: types.CallbackQuery):
    await call.message.edit_text("К кому хотите обратиться?", reply_markup=contact_kb())

@dp.message(F.text == "📞 Связаться с нами")
async def contact_us_msg(message: types.Message):
    await message.answer("К кому хотите обратиться?", reply_markup=contact_kb())

@dp.callback_query(F.data == "back_main")
async def back_main_cb(call: types.CallbackQuery):
    is_admin = call.from_user.id in ADMINS
    await call.message.edit_text("🔙 Главное меню", reply_markup=main_menu_inline(is_admin))

@dp.callback_query(F.data == "main_photos")
async def main_photos_cb(call: types.CallbackQuery):
    await call.message.edit_text("📸 Фотографии появятся здесь позже!", reply_markup=main_menu_inline(call.from_user.id in ADMINS))

# ---------- Меню (категории) ----------
@dp.callback_query(F.data == "main_menu")
async def show_menu_categories(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🥗 Еда", callback_data="menu_cat_Еда")],
            [InlineKeyboardButton(text="🍹 Напитки", callback_data="menu_cat_Напитки")],
            [InlineKeyboardButton(text="🍰 Десерты", callback_data="menu_cat_Десерты")],
            [InlineKeyboardButton(text="🌐 Посмотреть на сайте", url="https://veracoffeetea.com/?ysclid=mesnxzcdcm560404876")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ]
    )
    await call.message.edit_text("Выберите категорию меню:", reply_markup=kb)

@dp.callback_query(F.data.startswith("menu_cat_"))
async def show_menu_by_category(call: types.CallbackQuery):
    category = call.data.split("menu_cat_", 1)[1]
    cursor.execute("SELECT id, title, price FROM menu_items WHERE category=? AND is_active=1 ORDER BY id DESC", (category,))
    rows = cursor.fetchall()
    if not rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]])
        return await call.message.edit_text(f"В категории «{category}» пока пусто.", reply_markup=kb)

    kb_rows = [[InlineKeyboardButton(text=f"{r['title']} — {int(r['price'])} ₽", callback_data=f"menu_item_{r['id']}")] for r in rows]
    kb_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    await call.message.edit_text(f"📋 <b>{category}</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))

@dp.callback_query(F.data.startswith("menu_item_"))
async def open_menu_item(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[-1])
    cursor.execute("SELECT * FROM menu_items WHERE id=?", (item_id,))
    row = cursor.fetchone()
    if not row:
        return await call.answer("Блюдо не найдено", show_alert=True)
    is_admin = call.from_user.id in ADMINS
    text = (f"🍽 <b>{row['title']}</b>\n"
            f"{row['description']}\n"
            f"💰 <b>{int(row['price'])} ₽</b>")
    # Карточка с кнопками (админ — дополнительные)
    buttons = []
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="✏ Изменить", callback_data=f"m_edit_{row['id']}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"m_delask_{row['id']}")
        ])
        toggle_text = "🙈 Скрыть" if row["is_active"] else "👁 Показать"
        buttons.append([InlineKeyboardButton(text=toggle_text, callback_data=f"m_toggle_{row['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"menu_cat_{row['category']}")])
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ---------- Меню: админские операции (удаление/скрытие/редактирование) ----------
@dp.callback_query(F.data.startswith("m_delask_"))
async def menu_del_ask(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[-1])
    await call.message.edit_text("Вы уверены, что хотите удалить блюдо?", reply_markup=confirm_del_kb(item_id, return_to=f"menu_item_{item_id}"))

@dp.callback_query(F.data.startswith("m_del_"))
async def menu_del(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[-1])
    cursor.execute("DELETE FROM menu_items WHERE id=?", (item_id,))
    conn.commit()
    await call.message.edit_text("✅ Блюдо удалено.", reply_markup=main_menu_inline(call.from_user.id in ADMINS))

@dp.callback_query(F.data.startswith("m_toggle_"))
async def menu_toggle(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[-1])
    cursor.execute("UPDATE menu_items SET is_active = 1 - is_active WHERE id=?", (item_id,))
    conn.commit()
    cursor.execute("SELECT * FROM menu_items WHERE id=?", (item_id,))
    row = cursor.fetchone()
    await call.message.edit_reply_markup(InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=("👁 Показать" if row["is_active"]==0 else "🙈 Скрыть"), callback_data=f"m_toggle_{row['id']}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"menu_cat_{row['category']}")]
    ]))

# Редактирование меню через FSM
@dp.callback_query(F.data.startswith("m_edit_"))
async def menu_edit_start(call: types.CallbackQuery, state: FSMContext):
    item_id = int(call.data.split("_")[-1])
    await state.update_data(menu_edit_id=item_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data="m_field_title"),
         InlineKeyboardButton(text="Описание", callback_data="m_field_description")],
        [InlineKeyboardButton(text="Цена", callback_data="m_field_price"),
         InlineKeyboardButton(text="Категория", callback_data="m_field_category")],
        [InlineKeyboardButton(text="🔙 Назад к блюду", callback_data=f"menu_item_{item_id}")]
    ])
    await call.message.edit_text("Что изменить?", reply_markup=kb)
    await state.set_state(EditMenuFSM.waiting_field)

@dp.callback_query(EditMenuFSM.waiting_field, F.data.startswith("m_field_"))
async def menu_edit_field_selected(call: types.CallbackQuery, state: FSMContext):
    field = call.data.split("_", 2)[2]  # title | description | price | category
    await state.update_data(menu_edit_field=field)
    prompt = {
        "title": "Введите новое <b>название</b>:",
        "description": "Введите новое <b>описание</b>:",
        "price": "Введите новую <b>цену</b> (число):",
        "category": "Введите новую <b>категорию</b>:",
    }[field]
    await call.message.edit_text(prompt, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_menu_manage")]]
    ))
    await state.set_state(EditMenuFSM.waiting_value)

@dp.message(EditMenuFSM.waiting_value)
async def menu_edit_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item_id = data["menu_edit_id"]
    field = data["menu_edit_field"]
    new_val = message.text.strip()

    if field == "price":
        try:
            new_val = float(new_val.replace(",", "."))
        except ValueError:
            return await message.answer("Цена должна быть числом. Введите ещё раз:")

    # Безопасно обновляем поле
    if field in ("title", "description", "category"):
        cursor.execute(f"UPDATE menu_items SET {field}=? WHERE id=?", (new_val, item_id))
    else:
        cursor.execute(f"UPDATE menu_items SET {field}=? WHERE id=?", (new_val, item_id))
    conn.commit()

    # Показать обновлённую карточку
    cursor.execute("SELECT * FROM menu_items WHERE id=?", (item_id,))
    row = cursor.fetchone()
    is_admin = message.from_user.id in ADMINS
    text = (f"🍽 <b>{row['title']}</b>\n"
            f"{row['description']}\n"
            f"💰 <b>{int(row['price'])} ₽</b>")
    await message.answer(text, reply_markup=main_menu_inline(is_admin))
    await state.clear()

# ---------- Бронирование (онлайн-навигация) ----------
@dp.callback_query(F.data == "main_book")
async def booking_start_cb(call: types.CallbackQuery, state: FSMContext):
    await _ask_step(call, state, "fullname")

# legacy message handler — для пользователей, которые нажимают старую кнопку из reply (совместимость)
@dp.message(F.text == "📅 Забронировать столик")
async def booking_start_msg(message: types.Message, state: FSMContext):
    await _ask_step(message, state, "fullname")

@dp.message(BookingFSM.fullname)
async def booking_fullname(message: types.Message, state: FSMContext):
    await state.update_data(fullname=message.text)
    await _ask_step(message, state, "phone")

@dp.message(BookingFSM.phone)
async def booking_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await _ask_step(message, state, "datetime")

@dp.message(BookingFSM.datetime)
async def booking_datetime(message: types.Message, state: FSMContext):
    await state.update_data(datetime=message.text)
    await _ask_step(message, state, "source")

@dp.message(BookingFSM.source)
async def booking_source(message: types.Message, state: FSMContext):
    await state.update_data(source=message.text)
    await _ask_step(message, state, "notes")

@dp.message(BookingFSM.notes)
async def booking_notes(message: types.Message, state: FSMContext):
    await state.update_data(notes=message.text)
    await _save_booking_and_finish(message, state)

# Навигация: назад / пропустить / отмена
@dp.callback_query(F.data.startswith("book_back_"))
async def book_back(call: types.CallbackQuery, state: FSMContext):
    cur_step = call.data.split("_", 2)[2]
    prev_step = PREV.get(cur_step)
    if prev_step is None:
        # Назад до fullname → отменяем бронирование
        await state.clear()
        await call.message.edit_text(
            "❌ Бронирование отменено. Если захотите — начните заново.",
            reply_markup=main_menu_inline(call.from_user.id in ADMINS)
        )
        return
    await _ask_step(call, state, prev_step)

@dp.callback_query(F.data.startswith("book_skip_"))
async def book_skip(call: types.CallbackQuery, state: FSMContext):
    step = call.data.split("_", 2)[2]
    # Ставим пустое значение и двигаемся дальше
    if step == "source":
        await state.update_data(source="")
        await _ask_step(call, state, "notes")
    elif step == "notes":
        await state.update_data(notes="")
        await _save_booking_and_finish(call, state)
    else:
        await call.answer("Нельзя пропустить этот шаг", show_alert=True)

@dp.callback_query(F.data == "book_cancel")
async def book_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Бронирование отменено.", reply_markup=main_menu_inline(call.from_user.id in ADMINS))

# ---------- Админ: просмотр бронирований (карточки с кнопками) ----------
@dp.callback_query(F.data == "adm_view_bookings")
async def view_bookings_cb(call: types.CallbackQuery):
    cursor.execute("SELECT * FROM bookings ORDER BY id DESC")
    rows = cursor.fetchall()
    if not rows:
        return await call.message.edit_text("📭 Пока нет бронирований.", reply_markup=admin_menu_inline() if call.from_user.id in ADMINS else main_menu_inline(False))

    await call.message.edit_text("📖 Список бронирований:")
    for row in rows:
        text = (
            f"🔖 ID: {row['id']}\n"
            f"👤 {row['fullname']}\n"
            f"📞 {row['phone']}\n"
            f"📅 {row['datetime']}\n"
            f"📌 {row['source']}\n"
            f"📝 {row['notes']}"
        )
        await call.message.answer(text, reply_markup=bookings_item_kb(row["id"]))

@dp.callback_query(F.data.startswith("askdel_"))
async def confirm_delete(call: types.CallbackQuery):
    bid = int(call.data.split("_")[1])
    await call.message.edit_text("Удалить бронирование?", reply_markup=confirm_del_kb(bid, return_to="adm_view_bookings"))

@dp.callback_query(F.data.startswith("delete_"))
async def process_delete(call: types.CallbackQuery):
    booking_id = int(call.data.split("_")[1])
    cursor.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    await call.message.edit_text(f"❌ Бронирование ID {booking_id} удалено.", reply_markup=main_menu_inline(call.from_user.id in ADMINS))

# ---------- Изменение бронирования (flow) ----------
@dp.callback_query(F.data.startswith("edit_"))
async def process_edit(call: types.CallbackQuery, state: FSMContext):
    booking_id = int(call.data.split("_")[1])
    await state.update_data(edit_id=booking_id)

    # Загружаем текущие данные
    cursor.execute("SELECT * FROM bookings WHERE id=?", (booking_id,))
    row = cursor.fetchone()
    if not row:
        return await call.message.edit_text("❌ Бронирование не найдено.", reply_markup=main_menu_inline(call.from_user.id in ADMINS))

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

# ---------- Админ: управление меню (точка входа) ----------
@dp.callback_query(F.data == "adm_menu_manage")
async def adm_menu_manage(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        return await call.answer("⛔ Нет доступа", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить блюдо", callback_data="m_add")],
        [InlineKeyboardButton(text="Все блюда", callback_data="m_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_admin")]
    ])
    await call.message.edit_text("Управление меню:", reply_markup=kb)

@dp.callback_query(F.data == "m_list")
async def m_list(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        return await call.answer("⛔ Нет доступа", show_alert=True)
    cursor.execute("SELECT * FROM menu_items ORDER BY id DESC")
    rows = cursor.fetchall()
    if not rows:
        return await call.message.edit_text("Пока нет блюд.", reply_markup=admin_menu_inline())
    await call.message.edit_text("Список блюд:")
    for r in rows:
        await call.message.answer(f"{r['id']}. {r['title']} — {int(r['price'])} ₽", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✏ Редактировать", callback_data=f"m_edit_{r['id']}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"m_delask_{r['id']}")
        ]]))

# Добавление блюда (через FSM) — базовый flow
@dp.callback_query(F.data == "m_add")
async def m_add_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        return await call.answer("⛔ Нет доступа", show_alert=True)
    await state.update_data(new_item={})
    await call.message.edit_text("Введите название блюда:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_menu_manage")]]))
    await state.set_state(EditMenuFSM.waiting_field)  # переиспользуем состояние для ступеней добавления

@dp.message(EditMenuFSM.waiting_field)
async def m_add_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_item = data.get("new_item", {})
    if "title" not in new_item:
        new_item["title"] = message.text.strip()
        await state.update_data(new_item=new_item)
        await message.answer("Введите описание блюда (или напишите '-' чтобы пропустить):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_menu_manage")]]))
        return
    if "description" not in new_item:
        if message.text.strip() == "-":
            new_item["description"] = ""
        else:
            new_item["description"] = message.text.strip()
        await state.update_data(new_item=new_item)
        await message.answer("Введите цену (число):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_menu_manage")]]))
        return
    if "price" not in new_item:
        try:
            price = float(message.text.replace(",", "."))
        except:
            return await message.answer("Цена должна быть числом. Попробуйте ещё раз:")
        new_item["price"] = price
        await state.update_data(new_item=new_item)
        await message.answer("Введите категорию (например: Еда / Напитки / Десерты):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_menu_manage")]]))
        return
    if "category" not in new_item:
        new_item["category"] = message.text.strip()
        # Сохраняем
        cursor.execute("INSERT INTO menu_items(title, description, price, category) VALUES(?,?,?,?)",
                       (new_item["title"], new_item["description"], new_item["price"], new_item["category"]))
        conn.commit()
        await message.answer("✅ Блюдо добавлено.", reply_markup=admin_menu_inline())
        await state.clear()
        return

# ---------- Прочие совместимые message-хендлеры ----------
@dp.message(F.text == "⚙ Админ меню")
async def admin_menu_msg(message: types.Message):
    if message.from_user.id not in ADMINS:
        return await message.answer("⛔ У вас нет доступа")
    await message.answer("⚙ Админ меню", reply_markup=admin_menu_inline())

# legacy compatibility for "Назад в меню" reply buttons
@dp.message(F.text == "🔙 Назад в меню")
async def back_to_menu_legacy(message: types.Message):
    is_admin = message.from_user.id in ADMINS
    await message.answer("🔙 Главное меню", reply_markup=main_menu_inline(is_admin))

# ========================== RUN ==========================
async def main():
    print("🤖 Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())