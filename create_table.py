import sqlite3

conn = sqlite3.connect('replied_emails.db')
c = conn.cursor()

# ✅ Step 1: Create table if it doesn't exist
c.execute('''
    CREATE TABLE IF NOT EXISTS replied_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        contact TEXT,
        subject TEXT,
        email_date TEXT,
        reply TEXT,
        reply_date TEXT,
        status TEXT
    )
''')

# ✅ Step 2: Now you can safely query it
c.execute("SELECT * FROM replied_emails ORDER BY email_date DESC")
rows = c.fetchall()

conn.commit()
conn.close()

print("✅ Table created successfully!")
print(f"📬 Total rows fetched: {len(rows)}")
