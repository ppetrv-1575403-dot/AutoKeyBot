# database.py
import sqlite3
from config import DATABASE_NAME
from datetime import datetime

class Database:
    def __init__(self):
        self.connection = sqlite3.connect(DATABASE_NAME)
        self.cursor = self.connection.cursor()
        self.create_tables()
    
    def create_tables(self):
        """Создание необходимых таблиц"""
        # Таблица пользователей
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TEXT,
                total_spent REAL DEFAULT 0
            )
        """)
        
        # Таблица заказов
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id INTEGER,
                product_id TEXT,
                amount REAL,
                status TEXT,
                created_at TEXT,
                completed_at TEXT,
                key_value TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        # Таблица для хранения ключей
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                key_value TEXT UNIQUE,
                is_sold INTEGER DEFAULT 0,
                sold_to_user INTEGER,
                sold_at TEXT
            )
        """)
        
        self.connection.commit()
    
    def add_user(self, user_id, username, first_name):
        """Добавление нового пользователя"""
        self.cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, datetime.now().isoformat()))
        self.connection.commit()
    
    def get_user_stats(self, user_id):
        """Получение статистики пользователя"""
        self.cursor.execute("""
            SELECT total_spent, COUNT(order_id) 
            FROM users u
            LEFT JOIN orders o ON u.user_id = o.user_id AND o.status = 'completed'
            WHERE u.user_id = ?
            GROUP BY u.user_id
        """, (user_id,))
        return self.cursor.fetchone()
    
    def create_order(self, order_id, user_id, product_id, amount):
        """Создание нового заказа"""
        self.cursor.execute("""
            INSERT INTO orders (order_id, user_id, product_id, amount, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, user_id, product_id, amount, 'pending', datetime.now().isoformat()))
        self.connection.commit()
    
    def complete_order(self, order_id, key_value):
        """Завершение заказа и списание ключа"""
        # Получаем информацию о заказе
        self.cursor.execute("SELECT user_id, amount FROM orders WHERE order_id = ?", (order_id,))
        order = self.cursor.fetchone()
        
        if order:
            user_id, amount = order
            
            # Обновляем заказ
            self.cursor.execute("""
                UPDATE orders 
                SET status = 'completed', completed_at = ?, key_value = ?
                WHERE order_id = ?
            """, (datetime.now().isoformat(), key_value, order_id))
            
            # Обновляем сумму покупок пользователя
            self.cursor.execute("""
                UPDATE users 
                SET total_spent = total_spent + ?
                WHERE user_id = ?
            """, (amount, user_id))
            
            # Отмечаем ключ как проданный
            self.cursor.execute("""
                UPDATE product_keys 
                SET is_sold = 1, sold_to_user = ?, sold_at = ?
                WHERE key_value = ?
            """, (user_id, datetime.now().isoformat(), key_value))
            
            self.connection.commit()
            return True
        return False
    
    def get_available_key(self, product_id):
        """Получение доступного ключа для товара"""
        self.cursor.execute("""
            SELECT key_value FROM product_keys 
            WHERE product_id = ? AND is_sold = 0 
            LIMIT 1
        """, (product_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def add_keys_bulk(self, product_id, keys_list):
        """Массовое добавление ключей"""
        for key in keys_list:
            try:
                self.cursor.execute("""
                    INSERT INTO product_keys (product_id, key_value, is_sold)
                    VALUES (?, ?, ?)
                """, (product_id, key.strip(), 0))
            except sqlite3.IntegrityError:
                continue
        self.connection.commit()
    
    def get_statistics(self):
        """Получение общей статистики"""
        # Всего пользователей
        self.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = self.cursor.fetchone()[0]
        
        # Всего продаж
        self.cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
        total_sales = self.cursor.fetchone()[0]
        
        # Общая выручка
        self.cursor.execute("SELECT SUM(amount) FROM orders WHERE status = 'completed'")
        total_revenue = self.cursor.fetchone()[0] or 0
        
        return total_users, total_sales, total_revenue
    
    def close(self):
        self.connection.close()