import sqlite3

def check_database():
    try:
        conn = sqlite3.connect('replied_emails.db')
        c = conn.cursor()
        c.execute("PRAGMA table_info(replied_emails)")
        columns = [row[1] for row in c.fetchall()]
        print(f"Table columns: {columns}")
        
        c.execute("SELECT sender, subject, status, message_id FROM replied_emails")
        rows = c.fetchall()
        print(f"Total emails in DB: {len(rows)}")
        for row in rows:
            print(f"Sender: {row[0]}, Subject: {row[1]}, Status: {row[2]}, Message ID: {row[3]}")
        conn.close()
    except Exception as e:
        print(f"⚠️ Error checking database: {e}")

if __name__ == "__main__":
    check_database()