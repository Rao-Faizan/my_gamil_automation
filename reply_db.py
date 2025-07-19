import sqlite3

def init_db():
    conn = sqlite3.connect('replied_emails.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS replied_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            contact TEXT,
            subject TEXT,
            email_date TEXT,
            reply TEXT,
            reply_date TEXT,
            status TEXT,
            original_body TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_email_reply(sender, contact, subject, email_date, reply, reply_date, status, original_body):
    conn = sqlite3.connect('replied_emails.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO replied_emails 
        (sender, contact, subject, email_date, reply, reply_date, status, original_body)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (sender, contact, subject, email_date, reply, reply_date, status, original_body))
    conn.commit()
    conn.close()
    print("📥 Reply saved to database.")
