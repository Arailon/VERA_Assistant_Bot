# VERA_Bot.py (исправленный)
import asyncio
import re
import sqlite3
import logging
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ================= НАСТРОЙКИ =================
logging.basicConfig(level=logging.INFO)

TOKEN = "8425551477:AAFyt2EgdZ3vqx3wDy1YOSDXr2XpcmAeANk"
CHAT_ID = -4875403747
TIMEZONE = pytz.timezone("Europe/Moscow")
ADMINS = {"Arailon", "AndreyGrebeshchikov"}  # ← логины админов без @

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

# ================= CONVERSATION: /guest (только в группе) =================
(FULLNAME, PHONE, EMAIL, SOURCE, NOTE, CONFIRM, SEARCH) = range(7)

# ================= ПОИСК ГОСТЯ =================
async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # защита: только группа
    if update.message.chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в группе.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🔍 Введите номер телефона, email, фамилию или ФИО гостя.\n"
        "Можно вводить частично. Чтобы отменить — нажмите «Отмена».",
        reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True),
    )
    return SEARCH

async def search_guest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пустой запрос — введите телефон, email или фамилию.")
        return SEARCH
    if text.lower() == "отмена":
        await update.message.reply_text("Поиск отменён.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    q = text.lower()
    digits_q = re.sub(r"\D", "", text)

    # Для удобства: если набор цифр начинается с 8 -> нормализуем в 7
    if digits_q.startswith("8"):
        digits_q = "7" + digits_q[1:]

    # Заберём всех гостей и отфильтруем
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, phone, email, source, note FROM guests ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        gid, fullname, phone, email, source, note = row
        full_text = " ".join([str(fullname or ""), str(email or ""), str(phone or "")]).lower()

        # Если запрос содержит @ — считаем это поиск по email (подстрока, нечувствительно к регистру)
        if "@" in text:
            if email and q in (email or "").lower():
                results.append(row)
                continue

        # По цифрам телефона (если в запросе есть >=3 цифры)
        if len(digits_q) >= 3:
            phone_digits = re.sub(r"\D", "", phone or "")
            if phone_digits.startswith("8"):
                phone_digits = "7" + phone_digits[1:]
            if digits_q in phone_digits:
                results.append(row)
                continue

        # По ФИО / фамилии: проверяем, что все слова запроса встречаются в fullname
        name_words = q.split()
        if fullname:
            fullname_l = fullname.lower()
            ok = all(w in fullname_l for w in name_words)
            if ok:
                results.append(row)
                continue

        # fallback: общая подстрока
        if q in full_text:
            results.append(row)
            continue

    if not results:
        await update.message.reply_text("❌ По вашему запросу ничего не найдено.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    # Ограничим вывод — максимум 20 карточек
    max_show = 20
    shown = 0
    for row in results:
        if shown >= max_show:
            break
        gid, fullname, phone, email, source, note = row
        card = (
            f"👤 {fullname or '—'}\n"
            f"📞 {phone or '—'}\n"
            f"📧 {email or '—'}\n"
            f"📌 {source or '—'}\n"
            f"📝 {note or '—'}\n"
            f"🆔 ID: {gid}"
        )
        await update.message.reply_text(card)
        shown += 1

    if len(results) > max_show:
        await update.message.reply_text(f"Показано {max_show} из {len(results)} совпадений. Уточните запрос для сужения поиска.")

    await update.message.reply_text("", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Поиск отменён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ================= GUEST CONVERSATION =================
async def start_guest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # защита: работаем только в группах
    if update.message.chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в группе.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "Добавляем нового гостя 🎉 Введите ФИО гостя (например: Иванов Сергей Александрович).",
        reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True),
    )
    return FULLNAME

async def fullname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (update.message.text or "").strip().lower() == "отмена":
        return await cancel(update, context)
    fn = update.message.text.strip()
    if not fn or len(fn) < 3:
        await update.message.reply_text("❌ Похоже на ошибку. Введите ФИО ещё раз или нажмите «Отмена».")
        return FULLNAME
    context.user_data["fullname"] = fn
    await update.message.reply_text(
        "Введите номер телефона (пример: +7 915 123 45 67 или 89151234567).",
        reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True),
    )
    return PHONE

async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (update.message.text or "").strip().lower() == "отмена":
        return await cancel(update, context)

    phone_fmt = normalize_phone(update.message.text)
    if not phone_fmt:
        await update.message.reply_text("❌ Телефон некорректный. Введите снова.")
        return PHONE

    context.user_data["phone"] = phone_fmt
    await update.message.reply_text(
        f"Телефон сохранён: {phone_fmt} ✅\nТеперь введите e-mail (или нажмите «Пропустить»).",
        reply_markup=ReplyKeyboardMarkup([["Пропустить"], ["Отмена"]], resize_keyboard=True),
    )
    return EMAIL

async def email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text.lower() == "отмена":
        return await cancel(update, context)

    if text.lower() == "пропустить":
        context.user_data["email"] = None
    else:
        # простая валидация email
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text):
            await update.message.reply_text("❌ Некорректный email. Введите снова или нажмите «Пропустить».")
            return EMAIL
        context.user_data["email"] = text

    await update.message.reply_text("Откуда пришёл гость? (например: Instagram, Рекомендация, Улица)")
    return SOURCE

async def source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (update.message.text or "").strip().lower() == "отмена":
        return await cancel(update, context)
    context.user_data["source"] = update.message.text.strip()
    await update.message.reply_text(
        "Заметка (если есть). Или нажмите «Пропустить».",
        reply_markup=ReplyKeyboardMarkup([["Пропустить"], ["Отмена"]], resize_keyboard=True),
    )
    return NOTE

