import os
import psycopg2
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = telebot.TeleBot(TOKEN)


# =========================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# =========================

def get_db():
    return psycopg2.connect(DATABASE_URL)


def create_tables():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            balance NUMERIC(10,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


# =========================
# ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯ
# =========================

def register_user(message):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (telegram_id, username)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id)
        DO UPDATE SET username = EXCLUDED.username
    """, (
        message.from_user.id,
        message.from_user.username
    ))

    conn.commit()

    cursor.close()
    conn.close()


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

def main_menu():

    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        types.InlineKeyboardButton(
            "🛒 Каталог",
            callback_data="catalog"
        ),
        types.InlineKeyboardButton(
            "👤 Профиль",
            callback_data="profile"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "📦 Мои покупки",
            callback_data="purchases"
        ),
        types.InlineKeyboardButton(
            "💰 Баланс",
            callback_data="balance"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "🎟 Промокод",
            callback_data="promo"
        ),
        types.InlineKeyboardButton(
            "💬 Поддержка",
            callback_data="support"
        )
    )

    return keyboard


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    register_user(message)

    bot.send_message(
        message.chat.id,
        "👋 <b>Добро пожаловать в магазин!</b>\n\n"
        "Выберите нужный раздел:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================
# КНОПКИ
# =========================

@bot.callback_query_handler(func=lambda call: True)
def buttons(call):

    if call.data == "catalog":

        keyboard = types.InlineKeyboardMarkup()

        keyboard.add(
            types.InlineKeyboardButton(
                "🎮 Товар №1 — 100 ₽",
                callback_data="product_1"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "⭐ Товар №2 — 200 ₽",
                callback_data="product_2"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔙 Назад",
                callback_data="back"
            )
        )

        bot.edit_message_text(
            "🛒 <b>КАТАЛОГ</b>\n\n"
            "Выберите товар:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    elif call.data == "profile":

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT balance FROM users WHERE telegram_id = %s",
            (call.from_user.id,)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        balance = user[0] if user else 0

        bot.edit_message_text(
            "👤 <b>ПРОФИЛЬ</b>\n\n"
            f"🆔 ID: <code>{call.from_user.id}</code>\n"
            f"💰 Баланс: <b>{balance} ₽</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )

    elif call.data == "balance":

        bot.edit_message_text(
            "💰 <b>БАЛАНС</b>\n\n"
            "Ваш баланс отображается в профиле.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )

    elif call.data == "purchases":

        bot.edit_message_text(
            "📦 <b>МОИ ПОКУПКИ</b>\n\n"
            "Покупок пока нет.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )

    elif call.data == "promo":

        bot.edit_message_text(
            "🎟 <b>ПРОМОКОД</b>\n\n"
            "Функция промокодов скоро будет доступна.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )

    elif call.data == "support":

        bot.edit_message_text(
            "💬 <b>ПОДДЕРЖКА</b>\n\n"
            "Обратитесь к администратору.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )

    elif call.data == "back":

        bot.edit_message_text(
            "👋 <b>Главное меню</b>\n\n"
            "Выберите нужный раздел:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=main_menu()
        )

    elif call.data in ["product_1", "product_2"]:

        bot.answer_callback_query(
            call.id,
            "Покупка будет доступна после подключения оплаты."
        )
        return

    bot.answer_callback_query(call.id)


# =========================
# НАЗАД
# =========================

def back_button():

    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "🔙 Главное меню",
            callback_data="back"
        )
    )

    return keyboard


# =========================
# ЗАПУСК
# =========================

create_tables()

bot.infinity_polling()