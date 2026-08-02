import os
import telebot
from telebot import types
import psycopg2
import random
import string
import time

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [7845398556]  # Твой ID

bot = telebot.TeleBot(TOKEN)

# ========== БАЗА ДАННЫХ ==========
def get_db():
    if not DATABASE_URL:
        raise Exception("❌ DATABASE_URL не найден!")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Проверяем существование таблиц и создаем если нет
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                balance INTEGER DEFAULT 0,
                stars INTEGER DEFAULT 0,
                ref_code TEXT UNIQUE,
                invited_by INTEGER DEFAULT 0,
                referrals_count INTEGER DEFAULT 0,
                ref_earnings INTEGER DEFAULT 0
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT,
                category TEXT,
                price INTEGER DEFAULT 0,
                stars_price INTEGER DEFAULT 0,
                stock INTEGER DEFAULT 0
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                product_id INTEGER,
                amount INTEGER,
                payment_type TEXT,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Добавляем колонку stars если ее нет
        try:
            cur.execute("ALTER TABLE users ADD COLUMN stars INTEGER DEFAULT 0")
        except:
            pass  # Колонка уже существует
        
        # Добавляем колонку stars_price если ее нет
        try:
            cur.execute("ALTER TABLE products ADD COLUMN stars_price INTEGER DEFAULT 0")
        except:
            pass  # Колонка уже существует
        
        conn.commit()
        conn.close()
        print("✅ PostgreSQL готов!")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ========== ПОЛЬЗОВАТЕЛИ ==========
def generate_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def register_user(tg_id, username, invited_by=None):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM users WHERE tg_id = %s", (tg_id,))
    user = cur.fetchone()
    
    if user:
        conn.close()
        return user[0]
    
    ref_code = generate_ref_code()
    
    cur.execute(
        "INSERT INTO users (tg_id, username, ref_code, invited_by, stars) VALUES (%s, %s, %s, %s, 0) RETURNING id",
        (tg_id, username, ref_code, invited_by or 0)
    )
    user_id = cur.fetchone()[0]
    
    if invited_by:
        cur.execute("UPDATE users SET balance = balance + 10, referrals_count = referrals_count + 1, ref_earnings = ref_earnings + 10 WHERE id = %s", (invited_by,))
        cur.execute("SELECT tg_id FROM users WHERE id = %s", (invited_by,))
        inviter_tg = cur.fetchone()
        if inviter_tg:
            try:
                bot.send_message(inviter_tg[0], f"👤 Новый реферал!\n💰 +10₽ на баланс!")
            except:
                pass
    
    conn.commit()
    conn.close()
    return user_id

def get_user(tg_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, tg_id, username, balance, stars, ref_code, invited_by, referrals_count, ref_earnings FROM users WHERE tg_id = %s", (tg_id,))
    user = cur.fetchone()
    conn.close()
    return user

def get_user_by_ref_code(ref_code):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, tg_id FROM users WHERE ref_code = %s", (ref_code,))
    user = cur.fetchone()
    conn.close()
    return user

def get_balance(tg_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE tg_id = %s", (tg_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def get_stars(tg_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT stars FROM users WHERE tg_id = %s", (tg_id,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def get_all_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, tg_id, username, balance, stars, ref_code, referrals_count, ref_earnings FROM users ORDER BY id")
    users = cur.fetchall()
    conn.close()
    return users

def add_money(user_id, amount):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE id = %s RETURNING balance", (amount, user_id))
    new_balance = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return new_balance

def add_stars(user_id, amount):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET stars = stars + %s WHERE id = %s RETURNING stars", (amount, user_id))
    new_stars = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return new_stars

def remove_money(tg_id, amount):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE tg_id = %s", (tg_id,))
    result = cur.fetchone()
    if not result or result[0] < amount:
        conn.close()
        return None
    cur.execute("UPDATE users SET balance = balance - %s WHERE tg_id = %s RETURNING balance", (amount, tg_id))
    new_balance = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return new_balance

def remove_stars(tg_id, amount):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT stars FROM users WHERE tg_id = %s", (tg_id,))
    result = cur.fetchone()
    if not result or result[0] < amount:
        conn.close()
        return None
    cur.execute("UPDATE users SET stars = stars - %s WHERE tg_id = %s RETURNING stars", (amount, tg_id))
    new_stars = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return new_stars

def is_admin(tg_id):
    return tg_id in ADMIN_IDS

def save_order(user_id, product_id, amount, payment_type):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, product_id, amount, payment_type) VALUES (%s, %s, %s, %s)",
        (user_id, product_id, amount, payment_type)
    )
    conn.commit()
    conn.close()

# ========== ТОВАРЫ ==========
def get_all_products():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, category, price, stars_price, stock FROM products ORDER BY category, name")
    products = cur.fetchall()
    conn.close()
    return products

def get_products_by_category(category):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, category, price, stars_price, stock FROM products WHERE category = %s ORDER BY name", (category,))
    products = cur.fetchall()
    conn.close()
    return products

def get_categories():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM products")
    categories = cur.fetchall()
    conn.close()
    return [c[0] for c in categories]

def add_product(name, category, price, stars_price, stock):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO products (name, category, price, stars_price, stock) VALUES (%s, %s, %s, %s, %s)",
        (name, category, price, stars_price, stock)
    )
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
    conn.commit()
    conn.close()

