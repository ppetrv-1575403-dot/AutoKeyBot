# bot.py
import json
import logging
import uuid

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from config import BOT_TOKEN, ADMIN_ID
from database import Database
from payments import create_payment, check_payment

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Инициализация базы данных
db = Database()

# Загрузка товаров
with open('products.json', 'r', encoding='utf-8') as f:
    PRODUCTS = json.load(f)

# Временное хранилище для ожидающих платежей
pending_payments = {}

def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for product_id, product in PRODUCTS.items():
        keyboard.add(InlineKeyboardButton(
            f"{product['emoji']} {product['name']} - {product['price']}₽",
            callback_data=f"buy_{product_id}"
        ))
    
    keyboard.add(InlineKeyboardButton("📊 Моя статистика", callback_data="stats"))
    keyboard.add(InlineKeyboardButton("ℹ️ Помощь", callback_data="help"))
    
    return keyboard

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Добавляем пользователя в БД
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""
🎉 Добро пожаловать в магазин цифровых товаров, {user.first_name}!

Здесь вы можете приобрести лицензионные ключи для игр и программ.

⭐️ Наши преимущества:
✅ Мгновенная выдача после оплаты
✅ Официальные лицензионные ключи
✅ Поддержка 24/7
✅ Гарантия возврата при проблемах

💰 Доступные товары:
    """
    
    for product_id, product in PRODUCTS.items():
        welcome_text += f"\n{product['emoji']} *{product['name']}* - {product['price']}₽\n_{product['description']}_\n"
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "stats")
async def show_stats(callback_query: types.CallbackQuery):
    """Показать статистику пользователя"""
    user_id = callback_query.from_user.id
    stats = db.get_user_stats(user_id)
    
    if stats:
        total_spent, orders_count = stats
        stats_text = f"""
📊 *Ваша статистика:*

💰 Всего потрачено: {total_spent or 0}₽
📦 Количество покупок: {orders_count or 0}
⭐️ Статус: {'Постоянный покупатель' if orders_count and orders_count > 5 else 'Новый покупатель'}
        """
    else:
        stats_text = "📊 У вас пока нет покупок"
    
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(user_id, stats_text, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "help")
async def show_help(callback_query: types.CallbackQuery):
    """Показать помощь"""
    help_text = """
ℹ️ *Как совершить покупку:*

1️⃣ Выберите товар из списка
2️⃣ Нажмите на кнопку с товаром
3️⃣ Подтвердите покупку
4️⃣ Оплатите через банковскую карту
5️⃣ После оплаты бот автоматически отправит ключ

❓ *Частые вопросы:*

*Как быстро приходит ключ?*
Ключ приходит мгновенно после подтверждения оплаты.

*Что делать, если ключ не подошел?*
Напишите администратору, мы заменим ключ или вернем деньги.

*Безопасно ли покупать?*
Да, оплата проходит через защищенный платежный шлюз ЮKassa.

