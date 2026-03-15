"""
Run this script once to initialize the SQLite database.
It is also called automatically when you run app.py with debug=True.
"""
import sqlite3

def init_db():
    conn = sqlite3.connect('farmer.db')
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            email    TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            crop          TEXT    NOT NULL,
            location      TEXT    NOT NULL,
            weather_data  TEXT,
            ai_prediction TEXT,
            date          TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully: farmer.db")

if __name__ == '__main__':
    init_db()
