import os
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

def main_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        types.InlineKeyboardButton("🛒 Каталог", callback_data="catalog"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )

    keyboard.add(
        types.InlineKeyboardButton("📦 Мои покупки", callback_data="purchases"),
        types.InlineKeyboardButton("💰 Баланс", callback_data="balance")
    )

    keyboard.add(
        types.InlineKeyboardButton("🎟 Промокод", callback_data="promo"),
        types.InlineKeyboardButton("💬 Поддержка", callback_data="support")
    )

    return keyboard


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    bot.send_message(
        message.chat.id,
        "👋 <b>Добро пожаловать в магазин!</b>\n\n"
        "Здесь вы можете приобрести цифровые товары.\n\n"
        "👇 Выберите нужный раздел:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================
# КНОПКИ
# =========================

@bot.callback_query_handler(func=lambda call: True)
def buttons(call):

    # КАТАЛОГ
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


    # ТОВАР 1
    elif call.data == "product_1":

        keyboard = types.InlineKeyboardMarkup()

        keyboard.add(
            types.InlineKeyboardButton(
                "💳 Купить",
                callback_data="buy_1"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔙 Назад",
                callback_data="catalog"
            )
        )

        bot.edit_message_text(
            "🎮 <b>ТОВАР №1</b>\n\n"
            "Описание товара.\n\n"
            "💰 Цена: <b>100 ₽</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )


    # ТОВАР 2
    elif call.data == "product_2":

        keyboard = types.InlineKeyboardMarkup()

        keyboard.add(
            types.InlineKeyboardButton(
                "💳 Купить",
                callback_data="buy_2"
            )
        )

        keyboard.add(
            types.InlineKeyboardButton(
                "🔙 Назад",
                callback_data="catalog"
            )
        )

        bot.edit_message_text(
            "⭐ <b>ТОВАР №2</b>\n\n"
            "Описание товара.\n\n"
            "💰 Цена: <b>200 ₽</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )


    # ПРОФИЛЬ
    elif call.data == "profile":

        bot.edit_message_text(
            "👤 <b>ПРОФИЛЬ</b>\n\n"
            f"🆔 ID: <code>{call.from_user.id}</code>\n"
            "💰 Баланс: <b>0 ₽</b>\n"
            "📦 Покупок: <b>0</b>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )


    # БАЛАНС
    elif call.data == "balance":

        bot.edit_message_text(
            "💰 <b>БАЛАНС</b>\n\n"
            "Ваш баланс: <b>0 ₽</b>\n\n"
            "Пополнение баланса пока недоступно.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )


    # ПОКУПКИ
    elif call.data == "purchases":

        bot.edit_message_text(
            "📦 <b>МОИ ПОКУПКИ</b>\n\n"
            "У вас пока нет покупок.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )


    # ПРОМО
    elif call.data == "promo":

        bot.edit_message_text(
            "🎟 <b>ПРОМОКОД</b>\n\n"
            "Функция промокодов скоро будет доступна.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )


    # ПОДДЕРЖКА
    elif call.data == "support":

        bot.edit_message_text(
            "💬 <b>ПОДДЕРЖКА</b>\n\n"
            "Если у вас возникли проблемы с покупкой, "
            "обратитесь к администратору.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )


    # НАЗАД
    elif call.data == "back":

        bot.edit_message_text(
            "👋 <b>Главное меню</b>\n\n"
            "Выберите нужный раздел:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=main_menu()
        )


    # ПОКУПКА
    elif call.data.startswith("buy_"):

        bot.answer_callback_query(
            call.id,
            "Покупка пока находится в разработке."
        )

    bot.answer_callback_query(call.id)


# =========================
# КНОПКА НАЗАД
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

bot.infinity_polling()