import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_db():
    try:
        conn = sqlite3.connect('replied_emails.db')
        c = conn.cursor()

        # Check if columns exist
        c.execute("PRAGMA table_info(replied_emails)")
        columns = [info[1] for info in c.fetchall()]

        # Add draft_id if missing
        if 'draft_id' not in columns:
            c.execute('ALTER TABLE replied_emails ADD COLUMN draft_id TEXT')
            logger.info("✅ Added draft_id column")

        # Add message_id if missing
        if 'message_id' not in columns:
            c.execute('ALTER TABLE replied_emails ADD COLUMN message_id TEXT')
            logger.info("✅ Added message_id column")

        conn.commit()
    except Exception as e:
        logger.error(f"⚠️ Error migrating database: {e}")
        raise
    finally:
        conn.close()
    logger.info("✅ Database migration completed")

if __name__ == "__main__":
    migrate_db()