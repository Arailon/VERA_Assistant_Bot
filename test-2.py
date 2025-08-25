import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== DATABASE ==================
DB_FILE = "vera.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Таблица гостей
    c.execute("""
        CREATE TABLE IF NOT EXISTS guests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fio TEXT,
            phone TEXT,
            email TEXT,
            source TEXT,
            note TEXT
        )
    """)

    # Таблица расписания
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cafe TEXT,
            date TEXT,
            name TEXT,
            time_from TEXT,
            time_to TEXT,
            hours INTEGER
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ================== CONSTANTS ==================
(
    ADD_FIO,
    ADD_PHONE,
    ADD_EMAIL,
    ADD_SOURCE,
    ADD_NOTE,
    SEARCH_QUERY,
    EDIT_FIELD,
    EDIT_VALUE,
    SCHEDULE_DATE,
    SCHEDULE_NAME,
    SCHEDULE_FROM,
    SCHEDULE_TO,
    SCHEDULE_HOURS,
) = range(13)

ADMIN_IDS = [123456789]  # <-- сюда вставь ID админов

# ================== HELPERS ==================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def format_guest(g):
    return f"🧑‍💼 <b>{g[1]}</b>\n📞 {g[2] or '-'}\n✉️ {g[3] or '-'}\n📌 {g[4] or '-'}\n📝 {g[5] or '-'}"

