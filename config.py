import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "token.json")
    CLIENT_SECRETS_PATH = os.getenv("CLIENT_SECRETS_PATH", "credentials.json")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    BULK_EMAIL_LIMIT_MIN = int(os.getenv("BULK_EMAIL_LIMIT_MIN", 2))
    BULK_EMAIL_LIMIT_MAX = int(os.getenv("BULK_EMAIL_LIMIT_MAX", 400))
    SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']