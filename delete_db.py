import sqlite3

def show_all_emails():
    conn = sqlite3.connect('replied_emails.db')
    c = conn.cursor()

    c.execute("SELECT * FROM replied_emails")
    rows = c.fetchall()

    print(f"🟢 Total Records Found: {len(rows)}\n")
    for i, row in enumerate(rows, start=1):
        print(f"{i}. Sender: {row[1]}")
        print(f"   Subject: {row[3]}")
        print(f"   Email Date: {row[4]}")
        print(f"   Status: {row[7]}")
        print(f"   Original Body: {row[8][:100]}...")  # preview first 100 chars
        print(f"   Reply: {row[5][:100]}...")         # preview first 100 chars
        print("--------------------------------------------------")

    conn.close()

if __name__ == "__main__":
    show_all_emails()