👨‍💻 *По вопросам:*
@support_username
    """
    
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, help_text, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def process_buy(callback_query: types.CallbackQuery):
    """Обработка покупки товара"""
    product_id = callback_query.data.replace('buy_', '')
    product = PRODUCTS.get(product_id)
    
    if not product:
        await bot.answer_callback_query(callback_query.id, "Товар не найден")
        return
    
    # Проверяем наличие ключей
    available_key = db.get_available_key(product_id)
    if not available_key:
        await bot.answer_callback_query(callback_query.id, "Извините, товар временно отсутствует")
        await bot.send_message(ADMIN_ID, f"⚠️ Товар {product['name']} закончился! Нужно добавить ключи.")
        return
    
    # Создаем клавиатуру подтверждения
    confirm_keyboard = InlineKeyboardMarkup(row_width=2)
    confirm_keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{product_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )
    
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        f"🛒 Вы выбрали: *{product['name']}*\n"
        f"💰 Цена: {product['price']}₽\n\n"
        f"Подтвердите покупку:",
        reply_markup=confirm_keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data.startswith('confirm_'))
async def process_payment(callback_query: types.CallbackQuery):
    """Создание платежа"""
    product_id = callback_query.data.replace('confirm_', '')
    product = PRODUCTS.get(product_id)
    user_id = callback_query.from_user.id
    
    if not product:
        await bot.answer_callback_query(callback_query.id, "Ошибка: товар не найден")
        return
    
    # Создаем уникальный ID заказа
    order_id = str(uuid.uuid4())[:8]
    
    # Создаем платеж в ЮKassa
    payment = create_payment(
        amount=product['price'],
        description=f"Покупка {product['name']}",
        order_id=order_id,
        user_id=user_id
    )
    
    if payment:
        # Сохраняем заказ в БД
        db.create_order(order_id, user_id, product_id, product['price'])
        
        # Сохраняем информацию об ожидании платежа
        pending_payments[order_id] = {
            'user_id': user_id,
            'product_id': product_id,
            'amount': product['price'],
            'payment_id': payment.id
        }
        
        # Создаем клавиатуру с ссылкой на оплату
        payment_keyboard = InlineKeyboardMarkup()
        payment_keyboard.add(
            InlineKeyboardButton("💳 Перейти к оплате", url=payment.confirmation.confirmation_url)
        )
        payment_keyboard.add(
            InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_{order_id}")
        )
        payment_keyboard.add(
            InlineKeyboardButton("❌ Отменить", callback_data="cancel")
        )
        
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(
            user_id,
            f"💳 Создан платеж на сумму {product['price']}₽\n\n"
            f"Нажмите на кнопку ниже, чтобы перейти к оплате.\n"
            f"После оплаты нажмите 'Проверить оплату'",
            reply_markup=payment_keyboard
        )
    else:
        await bot.answer_callback_query(callback_query.id, "Ошибка создания платежа. Попробуйте позже")

@dp.callback_query_handler(lambda c: c.data.startswith('check_'))
async def check_payment_status(callback_query: types.CallbackQuery):
    """Проверка статуса платежа"""
    order_id = callback_query.data.replace('check_', '')
    payment_info = pending_payments.get(order_id)
    
    if not payment_info:
        await bot.answer_callback_query(callback_query.id, "Платеж не найден")
        return
    
    # Проверяем статус платежа
    payment_status = check_payment(payment_info['payment_id'])
    
    if payment_status:
        # Получаем ключ
        key = db.get_available_key(payment_info['product_id'])
        
        if key:
            # Завершаем заказ
            db.complete_order(order_id, key)
            
            # Удаляем из ожидающих
            del pending_payments[order_id]
            
            # Отправляем ключ пользователю
            await bot.send_message(
                callback_query.from_user.id,
                f"✅ *Оплата получена!*\n\n"
                f"Ваш ключ: `{key}`\n\n"
                f"Сохраните его в надежном месте.\n"
                f"По вопросам активации обращайтесь к администратору.",
                parse_mode="Markdown"
            )
            
            # Уведомляем администратора
            await bot.send_message(
                ADMIN_ID,
                f"💰 Новая продажа!\n"
                f"Товар: {payment_info['product_id']}\n"
                f"Сумма: {payment_info['amount']}₽\n"
                f"Пользователь: {callback_query.from_user.id}"
            )
            
            await bot.answer_callback_query(callback_query.id, "Оплата подтверждена! Ключ отправлен.")
        else:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Ошибка: ключи закончились. Администратор уже уведомлен. Деньги будут возвращены."
            )
            await bot.send_message(ADMIN_ID, f"⚠️ СРОЧНО! Закончились ключи для {payment_info['product_id']}")
    else:
        await bot.answer_callback_query(callback_query.id, "Оплата еще не поступила. Подождите или проверьте позже", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "cancel")
async def cancel_payment(callback_query: types.CallbackQuery):
    """Отмена покупки"""
    await bot.answer_callback_query(callback_query.id, "Покупка отменена")
    await bot.send_message(
        callback_query.from_user.id,
        "❌ Покупка отменена. Если у вас есть вопросы, обращайтесь к администратору.",
        reply_markup=get_main_keyboard()
    )

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    """Админ-панель (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    stats = db.get_statistics()
    stats_text = f"""
📊 *Статистика магазина:*

👥 Всего пользователей: {stats[0]}
💳 Всего продаж: {stats[1]}
💰 Общая выручка: {stats[2]}₽
⏳ Ожидает оплаты: {len(pending_payments)}

📝 *Команды админа:*
/add_keys product_1 ключ1,ключ2,ключ3 - добавить ключи
/check_orders - проверить все заказы
    """
    
    await message.answer(stats_text, parse_mode="Markdown")

@dp.message_handler(commands=['add_keys'])
async def add_keys(message: types.Message):
    """Добавление ключей (только для админа)"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        # Формат: /add_keys product_1 key1,key2,key3
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("❌ Использование: /add_keys product_id ключ1,ключ2,ключ3")
            return
        
        product_id = parts[1]
        keys = parts[2].split(',')
        
        db.add_keys_bulk(product_id, keys)
        await message.answer(f"✅ Добавлено {len(keys)} ключей для товара {product_id}")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message_handler(commands=['check_orders'])
async def check_all_orders(message: types.Message):
    """Проверка всех заказов (админ)"""
    if message.from_user.id != ADMIN_ID:
        return
    
    # Здесь можно добавить логику проверки всех ожидающих платежей
    await message.answer(f"ℹ️ Ожидает оплаты: {len(pending_payments)} заказов")

if __name__ == '__main__':
    print("🚀 Бот запущен...")
    executor.start_polling(dp, skip_updates=True)