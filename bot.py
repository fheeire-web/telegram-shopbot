import os
import psycopg2
import psycopg2.extras
import telebot
from telebot import types
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ⚠️ ВАЖНО: Замените на ваш Telegram ID (узнать можно у @userinfobot)
ADMIN_IDS = [123456789]  # Сюда вставьте свой ID!

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    # Сначала проверяем по списку
    if telegram_id in ADMIN_IDS:
        return True
    
    # Потом проверяем в БД
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_admin FROM users WHERE telegram_id = %s",
            (telegram_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result and result[0]
    except:
        return False

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
# КНОПКИ НАЗАД
# =========================

def back_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="back")
    )
    return keyboard

# =========================
# АДМИН-ПАНЕЛЬ
# =========================

def admin_panel_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        types.InlineKeyboardButton("📦 Товары", callback_data="admin_products"),
        types.InlineKeyboardButton("📊 Заказы", callback_data="admin_orders")
    )
    
    keyboard.add(
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        types.InlineKeyboardButton("➕ Добавить товар", callback_data="product_add")
    )
    
    keyboard.add(
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="back")
    )
    
    return keyboard

# =========================
# СПИСОК ТОВАРОВ ДЛЯ АДМИНА
# =========================

def products_list_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, price, stock, is_active FROM products ORDER BY id DESC LIMIT 10"
    )
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not products:
        keyboard.add(
            types.InlineKeyboardButton("📭 Товаров пока нет", callback_data="ignore")
        )
    else:
        for product in products:
            status = "✅" if product[4] else "❌"
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{status} {product[1]} - {product[2]}₽ (в наличии: {product[3]})",
                    callback_data=f"product_view_{product[0]}"
                )
            )
    
    keyboard.add(
        types.InlineKeyboardButton("➕ Добавить товар", callback_data="product_add"),
        types.InlineKeyboardButton("🔙 Админ-панель", callback_data="admin_panel")
    )
    
    return keyboard

# =========================
# ПРОСМОТР ТОВАРА
# =========================

def product_view_menu(product_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"product_edit_{product_id}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"product_delete_{product_id}")
    )
    
    keyboard.add(
        types.InlineKeyboardButton("🔄 Вкл/Откл", callback_data=f"product_toggle_{product_id}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_products")
    )
    
    return keyboard

