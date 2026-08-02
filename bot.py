import os
import psycopg2
import psycopg2.extras
import telebot
from telebot import types
import json
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [123456789, 987654321]  # Замените на ID ваших админов

bot = telebot.TeleBot(TOKEN)

# =========================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# =========================

def get_db():
    return psycopg2.connect(DATABASE_URL)

def create_tables():
    conn = get_db()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            balance NUMERIC(10,2) DEFAULT 0,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица товаров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            price NUMERIC(10,2) NOT NULL,
            category VARCHAR(100),
            stock INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица заказов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER DEFAULT 1,
            total_price NUMERIC(10,2),
            status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица ключей для товаров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_keys (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            key_value TEXT NOT NULL,
            is_sold BOOLEAN DEFAULT FALSE,
            order_id INTEGER REFERENCES orders(id),
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
        RETURNING id, is_admin
    """, (
        message.from_user.id,
        message.from_user.username
    ))

    user_data = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()
    
    return user_data

# =========================
# ПРОВЕРКА АДМИНА
# =========================

def is_admin(telegram_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT is_admin FROM users WHERE telegram_id = %s",
        (telegram_id,)
    )
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return result and result[0] or telegram_id in ADMIN_IDS

# =========================
# КНОПКИ НАЗАД
# =========================

def back_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="back")
    )
    return keyboard

def admin_back_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🔙 Админ-панель", callback_data="admin_panel")
    )
    return keyboard

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
# АДМИН-ПАНЕЛЬ
# =========================

def admin_panel_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        types.InlineKeyboardButton("📦 Управление товарами", callback_data="admin_products"),
        types.InlineKeyboardButton("📊 Заказы", callback_data="admin_orders")
    )
    
    keyboard.add(
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        types.InlineKeyboardButton("📈 Статистика", callback_data="admin_stats")
    )
    
    keyboard.add(
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings"),
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="back")
    )
    
    return keyboard

# =========================
# УПРАВЛЕНИЕ ТОВАРАМИ
# =========================

def products_management_menu(page=1, per_page=5):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    conn = get_db()
    cursor = conn.cursor()
    
    offset = (page - 1) * per_page
    cursor.execute("""
        SELECT id, name, price, stock, is_active 
        FROM products 
        ORDER BY id DESC 
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    
    products = cursor.fetchall()
    
    # Считаем общее количество
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    for product in products:
        status = "✅" if product[4] else "❌"
        keyboard.add(
            types.InlineKeyboardButton(
                f"{status} {product[1]} - {product[2]}₽ (в наличии: {product[3]})",
                callback_data=f"product_edit_{product[0]}"
            )
        )
    
    # Пагинация
    nav_buttons = []
    total_pages = (total + per_page - 1) // per_page
    
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton("⬅️", callback_data=f"products_page_{page-1}"))
    
    nav_buttons.append(types.InlineKeyboardButton(f"{page}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages:
        nav_buttons.append(types.InlineKeyboardButton("➡️", callback_data=f"products_page_{page+1}"))
    
    if nav_buttons:
        keyboard.row(*nav_buttons)
    
    keyboard.add(
        types.InlineKeyboardButton("➕ Добавить товар", callback_data="product_add"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")
    )
    
    return keyboard

# =========================
# РЕДАКТИРОВАНИЕ ТОВАРА
# =========================

def product_edit_menu(product_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"product_edit_form_{product_id}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"product_delete_{product_id}")
    )
    
    keyboard.add(
        types.InlineKeyboardButton("📝 Добавить ключи", callback_data=f"product_add_keys_{product_id}"),
        types.InlineKeyboardButton("🔑 Просмотр ключей", callback_data=f"product_keys_{product_id}")
    )
    
    keyboard.add(
        types.InlineKeyboardButton("🔄 Вкл/Откл", callback_data=f"product_toggle_{product_id}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_products")
    )
    
    return keyboard

# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    user_data = register_user(message)
    
    keyboard = main_menu()
    
    # Если админ - добавляем кнопку админ-панели
    if is_admin(message.from_user.id):
        keyboard.add(
            types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")
        )
    
    bot.send_message(
        message.chat.id,
        "👋 <b>Добро пожаловать в магазин!</b>\n\n"
        "Выберите нужный раздел:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# =========================
# ОБРАБОТЧИКИ КНОПОК
# =========================

@bot.callback_query_handler(func=lambda call: True)
def buttons(call):
    if call.data == "ignore":
        bot.answer_callback_query(call.id)
        return
    
    # ====== АДМИН-ПАНЕЛЬ ======
    if call.data == "admin_panel":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "⚙️ <b>АДМИН-ПАНЕЛЬ</b>\n\n"
            "Управление магазином:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_panel_menu()
        )
    
    # ====== УПРАВЛЕНИЕ ТОВАРАМИ ======
    elif call.data == "admin_products":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "📦 <b>УПРАВЛЕНИЕ ТОВАРАМИ</b>\n\n"
            "Список товаров:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=products_management_menu()
        )
    
    elif call.data.startswith("products_page_"):
        page = int(call.data.split("_")[2])
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=products_management_menu(page=page)
        )
    
    elif call.data.startswith("product_edit_"):
        product_id = int(call.data.split("_")[2])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, price, category, stock, is_active FROM products WHERE id = %s",
            (product_id,)
        )
        product = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if product:
            text = (
                f"📦 <b>ТОВАР #{product[0]}</b>\n\n"
                f"📌 Название: <b>{product[1]}</b>\n"
                f"📝 Описание: {product[2] or 'Нет'}\n"
                f"💰 Цена: <b>{product[3]} ₽</b>\n"
                f"📂 Категория: {product[4] or 'Нет'}\n"
                f"📦 В наличии: <b>{product[5]}</b>\n"
                f"🔄 Статус: {'✅ Активен' if product[6] else '❌ Неактивен'}"
            )
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=product_edit_menu(product_id)
            )
    
    # ====== ДОБАВЛЕНИЕ ТОВАРА ======
    elif call.data == "product_add":
        bot.edit_message_text(
            "➕ <b>ДОБАВЛЕНИЕ ТОВАРА</b>\n\n"
            "Введите данные товара в формате:\n\n"
            "<code>Название | Цена | Категория | Количество | Описание</code>\n\n"
            "Пример:\n"
            "<code>PlayStation 5 | 50000 | Консоли | 10 | Новая консоль</code>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_back_button()
        )
        
        # Устанавливаем состояние для ввода
        bot.register_next_step_handler(call.message, process_product_add)
    
    elif call.data == "catalog":
        show_catalog(call)
    
    elif call.data == "profile":
        show_profile(call)
    
    elif call.data == "balance":
        show_balance(call)
    
    elif call.data == "purchases":
        show_purchases(call)
    
    elif call.data == "promo":
        show_promo(call)
    
    elif call.data == "support":
        show_support(call)
    
    elif call.data == "back":
        show_main_menu(call)
    
    elif call.data in ["product_1", "product_2"]:
        bot.answer_callback_query(call.id, "Покупка будет доступна после подключения оплаты.")
        return
    
    bot.answer_callback_query(call.id)

