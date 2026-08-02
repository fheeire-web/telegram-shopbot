import os
import telebot
from telebot import types
import sqlite3

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [7845398556]

bot = telebot.TeleBot(TOKEN)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            username TEXT,
            balance INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def register_user(tg_id, username):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO users (tg_id, username) VALUES (?, ?)",
        (tg_id, username)
    )
    conn.commit()
    conn.close()

def get_balance(tg_id):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def get_all_users():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT id, tg_id, username, balance FROM users")
    users = cur.fetchall()
    conn.close()
    return users

def add_money(user_id, amount):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    new_balance = cur.fetchone()[0]
    conn.close()
    return new_balance

def is_admin(tg_id):
    return tg_id in ADMIN_IDS

# ========== МЕНЮ ==========
def main_menu(tg_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🛒 Каталог", callback_data="catalog")
    )
    if is_admin(tg_id):
        kb.add(types.InlineKeyboardButton("⚙️ Админ", callback_data="admin"))
    return kb

def admin_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("👥 Пользователи", callback_data="users"),
        types.InlineKeyboardButton("💰 Выдать деньги", callback_data="give_money")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def users_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    users = get_all_users()
    if not users:
        kb.add(types.InlineKeyboardButton("📭 Нет", callback_data="none"))
    else:
        for u in users:
            name = f"@{u[2]}" if u[2] else f"ID: {u[1]}"
            kb.add(types.InlineKeyboardButton(f"{name} - {u[3]}₽", callback_data=f"user_{u[0]}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin"))
    return kb

def user_actions(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ 100", callback_data=f"add_{user_id}_100"),
        types.InlineKeyboardButton("➕ 500", callback_data=f"add_{user_id}_500"),
        types.InlineKeyboardButton("➕ 1000", callback_data=f"add_{user_id}_1000"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="users")
    )
    return kb

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=["start"])
def start(msg):
    register_user(msg.from_user.id, msg.from_user.username)
    bot.send_message(msg.chat.id, "👋 Привет!", reply_markup=main_menu(msg.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def handle(call):
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return

    if call.data == "back":
        bot.edit_message_text("👋 Главное", call.message.chat.id, call.message.message_id,
                             reply_markup=main_menu(call.from_user.id))
        bot.answer_callback_query(call.id)
        return

    if call.data == "profile":
        bal = get_balance(call.from_user.id)
        bot.edit_message_text(f"💰 Баланс: {bal} ₽", call.message.chat.id, call.message.message_id,
                             reply_markup=main_menu(call.from_user.id))
        bot.answer_callback_query(call.id)
        return

    if call.data == "admin":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.edit_message_text("⚙️ Админ", call.message.chat.id, call.message.message_id,
                             reply_markup=admin_menu())
        bot.answer_callback_query(call.id)
        return

    if call.data == "users" or call.data == "give_money":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.edit_message_text("👥 Выбери:", call.message.chat.id, call.message.message_id,
                             reply_markup=users_menu())
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("user_"):
        user_id = int(call.data.split("_")[1])
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute("SELECT tg_id, username, balance FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        conn.close()
        if u:
            name = f"@{u[1]}" if u[1] else f"ID: {u[0]}"
            bot.edit_message_text(f"👤 {name}\n💰 {u[2]}₽", call.message.chat.id, call.message.message_id,
                                 reply_markup=user_actions(user_id))
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("add_"):
        parts = call.data.split("_")
        user_id = int(parts[1])
        amount = int(parts[2])
        
        new_bal = add_money(user_id, amount)
        
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute("SELECT tg_id FROM users WHERE id = ?", (user_id,))
        tg = cur.fetchone()
        conn.close()
        
        if tg:
            try:
                bot.send_message(tg[0], f"💰 +{amount}₽\nБаланс: {new_bal}₽")
            except:
                pass
        
        bot.answer_callback_query(call.id, f"✅ +{amount}₽")
        
        # Обновляем
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute("SELECT tg_id, username, balance FROM users WHERE id = ?", (user_id,))
        u = cur.fetchone()
        conn.close()
        if u:
            name = f"@{u[1]}" if u[1] else f"ID: {u[0]}"
            bot.edit_message_text(f"👤 {name}\n💰 {u[2]}₽", call.message.chat.id, call.message.message_id,
                                 reply_markup=user_actions(user_id))
        return

    if call.data == "catalog":
        bot.edit_message_text("🛒 Товаров нет", call.message.chat.id, call.message.message_id,
                             reply_markup=main_menu(call.from_user.id))
        bot.answer_callback_query(call.id)
        return

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    init_db()
    print("🤖 Бот запущен!")
    while True:
        try:
            bot.polling(none_stop=True)
        except:
            import time
            time.sleep(5)
