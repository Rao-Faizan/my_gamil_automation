from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from email.mime.text import MIMEText
import base64
import csv
from datetime import datetime
import asyncio
import logging
import os
import bleach

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.post("/fetch_emails")
async def fetch_emails():
    try:
        result = await fetch_emails_from_gmail()
        return result
    except Exception as e:
        logger.error(f"⚠️ Error in fetch_emails endpoint: {e}")
        return {
            "success": False,
            "message": str(e)
        }

# Sanitize text to prevent XSS
def sanitize_text(text):
    return bleach.clean(text, tags=['p', 'strong', 'em', 'a'], attributes={'a': ['href']}) if text else ""

# Check if email is from a no-reply address
def is_no_reply_email(email):
    noreply_patterns = [
        '@noreply.',
        '@no-reply.',
        'noreply@',
        'no-reply@',
        'donotreply@',
        'do-not-reply@',
        'no.reply@',
        'notifications@',
        'alerts@',
        'system@',
        'mailer-daemon@',
        'postmaster@',
        'automated@',
        '@email.google.com',
        '@notifications.',
        '@automated.',
        'auto-confirm@',
        'auto-notify@',
        'auto-reply@',
        'bounces@'
    ]
    email = email.lower()
    return any(pattern in email for pattern in noreply_patterns)

# Gmail API service initialization
def get_gmail_service():
    try:
        SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
                with open("token.json", "w") as token_file:
                    token_file.write(creds.to_json())
        service = build("gmail", "v1", credentials=creds)
        return service
    except Exception as e:
        logger.error(f"⚠️ Error initializing Gmail service: {e}")
        return None

# Create draft in Gmail
def create_draft(sender, subject, message_text):
    try:
        service = get_gmail_service()
        if not service:
            return None
        message = MIMEText(message_text)
        message["to"] = sender
        message["subject"] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = {"message": {"raw": raw_message}}
        draft_response = service.users().drafts().create(userId="me", body=draft).execute()
        draft_id = draft_response["id"]
        logger.info(f"📝 Draft created: {draft_id}")
        return draft_id
    except Exception as e:
        logger.error(f"⚠️ Error creating draft for {subject}: {e}")
        return None

# Verify draft exists
def verify_draft(draft_id):
    try:
        service = get_gmail_service()
        if not service or not draft_id:
            return False
        draft = service.users().drafts().get(userId="me", id=draft_id).execute()
        return bool(draft)
    except Exception as e:
        logger.error(f"⚠️ Error verifying draft {draft_id}: {e}")
        return False

# Send email with delay
async def send_email_with_delay(service, draft_id, delay=10):
    try:
        if not service or not draft_id:
            return False
        await asyncio.sleep(delay)
        message = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
        logger.info(f"✅ Email sent from draft: {draft_id}")
        return True
    except Exception as e:
        logger.error(f"⚠️ Error sending email from draft {draft_id}: {e}")
        return False

