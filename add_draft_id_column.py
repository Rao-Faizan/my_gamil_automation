import sqlite3

def add_draft_id_column():
    try:
        conn = sqlite3.connect('replied_emails.db')
        c = conn.cursor()
        c.execute('ALTER TABLE replied_emails ADD COLUMN draft_id TEXT')
        conn.commit()
        print("✅ draft_id column added to replied_emails table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ draft_id column already exists")
        else:
            print(f"⚠️ Error adding draft_id column: {e}")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_draft_id_column()