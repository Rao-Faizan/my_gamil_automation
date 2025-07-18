import sqlite3
from datetime import datetime

DB_FILE = 'email_log.db'

# ✅ Create table (runs only first time)
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS email_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            subject TEXT,
            received_date TEXT,
            reply TEXT,
            status TEXT,
            logged_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ✅ Insert record
def save_email_reply(sender, subject, date, reply, status):
    conn = sqlite3.connect('replied_emails.db')
    c = conn.cursor()

    c.execute('''
        INSERT INTO replied_emails (sender, subject, date, reply, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (str(sender), str(subject), str(date), str(reply), str(status)))

    conn.commit()
    conn.close()
    print("📥 Reply saved to database.")
