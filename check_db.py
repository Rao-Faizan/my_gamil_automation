import sqlite3

conn = sqlite3.connect("replied_emails.db")
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM replied_emails")
count = c.fetchone()[0]
conn.close()

print("📊 Total emails in DB:", count)
