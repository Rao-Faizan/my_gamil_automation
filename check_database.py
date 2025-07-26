import sqlite3

def check_database():
    try:
        conn = sqlite3.connect('replied_emails.db')
        c = conn.cursor()
        c.execute('SELECT sender, subject, draft_id, status FROM replied_emails')
        rows = c.fetchall()
        print("📋 Database Contents:")
        if not rows:
            print("⚠️ No entries found in replied_emails table")
        for row in rows:
            print(f"Sender: {row[0]}, Subject: {row[1]}, Draft ID: {row[2]}, Status: {row[3]}")
        conn.close()
    except Exception as e:
        print(f"⚠️ Error checking database: {e}")

if __name__ == "__main__":
    check_database()