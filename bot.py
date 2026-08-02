import os
import time
import psycopg2
import psycopg2.extras
import telebot
from telebot import types
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# ⚠️ ВАЖНО: Замените на ваш Telegram ID
ADMIN_IDS = [7845398556]  # Сюда ваш ID!

bot = telebot.TeleBot(TOKEN)

# =========================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# =========================

def get_db():
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL не установлен!")
    return psycopg2.connect(DATABASE_URL)

def wait_for_db(max_retries=10, delay=5):
    for i in range(max_retries):
        try:
            conn = get_db()
            conn.close()
            print(f"✅ База данных готова! (попытка {i+1})")
            return True
        except Exception as e:
            print(f"⏳ Ожидание БД... попытка {i+1}/{max_retries}")
            time.sleep(delay)
    return False

def create_tables():
    try:
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
        
        # Таблица транзакций (для истории)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                amount NUMERIC(10,2) NOT NULL,
                type VARCHAR(50) NOT NULL,
                description TEXT,
                admin_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Таблицы созданы/проверены")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        return False

# =========================
# РАБОТА С ПОЛЬЗОВАТЕЛЯМИ
# =========================

def register_user(message):
    try:
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
    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        return None

def is_admin(telegram_id):
    if telegram_id in ADMIN_IDS:
        return True
    
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

