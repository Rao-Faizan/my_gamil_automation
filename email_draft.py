from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from email.mime.text import MIMEText
import base64

def create_draft(to, subject, message_text):
    creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.modify'])
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(message_text)
    message['to'] = to
    message['subject'] = subject

    create_message = {
        'message': {
            'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()
        }
    }

    draft = service.users().drafts().create(userId='me', body=create_message).execute()
    print(f"✅ Draft created with ID: {draft['id']}")
