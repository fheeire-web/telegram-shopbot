import os
import psycopg2
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [7845398556]  # Твой ID!

bot = telebot.TeleBot(TOKEN)

# =========================
# БАЗА ДАННЫХ
# =========================

def get_db():
    return psycopg2.connect(DATABASE_URL)

def create_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            balance NUMERIC(10,2) DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            price NUMERIC(10,2),
            stock INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Таблицы созданы")

# =========================
# ФУНКЦИИ
# =========================

def register_user(message):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (telegram_id, username)
            VALUES (%s, %s)
            ON CONFLICT (telegram_id)
            DO UPDATE SET username = EXCLUDED.username
        """, (message.from_user.id, message.from_user.username))
        conn.commit()
        conn.close()
    except:
        pass

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_balance(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE telegram_id = %s", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def get_all_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, telegram_id, username, balance FROM users ORDER BY id")
    users = cur.fetchall()
    conn.close()
    return users

def add_money(user_id, amount):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
    conn.commit()
    cur.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
    new_balance = cur.fetchone()[0]
    conn.close()
    return new_balance

# =========================
# МЕНЮ
# =========================

def main_menu(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🛒 Каталог", callback_data="catalog"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )
    if is_admin(user_id):
        keyboard.add(types.InlineKeyboardButton("⚙️ Админ", callback_data="admin"))
    return keyboard

def admin_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("👥 Пользователи", callback_data="users"),
        types.InlineKeyboardButton("💰 Выдать деньги", callback_data="give_money")
    )
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def users_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    users = get_all_users()
    if not users:
        keyboard.add(types.InlineKeyboardButton("📭 Нет пользователей", callback_data="none"))
    else:
        for user in users:
            name = f"@{user[2]}" if user[2] else f"ID: {user[1]}"
            keyboard.add(types.InlineKeyboardButton(
                f"{name} - {user[3]}₽", 
                callback_data=f"user_{user[0]}"
            ))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin"))
    return keyboard

def user_actions_menu(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ 100₽", callback_data=f"add_{user_id}_100"),
        types.InlineKeyboardButton("➕ 500₽", callback_data=f"add_{user_id}_500"),
        types.InlineKeyboardButton("➕ 1000₽", callback_data=f"add_{user_id}_1000"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="users")
    )
    return keyboard

# =========================
# КОМАНДЫ
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message)
    bot.send_message(
        message.chat.id,
        "👋 Привет! Это магазин.",
        reply_markup=main_menu(message.from_user.id)
    )

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    # Главное меню
    if call.data == "back":
        bot.edit_message_text(
            "👋 Главное меню",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu(call.from_user.id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Профиль
    if call.data == "profile":
        balance = get_balance(call.from_user.id)
        bot.edit_message_text(
            f"👤 Твой профиль\n💰 Баланс: {balance} ₽",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu(call.from_user.id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Админ-панель
    if call.data == "admin":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.edit_message_text(
            "⚙️ Админ-панель",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=admin_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Список пользователей
    if call.data == "users":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.edit_message_text(
            "👥 Список пользователей:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=users_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Выдать деньги - выбор пользователя
    if call.data == "give_money":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.edit_message_text(
            "💰 Выберите пользователя:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=users_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # Выбор пользователя
    if call.data.startswith("user_"):
        user_id = int(call.data.split("_")[1])
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT telegram_id, username, balance FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        conn.close()
        if user:
            name = f"@{user[1]}" if user[1] else f"ID: {user[0]}"
            bot.edit_message_text(
                f"👤 {name}\n💰 Баланс: {user[2]} ₽",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=user_actions_menu(user_id)
            )
        bot.answer_callback_query(call.id)
        return
    
    # Выдать деньги
    if call.data.startswith("add_"):
        parts = call.data.split("_")
        user_id = int(parts[1])
        amount = float(parts[2])
        
        new_balance = add_money(user_id, amount)
        
        # Уведомление пользователю
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT telegram_id FROM users WHERE id = %s", (user_id,))
        user_tg = cur.fetchone()
        conn.close()
        
        if user_tg:
            try:
                bot.send_message(user_tg[0], f"💰 +{amount} ₽\nНовый баланс: {new_balance} ₽")
            except:
                pass
        
        bot.answer_callback_query(call.id, f"✅ Выдано {amount}₽!")
        
        # Обновляем сообщение
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT telegram_id, username, balance FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        conn.close()
        if user:
            name = f"@{user[1]}" if user[1] else f"ID: {user[0]}"
            bot.edit_message_text(
                f"👤 {name}\n💰 Баланс: {user[2]} ₽",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=user_actions_menu(user_id)
            )
        return
    
    # Каталог (заглушка)
    if call.data == "catalog":
        bot.edit_message_text(
            "🛒 Каталог\n\nТоваров пока нет.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu(call.from_user.id)
        )
        bot.answer_callback_query(call.id)
        return
    
    # Игнор
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return

# =========================
# ЗАПУСК
# =========================

create_tables()
print("🤖 Бот запущен!")

while True:
    try:
        bot.polling(none_stop=True, interval=1)
    except Exception as e:
        print(f"Ошибка: {e}")
        import time
        time.sleep(5)