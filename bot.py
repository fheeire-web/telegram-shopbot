import os
import time
import psycopg2
import telebot
from telebot import types
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS = [7845398556]  # Ваш ID!

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# =========================
# БАЗА ДАННЫХ
# =========================

def get_db():
    return psycopg2.connect(DATABASE_URL)

def create_tables():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                balance NUMERIC(10,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price NUMERIC(10,2) NOT NULL,
                stock INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        print("✅ Таблицы созданы")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        return False

# =========================
# ФУНКЦИИ
# =========================

def register_user(telegram_id, username):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (telegram_id, username)
            VALUES (%s, %s)
            ON CONFLICT (telegram_id)
            DO UPDATE SET username = EXCLUDED.username
            RETURNING id
        """, (telegram_id, username))
        user_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return user_id
    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        return None

def is_admin(telegram_id):
    return telegram_id in ADMIN_IDS

def get_user_by_db_id(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, telegram_id, username, balance FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except:
        return None

def get_all_users(page=1, per_page=5):
    try:
        conn = get_db()
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        cursor.execute("SELECT id, telegram_id, username, balance FROM users ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))
        users = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return users, total
    except:
        return [], 0

def update_balance(user_id, amount, description, admin_id=None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        if not result:
            return None
        new_balance = result[0] + amount
        cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, user_id))
        cursor.execute("INSERT INTO transactions (user_id, amount, type, description, admin_id) VALUES (%s, %s, %s, %s, %s)",
                      (user_id, amount, "add" if amount > 0 else "remove", description, admin_id))
        conn.commit()
        cursor.close()
        conn.close()
        return new_balance
    except:
        return None

# =========================
# МЕНЮ
# =========================

def main_menu(telegram_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🛒 Каталог", callback_data="catalog"),
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )
    keyboard.add(
        types.InlineKeyboardButton("📦 Мои покупки", callback_data="purchases"),
        types.InlineKeyboardButton("💰 Баланс", callback_data="balance")
    )
    if is_admin(telegram_id):
        keyboard.add(types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return keyboard

def admin_panel_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("💰 Баланс", callback_data="admin_balance"),
        types.InlineKeyboardButton("📦 Товары", callback_data="admin_products")
    )
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def user_list_menu(page=1, per_page=5):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    users, total = get_all_users(page, per_page)
    if users:
        for user in users:
            name = f"@{user[2]}" if user[2] else f"ID: {user[1]}"
            keyboard.add(types.InlineKeyboardButton(f"{name} - {user[3]}₽", callback_data=f"user_{user[0]}"))
    else:
        keyboard.add(types.InlineKeyboardButton("📭 Нет пользователей", callback_data="ignore"))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_balance"))
    return keyboard

def user_balance_menu(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ +100₽", callback_data=f"add_{user_id}_100"),
        types.InlineKeyboardButton("➕ +500₽", callback_data=f"add_{user_id}_500")
    )
    keyboard.add(
        types.InlineKeyboardButton("➕ +1000₽", callback_data=f"add_{user_id}_1000"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_balance")
    )
    return keyboard

def back_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="back"))
    return keyboard

def products_list_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price, stock, is_active FROM products ORDER BY id DESC LIMIT 10")
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        if not products:
            keyboard.add(types.InlineKeyboardButton("📭 Товаров нет", callback_data="ignore"))
        else:
            for product in products:
                status = "✅" if product[4] else "❌"
                keyboard.add(types.InlineKeyboardButton(
                    f"{status} {product[1]} - {product[2]}₽ ({product[3]} шт)",
                    callback_data=f"product_{product[0]}"
                ))
    except:
        keyboard.add(types.InlineKeyboardButton("⚠️ Ошибка", callback_data="ignore"))
    keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_panel"))
    return keyboard

def product_view_menu(product_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{product_id}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{product_id}")
    )
    keyboard.add(
        types.InlineKeyboardButton("🔄 Вкл/Откл", callback_data=f"toggle_{product_id}"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="admin_products")
    )
    return keyboard

# =========================
# ОБРАБОТЧИКИ
# =========================

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message.from_user.id, message.from_user.username)
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в магазин!",
        reply_markup=main_menu(message.from_user.id)
    )

@bot.callback_query_handler(func=lambda call: True)
def handle(call):
    if call.data == "ignore":
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "back":
        bot.edit_message_text("👋 Главное меню", call.message.chat.id, call.message.message_id,
                             reply_markup=main_menu(call.from_user.id))
        bot.answer_callback_query(call.id)
        return
    
    # АДМИН-ПАНЕЛЬ
    if call.data == "admin_panel":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.edit_message_text("⚙️ Админ-панель", call.message.chat.id, call.message.message_id,
                             reply_markup=admin_panel_menu())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_balance":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.edit_message_text("💰 Выберите пользователя:", call.message.chat.id, call.message.message_id,
                             reply_markup=user_list_menu())
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "admin_products":
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!", True)
            return
        bot.edit_message_text("📦 Список товаров:", call.message.chat.id, call.message.message_id,
                             reply_markup=products_list_menu())
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("product_"):
        product_id = int(call.data.split("_")[1])
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, price, stock, is_active FROM products WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            cursor.close()
            conn.close()
            if product:
                text = f"📦 {product[1]}\n💰 {product[3]} ₽\n📦 {product[4]} шт\n🔄 {'✅' if product[5] else '❌'}"
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                     reply_markup=product_view_menu(product_id))
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("user_"):
        user_id = int(call.data.split("_")[1])
        user = get_user_by_db_id(user_id)
        if user:
            name = f"@{user[2]}" if user[2] else f"ID: {user[1]}"
            bot.edit_message_text(f"👤 {name}\n💰 Баланс: {user[3]} ₽",
                                 call.message.chat.id, call.message.message_id,
                                 reply_markup=user_balance_menu(user_id))
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("add_"):
        parts = call.data.split("_")
        user_id = int(parts[1])
        amount = float(parts[2])
        user = get_user_by_db_id(user_id)
        if user:
            new_balance = update_balance(user_id, amount, f"+{amount}₽", call.from_user.id)
            if new_balance is not None:
                bot.answer_callback_query(call.id, f"✅ Выдано {amount}₽!")
                try:
                    bot.send_message(user[1], f"💰 +{amount} ₽\nБаланс: {new_balance} ₽")
                except:
                    pass
                user = get_user_by_db_id(user_id)
                if user:
                    name = f"@{user[2]}" if user[2] else f"ID: {user[1]}"
                    bot.edit_message_text(f"👤 {name}\n💰 Баланс: {user[3]} ₽",
                                         call.message.chat.id, call.message.message_id,
                                         reply_markup=user_balance_menu(user_id))
        return
    
    if call.data.startswith("delete_"):
        product_id = int(call.data.split("_")[1])
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Да", callback_data=f"confirm_delete_{product_id}"),
            types.InlineKeyboardButton("❌ Нет", callback_data=f"product_{product_id}")
        )
        bot.edit_message_text(f"⚠️ Удалить товар #{product_id}?", call.message.chat.id, call.message.message_id,
                             reply_markup=keyboard)
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("confirm_delete_"):
        product_id = int(call.data.split("_")[2])
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
            conn.commit()
            cursor.close()
            conn.close()
            bot.edit_message_text(f"✅ Товар #{product_id} удален", call.message.chat.id, call.message.message_id,
                                 reply_markup=products_list_menu())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("toggle_"):
        product_id = int(call.data.split("_")[1])
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE products SET is_active = NOT is_active WHERE id = %s RETURNING is_active", (product_id,))
            cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
            bot.answer_callback_query(call.id, "✅ Статус изменен!")
            # Обновляем
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, price, stock, is_active FROM products WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            cursor.close()
            conn.close()
            if product:
                text = f"📦 {product[1]}\n💰 {product[3]} ₽\n📦 {product[4]} шт\n🔄 {'✅' if product[5] else '❌'}"
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                     reply_markup=product_view_menu(product_id))
        except:
            pass
        return
    
    # ПРОФИЛЬ
    if call.data == "profile":
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE telegram_id = %s", (call.from_user.id,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            balance = user[0] if user else 0
            bot.edit_message_text(f"👤 ПРОФИЛЬ\n💰 Баланс: {balance} ₽",
                                 call.message.chat.id, call.message.message_id,
                                 reply_markup=back_button())
        except:
            pass
        bot.answer_callback_query(call.id)
        return
    
    if call.data == "balance":
        bot.edit_message_text("💰 Баланс в профиле", call.message.chat.id, call.message.message_id,
                             reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    # КАТАЛОГ
    if call.data == "catalog":
        keyboard = types.InlineKeyboardMarkup()
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, price FROM products WHERE is_active = TRUE")
            products = cursor.fetchall()
            cursor.close()
            conn.close()
            if products:
                for p in products:
                    keyboard.add(types.InlineKeyboardButton(f"{p[1]} - {p[2]}₽", callback_data=f"buy_{p[0]}"))
            else:
                keyboard.add(types.InlineKeyboardButton("📭 Нет товаров", callback_data="ignore"))
        except:
            keyboard.add(types.InlineKeyboardButton("⚠️ Ошибка", callback_data="ignore"))
        keyboard.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
        bot.edit_message_text("🛒 КАТАЛОГ", call.message.chat.id, call.message.message_id,
                             reply_markup=keyboard)
        bot.answer_callback_query(call.id)
        return
    
    if call.data.startswith("buy_"):
        bot.answer_callback_query(call.id, "💰 Скоро!", True)
        return
    
    if call.data in ["purchases", "promo", "support"]:
        texts = {"purchases": "📦 Покупок нет", "promo": "🎟 Скоро", "support": "💬 Обратитесь к админу"}
        bot.edit_message_text(texts[call.data], call.message.chat.id, call.message.message_id,
                             reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return

# =========================
# FLASK WEBHOOK
# =========================

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

@app.route('/', methods=['GET'])
def home():
    return 'Bot is running!', 200

# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":
    print("🚀 Запуск бота...")
    create_tables()
    
    # Удаляем старые вебхуки
    try:
        bot.remove_webhook()
        print("✅ Вебхук удален")
    except:
        pass
    time.sleep(2)
    
    # Получаем URL из переменных
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if webhook_url:
        try:
            bot.set_webhook(url=webhook_url)
            print(f"✅ Вебхук установлен: {webhook_url}")
        except Exception as e:
            print(f"❌ Ошибка установки вебхука: {e}")
        
        port = int(os.getenv("PORT", 5000))
        print(f"🚀 Запуск Flask на порту {port}")
        app.run(host='0.0.0.0', port=port)
    else:
        print("⚠️ WEBHOOK_URL не установлен! Использую polling...")
        while True:
            try:
                bot.polling(none_stop=True, interval=1)
            except Exception as e:
                print(f"🔄 Перезапуск... {e}")
                time.sleep(5)