import os
import telebot
from telebot import types
import sqlite3

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [7845398556]  # Твой ID

bot = telebot.TeleBot(TOKEN)

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE,
            username TEXT,
            balance INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица товаров
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            stock INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

# ========== ПОЛЬЗОВАТЕЛИ ==========
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

# ========== ТОВАРЫ ==========
def get_all_products():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT id, name, price, stock FROM products ORDER BY id")
    products = cur.fetchall()
    conn.close()
    return products

def add_product(name, price, stock):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
        (name, price, stock)
    )
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

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
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👥 Пользователи", callback_data="users"),
        types.InlineKeyboardButton("💰 Баланс", callback_data="give_money")
    )
    kb.add(
        types.InlineKeyboardButton("📦 Товары", callback_data="admin_products"),
        types.InlineKeyboardButton("➕ Добавить товар", callback_data="add_product")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def products_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    products = get_all_products()
    if not products:
        kb.add(types.InlineKeyboardButton("📭 Товаров нет", callback_data="none"))
    else:
        for p in products:
            kb.add(types.InlineKeyboardButton(
                f"{p[1]} - {p[2]}₽ ({p[3]} шт)", 
                callback_data=f"product_{p[0]}"
            ))
    kb.add(types.InlineKeyboardButton("🔙 Админ", callback_data="admin"))
    return kb

def product_actions_menu(product_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_product_{product_id}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_products")
    )
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

def user_actions_menu(user_id):
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

    # ===== НАЗАД =====
    if call.data == "back":
        bot.edit_message_text("👋 Главное", call.message.chat.id, call.message.message_id,
                             reply_markup=main_menu(call.from_user.id))
        bot.answer_callback_query(call.id)
        return

    # ===== ПРОФИЛЬ =====
    if call.data == "profile":
        bal = get_balance(call.from_user.id)
        bot.edit_message_text(f"💰 Баланс: {bal} ₽", call.message.chat.id, call.message.message_id,
                             reply_markup=main_menu(call.from_user.id))
        bot.answer_callback_query(call.id)
        return

    # ===== КАТАЛОГ =====
    if call.data == "catalog":
        products = get_all_products()
        if not products:
            text = "🛒 Товаров пока нет"
        else:
            text = "🛒 КАТАЛОГ\n\n"
            for p in products:
                text += f"📦 {p[1]}\n💰 {p[2]}₽\n📦 В наличии: {p[3]} шт\n\n"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                             reply_markup=main_menu(call.from_user.id))
        bot.answer_callback_query(call.id)
        return

    # ===== АДМИН-ПАНЕЛЬ =====
    if call.data == "admin":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.edit_message_text("⚙️ АДМИН-ПАНЕЛЬ", call.message.chat.id, call.message.message_id,
                             reply_markup=admin_menu())
        bot.answer_callback_query(call.id)
        return

    # ===== ТОВАРЫ (список) =====
    if call.data == "admin_products":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.edit_message_text("📦 СПИСОК ТОВАРОВ", call.message.chat.id, call.message.message_id,
                             reply_markup=products_menu())
        bot.answer_callback_query(call.id)
        return

    # ===== ПРОСМОТР ТОВАРА =====
    if call.data.startswith("product_"):
        product_id = int(call.data.split("_")[1])
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,))
        p = cur.fetchone()
        conn.close()
        if p:
            text = f"📦 {p[1]}\n💰 {p[2]}₽\n📦 В наличии: {p[3]} шт"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                 reply_markup=product_actions_menu(product_id))
        bot.answer_callback_query(call.id)
        return

    # ===== ДОБАВИТЬ ТОВАР =====
    if call.data == "add_product":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        msg = bot.send_message(call.message.chat.id, 
            "➕ ВВЕДИ ТОВАР\n\nФормат:\nНазвание | Цена | Количество\n\nПример:\nPlayStation 5 | 50000 | 10")
        bot.register_next_step_handler(msg, process_add_product)
        bot.answer_callback_query(call.id)
        return

    # ===== УДАЛИТЬ ТОВАР =====
    if call.data.startswith("delete_product_"):
        product_id = int(call.data.split("_")[2])
        delete_product(product_id)
        bot.answer_callback_query(call.id, "✅ Товар удален!")
        bot.edit_message_text("📦 Товар удален", call.message.chat.id, call.message.message_id,
                             reply_markup=products_menu())
        return

    # ===== ПОЛЬЗОВАТЕЛИ =====
    if call.data == "users" or call.data == "give_money":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.edit_message_text("👥 ВЫБЕРИ ПОЛЬЗОВАТЕЛЯ", call.message.chat.id, call.message.message_id,
                             reply_markup=users_menu())
        bot.answer_callback_query(call.id)
        return

    # ===== ВЫБОР ПОЛЬЗОВАТЕЛЯ =====
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
                                 reply_markup=user_actions_menu(user_id))
        bot.answer_callback_query(call.id)
        return

    # ===== ВЫДАТЬ ДЕНЬГИ =====
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
                                 reply_markup=user_actions_menu(user_id))
        return

# ===== ДОБАВЛЕНИЕ ТОВАРА (обработка) =====
def process_add_product(msg):
    try:
        data = msg.text.split('|')
        if len(data) < 3:
            bot.send_message(msg.chat.id, "❌ Неверный формат!\nНужно: Название | Цена | Количество")
            return
        
        name = data[0].strip()
        price = int(data[1].strip())
        stock = int(data[2].strip())
        
        add_product(name, price, stock)
        bot.send_message(msg.chat.id, f"✅ Товар '{name}' добавлен!", reply_markup=admin_menu())
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка! Проверь формат")

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