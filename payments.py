# payments.py
from yookassa import Configuration, Payment
from config import SHOP_ID, SECRET_KEY
import uuid

# Настройка ЮKassa
Configuration.account_id = SHOP_ID
Configuration.secret_key = SECRET_KEY

def create_payment(amount, description, order_id, user_id):
    """Создание платежа"""
    try:
        payment = Payment.create({
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "payment_method_data": {
                "type": "bank_card"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/your_bot"  # Замените на ссылку на вашего бота
            },
            "description": description,
            "metadata": {
                "order_id": order_id,
                "user_id": str(user_id)
            }
        }, uuid.uuid4())
        
        return payment
    except Exception as e:
        print(f"Ошибка создания платежа: {e}")
        return None

def check_payment(payment_id):
    """Проверка статуса платежа"""
    try:
        payment = Payment.find_one(payment_id)
        return payment.status == "succeeded"
    except Exception as e:
        print(f"Ошибка проверки платежа: {e}")
        return False