# =========================
# СТАРТ
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message)
    
    keyboard = main_menu()
    
    # Если админ - добавляем кнопку админ-панели
    if is_admin(message.from_user.id):
        admin_button = types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")
        keyboard.add(admin_button)
    
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
def handle_callback(call):
    # Игнорируем пустые callback
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
        bot.answer_callback_query(call.id)
        return
    
    # ====== ТОВАРЫ АДМИНА ======
    if call.data == "admin_products":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "📦 <b>СПИСОК ТОВАРОВ</b>\n\n"
            "Последние 10 товаров:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=products_list_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ПРОСМОТР ТОВАРА ======
    if call.data.startswith("product_view_"):
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
                reply_markup=product_view_menu(product_id)
            )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ДОБАВЛЕНИЕ ТОВАРА ======
    if call.data == "product_add":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "➕ <b>ДОБАВЛЕНИЕ ТОВАРА</b>\n\n"
            "Отправьте данные в формате:\n\n"
            "<code>Название | Цена | Количество | Категория | Описание</code>\n\n"
            "Пример:\n"
            "<code>PlayStation 5 | 50000 | 10 | Консоли | Новая консоль</code>\n\n"
            "Или нажмите 'Отмена'",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=cancel_button()
        )
        
        # Сохраняем состояние
        bot.register_next_step_handler(call.message, process_add_product)
        bot.answer_callback_query(call.id)
        return
    
    # ====== РЕДАКТИРОВАНИЕ ТОВАРА ======
    if call.data.startswith("product_edit_"):
        product_id = int(call.data.split("_")[2])
        
        bot.edit_message_text(
            f"✏️ <b>РЕДАКТИРОВАНИЕ ТОВАРА #{product_id}</b>\n\n"
            "Отправьте новые данные в формате:\n"
            "<code>Название | Цена | Количество | Категория | Описание</code>",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=cancel_button()
        )
        
        bot.register_next_step_handler(call.message, process_edit_product, product_id)
        bot.answer_callback_query(call.id)
        return
    
    # ====== УДАЛЕНИЕ ТОВАРА ======
    if call.data.startswith("product_delete_"):
        product_id = int(call.data.split("_")[2])
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"product_confirm_delete_{product_id}"),
            types.InlineKeyboardButton("❌ Нет, отмена", callback_data=f"product_view_{product_id}")
        )
        
        bot.edit_message_text(
            f"⚠️ <b>ВЫ УВЕРЕНЫ?</b>\n\n"
            f"Товар #{product_id} будет удален без возможности восстановления.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ======
    if call.data.startswith("product_confirm_delete_"):
        product_id = int(call.data.split("_")[3])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        bot.edit_message_text(
            f"✅ Товар #{product_id} успешно удален!",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=products_list_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ВКЛ/ОТКЛ ТОВАРА ======
    if call.data.startswith("product_toggle_"):
        product_id = int(call.data.split("_")[2])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET is_active = NOT is_active WHERE id = %s RETURNING is_active",
            (product_id,)
        )
        new_status = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        status_text = "активирован" if new_status else "деактивирован"
        bot.answer_callback_query(call.id, f"✅ Товар {status_text}!")
        
        # Обновляем сообщение
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
                reply_markup=product_view_menu(product_id)
            )
        return
    
    # ====== КАТАЛОГ ======
    if call.data == "catalog":
        keyboard = types.InlineKeyboardMarkup()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, price FROM products WHERE is_active = TRUE ORDER BY id"
        )
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if products:
            for product in products:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"{product[1]} — {product[2]} ₽",
                        callback_data=f"buy_{product[0]}"
                    )
                )
        else:
            keyboard.add(
                types.InlineKeyboardButton("📭 Товаров пока нет", callback_data="ignore")
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
        bot.answer_callback_query(call.id)
        return
    
    # ====== ПОКУПКА ТОВАРА ======
    if call.data.startswith("buy_"):
        product_id = int(call.data.split("_")[1])
        bot.answer_callback_query(
            call.id,
            "💰 Покупка будет доступна после настройки оплаты!"
        )
        return
    
    # ====== ПРОФИЛЬ ======
    if call.data == "profile":
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
        bot.answer_callback_query(call.id)
        return
    
    # ====== ОСТАЛЬНЫЕ РАЗДЕЛЫ ======
    if call.data in ["balance", "purchases", "promo", "support"]:
        texts = {
            "balance": "💰 <b>БАЛАНС</b>\n\nВаш баланс отображается в профиле.",
            "purchases": "📦 <b>МОИ ПОКУПКИ</b>\n\nПокупок пока нет.",
            "promo": "🎟 <b>ПРОМОКОД</b>\n\nФункция промокодов скоро будет доступна.",
            "support": "💬 <b>ПОДДЕРЖКА</b>\n\nОбратитесь к администратору."
        }
        
        bot.edit_message_text(
            texts[call.data],
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=back_button()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== НАЗАД ======
    if call.data == "back":
        keyboard = main_menu()
        
        if is_admin(call.from_user.id):
            admin_button = types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")
            keyboard.add(admin_button)
        
        bot.edit_message_text(
            "👋 <b>Главное меню</b>\n\n"
            "Выберите нужный раздел:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        bot.answer_callback_query(call.id)
        return

# =========================
# КНОПКА ОТМЕНЫ
# =========================

def cancel_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("❌ Отмена", callback_data="admin_products")
    )
    return keyboard

# =========================
# ОБРАБОТКА ДОБАВЛЕНИЯ ТОВАРА
# =========================

def process_add_product(message):
    # Проверяем, не нажал ли пользователь кнопку
    if hasattr(message, 'text') and message.text == "/start":
        start(message)
        return
    
    try:
        data = message.text.split('|')
        if len(data) < 4:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат. Нужно: Название | Цена | Количество | Категория | Описание",
                reply_markup=back_button()
            )
            return
        
        name = data[0].strip()
        price = float(data[1].strip())
        stock = int(data[2].strip())
        category = data[3].strip() if len(data) > 3 else None
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
            reply_markup=products_list_menu()
        )
        
    except ValueError as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}\nПроверьте правильность ввода данных.",
            reply_markup=back_button()
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=back_button()
        )

# =========================
# ОБРАБОТКА РЕДАКТИРОВАНИЯ ТОВАРА
# =========================

def process_edit_product(message, product_id):
    try:
        data = message.text.split('|')
        if len(data) < 4:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат. Нужно: Название | Цена | Количество | Категория | Описание",
                reply_markup=back_button()
            )
            return
        
        name = data[0].strip()
        price = float(data[1].strip())
        stock = int(data[2].strip())
        category = data[3].strip() if len(data) > 3 else None
        description = data[4].strip() if len(data) > 4 else None
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE products 
            SET name = %s, description = %s, price = %s, category = %s, stock = %s
            WHERE id = %s
        """, (name, description, price, category, stock, product_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        bot.send_message(
            message.chat.id,
            f"✅ Товар #{product_id} успешно обновлен!",
            parse_mode="HTML",
            reply_markup=products_list_menu()
        )
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=back_button()
        )

# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":
    # Создаем таблицы
    create_tables()
    
    print("🤖 Бот запущен!")
    print(f"Админы: {ADMIN_IDS}")
    
    # Запускаем бота
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"Ошибка: {e}")
        # Альтернативный запуск
        while True:
            try:
                bot.polling(none_stop=True, interval=1, timeout=20)
            except Exception as e:
                print(f"Перезапуск... Ошибка: {e}")