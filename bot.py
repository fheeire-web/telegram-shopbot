import os
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=["start"])
def start(message):
    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton("🛒 Каталог", callback_data="catalog")
    )

    keyboard.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )

    keyboard.add(
        types.InlineKeyboardButton("📦 Мои покупки", callback_data="purchases")
    )

    keyboard.add(
        types.InlineKeyboardButton("💬 Поддержка", callback_data="support")
    )

    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в магазин!\n\n"
        "Выберите нужный раздел:",
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: True)
def buttons(call):

    if call.data == "catalog":
        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            "🛒 КАТАЛОГ\n\n"
            "Пока товаров нет.\n"
            "Скоро здесь появятся товары."
        )

    elif call.data == "profile":
        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            "👤 ПРОФИЛЬ\n\n"
            f"ID: {call.from_user.id}\n"
            "💰 Баланс: 0 ₽"
        )

    elif call.data == "purchases":
        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            "📦 МОИ ПОКУПКИ\n\n"
            "У вас пока нет покупок."
        )

    elif call.data == "support":
        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            "💬 ПОДДЕРЖКА\n\n"
            "Напишите администратору."
        )


bot.infinity_polling()