async def note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or "").strip()
    if txt.lower() == "отмена":
        return await cancel(update, context)
    context.user_data["note"] = None if txt.lower() == "пропустить" else txt

    d = context.user_data
    text = (
        "Проверьте данные:\n\n"
        f"👤 ФИО: {d.get('fullname','—')}\n"
        f"📞 Телефон: {d.get('phone','—')}\n"
        f"📧 E-mail: {d.get('email','—') or '—'}\n"
        f"📌 Источник: {d.get('source','—')}\n"
        f"📝 Заметка: {d.get('note','—') or '—'}\n\n"
        "Сохранить гостя?"
    )
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup([["Да"], ["Отмена"]], resize_keyboard=True),
    )
    return CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if (update.message.text or "").strip().lower() != "да":
        await update.message.reply_text("❌ Отменено.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    d = context.user_data
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO guests (fullname, phone, email, source, note) VALUES (?, ?, ?, ?, ?)",
        (d.get("fullname"), d.get("phone"), d.get("email"), d.get("source"), d.get("note")),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Гость успешно добавлен:\n\n"
        f"👤 {d.get('fullname')}\n"
        f"📞 {d.get('phone')}\n"
        f"📧 {d.get('email','—') or '—'}\n"
        f"📌 {d.get('source','—')}\n"
        f"📝 {d.get('note','—') or '—'}\n",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Ввод отменён.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ================= /start: ЛС и ГРУППА раздельно =================
async def start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # меню для гостей (личка)
    kb = [["Забронировать столик"], ["Посмотреть меню"], ["Фотографии"], ["Связаться с бариста"]]
    await update.message.reply_text(
        f"Добрый день, {update.effective_user.first_name}! 👋\n"
        "Я виртуальный помощник кофейни VERA. Что Вам подсказать?",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )

async def start_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # меню для группы (сотрудники)
    kb = [
        ["➕Добавить гостя"],
        ["📋 Список гостей"],
        ["🔍 Найти гостя"],
        ["🕵️Админ-меню"]
    ]
    await update.message.reply_text(
        "👋 Привет! Я бот кофейни VERA. Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )

# ================= FRONT =================
async def booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Напишите дату и время для брони.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 Меню: https://your-menu-link")

async def photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Фотографии: https://your-photos-link")

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 Телефон бариста: +7 XXX XXX-XX-XX")

# ================= ADMIN =================
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔️ У вас нет доступа к этой команде.")
        return
    kb = [["Список гостей"], ["Отмена"]]
    await update.message.reply_text("Админ-меню:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def guest_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    # Пытаемся отправить список в ЛС админа
    u = update.effective_user
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT fullname, phone, email, source, note FROM guests ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        try:
            await context.bot.send_message(chat_id=u.id, text="📭 Гостей пока нет.")
        except Exception:
            await update.message.reply_text("Напишите боту в личку сначала, чтобы он мог отправлять вам сообщения.")
        return

    # Формируем порционно (чтобы не упереться в лимиты)
    chunk = []
    total_texts = []
    for row in rows:
        chunk.append(
            f"👤 {row[0]}\n"
            f"📞 {row[1]}\n"
            f"📧 {row[2] or '—'}\n"
            f"📌 {row[3] or '—'}\n"
            f"📝 {row[4] or '—'}\n"
        )
        if len(chunk) == 20:
            total_texts.append("\n".join(chunk))
            chunk = []
    if chunk:
        total_texts.append("\n".join(chunk))

    try:
        for part in total_texts:
            await context.bot.send_message(chat_id=u.id, text="📋 Список гостей:\n\n" + part)
    except Exception:
        await update.message.reply_text("Напишите боту в личку сначала, чтобы он мог отправлять вам сообщения.")

# ================= ОШИБКИ =================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.exception("Exception while handling an update:", exc_info=context.error)

# ================= MAIN =================
async def main():
    init_db()

    app = Application.builder().token(TOKEN).build()
    app.add_error_handler(error_handler)

    # --- /start раздельно ---
    app.add_handler(CommandHandler("start", start_private, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("start", start_group, filters=filters.ChatType.GROUPS))

    # --- фронт-кнопки (личка) ---
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Забронировать столик$"), booking))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Посмотреть меню$"), menu))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Фотографии$"), photos))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.Regex("(?i)^Связаться с бариста$"), contact))

    # --- admin ---
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.Regex(r"(?i)^🕵️Админ-меню$"), admin_menu))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.Regex("(?i)^Список гостей$"), guest_list))

    # --- conversation: поиск гостей ---
    search_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.ChatType.GROUPS & filters.Regex(r"(?i)^🔍 Найти гостя$"), start_search),
        ],
        states={
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_guest)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("(?i)^Отмена$"), cancel_search),
            CommandHandler("cancel", cancel_search),
        ],
        allow_reentry=True,
    )
    app.add_handler(search_conv)

    # --- conversation /guest (только в группах) ---
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
        fallbacks=[MessageHandler(filters.Regex(r"(?i)^Отмена$"), cancel), CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv_handler)

    # --- планировщик (работает в том же event loop) ---
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(task_0830, "cron", hour=8, minute=30, args=[app])
    scheduler.add_job(task_0900, "cron", hour=9, minute=0, args=[app])
    scheduler.add_job(task_1700, "cron", hour=17, minute=0, args=[app])
    scheduler.add_job(task_1800, "cron", hour=18, minute=0, args=[app])
    scheduler.start()

    # --- запуск бота (упрощённо) ---
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())