from datetime import datetime
import os
import json
import base64
import sqlite3
from dotenv import load_dotenv
from email_draft import create_draft
from reply_db import init_db, save_email_reply
from generate_reply import generate_email_reply
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
creds = Credentials.from_authorized_user_file(os.getenv("GOOGLE_CREDENTIALS_PATH"), SCOPES)
service = build('gmail', 'v1', credentials=creds)

REPLIED_LOG_FILE = "replied_log.json"

def load_replied_ids():
    if os.path.exists(REPLIED_LOG_FILE):
        with open(REPLIED_LOG_FILE, 'r') as f:
            return json.load(f)
    return []

def save_replied_id(email_id):
    replied = load_replied_ids()
    replied.append(email_id)
    with open(REPLIED_LOG_FILE, 'w') as f:
        json.dump(replied, f)

def extract_body(msg):
    payload = msg.get('payload', {})
    body_data = ""

    def find_html_part(parts):
        for part in parts:
            if part['mimeType'] == 'text/html':
                return part['body'].get('data', '')
            elif part.get('parts'):
                nested = find_html_part(part['parts'])
                if nested:
                    return nested
        return ''

    if 'parts' in payload:
        body_data = find_html_part(payload['parts'])
    else:
        body_data = payload.get('body', {}).get('data', '')

    if body_data:
        try:
            decoded = base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8')
            return decoded
        except Exception as e:
            print("⚠️ Error decoding body:", e)
    return ""

def fetch_emails():
    replied_ids = load_replied_ids()

    results = service.users().messages().list(
        userId='me',
        q="in:inbox",
        maxResults=10
    ).execute()

    messages = results.get('messages', [])
    print(f"📨 Total Emails Found: {len(messages)}\n")

    for msg in messages:
        if msg['id'] in replied_ids:
            print(f"📩 [✓] Replied (skipped): {msg['id']}")
            continue

        data = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = data['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
        body = extract_body(data)

        print(f"📩 [ ] New Email From: {sender}")
        print(f"📝 Subject: {subject}\n")

        # Generate AI reply
        reply = generate_email_reply(subject, body)
        print("🤖 Gemini's Reply:\n", reply)
        print("--------------------------------------------------\n")

        # Create draft in Gmail
        create_draft(
            to=sender,
            subject=f"Re: {subject}",
            message_text=reply
        )

        # Save to DB
        contact = ""
        email_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reply_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "draft"
        original_body = body

        save_email_reply(
            sender, contact, subject, email_date,
            reply, reply_date, status, original_body
        )

        save_replied_id(msg['id'])

if __name__ == "__main__":
    print("📂 Initializing database...")
    init_db()
    fetch_emails()