def format_schedule(s):
    return f"📅 {s[2]} | 🏢 {s[1]}\n👤 {s[3]}\n⏰ {s[4]} - {s[5]} ({s[6]} ч.)"

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🔎 Найти гостя")],
        [KeyboardButton("📅 Расписание Prechistenskaya"),
         KeyboardButton("📅 Расписание Komsomolsky")]
    ]
    if is_admin(update.effective_user.id):
        keyboard.append([KeyboardButton("🛠 Админ-панель")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Добро пожаловать в VERA Assistant 👋", reply_markup=reply_markup)

# ================== ADMIN MENU ==================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ У вас нет доступа")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Добавить гостя", callback_data="add_guest")],
        [InlineKeyboardButton("📋 Список гостей", callback_data="list_guests")],
    ]
    await update.message.reply_text("🛠 Админ-панель", reply_markup=InlineKeyboardMarkup(keyboard))

# ================== GUESTS ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    if query.data == "add_guest":
        await query.edit_message_text("Введите ФИО гостя:")
        context.user_data["new_guest"] = {}
        return ADD_FIO

    elif query.data == "list_guests":
        c.execute("SELECT * FROM guests ORDER BY id DESC LIMIT 10")
        rows = c.fetchall()
        if not rows:
            await query.edit_message_text("📭 Гостей нет")
            return
        for g in rows:
            buttons = [
                [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_guest:{g[0]}")],
                [InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_guest:{g[0]}")]
            ]
            await query.message.reply_text(format_guest(g), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    elif query.data.startswith("delete_guest:"):
        gid = int(query.data.split(":")[1])
        c.execute("DELETE FROM guests WHERE id=?", (gid,))
        conn.commit()
        await query.edit_message_text("✅ Гость удалён")

    elif query.data.startswith("edit_guest:"):
        gid = int(query.data.split(":")[1])
        context.user_data["edit_guest_id"] = gid
        fields = [
            ("fio", "ФИО"), ("phone", "Телефон"),
            ("email", "Email"), ("source", "Источник"),
            ("note", "Заметка")
        ]
        buttons = [[InlineKeyboardButton(f[1], callback_data=f"edit_field:{gid}:{f[0]}")] for f in fields]
        await query.edit_message_text("✏️ Что редактировать?", reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("edit_field:"):
        _, gid, field = query.data.split(":")
        context.user_data["edit_guest_id"] = int(gid)
        context.user_data["edit_field"] = field
        await query.edit_message_text(f"Введите новое значение для {field}:")
        return EDIT_VALUE

    conn.close()

# добавление гостя
async def add_guest_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_guest"]["fio"] = update.message.text
    await update.message.reply_text("Введите телефон:")
    return ADD_PHONE

async def add_guest_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_guest"]["phone"] = update.message.text
    await update.message.reply_text("Введите email:")
    return ADD_EMAIL

async def add_guest_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_guest"]["email"] = update.message.text
    await update.message.reply_text("Источник?")
    return ADD_SOURCE

async def add_guest_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_guest"]["source"] = update.message.text
    await update.message.reply_text("Заметка:")
    return ADD_NOTE

async def add_guest_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_guest"]["note"] = update.message.text
    g = context.user_data["new_guest"]
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO guests (fio, phone, email, source, note) VALUES (?, ?, ?, ?, ?)",
              (g["fio"], g["phone"], g["email"], g["source"], g["note"]))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Гость добавлен")
    return ConversationHandler.END

# редактирование значения
async def edit_guest_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = context.user_data["edit_guest_id"]
    field = context.user_data["edit_field"]
    value = update.message.text
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(f"UPDATE guests SET {field}=? WHERE id=?", (value, gid))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Данные обновлены")
    return ConversationHandler.END

# поиск гостя
async def search_guest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.replace("🔎 Найти гостя", "").strip()
    if not query:
        await update.message.reply_text("Введите запрос: ФИО, телефон или email")
        return SEARCH_QUERY

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""SELECT * FROM guests 
                 WHERE fio LIKE ? OR phone LIKE ? OR email LIKE ?""",
              (f"%{query}%", f"%{query}%", f"%{query}%"))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 Ничего не найдено")
        return

    for g in rows:
        buttons = []
        if is_admin(update.effective_user.id):
            buttons = [
                [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_guest:{g[0]}")],
                [InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_guest:{g[0]}")]
            ]
        await update.message.reply_text(format_guest(g), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

    return ConversationHandler.END

# ================== SCHEDULE ==================
async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, cafe: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    week_start = datetime.today().date()
    week_end = week_start + timedelta(days=7)
    c.execute("SELECT * FROM schedule WHERE cafe=? AND date BETWEEN ? AND ? ORDER BY date",
              (cafe, str(week_start), str(week_end)))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(f"📅 Расписание {cafe} пусто на этой неделе")
        return

    for s in rows:
        buttons = []
        if is_admin(update.effective_user.id):
            buttons = [[InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_schedule:{s[0]}")]]
        await update.message.reply_text(format_schedule(s), reply_markup=InlineKeyboardMarkup(buttons))

async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Prechistenskaya" in text:
        await show_schedule(update, context, "Prechistenskaya")
    elif "Komsomolsky" in text:
        await show_schedule(update, context, "Komsomolsky")

# добавление расписания
async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, cafe: str):
    context.user_data["new_schedule"] = {"cafe": cafe}
    await update.message.reply_text("Введите дату (ГГГГ-ММ-ДД):")
    return SCHEDULE_DATE

async def add_schedule_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_schedule"]["date"] = update.message.text
    await update.message.reply_text("Введите Фамилию Имя:")
    return SCHEDULE_NAME

async def add_schedule_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_schedule"]["name"] = update.message.text
    await update.message.reply_text("Время начала (чч:мм):")
    return SCHEDULE_FROM

async def add_schedule_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_schedule"]["time_from"] = update.message.text
    await update.message.reply_text("Время окончания (чч:мм):")
    return SCHEDULE_TO

async def add_schedule_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_schedule"]["time_to"] = update.message.text
    await update.message.reply_text("Количество часов:")
    return SCHEDULE_HOURS

async def add_schedule_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_schedule"]["hours"] = int(update.message.text)
    s = context.user_data["new_schedule"]
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO schedule (cafe, date, name, time_from, time_to, hours) VALUES (?, ?, ?, ?, ?, ?)",
              (s["cafe"], s["date"], s["name"], s["time_from"], s["time_to"], s["hours"]))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Запись добавлена")
    return ConversationHandler.END

# удаление расписания
async def delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.split(":")[1])
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM schedule WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    await query.edit_message_text("✅ Запись удалена")

# ================== MAIN ==================
async def main():
    app = Application.builder().token("YOUR_BOT_TOKEN").build()

    # команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    # кнопки
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(delete_schedule, pattern="^delete_schedule:"))

    # поиск
    app.add_handler(MessageHandler(filters.Regex("^🔎 Найти гостя$"), search_guest))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_guest))

    # расписание
    app.add_handler(MessageHandler(filters.Regex("Prechistenskaya|Komsomolsky"), schedule_handler))

    # диалоги
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^add_guest$")],
        states={
            ADD_FIO: [MessageHandler(filters.TEXT, add_guest_fio)],
            ADD_PHONE: [MessageHandler(filters.TEXT, add_guest_phone)],
            ADD_EMAIL: [MessageHandler(filters.TEXT, add_guest_email)],
            ADD_SOURCE: [MessageHandler(filters.TEXT, add_guest_source)],
            ADD_NOTE: [MessageHandler(filters.TEXT, add_guest_note)],
            EDIT_VALUE: [MessageHandler(filters.TEXT, edit_guest_value)],
            SCHEDULE_DATE: [MessageHandler(filters.TEXT, add_schedule_date)],
            SCHEDULE_NAME: [MessageHandler(filters.TEXT, add_schedule_name)],
            SCHEDULE_FROM: [MessageHandler(filters.TEXT, add_schedule_from)],
            SCHEDULE_TO: [MessageHandler(filters.TEXT, add_schedule_to)],
            SCHEDULE_HOURS: [MessageHandler(filters.TEXT, add_schedule_hours)],
        },
        fallbacks=[],
    )
    app.add_handler(conv)

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())