# =========================
# ОБРАБОТКА ДОБАВЛЕНИЯ ТОВАРА
# =========================

def process_product_add(message):
    try:
        data = message.text.split('|')
        if len(data) < 4:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат. Используйте: Название | Цена | Категория | Количество | Описание"
            )
            return
        
        name = data[0].strip()
        price = float(data[1].strip())
        category = data[2].strip()
        stock = int(data[3].strip())
        description = data[4].strip() if len(data) > 4 else None
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (name, description, price, category, stock)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (name, description, price, category, stock))
        
        product_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ Товар <b>{name}</b> успешно добавлен! (ID: {product_id})",
            parse_mode="HTML",
            reply_markup=admin_back_button()
        )
        
    except ValueError as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}\nПроверьте правильность ввода данных."
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при добавлении товара: {str(e)}"
        )

# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def show_catalog(call):
    keyboard = types.InlineKeyboardMarkup()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, price FROM products WHERE is_active = TRUE ORDER BY id"
    )
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    
    for product in products:
        keyboard.add(
            types.InlineKeyboardButton(
                f"{product[1]} — {product[2]} ₽",
                callback_data=f"buy_product_{product[0]}"
            )
        )
    
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    
    bot.edit_message_text(
        "🛒 <b>КАТАЛОГ</b>\n\n"
        "Выберите товар для покупки:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard
    )

def show_profile(call):
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

def show_balance(call):
    bot.edit_message_text(
        "💰 <b>БАЛАНС</b>\n\n"
        "Ваш баланс отображается в профиле.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=back_button()
    )

def show_purchases(call):
    bot.edit_message_text(
        "📦 <b>МОИ ПОКУПКИ</b>\n\n"
        "Покупок пока нет.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=back_button()
    )

def show_promo(call):
    bot.edit_message_text(
        "🎟 <b>ПРОМОКОД</b>\n\n"
        "Функция промокодов скоро будет доступна.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=back_button()
    )

def show_support(call):
    bot.edit_message_text(
        "💬 <b>ПОДДЕРЖКА</b>\n\n"
        "Обратитесь к администратору.",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=back_button()
    )

def show_main_menu(call):
    keyboard = main_menu()
    
    if is_admin(call.from_user.id):
        keyboard.add(
            types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")
        )
    
    bot.edit_message_text(
        "👋 <b>Главное меню</b>\n\n"
        "Выберите нужный раздел:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# =========================
# ЗАПУСК
# =========================

create_tables()

print("🤖 Бот запущен!")
bot.infinity_polling(skip_pending=True)