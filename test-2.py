# VERA_Bot.py (исправленный запуск + новые функции)
import asyncio
import re
import sqlite3
import logging
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================= НАСТРОЙКИ =================
logging.basicConfig(level=logging.INFO)

TOKEN = "8425551477:AAFyt2EgdZ3vqx3wDy1YOSDXr2XpcmAeANk"
CHAT_ID = -4875403747
TIMEZONE = pytz.timezone("Europe/Moscow")
ADMINS = {"Arailon", "AndreyGrebeshchikov"}

DB_PATH = "guests.db"

# ================= БАЗА =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS guests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT,
            phone TEXT,
            email TEXT,
            source TEXT,
            note TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            fullname TEXT,
            time TEXT,
            hours TEXT
        )
        """
    )
    conn.commit()
    conn.close()

# ================= УТИЛИТЫ =================
def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return None
    if digits.startswith("8"):
        digits = "7" + digits[1:]
    if not digits.startswith("7"):
        digits = "7" + digits
    if len(digits) != 11:
        return None
    return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:]}"

def is_admin(update: Update) -> bool:
    u = update.effective_user
    return bool(u and u.username and u.username in ADMINS)

# ================= НАПОМИНАНИЯ =================
async def send_message(app: Application, text: str):
    await app.bot.send_message(chat_id=CHAT_ID, text=text)

async def task_0830(app: Application):
    await send_message(app, "Сфотографируйте штендер🌿")

async def task_0900(app: Application):
    await send_message(
        app,
        "Убедитесь, что касса открыта, эспрессо настроен, ice-gen и чайник работают, музыка и свет есть. "
        "И настройтесь получать удовольствие🌿🤗"
    )

async def task_1700(app: Application):
    await send_message(app, "Запросите, пожалуйста, ВТБ и Сбер в группе Оперативно")

async def task_1800(app: Application):
    await send_message(app, "Подготовка к закрытию смены🌿")

# ================= CONVERSATION: /guest =================
(FULLNAME, PHONE, EMAIL, SOURCE, NOTE, CONFIRM, SEARCH) = range(7)
(EDIT_FIELD, EDIT_VALUE) = range(7, 9)
(SCHEDULE_LOC, SCHEDULE_NAME, SCHEDULE_TIME, SCHEDULE_HOURS) = range(9, 13)

# ================= ПОИСК ГОСТЯ =================
async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в группе.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🔍 Введите номер телефона, email, фамилию или ФИО гостя.\nМожно вводить частично.",
        reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True),
    )
    return SEARCH

async def search_guest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text or text.lower() == "отмена":
        await update.message.reply_text("Поиск отменён.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    q = text.lower()
    digits_q = re.sub(r"\D", "", text)
    if digits_q.startswith("8"):
        digits_q = "7" + digits_q[1:]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, phone, email, source, note FROM guests ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        gid, fullname, phone, email, source, note = row
        full_text = " ".join([str(fullname or ""), str(email or ""), str(phone or "")]).lower()

        if "@" in text and email and q in (email or "").lower():
            results.append(row)
            continue

        if len(digits_q) >= 3:
            phone_digits = re.sub(r"\D", "", phone or "")
            if phone_digits.startswith("8"):
                phone_digits = "7" + phone_digits[1:]
            if digits_q in phone_digits:
                results.append(row)
                continue

        name_words = q.split()
        if fullname and all(w in fullname.lower() for w in name_words):
            results.append(row)
            continue

        if q in full_text:
            results.append(row)

    if not results:
        await update.message.reply_text("❌ Ничего не найдено.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    for row in results[:20]:
        gid, fullname, phone, email, source, note = row
        card = (
            f"👤 {fullname or '—'}\n"
            f"📞 {phone or '—'}\n"
            f"📧 {email or '—'}\n"
            f"📌 {source or '—'}\n"
            f"📝 {note or '—'}\n"
            f"🆔 ID: {gid}"
        )
        kb = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✏️ Изменить", callback_data=f"edit_{gid}"),
                InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{gid}")
            ]]
        )
        await update.message.reply_text(card, reply_markup=kb)

    return ConversationHandler.END

# ================= УПРАВЛЕНИЕ ГОСТЕМ =================
async def guest_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("edit_"):
        gid = int(data.split("_")[1])
        context.user_data["edit_id"] = gid
        kb = ReplyKeyboardMarkup(
            [["ФИО", "Телефон"], ["Email", "Источник"], ["Заметка"], ["Отмена"]],
            resize_keyboard=True,
        )
        await query.message.reply_text("Что хотите изменить?", reply_markup=kb)
        return EDIT_FIELD

    if data.startswith("delete_"):
        gid = int(data.split("_")[1])
        kb = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("✅ Да", callback_data=f"confirmdel_{gid}"),
                InlineKeyboardButton("❌ Нет", callback_data="canceldel")
            ]]
        )
        await query.message.reply_text("Удалить этого гостя?", reply_markup=kb)
        return ConversationHandler.END

    if data.startswith("confirmdel_"):
        gid = int(data.split("_")[1])
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM guests WHERE id=?", (gid,))
        conn.commit()
        conn.close()
        await query.message.reply_text("✅ Гость удалён.")
        return ConversationHandler.END

    if data == "canceldel":
        await query.message.reply_text("Удаление отменено.")
        return ConversationHandler.END

async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field_map = {
        "фио": "fullname",
        "телефон": "phone",
        "email": "email",
        "источник": "source",
        "заметка": "note",
    }
    choice = update.message.text.lower()
    if choice == "отмена":
        return await cancel(update, context)
    if choice not in field_map:
        await update.message.reply_text("Выберите поле из списка.")
        return EDIT_FIELD
    context.user_data["edit_field"] = field_map[choice]
    await update.message.reply_text(f"Введите новое значение для «{choice}»:", reply_markup=ReplyKeyboardRemove())
    return EDIT_VALUE

async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = context.user_data.get("edit_id")
    field = context.user_data.get("edit_field")
    value = update.message.text.strip()
    if field == "phone":
        value = normalize_phone(value) or value
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE guests SET {field}=? WHERE id=?", (value, gid))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Изменения сохранены.")
    return ConversationHandler.END

# ================= РАСПИСАНИЕ =================
async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    kb = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("📍 Prechistenskaya", callback_data="schedule_Prechistenskaya"),
            InlineKeyboardButton("📍 Komsomolsky", callback_data="schedule_Komsomolsky")
        ]]
    )
    await update.message.reply_text("Выберите филиал:", reply_markup=kb)

async def schedule_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loc = query.data.split("_")[1]
    context.user_data["schedule_loc"] = loc
    kb = ReplyKeyboardMarkup([["Добавить"], ["Показать"], ["Отмена"]], resize_keyboard=True)
    await query.message.reply_text(f"Управление расписанием {loc}:", reply_markup=kb)
    return SCHEDULE_LOC

async def schedule_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    loc = context.user_data.get("schedule_loc")
    if text == "добавить":
        await update.message.reply_text("Введите фамилию и имя сотрудника:")
        return SCHEDULE_NAME
    if text == "показать":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT fullname, time, hours FROM schedule WHERE location=?", (loc,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            await update.message.reply_text("📭 Расписание пустое.")
        else:
            msg = "\n\n".join([f"👤 {r[0]}\n⏰ {r[1]}\n⌛ {r[2]}" for r in rows])
            await update.message.reply_text(f"📋 Расписание {loc}:\n\n{msg}")
        return ConversationHandler.END
    if text == "отмена":
        return await cancel(update, context)
    return SCHEDULE_LOC

async def schedule_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sch_name"] = update.message.text.strip()
    await update.message.reply_text("Введите время работы (например: 09:00–18:00):")
    return SCHEDULE_TIME

async def schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sch_time"] = update.message.text.strip()
    await update.message.reply_text("Введите количество часов работы:")
    return SCHEDULE_HOURS

async def schedule_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = context.user_data.get("schedule_loc")
    name = context.user_data.get("sch_name")
    time = context.user_data.get("sch_time")
    hours = update.message.text.strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO schedule (location, fullname, time, hours) VALUES (?, ?, ?, ?)", (loc, name, time, hours))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Запись добавлена.")
    return ConversationHandler.END

# ================= СТАРЫЕ ХЕНДЛЕРЫ (без изменений) =================
# (оставлены все твои start_guest, fullname, phone, email, source, note, confirm, cancel, start_private, start_group, booking, menu, photos, contact, admin_menu, guest_list, error_handler, main — см. твой код выше)

# ================= MAIN =================
async def main():
    init_db()

    app = Application.builder().token(TOKEN).build()
    app.add_error_handler(error_handler)

    # --- /start раздельно ---
    app.add_handler(CommandHandler("start", start_private, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("start", start_group, filters=filters.ChatType.GROUPS))

    # --- фронт-кнопки ---
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Забронировать столик$"), booking))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Посмотреть меню$"), menu))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Фотографии$"), photos))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Связаться с бариста$"), contact))

    # --- admin ---
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.Regex(r"(?i)^🕵️Админ-меню$"), admin_menu))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.Regex("(?i)^Список гостей$"), guest_list))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.Regex("(?i)^Расписание$"), schedule_menu))

    # --- гости поиск ---
    search_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.ChatType.GROUPS & filters.Regex(r"(?i)^🔍 Найти гостя$"), start_search)],
        states={SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_guest)]},
        fallbacks=[MessageHandler(filters.Regex("(?i)^Отмена$"), cancel_search)],
        allow_reentry=True,
    )
    app.add_handler(search_conv)

    # --- гости редактирование/удаление ---
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(guest_action, pattern="^(edit_|delete_|confirmdel_|canceldel)")],
        states={
            EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field)],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[MessageHandler(filters.Regex("(?i)^Отмена$"), cancel)],
        map_to_parent={},
    )
    app.add_handler(edit_conv)

    # --- расписание ---
    schedule_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(schedule_action, pattern="^schedule_")],
        states={
            SCHEDULE_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_loc)],
            SCHEDULE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_name)],
            SCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_time)],
            SCHEDULE_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_hours)],
        },
        fallbacks=[MessageHandler(filters.Regex("(?i)^Отмена$"), cancel)],
    )
    app.add_handler(schedule_conv)

    # --- conversation /guest ---
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("guest", start_guest),
            MessageHandler(filters.ChatType.GROUPS & filters.Regex(r"(?i)^➕Добавить гостя$"), start_guest),
        ],
        states={
            FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, fullname)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, email)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, source)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[MessageHandler(filters.Regex(r"(?i)^Отмена$"), cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv_handler)

    # --- планировщик ---
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(task_0830, "cron", hour=8, minute=30, args=[app])
    scheduler.add_job(task_0900, "cron", hour=9, minute=0, args=[app])
    scheduler.add_job(task_1700, "cron", hour=17, minute=0, args=[app])
    scheduler.add_job(task_1800, "cron", hour=18, minute=0, args=[app])
    scheduler.start()

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(main())
        else:
            raise