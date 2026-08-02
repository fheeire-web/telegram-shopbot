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
    
    # Таблица товаров с категорией
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
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

def remove_money(user_id, amount):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    result = cur.fetchone()
    if not result or result[0] < amount:
        conn.close()
        return None
    cur.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
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
    cur.execute("SELECT id, name, category, price, stock FROM products ORDER BY category, name")
    products = cur.fetchall()
    conn.close()
    return products

def get_products_by_category(category):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT id, name, category, price, stock FROM products WHERE category = ? ORDER BY name", (category,))
    products = cur.fetchall()
    conn.close()
    return products

def get_categories():
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM products")
    categories = cur.fetchall()
    conn.close()
    return [c[0] for c in categories]

def add_product(name, category, price, stock):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        (name, category, price, stock)
    )
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def get_product_by_id(product_id):
    conn = sqlite3.connect('bot.db')
    cur = conn.cursor()
    cur.execute("SELECT id, name, category, price, stock FROM products WHERE id = ?", (product_id,))
    product = cur.fetchone()
    conn.close()
    return product

# ========== МЕНЮ ==========
def main_menu(tg_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛒 Каталог", callback_data="catalog"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
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
        types.InlineKeyboardButton("➕ Добавить", callback_data="add_product")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return kb

def categories_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    categories = get_categories()
    if not categories:
        kb.add(types.InlineKeyboardButton("📭 Нет категорий", callback_data="none"))
    else:
        for cat in categories:
            kb.add(types.InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat_{cat}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin"))
    return kb

def products_menu(category):
    kb = types.InlineKeyboardMarkup(row_width=1)
    products = get_products_by_category(category)
    if not products:
        kb.add(types.InlineKeyboardButton("📭 Нет товаров", callback_data="none"))
    else:
        for p in products:
            kb.add(types.InlineKeyboardButton(
                f"📦 {p[1]} - {p[3]}₽ ({p[4]} шт)", 
                callback_data=f"product_{p[0]}"
            ))
    kb.add(types.InlineKeyboardButton("🔙 Категории", callback_data="admin_products"))
    return kb

def product_actions_menu(product_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{product_id}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{product_id}")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_products"))
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
        types.InlineKeyboardButton("➕ 1000", callback_data=f"add_{user_id}_1000")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="users"))
    return kb

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=["start"])
def start(msg):
    register_user(msg.from_user.id, msg.from_user.username)
    bot.send_message(msg.chat.id, "👋 Добро пожаловать в магазин!", reply_markup=main_menu(msg.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def handle(call):
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return

    # ===== НАЗАД =====
    if call.data == "back":
        bot.send_message(call.message.chat.id, "👋 Главное меню", reply_markup=main_menu(call.from_user.id))
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== ПРОФИЛЬ =====
    if call.data == "profile":
        bal = get_balance(call.from_user.id)
        bot.send_message(call.message.chat.id, f"👤 ТВОЙ ПРОФИЛЬ\n\n💰 Баланс: {bal} ₽", 
                        reply_markup=main_menu(call.from_user.id))
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== КАТАЛОГ =====
    if call.data == "catalog":
        categories = get_categories()
        if not categories:
            bot.send_message(call.message.chat.id, "🛒 Товаров пока нет", 
                           reply_markup=main_menu(call.from_user.id))
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            for cat in categories:
                kb.add(types.InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat_{cat}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
            bot.send_message(call.message.chat.id, "🛒 ВЫБЕРИ КАТЕГОРИЮ", reply_markup=kb)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== КАТЕГОРИЯ В КАТАЛОГЕ =====
    if call.data.startswith("cat_"):
        category = call.data.split("_")[1]
        products = get_products_by_category(category)
        if not products:
            bot.send_message(call.message.chat.id, f"📭 В категории {category} нет товаров",
                           reply_markup=main_menu(call.from_user.id))
        else:
            kb = types.InlineKeyboardMarkup(row_width=1)
            for p in products:
                kb.add(types.InlineKeyboardButton(f"📦 {p[1]} - {p[3]}₽", callback_data=f"buy_{p[0]}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="catalog"))
            bot.send_message(call.message.chat.id, f"📁 {category}\n\nВыбери товар:", reply_markup=kb)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== КУПИТЬ ТОВАР =====
    if call.data.startswith("buy_"):
        product_id = int(call.data.split("_")[1])
        product = get_product_by_id(product_id)
        
        if not product:
            bot.answer_callback_query(call.id, "❌ Товар не найден!", True)
            return
        
        if product[4] <= 0:
            bot.answer_callback_query(call.id, "❌ Товара нет в наличии!", True)
            return
        
        user_balance = get_balance(call.from_user.id)
        if user_balance < product[3]:
            bot.answer_callback_query(call.id, f"❌ Не хватает! Нужно {product[3]}₽", True)
            return
        
        # Покупка
        new_balance = remove_money(product_id, product[3])
        # Уменьшаем сток
        conn = sqlite3.connect('bot.db')
        cur = conn.cursor()
        cur.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"✅ Куплено {product[1]} за {product[3]}₽!")
        bot.send_message(call.from_user.id, 
            f"🛒 ПОКУПКА\n\nТовар: {product[1]}\nКатегория: {product[2]}\nЦена: {product[3]}₽\nОстаток: {product[4]-1} шт")
        
        # Обновляем сообщение
        bal = get_balance(call.from_user.id)
        bot.send_message(call.message.chat.id, f"💰 Новый баланс: {bal}₽", reply_markup=main_menu(call.from_user.id))
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    # ===== АДМИН-ПАНЕЛЬ =====
    if call.data == "admin":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.send_message(call.message.chat.id, "⚙️ АДМИН-ПАНЕЛЬ", reply_markup=admin_menu())
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== ТОВАРЫ (админ) =====
    if call.data == "admin_products":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.send_message(call.message.chat.id, "📦 ВЫБЕРИ КАТЕГОРИЮ", reply_markup=categories_menu())
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== ПРОСМОТР ТОВАРА (админ) =====
    if call.data.startswith("product_"):
        product_id = int(call.data.split("_")[1])
        p = get_product_by_id(product_id)
        if p:
            text = f"📦 {p[1]}\n📁 Категория: {p[2]}\n💰 {p[3]}₽\n📦 В наличии: {p[4]} шт"
            bot.send_message(call.message.chat.id, text, reply_markup=product_actions_menu(product_id))
            bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== ДОБАВИТЬ ТОВАР =====
    if call.data == "add_product":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        msg = bot.send_message(call.message.chat.id, 
            "➕ ДОБАВИТЬ ТОВАР\n\nФормат:\nНазвание | Категория | Цена | Количество\n\nПример:\nVIP Access | Премиумы | 1500 | 5")
        bot.register_next_step_handler(msg, process_add_product)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    # ===== УДАЛИТЬ ТОВАР =====
    if call.data.startswith("delete_"):
        product_id = int(call.data.split("_")[1])
        product = get_product_by_id(product_id)
        delete_product(product_id)
        bot.answer_callback_query(call.id, f"✅ {product[1]} удален!")
        bot.send_message(call.message.chat.id, f"✅ Товар '{product[1]}' удален", reply_markup=admin_menu())
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    # ===== ПОЛЬЗОВАТЕЛИ =====
    if call.data == "users" or call.data == "give_money":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.send_message(call.message.chat.id, "👥 ВЫБЕРИ ПОЛЬЗОВАТЕЛЯ", reply_markup=users_menu())
        bot.delete_message(call.message.chat.id, call.message.message_id)
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
            bot.send_message(call.message.chat.id, f"👤 {name}\n💰 {u[2]}₽", 
                           reply_markup=user_actions_menu(user_id))
            bot.delete_message(call.message.chat.id, call.message.message_id)
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
            bot.send_message(call.message.chat.id, f"👤 {name}\n💰 {u[2]}₽", 
                           reply_markup=user_actions_menu(user_id))
            bot.delete_message(call.message.chat.id, call.message.message_id)
        return

# ===== ДОБАВЛЕНИЕ ТОВАРА (обработка) =====
def process_add_product(msg):
    try:
        data = msg.text.split('|')
        if len(data) < 4:
            bot.send_message(msg.chat.id, "❌ Неверный формат!\nНужно: Название | Категория | Цена | Количество")
            return
        
        name = data[0].strip()
        category = data[1].strip()
        price = int(data[2].strip())
        stock = int(data[3].strip())
        
        add_product(name, category, price, stock)
        bot.send_message(msg.chat.id, f"✅ Товар '{name}' добавлен в категорию '{category}'!", 
                        reply_markup=admin_menu())
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка! Проверь формат", reply_markup=admin_menu())

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