# Fetch emails from Gmail
async def fetch_emails_from_gmail():
    try:
        service = get_gmail_service()
        if not service:
            raise Exception("Failed to initialize Gmail service")

        # Get emails from Gmail
        results = service.users().messages().list(userId='me', labelIds=['INBOX'], q='is:unread').execute()
        messages = results.get('messages', [])

        if not messages:
            return {"success": True, "count": 0, "message": "No new emails found"}

        conn = sqlite3.connect('email_log.db')
        cursor = conn.cursor()

        fetched_count = 0
        for message in messages:
            try:
                # Get the email details
                msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
                
                # Extract headers
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'No Sender')
                date = int(msg['internalDate']) / 1000  # Convert to seconds
                
                # Extract body
                body = ""
                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        if part['mimeType'] == 'text/html':
                            body = base64.urlsafe_b64decode(part['body']['data']).decode()
                            break
                elif 'body' in msg['payload']:
                    body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode()

                # Sanitize the data
                subject = sanitize_text(subject)
                sender = sanitize_text(sender)
                body = sanitize_text(body)

                # Check if it's a no-reply email
                status = 'no-reply' if is_no_reply_email(sender) else 'unread'

                # Save to database
                cursor.execute('''
                    INSERT OR IGNORE INTO emails 
                    (message_id, subject, sender, original_body, email_date, status) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (message['id'], subject, sender, body, datetime.fromtimestamp(date), status))
                
                if cursor.rowcount > 0:
                    fetched_count += 1

            except Exception as e:
                logger.error(f"⚠️ Error processing email {message['id']}: {e}")
                continue

        conn.commit()
        conn.close()

        return {
            "success": True,
            "count": fetched_count,
            "message": f"Successfully fetched {fetched_count} new emails"
        }

    except Exception as e:
        logger.error(f"⚠️ Error fetching emails: {e}")
        return {
            "success": False,
            "message": f"Failed to fetch emails: {str(e)}"
        }

# Initialize Gemini API
import google.generativeai as genai
from textwrap import dedent

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")  # Set your API key in environment variables
genai.configure(api_key=GOOGLE_API_KEY)

def generate_email_reply(subject, original_body, custom_prompt=None):
    try:
        # Clean and prepare the email content
        clean_body = bleach.clean(original_body, tags=[], strip=True)
        
        # Create the base prompt
        base_prompt = dedent(f"""
            You are a professional email assistant. Generate a polite and professional reply to this email.
            Keep the tone friendly but professional. Address the sender's points clearly and concisely.
            
            Original Email Subject: {subject}
            
            Original Email Content:
            {clean_body}
            
            Instructions:
            1. Start with an appropriate greeting
            2. Acknowledge the email's content
            3. Address the main points or questions
            4. End professionally
            5. Include a signature
            
            Additional Context: Reply as Rao Faizan Raza, IT Instructor at Al-Khair Institute
        """).strip()
        
        # Use custom prompt if provided
        prompt = custom_prompt if custom_prompt else base_prompt
        
        # Get Gemini model
        model = genai.GenerativeModel('gemini-pro')
        
        # Generate response
        response = model.generate_content(prompt)
        
        if not response.text:
            raise Exception("Empty response from AI")
        
        # Post-process the response
        reply = response.text.strip()
        
        # Ensure signature is present
        if "Best regards" not in reply and "Sincerely" not in reply:
            reply += "\n\nBest regards,\nRao Faizan Raza\nIT Instructor at Al-Khair Institute"
        
        logger.info("✅ Successfully generated AI reply")
        return reply
        
    except Exception as e:
        logger.error(f"⚠️ Error generating AI reply: {e}")
        # Fallback response if AI fails
        return dedent(f"""
            Dear {subject.split('<')[0].strip()},
            
            Thank you for your email. We have received your message and will process it accordingly.
            
            Best regards,
            Rao Faizan Raza
            IT Instructor at Al-Khair Institute
        """).strip()

# Update email reply in database
def update_email_reply(sender, subject, reply, draft_id, email_date):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute('''
            UPDATE replied_emails 
            SET reply = ?, reply_date = ?, draft_id = ?
            WHERE sender = ? AND subject = ? AND email_date = ?
        ''', (reply, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), draft_id, sender, subject, email_date))
        if c.rowcount == 0:
            logger.warning(f"⚠️ No record found to update for {sender} - {subject}")
        else:
            conn.commit()
            logger.info(f"📝 Reply updated in database for {subject}")
        conn.close()
    except Exception as e:
        logger.error(f"⚠️ Error updating reply in database: {e}")
        raise

# Update draft ID in database
def update_draft_id_in_db(sender, subject, draft_id, email_date):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute('''
            UPDATE replied_emails 
            SET draft_id = ?
            WHERE sender = ? AND subject = ? AND email_date = ?
        ''', (draft_id, sender, subject, email_date))
        if c.rowcount == 0:
            logger.warning(f"⚠️ No record found to update draft_id for {sender} - {subject}")
        else:
            conn.commit()
            logger.info(f"📝 Draft ID updated in database for {subject}")
        conn.close()
    except Exception as e:
        logger.error(f"⚠️ Error updating draft_id in database: {e}")
        raise

# Home route to display emails
@app.get("/", response_class=HTMLResponse)
async def read_data(request: Request):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        
        c.execute("SELECT sender, subject, email_date, status, reply, original_body, draft_id, message_id FROM replied_emails WHERE status='unread' ORDER BY email_date DESC")
        unread_emails = [dict(zip(['sender', 'subject', 'email_date', 'status', 'reply', 'original_body', 'draft_id', 'message_id'], row)) for row in c.fetchall()]
        
        c.execute("SELECT sender, subject, email_date, status, reply, original_body, draft_id, message_id FROM replied_emails WHERE status='sent' ORDER BY email_date DESC")
        sent_emails = [dict(zip(['sender', 'subject', 'email_date', 'status', 'reply', 'original_body', 'draft_id', 'message_id'], row)) for row in c.fetchall()]
        
        c.execute("SELECT sender, subject, email_date, status, reply, original_body, draft_id, message_id FROM replied_emails WHERE status='draft' ORDER BY email_date DESC")
        draft_emails = [dict(zip(['sender', 'subject', 'email_date', 'status', 'reply', 'original_body', 'draft_id', 'message_id'], row)) for row in c.fetchall()]
        
        c.execute("SELECT sender, subject, email_date, status, reply, original_body, draft_id, message_id FROM replied_emails WHERE status='no-reply' ORDER BY email_date DESC")
        no_reply_emails = [dict(zip(['sender', 'subject', 'email_date', 'status', 'reply', 'original_body', 'draft_id', 'message_id'], row)) for row in c.fetchall()]
        
        conn.close()
        logger.info(f"✅ Fetched emails: unread={len(unread_emails)}, sent={len(sent_emails)}, draft={len(draft_emails)}, no-reply={len(no_reply_emails)}")
        return templates.TemplateResponse("emails.html", {
            "request": request,
            "unread_emails": unread_emails,
            "sent_emails": sent_emails,
            "draft_emails": draft_emails,
            "no_reply_emails": no_reply_emails
        })
    except Exception as e:
        logger.error(f"⚠️ Error fetching emails: {e}")
        return templates.TemplateResponse("emails.html", {
            "request": request,
            "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
            "message": f"Failed to fetch emails: {str(e)}. Please check database connection.",
            "message_type": "error"
        })

# Generate reply for a single email
@app.post("/generate_reply", response_class=HTMLResponse)
async def generate_reply(request: Request, sender: str = Form(...), subject: str = Form(default='No Subject'), original_body: str = Form(...), message_id: str = Form(...), custom_prompt: str = Form(default=None)):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute("SELECT status, email_date FROM replied_emails WHERE message_id=?", (message_id,))
        result = c.fetchone()
        conn.close()
        if not result or result[0] in ['no-reply', 'sent']:
            return templates.TemplateResponse("email_view.html", {
                "request": request,
                "email": {"sender": sender, "subject": subject, "original_body": original_body, "message_id": message_id},
                "message": "Reply cannot be generated for this email.",
                "message_type": "error"
            })
        
        email_date = result[1]
        reply = generate_email_reply(subject, original_body, custom_prompt=custom_prompt) if custom_prompt else generate_email_reply(subject, original_body)
        if not reply:
            return templates.TemplateResponse("email_view.html", {
                "request": request,
                "email": {"sender": sender, "subject": subject, "original_body": original_body, "message_id": message_id},
                "message": "Failed to generate reply: Empty response from AI.",
                "message_type": "error"
            })
        
        draft_id = create_draft(sender, f"Re: {subject}", reply)
        if not draft_id:
            return templates.TemplateResponse("email_view.html", {
                "request": request,
                "email": {"sender": sender, "subject": subject, "original_body": original_body, "message_id": message_id},
                "message": "Failed to create draft. Please check authentication.",
                "message_type": "error"
            })
        
        update_email_reply(sender, subject, reply, draft_id, email_date)
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute("UPDATE replied_emails SET status='draft', draft_id=? WHERE message_id=?", (draft_id, message_id))
        conn.commit()
        conn.close()
        
        return RedirectResponse(url=f"/view/{message_id}", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error generating reply for {subject}: {e}")
        return templates.TemplateResponse("email_view.html", {
            "request": request,
            "email": {"sender": sender, "subject": subject, "original_body": original_body, "message_id": message_id},
            "message": f"Error generating reply: {str(e)}.",
            "message_type": "error"
        })

# Upload CSV endpoint with improved error handling
@app.post("/upload_csv", response_class=HTMLResponse)
async def upload_csv(request: Request, file: UploadFile = File(...)):
    try:
        # Check if file is a CSV
        if not file.filename.endswith('.csv'):
            logger.error("⚠️ Invalid file format: Only CSV files are allowed")
            return templates.TemplateResponse("emails.html", {
                "request": request,
                "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
                "message": "Invalid file format: Please upload a CSV file.", "message_type": "error"
            })

        # Read CSV file
        content = await file.read()
        try:
            decoded_content = content.decode('utf-8-sig')  # Handle BOM encoding
        except UnicodeDecodeError:
            logger.error("⚠️ Failed to decode CSV file: Invalid encoding")
            return templates.TemplateResponse("emails.html", {
                "request": request,
                "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
                "message": "Failed to decode CSV file: Ensure it is UTF-8 encoded.", "message_type": "error"
            })

        # Parse CSV
        csv_reader = csv.DictReader(decoded_content.splitlines())
        required_fields = {'sender', 'subject', 'original_body'}
        
        # Check if required columns exist
        if not csv_reader.fieldnames or not all(field in csv_reader.fieldnames for field in required_fields):
            logger.error(f"⚠️ Missing required columns in CSV. Found: {csv_reader.fieldnames}")
            return templates.TemplateResponse("emails.html", {
                "request": request,
                "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
                "message": f"CSV must contain 'sender', 'subject', 'original_body' columns. Found: {csv_reader.fieldnames}", 
                "message_type": "error"
            })

        # Insert data into database
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        inserted_count = 0
        for row in csv_reader:
            try:
                # Generate unique message_id for CSV entries
                message_id = f"csv_{inserted_count}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                c.execute(
                    "INSERT INTO replied_emails (sender, subject, email_date, status, original_body, message_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (row['sender'], row['subject'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'unread', row['original_body'], message_id)
                )
                inserted_count += 1
            except KeyError as e:
                logger.error(f"⚠️ Missing column in row {inserted_count + 1}: {e}")
                continue
            except sqlite3.IntegrityError as e:
                logger.error(f"⚠️ Duplicate entry in row {inserted_count + 1}: {e}")
                continue
        conn.commit()
        conn.close()

        logger.info(f"✅ Uploaded {inserted_count} emails from CSV")
        if inserted_count == 0:
            return templates.TemplateResponse("emails.html", {
                "request": request,
                "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
                "message": "No valid emails were uploaded from the CSV. Check the file format.", "message_type": "error"
            })
        
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error uploading CSV: {e}")
        return templates.TemplateResponse("emails.html", {
            "request": request,
            "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
            "message": f"Failed to upload CSV: {str(e)}.", "message_type": "error"
        })

# View emails for bulk actions
@app.get("/bulk", response_class=HTMLResponse)
async def bulk_page(request: Request):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute("SELECT sender, subject, email_date, status, reply, original_body, draft_id, message_id FROM replied_emails WHERE status IN ('unread', 'draft') ORDER BY email_date DESC")
        rows = c.fetchall()
        conn.close()
        emails = [dict(zip(['sender', 'subject', 'email_date', 'status', 'reply', 'original_body', 'draft_id', 'message_id'], row)) for row in rows]
        logger.info(f"✅ Fetched {len(emails)} emails for bulk action")
        return templates.TemplateResponse("bulk.html", {"request": request, "emails": emails})
    except Exception as e:
        logger.error(f"⚠️ Error fetching emails for bulk: {e}")
        return templates.TemplateResponse("bulk.html", {"request": request, "emails": [], "message": f"Failed to fetch emails: {str(e)}", "message_type": "error"})

# View single email
@app.get("/view/{message_id}", response_class=HTMLResponse)
async def view_email(request: Request, message_id: str):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute("SELECT sender, subject, email_date, status, reply, original_body, draft_id, message_id FROM replied_emails WHERE message_id=?", (message_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return templates.TemplateResponse("email_view.html", {"request": request, "message": "Email not found.", "message_type": "error"})
        email = dict(zip(['sender', 'subject', 'email_date', 'status', 'reply', 'original_body', 'draft_id', 'message_id'], row))
        return templates.TemplateResponse("email_view.html", {"request": request, "email": email})
    except Exception as e:
        logger.error(f"⚠️ Error viewing email {message_id}: {e}")
        return templates.TemplateResponse("email_view.html", {"request": request, "message": f"Failed to view email: {str(e)}", "message_type": "error"})

# Bulk send emails
@app.post("/bulk_send", response_class=HTMLResponse)
async def bulk_send(request: Request, subject: str = Form(default='No Subject'), message: str = Form(default=''), selected_emails: list = Form(...), use_ai_reply: bool = Form(default=False), custom_prompt: str = Form(default=None)):
    try:
        if not message and not use_ai_reply:
            return templates.TemplateResponse("bulk.html", {
                "request": request,
                "emails": (await bulk_page(request)).body,
                "message": "Message cannot be empty unless using AI-generated replies.",
                "message_type": "error"
            })
        if len(selected_emails) < 2 or len(selected_emails) > 400:
            return templates.TemplateResponse("bulk.html", {
                "request": request,
                "emails": (await bulk_page(request)).body,
                "message": f"Please select between 2 and 400 emails (selected: {len(selected_emails)}).",
                "message_type": "error"
            })

        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        emails = []
        for message_id in selected_emails:
            c.execute("SELECT sender, subject, draft_id, message_id, original_body, email_date FROM replied_emails WHERE message_id=?", (message_id,))
            row = c.fetchone()
            if row:
                emails.append({"sender": row[0], "subject": row[1] or 'No Subject', "draft_id": row[2], "message_id": row[3], "original_body": row[4], "email_date": row[5]})
        conn.close()

        if not emails:
            return templates.TemplateResponse("bulk.html", {
                "request": request,
                "emails": (await bulk_page(request)).body,
                "message": "No valid emails found for selected message IDs.",
                "message_type": "error"
            })

        service = get_gmail_service()
        if not service:
            return templates.TemplateResponse("bulk.html", {
                "request": request,
                "emails": (await bulk_page(request)).body,
                "message": "Failed to initialize Gmail service.",
                "message_type": "error"
            })

        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        sent_count = 0
        failed_emails = []
        for email in emails:
            try:
                message_text = None
                if use_ai_reply:
                    message_text = generate_email_reply(email['subject'], email['original_body'], custom_prompt=custom_prompt) if custom_prompt else generate_email_reply(email['subject'], email['original_body'])
                else:
                    message_text = sanitize_text(message)
                
                if not message_text:
                    failed_emails.append(email['sender'])
                    continue
                
                draft_id = email['draft_id']
                if draft_id == "None" or not verify_draft(draft_id):
                    new_draft_id = create_draft(email['sender'], subject, message_text)
                    if not new_draft_id:
                        failed_emails.append(email['sender'])
                        continue
                    update_draft_id_in_db(email['sender'], email['subject'], new_draft_id, email['email_date'])
                    draft_id = new_draft_id

                update_email_reply(email['sender'], email['subject'], message_text, draft_id, email['email_date'])
                await send_email_with_delay(service, draft_id, delay=10)

                c.execute("UPDATE replied_emails SET status='sent', reply_date=? WHERE message_id=?", 
                         (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email['message_id']))
                conn.commit()
                sent_count += 1
            except Exception as e:
                logger.error(f"⚠️ Error processing email for {email['sender']}: {e}")
                failed_emails.append(email['sender'])

        conn.close()
        if failed_emails:
            return templates.TemplateResponse("bulk.html", {
                "request": request,
                "emails": (await bulk_page(request)).body,
                "message": f"Sent {sent_count} emails successfully. Failed for {len(failed_emails)}: {', '.join(failed_emails)}",
                "message_type": "error"
            })
        return RedirectResponse(url="/bulk", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error during bulk send: {e}")
        return templates.TemplateResponse("bulk.html", {
            "request": request,
            "emails": (await bulk_page(request)).body,
            "message": f"Failed to send emails: {str(e)}.",
            "message_type": "error"
        })

# Delete specific email
@app.post("/delete_email", response_class=RedirectResponse)
async def delete_email(request: Request, message_id: str = Form(...)):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        # Debug: Log the message_id being deleted
        logger.info(f"Attempting to delete email with message_id: {message_id}")
        c.execute("SELECT sender, subject FROM replied_emails WHERE message_id = ?", (message_id,))
        email = c.fetchone()
        if not email:
            logger.warning(f"⚠️ No email found with message_id: {message_id}")
            return templates.TemplateResponse("emails.html", {
                "request": request,
                "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
                "message": f"No email found with ID: {message_id}", "message_type": "error"
            })
        c.execute("DELETE FROM replied_emails WHERE message_id = ?", (message_id,))
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        logger.info(f"✅ Deleted email with message_id: {message_id} (Sender: {email[0]}, Subject: {email[1]})")
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error deleting email with message_id {message_id}: {e}")
        return templates.TemplateResponse("emails.html", {
            "request": request,
            "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
            "message": f"Failed to delete email: {str(e)}", "message_type": "error"
        })

# Delete all emails or specific category
@app.post("/delete_all_emails", response_class=RedirectResponse)
async def delete_all_emails(request: Request, category: str = Form(default="all")):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        if category == "all":
            c.execute("DELETE FROM replied_emails")
            deleted_count = c.rowcount
        else:
            c.execute("DELETE FROM replied_emails WHERE status = ?", (category,))
            deleted_count = c.rowcount
        conn.commit()
        logger.info(f"✅ Deleted {deleted_count} emails from category: {category}")
        conn.close()
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error deleting emails from category {category}: {e}")
        return templates.TemplateResponse("emails.html", {
            "request": request,
            "unread_emails": [], "sent_emails": [], "draft_emails": [], "no_reply_emails": [],
            "message": f"Failed to delete emails: {str(e)}", "message_type": "error"
        })

# Delete selected emails (for bulk delete)
@app.post("/delete_selected_emails", response_class=RedirectResponse)
async def delete_selected_emails(request: Request, selected_emails: list = Form(...)):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        deleted_count = 0
        for message_id in selected_emails:
            c.execute("SELECT sender, subject FROM replied_emails WHERE message_id = ?", (message_id,))
            email = c.fetchone()
            if email:
                c.execute("DELETE FROM replied_emails WHERE message_id = ?", (message_id,))
                deleted_count += c.rowcount
                logger.info(f"✅ Deleted email with message_id: {message_id} (Sender: {email[0]}, Subject: {email[1]})")
        conn.commit()
        conn.close()
        logger.info(f"✅ Deleted {deleted_count} selected emails")
        return RedirectResponse(url="/bulk", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error deleting selected emails: {e}")
        return templates.TemplateResponse("bulk.html", {
            "request": request,
            "emails": [],
            "message": f"Failed to delete selected emails: {str(e)}", "message_type": "error"
        })

# Send reply for a single email
@app.post("/send_reply", response_class=HTMLResponse)
async def send_reply(request: Request, sender: str = Form(...), subject: str = Form(...), reply: str = Form(...), message_id: str = Form(...)):
    try:
        reply = sanitize_text(reply)
        draft_id = create_draft(sender, f"Re: {subject}", reply)
        if not draft_id:
            return templates.TemplateResponse("email_view.html", {
                "request": request,
                "email": {"sender": sender, "subject": subject, "message_id": message_id},
                "message": "Failed to create draft.", "message_type": "error"
            })
        
        service = get_gmail_service()
        if not service:
            return templates.TemplateResponse("email_view.html", {
                "request": request,
                "email": {"sender": sender, "subject": subject, "message_id": message_id},
                "message": "Failed to initialize Gmail service.", "message_type": "error"
            })
        
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute("SELECT email_date FROM replied_emails WHERE message_id=?", (message_id,))
        email_date = c.fetchone()[0]
        update_email_reply(sender, subject, reply, draft_id, email_date)
        c.execute("UPDATE replied_emails SET status='sent', reply_date=? WHERE message_id=?", 
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message_id))
        conn.commit()
        conn.close()
        
        await send_email_with_delay(service, draft_id, delay=10)
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error sending reply for {subject}: {e}")
        return templates.TemplateResponse("email_view.html", {
            "request": request,
            "email": {"sender": sender, "subject": subject, "message_id": message_id},
            "message": f"Failed to send reply: {str(e)}.", "message_type": "error"
        })