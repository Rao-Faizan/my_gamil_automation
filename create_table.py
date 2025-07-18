import sqlite3

conn = sqlite3.connect('replied_emails.db')
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS replied_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        subject TEXT,
        date TEXT,
        reply TEXT,
        status TEXT
    )
''')

conn.commit()
conn.close()

print("✅ Table created successfully!")
