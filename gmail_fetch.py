from datetime import datetime
import os
import json
import base64
import sqlite3
from dotenv import load_dotenv
from email.mime.text import MIMEText
from reply_db import init_db, save_email_reply
from generate_reply import generate_email_reply
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']

def get_credentials():
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "token.json")
    creds = None
    if os.path.exists(credentials_path):
        try:
            creds = Credentials.from_authorized_user_file(credentials_path, SCOPES)
            logger.info("✅ Loaded credentials from token.json")
        except Exception as e:
            logger.error(f"⚠️ Error loading token.json: {e}")
    
    if not creds or not creds.valid:
        try:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            with open(credentials_path, 'w') as token_file:
                token_file.write(creds.to_json())
            logger.info("✅ New token.json generated")
        except Exception as e:
            logger.error(f"⚠️ Error generating token: {e}")
            raise
    return creds

# Initialize Gmail service
service = build('gmail', 'v1', credentials=get_credentials())

REPLIED_LOG_FILE = "replied_log.json"

def load_replied_ids():
    if os.path.exists(REPLIED_LOG_FILE):
        try:
            with open(REPLIED_LOG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"⚠️ Error loading replied_log.json: {e}")
            return []
    return []

def save_replied_id(email_id):
    try:
        replied = load_replied_ids()
        if email_id not in replied:
            replied.append(email_id)
            with open(REPLIED_LOG_FILE, 'w') as f:
                json.dump(replied, f)
            logger.info(f"✅ Saved replied ID: {email_id}")
    except Exception as e:
        logger.error(f"⚠️ Error saving replied ID: {e}")

def sanitize_html(html):
    safe_tags = ['div', 'p', 'a', 'img', 'br', 'strong', 'em', 'h1', 'h2', 'h3', 'ul', 'li']
    safe_attrs = ['href', 'src', 'alt']
    html = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html)
    html = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', html)
    html = re.sub(r'\bon\w+\s*=\s*".*?"', '', html)
    return html

def extract_body(msg):
    payload = msg.get('payload', {})
    body_data = ""

    def find_part(parts, mime_type):
        for part in parts:
            if part['mimeType'] == mime_type:
                return part['body'].get('data', '')
            elif part.get('parts'):
                nested = find_part(part['parts'], mime_type)
                if nested:
                    return nested
        return ''

    # Try HTML first, then plain text
    for mime_type in ['text/html', 'text/plain']:
        if 'parts' in payload:
            body_data = find_part(payload['parts'], mime_type)
        else:
            if payload.get('mimeType') == mime_type:
                body_data = payload.get('body', {}).get('data', '')
        
        if body_data:
            try:
                decoded = base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8')
                if mime_type == 'text/html':
                    return sanitize_html(decoded)
                return decoded
            except Exception as e:
                logger.error(f"⚠️ Error decoding body: {e}")
                return "<p>Error: Could not load email content.</p>"
    
    return "<p>No content available.</p>"

def create_draft(to, subject, message_text):
    try:
        message = MIMEText(message_text)
        message['to'] = to
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = service.users().drafts().create(userId='me', body={'message': {'raw': raw}}).execute()
        draft_id = draft.get('id')
        logger.info(f"📝 Draft created: {draft_id}")
        return draft_id
    except Exception as e:
        logger.error(f"⚠️ Error creating draft: {e}")
        return None

def fetch_emails():
    replied_ids = load_replied_ids()

    try:
        results = service.users().messages().list(
            userId='me',
            q="in:inbox",
            maxResults=10
        ).execute()
    except Exception as e:
        logger.error(f"⚠️ Error fetching emails: {e}")
        return

    messages = results.get('messages', [])
    logger.info(f"📨 Total Emails Found: {len(messages)}\n")

    for msg in messages:
        if msg['id'] in replied_ids:
            logger.info(f"📩 [✓] Replied (skipped): {msg['id']}")
            continue

        try:
            data = service.users().messages().get(userId='me', id=msg['id']).execute()
            headers = data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            message_id = msg['id']
            body = extract_body(data)

            if not body or body == "<p>No content available.</p>":
                logger.warning(f"⚠️ Skipping email {msg['id']} due to empty or invalid body")
                continue

            logger.info(f"📩 [ ] New Email From: {sender}")
            logger.info(f"📝 Subject: {subject}\n")

            # Generate AI reply
            try:
                reply = generate_email_reply(subject, body)
                logger.info(f"🤖 Gemini's Reply:\n{reply}\n--------------------------------------------------\n")
            except Exception as e:
                logger.error(f"⚠️ Failed to generate reply for {subject}: {e}")
                reply = f"Dear {sender.split('<')[0].strip()},\nThank you for your email. I'll get back to you soon.\nBest regards,\nRao Faizan Raza\nIT Instructor at Al-Khair Institute"
                logger.warning(f"⚠️ Using fallback reply for {subject}")

            # Create draft in Gmail
            draft_id = create_draft(
                to=sender,
                subject=f"Re: {subject}",
                message_text=reply
            )
            if not draft_id:
                logger.error(f"⚠️ Skipping email {msg['id']} due to draft creation failure")
                continue

            # Save to DB
            contact = sender
            email_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reply_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "draft"
            original_body = body

            save_email_reply(
                sender, contact, subject, email_date,
                reply, reply_date, status, original_body, draft_id, message_id
            )

            save_replied_id(msg['id'])
        except Exception as e:
            logger.error(f"⚠️ Error processing email {msg['id']}: {e}")

if __name__ == "__main__":
    logger.info("📂 Initializing database...")
    init_db()
    fetch_emails()