def get_user_by_telegram_id(telegram_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, telegram_id, username, balance FROM users WHERE telegram_id = %s",
            (telegram_id,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except:
        return None

def get_user_by_username(username):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, telegram_id, username, balance FROM users WHERE username ILIKE %s",
            (username,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except:
        return None

def update_balance(user_id, amount, transaction_type, description, admin_id=None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Обновляем баланс
        cursor.execute(
            "UPDATE users SET balance = balance + %s WHERE id = %s RETURNING balance",
            (amount, user_id)
        )
        new_balance = cursor.fetchone()[0]
        
        # Записываем транзакцию
        cursor.execute("""
            INSERT INTO transactions (user_id, amount, type, description, admin_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, amount, transaction_type, description, admin_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return new_balance
    except Exception as e:
        print(f"❌ Ошибка обновления баланса: {e}")
        return None

def get_transactions(user_id, limit=10):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, amount, type, description, created_at
            FROM transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        
        transactions = cursor.fetchall()
        cursor.close()
        conn.close()
        return transactions
    except:
        return []

# =========================
# МЕНЮ И КНОПКИ
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

def back_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back"))
    return keyboard

def admin_panel_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📦 Товары", callback_data="admin_products"),
        types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
    )
    keyboard.add(
        types.InlineKeyboardButton("💰 Управление балансом", callback_data="admin_balance"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    )
    keyboard.add(
        types.InlineKeyboardButton("➕ Добавить товар", callback_data="product_add"),
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="back")
    )
    return keyboard

def products_list_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, price, stock, is_active FROM products ORDER BY id DESC LIMIT 10"
        )
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not products:
            keyboard.add(types.InlineKeyboardButton("📭 Товаров пока нет", callback_data="ignore"))
        else:
            for product in products:
                status = "✅" if product[4] else "❌"
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"{status} {product[1]} - {product[2]}₽ (в наличии: {product[3]})",
                        callback_data=f"product_view_{product[0]}"
                    )
                )
    except:
        keyboard.add(types.InlineKeyboardButton("⚠️ Ошибка загрузки", callback_data="ignore"))
    
    keyboard.add(
        types.InlineKeyboardButton("➕ Добавить товар", callback_data="product_add"),
        types.InlineKeyboardButton("🔙 Админ-панель", callback_data="admin_panel")
    )
    return keyboard

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

def cancel_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("❌ Отмена", callback_data="admin_panel"))
    return keyboard

# =========================
# УПРАВЛЕНИЕ БАЛАНСОМ
# =========================

def balance_management_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Выдать деньги", callback_data="balance_add"),
        types.InlineKeyboardButton("➖ Списать деньги", callback_data="balance_remove")
    )
    keyboard.add(
        types.InlineKeyboardButton("📊 История транзакций", callback_data="balance_history"),
        types.InlineKeyboardButton("👤 Найти пользователя", callback_data="balance_find_user")
    )
    keyboard.add(
        types.InlineKeyboardButton("🔙 Админ-панель", callback_data="admin_panel")
    )
    return keyboard

def user_list_menu(page=1, per_page=5):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        offset = (page - 1) * per_page
        cursor.execute("""
            SELECT id, telegram_id, username, balance 
            FROM users 
            ORDER BY id DESC 
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        
        users = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        if not users:
            keyboard.add(types.InlineKeyboardButton("📭 Пользователей нет", callback_data="ignore"))
        else:
            for user in users:
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"👤 @{user[2] or user[1]} - {user[3]}₽",
                        callback_data=f"user_balance_{user[0]}"
                    )
                )
        
        # Пагинация
        total_pages = (total + per_page - 1) // per_page
        nav_buttons = []
        
        if page > 1:
            nav_buttons.append(types.InlineKeyboardButton("⬅️", callback_data=f"users_page_{page-1}"))
        
        if total_pages > 0:
            nav_buttons.append(types.InlineKeyboardButton(f"{page}/{total_pages}", callback_data="ignore"))
        
        if page < total_pages:
            nav_buttons.append(types.InlineKeyboardButton("➡️", callback_data=f"users_page_{page+1}"))
        
        if nav_buttons:
            keyboard.row(*nav_buttons)
            
    except:
        keyboard.add(types.InlineKeyboardButton("⚠️ Ошибка", callback_data="ignore"))
    
    keyboard.add(
        types.InlineKeyboardButton("🔙 Управление балансом", callback_data="admin_balance")
    )
    return keyboard

def user_balance_menu(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Выдать 100₽", callback_data=f"user_add_{user_id}_100"),
        types.InlineKeyboardButton("➕ Выдать 500₽", callback_data=f"user_add_{user_id}_500")
    )
    keyboard.add(
        types.InlineKeyboardButton("➕ Выдать 1000₽", callback_data=f"user_add_{user_id}_1000"),
        types.InlineKeyboardButton("💸 Своя сумма", callback_data=f"user_custom_{user_id}")
    )
    keyboard.add(
        types.InlineKeyboardButton("📊 История", callback_data=f"user_history_{user_id}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_balance")
    )
    return keyboard

# =========================
# СТАТИСТИКА
# =========================

def stats_menu():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("📊 Общая статистика", callback_data="stats_general"),
        types.InlineKeyboardButton("📈 Топ пользователей", callback_data="stats_top")
    )
    keyboard.add(
        types.InlineKeyboardButton("🔙 Админ-панель", callback_data="admin_panel")
    )
    return keyboard

# =========================
# ОБРАБОТЧИКИ КОМАНД
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message)
    
    keyboard = main_menu()
    if is_admin(message.from_user.id):
        keyboard.add(types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    
    bot.send_message(
        message.chat.id,
        "👋 <b>Добро пожаловать в магазин!</b>\n\n"
        "Выберите нужный раздел:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# =========================
# ОСНОВНЫЕ ОБРАБОТЧИКИ
# =========================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "ignore":
        bot.answer_callback_query(call.id)
        return
    
    # ====== АДМИН-ПАНЕЛЬ ======
    if call.data == "admin_panel":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "⚙️ <b>АДМИН-ПАНЕЛЬ</b>\n\nУправление магазином:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=admin_panel_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== УПРАВЛЕНИЕ БАЛАНСОМ ======
    if call.data == "admin_balance":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "💰 <b>УПРАВЛЕНИЕ БАЛАНСОМ</b>\n\n"
            "Выберите действие:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=balance_management_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ВЫДАТЬ ДЕНЬГИ ======
    if call.data == "balance_add":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "➕ <b>ВЫДАТЬ ДЕНЬГИ</b>\n\n"
            "Выберите пользователя:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=user_list_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== СПИСАТЬ ДЕНЬГИ ======
    if call.data == "balance_remove":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "➖ <b>СПИСАТЬ ДЕНЬГИ</b>\n\n"
            "Выберите пользователя:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=user_list_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ПОЛЬЗОВАТЕЛИ (пагинация) ======
    if call.data.startswith("users_page_"):
        page = int(call.data.split("_")[2])
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=user_list_menu(page=page)
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ПОЛЬЗОВАТЕЛЬ - БАЛАНС ======
    if call.data.startswith("user_balance_"):
        user_id = int(call.data.split("_")[2])
        user = get_user_by_telegram_id(user_id)
        
        if user:
            text = (
                f"👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n\n"
                f"🆔 ID: <code>{user[1]}</code>\n"
                f"👤 Username: @{user[2] or 'Не указан'}\n"
                f"💰 Баланс: <b>{user[3]} ₽</b>"
            )
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=user_balance_menu(user_id)
            )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ВЫДАТЬ СУММУ ======
    if call.data.startswith("user_add_"):
        parts = call.data.split("_")
        user_id = int(parts[2])
        amount = float(parts[3])
        
        user = get_user_by_telegram_id(user_id)
        if user:
            new_balance = update_balance(
                user_id, 
                amount, 
                "add", 
                f"Пополнение баланса на {amount}₽",
                call.from_user.id
            )
            
            if new_balance is not None:
                bot.answer_callback_query(
                    call.id, 
                    f"✅ Выдано {amount}₽ пользователю @{user[2] or user[1]}"
                )
                
                # Отправляем уведомление пользователю
                try:
                    bot.send_message(
                        user[1],
                        f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
                        f"Сумма: <b>+{amount} ₽</b>\n"
                        f"Новый баланс: <b>{new_balance} ₽</b>",
                        parse_mode="HTML"
                    )
                except:
                    pass
                
                # Обновляем сообщение
                user = get_user_by_telegram_id(user_id)
                if user:
                    text = (
                        f"👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n\n"
                        f"🆔 ID: <code>{user[1]}</code>\n"
                        f"👤 Username: @{user[2] or 'Не указан'}\n"
                        f"💰 Баланс: <b>{user[3]} ₽</b>"
                    )
                    bot.edit_message_text(
                        text,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode="HTML",
                        reply_markup=user_balance_menu(user_id)
                    )
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при выдаче!", show_alert=True)
        return
    
    # ====== СПИСАТЬ СУММУ ======
    if call.data.startswith("user_remove_"):
        parts = call.data.split("_")
        user_id = int(parts[2])
        amount = -float(parts[3])
        
        user = get_user_by_telegram_id(user_id)
        if user and user[3] >= abs(amount):
            new_balance = update_balance(
                user_id, 
                amount, 
                "remove", 
                f"Списание баланса на {abs(amount)}₽",
                call.from_user.id
            )
            
            if new_balance is not None:
                bot.answer_callback_query(
                    call.id, 
                    f"✅ Списано {abs(amount)}₽ у @{user[2] or user[1]}"
                )
                
                # Отправляем уведомление пользователю
                try:
                    bot.send_message(
                        user[1],
                        f"💰 <b>СПИСАНИЕ БАЛАНСА</b>\n\n"
                        f"Сумма: <b>-{abs(amount)} ₽</b>\n"
                        f"Новый баланс: <b>{new_balance} ₽</b>",
                        parse_mode="HTML"
                    )
                except:
                    pass
                
                # Обновляем сообщение
                user = get_user_by_telegram_id(user_id)
                if user:
                    text = (
                        f"👤 <b>ПОЛЬЗОВАТЕЛЬ</b>\n\n"
                        f"🆔 ID: <code>{user[1]}</code>\n"
                        f"👤 Username: @{user[2] or 'Не указан'}\n"
                        f"💰 Баланс: <b>{user[3]} ₽</b>"
                    )
                    bot.edit_message_text(
                        text,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode="HTML",
                        reply_markup=user_balance_menu(user_id)
                    )
            else:
                bot.answer_callback_query(call.id, "❌ Ошибка при списании!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств!", show_alert=True)
        return
    
    # ====== ПОЛЬЗОВАТЕЛЬ - СВОЯ СУММА ======
    if call.data.startswith("user_custom_"):
        user_id = int(call.data.split("_")[2])
        
        bot.edit_message_text(
            "💸 <b>ВВЕДИТЕ СУММУ</b>\n\n"
            "Введите сумму для выдачи (с плюсом) или списания (с минусом):\n\n"
            "Примеры:\n"
            "<code>+100</code> - выдать 100₽\n"
            "<code>-50</code> - списать 50₽\n\n"
            "Или отправьте 'отмена' для выхода.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=cancel_button()
        )
        
        bot.register_next_step_handler(call.message, process_custom_balance, user_id)
        bot.answer_callback_query(call.id)
        return
    
    # ====== ИСТОРИЯ ТРАНЗАКЦИЙ ======
    if call.data == "balance_history":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "📊 <b>ИСТОРИЯ ТРАНЗАКЦИЙ</b>\n\n"
            "Выберите пользователя:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=user_list_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("user_history_"):
        user_id = int(call.data.split("_")[2])
        user = get_user_by_telegram_id(user_id)
        transactions = get_transactions(user_id, 15)
        
        if user and transactions:
            text = f"📊 <b>ИСТОРИЯ @{user[2] or user[1]}</b>\n\n"
            
            for t in transactions:
                amount = t[1]
                type_text = "➕" if amount > 0 else "➖"
                date = t[4].strftime("%d.%m.%Y %H:%M")
                text += f"{type_text} {amount}₽ | {t[2]}\n"
                text += f"   📝 {t[3]}\n"
                text += f"   🕐 {date}\n\n"
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton("🔙 Назад", callback_data=f"user_balance_{user_id}")
            )
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            bot.edit_message_text(
                "📭 У пользователя нет транзакций",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=back_button()
            )
        bot.answer_callback_query(call.id)
        return
    
    # ====== СТАТИСТИКА ======
    if call.data == "admin_stats":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "📊 <b>СТАТИСТИКА</b>\n\n"
            "Выберите тип статистики:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=stats_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "stats_general":
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = TRUE")
            total_products = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(balance) FROM users")
            total_balance = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            text = (
                f"📊 <b>ОБЩАЯ СТАТИСТИКА</b>\n\n"
                f"👥 Всего пользователей: <b>{total_users}</b>\n"
                f"🛒 Активных товаров: <b>{total_products}</b>\n"
                f"💰 Общий баланс: <b>{total_balance} ₽</b>\n"
                f"📦 Всего заказов: <b>{total_orders}</b>"
            )
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=stats_menu()
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
        return
    
    if call.data == "stats_top":
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT username, balance 
                FROM users 
                WHERE balance > 0 
                ORDER BY balance DESC 
                LIMIT 10
            """)
            
            top_users = cursor.fetchall()
            cursor.close()
            conn.close()
            
            text = "🏆 <b>ТОП ПОЛЬЗОВАТЕЛЕЙ ПО БАЛАНСУ</b>\n\n"
            
            if top_users:
                for i, user in enumerate(top_users, 1):
                    text += f"{i}. @{user[0] or 'Пользователь'} - <b>{user[1]} ₽</b>\n"
            else:
                text += "📭 Пока нет пользователей с балансом"
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=stats_menu()
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
        return
    
    # ====== ОБРАБОТКА ТОВАРОВ ======
    if call.data == "admin_products":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ У вас нет доступа!", show_alert=True)
            return
        
        bot.edit_message_text(
            "📦 <b>СПИСОК ТОВАРОВ</b>\n\nПоследние 10 товаров:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=products_list_menu()
        )
        bot.answer_callback_query(call.id)
        return
    
    # ====== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (товары, каталог и т.д.) ======
    # ... (код из предыдущей версии для товаров)
    
    # ====== НАЗАД ======
    if call.data == "back":
        keyboard = main_menu()
        if is_admin(call.from_user.id):
            keyboard.add(types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
        
        bot.edit_message_text(
            "👋 <b>Главное меню</b>\n\nВыберите нужный раздел:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        bot.answer_callback_query(call.id)
        return

# =========================
# ОБРАБОТКА СВОЕЙ СУММЫ
# =========================

def process_custom_balance(message, user_id):
    if message.text.lower() == "отмена":
        bot.send_message(
            message.chat.id,
            "❌ Операция отменена",
            reply_markup=admin_panel_menu()
        )
        return
    
    try:
        amount = float(message.text.strip())
        user = get_user_by_telegram_id(user_id)
        
        if not user:
            bot.send_message(
                message.chat.id,
                "❌ Пользователь не найден",
                reply_markup=admin_panel_menu()
            )
            return
        
        if amount > 0:
            # Выдача
            new_balance = update_balance(
                user_id, 
                amount, 
                "add", 
                f"Пополнение баланса на {amount}₽ (админ)",
                message.from_user.id
            )
            
            if new_balance is not None:
                bot.send_message(
                    message.chat.id,
                    f"✅ Выдано {amount}₽ пользователю @{user[2] or user[1]}\n"
                    f"Новый баланс: {new_balance}₽",
                    reply_markup=admin_panel_menu()
                )
                
                try:
                    bot.send_message(
                        user[1],
                        f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\n"
                        f"Сумма: <b>+{amount} ₽</b>\n"
                        f"Новый баланс: <b>{new_balance} ₽</b>",
                        parse_mode="HTML"
                    )
                except:
                    pass
            
        elif amount < 0:
            # Списание
            amount_abs = abs(amount)
            if user[3] >= amount_abs:
                new_balance = update_balance(
                    user_id, 
                    amount, 
                    "remove", 
                    f"Списание баланса на {amount_abs}₽ (админ)",
                    message.from_user.id
                )
                
                if new_balance is not None:
                    bot.send_message(
                        message.chat.id,
                        f"✅ Списано {amount_abs}₽ у @{user[2] or user[1]}\n"
                        f"Новый баланс: {new_balance}₽",
                        reply_markup=admin_panel_menu()
                    )
                    
                    try:
                        bot.send_message(
                            user[1],
                            f"💰 <b>СПИСАНИЕ БАЛАНСА</b>\n\n"
                            f"Сумма: <b>-{amount_abs} ₽</b>\n"
                            f"Новый баланс: <b>{new_balance} ₽</b>",
                            parse_mode="HTML"
                        )
                    except:
                        pass
            else:
                bot.send_message(
                    message.chat.id,
                    f"❌ Недостаточно средств!\n"
                    f"Баланс пользователя: {user[3]}₽",
                    reply_markup=admin_panel_menu()
                )
        else:
            bot.send_message(
                message.chat.id,
                "❌ Сумма должна быть не равна 0",
                reply_markup=admin_panel_menu()
            )
            
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Неверный формат! Введите число:\n"
            "<code>+100</code> - выдать 100₽\n"
            "<code>-50</code> - списать 50₽",
            parse_mode="HTML",
            reply_markup=admin_panel_menu()
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {str(e)}",
            reply_markup=admin_panel_menu()
        )

# =========================
# ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ ТОВАРОВ
# =========================

# (Вставьте сюда обработчики товаров из предыдущего кода)
# Для краткости пропущены, но они должны быть

# =========================
# ЗАПУСК БОТА
# =========================

if __name__ == "__main__":
    print("🚀 Запуск бота...")
    print(f"📊 DATABASE_URL: {'Установлен' if DATABASE_URL else 'НЕ УСТАНОВЛЕН!'}")
    
    if DATABASE_URL:
        if wait_for_db():
            if create_tables():
                print("✅ Бот готов к работе!")
                print(f"👑 Админы: {ADMIN_IDS}")
                
                try:
                    bot.infinity_polling(timeout=10, long_polling_timeout=5)
                except Exception as e:
                    print(f"⚠️ Ошибка polling: {e}")
                    while True:
                        try:
                            bot.polling(none_stop=True, interval=1, timeout=20)
                        except Exception as e:
                            print(f"🔄 Перезапуск... Ошибка: {e}")
                            time.sleep(5)
            else:
                print("❌ Не удалось создать таблицы")
        else:
            print("❌ Не удалось подключиться к БД")
    else:
        print("❌ DATABASE_URL не найден! Добавьте PostgreSQL в Railway.")