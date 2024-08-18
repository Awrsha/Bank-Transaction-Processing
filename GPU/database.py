import sqlite3
import random

def create_database():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            card_number TEXT PRIMARY KEY,
            balance INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number TEXT,
            amount INTEGER,
            success INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_card_number ON users(card_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_card_number ON transactions(card_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)')
    
    conn.commit()
    conn.close()

def populate_database():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('BEGIN TRANSACTION')
    for i in range(10000):
        card_number = f"6219 8619 {i:04d} 8640"
        balance = random.randint(50000, 10000000)
        cursor.execute('INSERT OR REPLACE INTO users (card_number, balance) VALUES (?, ?)', (card_number, balance))
    cursor.execute('COMMIT')
    
    conn.close()

if __name__ == "__main__":
    create_database()
    populate_database()