import sqlite3
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect("replied_emails.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS replied_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            contact TEXT,
            subject TEXT,
            email_date DATETIME,
            reply TEXT,
            reply_date DATETIME,
            status TEXT,
            original_body TEXT,
            draft_id TEXT,
            message_id TEXT,
            UNIQUE(sender, subject, message_id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("📂 Database initialized")

def save_email_reply(sender, contact, subject, email_date, reply, reply_date, status, original_body, draft_id, message_id):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO replied_emails 
            (sender, contact, subject, email_date, reply, reply_date, status, original_body, draft_id, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sender, contact, subject, email_date, reply, reply_date, status, original_body, draft_id, message_id))
        conn.commit()
        logger.info(f"📥 Reply saved to database for {subject}")
    except sqlite3.IntegrityError as e:
        logger.error(f"⚠️ Error: Duplicate entry for {subject} - {e}")
        raise
    except Exception as e:
        logger.error(f"⚠️ Error saving reply to database: {e}")
        raise
    finally:
        conn.close()

def update_email_reply(sender, subject, reply, draft_id):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute('''
            UPDATE replied_emails 
            SET reply = ?, reply_date = ?, draft_id = ?
            WHERE sender = ? AND subject = ?
        ''', (reply, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), draft_id, sender, subject))
        if c.rowcount == 0:
            logger.warning(f"⚠️ No record found to update for {sender} - {subject}")
        else:
            conn.commit()
            logger.info(f"📝 Reply updated in database for {subject}")
    except Exception as e:
        logger.error(f"⚠️ Error updating reply in database: {e}")
        raise
    finally:
        conn.close()

def update_draft_id_in_db(sender, subject, draft_id):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute('''
            UPDATE replied_emails 
            SET draft_id = ?
            WHERE sender = ? AND subject = ?
        ''', (draft_id, sender, subject))
        if c.rowcount == 0:
            logger.warning(f"⚠️ No record found to update draft_id for {sender} - {subject}")
        else:
            conn.commit()
            logger.info(f"📝 Draft ID updated in database for {subject}")
    except Exception as e:
        logger.error(f"⚠️ Error updating draft_id in database: {e}")
        raise
    finally:
        conn.close()