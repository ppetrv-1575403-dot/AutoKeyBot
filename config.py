# config.py
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# ID администратора (можно узнать у @userinfobot)
ADMIN_ID = os.environ["TG_ADMIN_ID"]  # Замените на ваш Telegram ID
# Токен бота от @BotFather
BOT_TOKEN = os.environ["TG_BOT_TOKEN"]

# Данные от ЮKassa (https://yookassa.ru)
SHOP_ID = os.environ["YK_SHOP_ID"]
SECRET_KEY = os.environ["YK_SECRET_KEY"]

# Настройки базы данных
DATABASE_NAME = "keys_bot.db"