def get_product_by_id(product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, category, price, stars_price, stock FROM products WHERE id = %s", (product_id,))
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
    kb.add(
        types.InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="stats")
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
    kb.add(types.InlineKeyboardButton("🔙 Меню", callback_data="menu"))
    return kb

def categories_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    categories = get_categories()
    if not categories:
        kb.add(types.InlineKeyboardButton("📭 Нет категорий", callback_data="none"))
    else:
        for cat in categories:
            kb.add(types.InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat_{cat}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_products"))
    return kb

def products_menu(category):
    kb = types.InlineKeyboardMarkup(row_width=1)
    products = get_products_by_category(category)
    if not products:
        kb.add(types.InlineKeyboardButton("📭 Нет товаров", callback_data="none"))
    else:
        for p in products:
            price_text = f"{p[3]}₽" if p[3] > 0 else ""
            if p[4] > 0:
                price_text += f" / {p[4]}⭐"
            kb.add(types.InlineKeyboardButton(
                f"📦 {p[1]} - {price_text} ({p[5]} шт)", 
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
            kb.add(types.InlineKeyboardButton(f"{name} - {u[3]}₽ | {u[4]}⭐", callback_data=f"user_{u[0]}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin"))
    return kb

def user_actions_menu(user_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ 100₽", callback_data=f"add_{user_id}_100"),
        types.InlineKeyboardButton("➕ 500₽", callback_data=f"add_{user_id}_500"),
        types.InlineKeyboardButton("➕ 1000₽", callback_data=f"add_{user_id}_1000"),
        types.InlineKeyboardButton("⭐ +50⭐", callback_data=f"add_stars_{user_id}_50")
    )
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="users"))
    return kb

def menu_button():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Меню", callback_data="menu"))
    return kb

def back_to_catalog():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 В каталог", callback_data="catalog"))
    return kb

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=["start"])
def start(msg):
    ref_code = None
    if len(msg.text.split()) > 1:
        ref_code = msg.text.split()[1]
    
    invited_by = None
    if ref_code:
        inviter = get_user_by_ref_code(ref_code)
        if inviter and inviter[0] != msg.from_user.id:
            invited_by = inviter[0]
    
    register_user(msg.from_user.id, msg.from_user.username, invited_by)
    
    photo_url = "https://i.ibb.co/d1J7fjB/IMG-2390.png"
    
    try:
        bot.send_photo(
            msg.chat.id,
            photo_url,
            caption="👋 Добро пожаловать в магазин!\n\nВыбери нужный раздел:",
            reply_markup=main_menu(msg.from_user.id)
        )
    except Exception as e:
        print(f"Ошибка фото: {e}")
        bot.send_message(
            msg.chat.id,
            "👋 Добро пожаловать в магазин!\n\nВыбери нужный раздел:",
            reply_markup=main_menu(msg.from_user.id)
        )

@bot.callback_query_handler(func=lambda call: True)
def handle(call):
    if call.data == "none":
        bot.answer_callback_query(call.id)
        return

    # ===== МЕНЮ =====
    if call.data == "menu":
        try:
            bot.send_photo(
                call.message.chat.id,
                "https://i.ibb.co/d1J7fjB/IMG-2390.png",
                caption="👋 Главное меню\n\nВыбери нужный раздел:",
                reply_markup=main_menu(call.from_user.id)
            )
        except:
            bot.send_message(call.message.chat.id, "👋 Главное меню", reply_markup=main_menu(call.from_user.id))
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    # ===== ПРОФИЛЬ =====
    if call.data == "profile":
        user = get_user(call.from_user.id)
        if user:
            text = f"""👤 ТВОЙ ПРОФИЛЬ

🆔 ID: {user[1]}
👤 Username: @{user[2] or 'Не указан'}
💰 Баланс: {user[3]} ₽
⭐ Звезды: {user[4]}
👥 Приглашено: {user[7]} чел.
💸 Заработано с рефералов: {user[8]} ₽

📎 Твоя реферальная ссылка:
https://t.me/{bot.get_me().username}?start={user[5]}"""
            
            bot.send_message(call.message.chat.id, text, reply_markup=menu_button())
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        bot.answer_callback_query(call.id)
        return

    # ===== РЕФЕРАЛЫ =====
    if call.data == "referrals":
        user = get_user(call.from_user.id)
        if user:
            text = f"""👥 РЕФЕРАЛЬНАЯ СИСТЕМА

📎 Твоя ссылка:
https://t.me/{bot.get_me().username}?start={user[5]}

👥 Приглашено: {user[7]} чел.
💰 Заработано: {user[8]} ₽
💵 За каждого реферала: +10 ₽

📊 Как это работает:
1. Отправь ссылку другу
2. Он переходит по ссылке
3. Ты получаешь +10 ₽ на баланс"""
            
            bot.send_message(call.message.chat.id, text, reply_markup=menu_button())
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        bot.answer_callback_query(call.id)
        return

    # ===== СТАТИСТИКА =====
    if call.data == "stats":
        user = get_user(call.from_user.id)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT SUM(balance) FROM users")
        total_balance = cur.fetchone()[0] or 0
        cur.execute("SELECT SUM(stars) FROM users")
        total_stars = cur.fetchone()[0] or 0
        conn.close()
        
        text = f"""📊 СТАТИСТИКА МАГАЗИНА

👥 Всего пользователей: {total_users}
💰 Общий баланс: {total_balance} ₽
⭐ Всего звезд: {total_stars}
👤 Твои рефералы: {user[7] if user else 0}
💸 Заработано: {user[8] if user else 0} ₽"""
        
        bot.send_message(call.message.chat.id, text, reply_markup=menu_button())
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    # ===== КАТАЛОГ =====
    if call.data == "catalog":
        categories = get_categories()
        if not categories:
            bot.send_message(call.message.chat.id, "🛒 Товаров пока нет", reply_markup=menu_button())
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            for cat in categories:
                kb.add(types.InlineKeyboardButton(f"📁 {cat}", callback_data=f"user_cat_{cat}"))
            kb.add(types.InlineKeyboardButton("🔙 Меню", callback_data="menu"))
            bot.send_message(call.message.chat.id, "🛒 ВЫБЕРИ КАТЕГОРИЮ", reply_markup=kb)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    # ===== КАТЕГОРИЯ В КАТАЛОГЕ =====
    if call.data.startswith("user_cat_"):
        category = call.data.split("_")[2]
        products = get_products_by_category(category)
        if not products:
            bot.send_message(call.message.chat.id, f"📭 В категории {category} нет товаров", reply_markup=back_to_catalog())
        else:
            kb = types.InlineKeyboardMarkup(row_width=1)
            for p in products:
                price_text = f"{p[3]}₽" if p[3] > 0 else ""
                if p[4] > 0:
                    price_text += f" {p[4]}⭐"
                kb.add(types.InlineKeyboardButton(f"📦 {p[1]} - {price_text}", callback_data=f"user_buy_{p[0]}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="catalog"))
            bot.send_message(call.message.chat.id, f"📁 {category}\n\nВыбери товар:", reply_markup=kb)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    # ===== КУПИТЬ ТОВАР (выбор валюты) =====
    if call.data.startswith("user_buy_"):
        product_id = int(call.data.split("_")[2])
        p = get_product_by_id(product_id)
        if p:
            kb = types.InlineKeyboardMarkup(row_width=2)
            has_currency = p[3] > 0
            has_stars = p[4] > 0
            
            if has_currency:
                kb.add(types.InlineKeyboardButton(f"💰 Купить за {p[3]}₽", callback_data=f"buy_currency_{product_id}"))
            if has_stars:
                kb.add(types.InlineKeyboardButton(f"⭐ Купить за {p[4]}⭐", callback_data=f"buy_stars_{product_id}"))
            kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="catalog"))
            bot.send_message(call.message.chat.id, f"📦 {p[1]}\n\nВыбери способ оплаты:", reply_markup=kb)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        bot.answer_callback_query(call.id)
        return

    # ===== КУПИТЬ ЗА ЗВЕЗДЫ =====
    if call.data.startswith("buy_stars_"):
        product_id = int(call.data.split("_")[2])
        product = get_product_by_id(product_id)
        
        if not product:
            bot.answer_callback_query(call.id, "❌ Товар не найден!", True)
            return
        
        if product[5] <= 0:
            bot.answer_callback_query(call.id, "❌ Товара нет в наличии!", True)
            return
        
        user_stars = get_stars(call.from_user.id)
        if user_stars < product[4]:
            bot.answer_callback_query(call.id, f"❌ Не хватает звезд! Нужно {product[4]}⭐", True)
            return
        
        new_stars = remove_stars(call.from_user.id, product[4])
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE products SET stock = stock - 1 WHERE id = %s", (product_id,))
        conn.commit()
        conn.close()
        
        save_order(call.from_user.id, product_id, product[4], 'stars')
        
        bot.answer_callback_query(call.id, f"✅ Куплено за {product[4]}⭐!")
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 В каталог", callback_data="catalog"))
        kb.add(types.InlineKeyboardButton("🏠 Меню", callback_data="menu"))
        
        bot.send_message(call.from_user.id, 
            f"✅ ПОКУПКА УСПЕШНА!\n\n📦 {product[1]}\n📁 {product[2]}\n⭐ Цена: {product[4]}⭐\n📦 Остаток: {product[5]-1} шт\n\n⭐ Остаток звезд: {new_stars}⭐",
            reply_markup=kb)
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    # ===== КУПИТЬ ЗА ВАЛЮТУ =====
    if call.data.startswith("buy_currency_"):
        product_id = int(call.data.split("_")[2])
        product = get_product_by_id(product_id)
        
        if not product:
            bot.answer_callback_query(call.id, "❌ Товар не найден!", True)
            return
        
        if product[5] <= 0:
            bot.answer_callback_query(call.id, "❌ Товара нет в наличии!", True)
            return
        
        user_balance = get_balance(call.from_user.id)
        if user_balance < product[3]:
            bot.answer_callback_query(call.id, f"❌ Не хватает! Нужно {product[3]}₽", True)
            return
        
        new_balance = remove_money(call.from_user.id, product[3])
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE products SET stock = stock - 1 WHERE id = %s", (product_id,))
        conn.commit()
        conn.close()
        
        save_order(call.from_user.id, product_id, product[3], 'currency')
        
        bot.answer_callback_query(call.id, f"✅ Куплено за {product[3]}₽!")
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 В каталог", callback_data="catalog"))
        kb.add(types.InlineKeyboardButton("🏠 Меню", callback_data="menu"))
        
        bot.send_message(call.from_user.id, 
            f"✅ ПОКУПКА УСПЕШНА!\n\n📦 {product[1]}\n📁 {product[2]}\n💰 Цена: {product[3]}₽\n📦 Остаток: {product[5]-1} шт\n\n💰 Новый баланс: {new_balance}₽",
            reply_markup=kb)
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    # ===== АДМИН =====
    if call.data == "admin":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.send_message(call.message.chat.id, "⚙️ АДМИН-ПАНЕЛЬ", reply_markup=admin_menu())
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    if call.data == "admin_products":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.send_message(call.message.chat.id, "📦 ВЫБЕРИ КАТЕГОРИЮ", reply_markup=categories_menu())
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("product_"):
        product_id = int(call.data.split("_")[1])
        p = get_product_by_id(product_id)
        if p:
            price_text = f"{p[3]}₽" if p[3] > 0 else ""
            if p[4] > 0:
                price_text += f" / {p[4]}⭐"
            text = f"📦 {p[1]}\n📁 Категория: {p[2]}\n💰 Цена: {price_text}\n📦 В наличии: {p[5]} шт"
            bot.send_message(call.message.chat.id, text, reply_markup=product_actions_menu(product_id))
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        bot.answer_callback_query(call.id)
        return

    if call.data == "add_product":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        msg = bot.send_message(call.message.chat.id, 
            "➕ ДОБАВИТЬ ТОВАР\n\n"
            "Формат:\n"
            "Название | Категория | Цена₽ | Цена⭐ | Количество\n\n"
            "Если цена 0 - значит товар бесплатный\n\n"
            "Примеры:\n"
            "VIP Access | Премиумы | 0 | 50 | 10\n"
            "Wallhack | Читы | 500 | 0 | 20")
        bot.register_next_step_handler(msg, process_add_product)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("delete_"):
        product_id = int(call.data.split("_")[1])
        product = get_product_by_id(product_id)
        delete_product(product_id)
        bot.answer_callback_query(call.id, f"✅ {product[1]} удален!")
        bot.send_message(call.message.chat.id, f"✅ Товар '{product[1]}' удален", reply_markup=admin_menu())
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    # ===== ПОЛЬЗОВАТЕЛИ =====
    if call.data == "users" or call.data == "give_money":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет!", True)
            return
        bot.send_message(call.message.chat.id, "👥 ВЫБЕРИ ПОЛЬЗОВАТЕЛЯ", reply_markup=users_menu())
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("user_"):
        user_id = int(call.data.split("_")[1])
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT tg_id, username, balance, stars FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        conn.close()
        if u:
            name = f"@{u[1]}" if u[1] else f"ID: {u[0]}"
            bot.send_message(call.message.chat.id, f"👤 {name}\n💰 {u[2]}₽\n⭐ {u[3]}⭐", 
                           reply_markup=user_actions_menu(user_id))
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        bot.answer_callback_query(call.id)
        return

    # ===== ВЫДАТЬ ДЕНЬГИ =====
    if call.data.startswith("add_"):
        parts = call.data.split("_")
        user_id = int(parts[1])
        amount = int(parts[2])
        
        new_bal = add_money(user_id, amount)
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT tg_id FROM users WHERE id = %s", (user_id,))
        tg = cur.fetchone()
        conn.close()
        
        if tg:
            try:
                bot.send_message(tg[0], f"💰 +{amount}₽\nБаланс: {new_bal}₽")
            except:
                pass
        
        bot.answer_callback_query(call.id, f"✅ +{amount}₽")
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT tg_id, username, balance, stars FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        conn.close()
        if u:
            name = f"@{u[1]}" if u[1] else f"ID: {u[0]}"
            bot.send_message(call.message.chat.id, f"👤 {name}\n💰 {u[2]}₽\n⭐ {u[3]}⭐", 
                           reply_markup=user_actions_menu(user_id))
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        return

    # ===== ВЫДАТЬ ЗВЕЗДЫ =====
    if call.data.startswith("add_stars_"):
        parts = call.data.split("_")
        user_id = int(parts[2])
        amount = int(parts[3])
        
        new_stars = add_stars(user_id, amount)
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT tg_id FROM users WHERE id = %s", (user_id,))
        tg = cur.fetchone()
        conn.close()
        
        if tg:
            try:
                bot.send_message(tg[0], f"⭐ +{amount}⭐\nВсего звезд: {new_stars}⭐")
            except:
                pass
        
        bot.answer_callback_query(call.id, f"✅ +{amount}⭐")
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT tg_id, username, balance, stars FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        conn.close()
        if u:
            name = f"@{u[1]}" if u[1] else f"ID: {u[0]}"
            bot.send_message(call.message.chat.id, f"👤 {name}\n💰 {u[2]}₽\n⭐ {u[3]}⭐", 
                           reply_markup=user_actions_menu(user_id))
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        return

# ===== ДОБАВЛЕНИЕ ТОВАРА =====
def process_add_product(msg):
    try:
        data = msg.text.split('|')
        if len(data) < 5:
            bot.send_message(msg.chat.id, 
                "❌ Неверный формат!\n\nНужно:\nНазвание | Категория | Цена₽ | Цена⭐ | Количество")
            return
        
        name = data[0].strip()
        category = data[1].strip()
        price = int(data[2].strip())
        stars_price = int(data[3].strip())
        stock = int(data[4].strip())
        
        add_product(name, category, price, stars_price, stock)
        bot.send_message(msg.chat.id, f"✅ Товар '{name}' добавлен!\n💰 Цена: {price}₽\n⭐ Цена: {stars_price}⭐", 
                        reply_markup=admin_menu())
    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Ошибка! {e}", reply_markup=admin_menu())

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🤖 Запуск бота...")
    
    if not DATABASE_URL:
        print("❌ ОШИБКА: DATABASE_URL не найден!")
        exit(1)
    
    if not init_db():
        print("❌ Ошибка подключения к БД!")
        exit(1)
    
    print("🤖 Бот запущен!")
    
    # Удаляем вебхук чтобы избежать ошибки 409
    try:
        bot.remove_webhook()
        print("✅ Webhook удален")
    except:
        pass
    
    time.sleep(2)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)