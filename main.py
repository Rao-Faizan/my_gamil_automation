from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from email.mime.text import MIMEText
import base64
from reply_db import save_email_reply, update_email_reply, update_draft_id_in_db
from generate_reply import generate_email_reply
from datetime import datetime
import asyncio
import logging
import os
import csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Implement placeholder functions with basic logic or error handling
def sanitize_text(text):
    return text.replace("\n", "").replace("\r", "") if text else ""

def get_gmail_service():
    try:
        # Placeholder - Replace with actual Gmail API credentials logic
        creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/gmail.send"])
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
            else:
                logger.error("⚠️ Gmail credentials not found or invalid. Please authenticate.")
                return None
        service = build("gmail", "v1", credentials=creds)
        return service
    except Exception as e:
        logger.error(f"⚠️ Error initializing Gmail service: {e}")
        return None

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

async def send_email_with_delay(service, draft_id, delay=10):
    try:
        if not service or not draft_id:
            return False
        await asyncio.sleep(delay)  # Simulate delay
        message = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
        logger.info(f"✅ Email sent from draft: {draft_id}")
        return True
    except Exception as e:
        logger.error(f"⚠️ Error sending email from draft {draft_id}: {e}")
        return False

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
            "unread_emails": [],
            "sent_emails": [],
            "draft_emails": [],
            "no_reply_emails": [],
            "message": f"Failed to fetch emails: {str(e)}. Please check database connection.",
            "message_type": "error"
        })

@app.post("/generate_reply", response_class=HTMLResponse)
async def generate_reply(request: Request, sender: str = Form(...), subject: str = Form(default='No Subject'), original_body: str = Form(...), message_id: str = Form(...), custom_prompt: str = Form(default=None)):
    try:
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        c.execute("SELECT status FROM replied_emails WHERE message_id=?", (message_id,))
        status = c.fetchone()
        conn.close()
        if not status or status[0] in ['no-reply', 'sent']:
            return templates.TemplateResponse("email_view.html", {
                "request": request,
                "email": {"sender": sender, "subject": subject, "original_body": original_body, "message_id": message_id},
                "message": "Reply cannot be generated for this email.",
                "message_type": "error"
            })
        
        reply = generate_email_reply(subject, original_body) if not custom_prompt else generate_email_reply(subject, original_body, custom_prompt=custom_prompt)
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
        
        update_email_reply(sender, subject, reply, draft_id)
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

@app.post("/upload_csv", response_class=HTMLResponse)
async def upload_csv(request: Request, file: UploadFile = File(...)):
    try:
        content = await file.read()
        decoded_content = content.decode('utf-8')
        csv_reader = csv.DictReader(decoded_content.splitlines())
        required_fields = {'sender', 'subject', 'original_body'}
        
        conn = sqlite3.connect("replied_emails.db")
        c = conn.cursor()
        inserted_count = 0
        for row in csv_reader:
            if all(field in row for field in required_fields):
                c.execute(
                    "INSERT INTO replied_emails (sender, subject, email_date, status, original_body) VALUES (?, ?, ?, ?, ?)",
                    (row['sender'], row['subject'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'unread', row['original_body'])
                )
                inserted_count += 1
        conn.commit()
        conn.close()
        logger.info(f"✅ Uploaded {inserted_count} emails from CSV")
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error uploading CSV: {e}")
        return templates.TemplateResponse("emails.html", {
            "request": request,
            "unread_emails": [],
            "sent_emails": [],
            "draft_emails": [],
            "no_reply_emails": [],
            "message": f"Failed to upload CSV: {str(e)}. Ensure file has 'sender', 'subject', 'original_body' columns.",
            "message_type": "error"
        })

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
            c.execute("SELECT sender, subject, draft_id, message_id, original_body FROM replied_emails WHERE message_id=?", (message_id,))
            row = c.fetchone()
            if row:
                emails.append({"sender": row[0], "subject": row[1] or 'No Subject', "draft_id": row[2], "message_id": row[3], "original_body": row[4]})
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
                    try:
                        message_text = generate_email_reply(email['subject'], email['original_body'], custom_prompt=custom_prompt) if custom_prompt else generate_email_reply(email['subject'], email['original_body'])
                    except Exception as e:
                        logger.error(f"⚠️ Failed to generate AI reply for {email['sender']}: {e}")
                        message_text = f"Dear {email['sender'].split('<')[0].strip()},\nThank you for your email. We will get back to you soon.\nBest regards,\nRao Faizan Raza\nIT Instructor at Al-Khair Institute"
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
                    update_draft_id_in_db(email['sender'], email['subject'], new_draft_id)
                    draft_id = new_draft_id

                update_email_reply(email['sender'], email['subject'], message_text, draft_id)
                await send_email_with_delay(service, draft_id, delay=10)

                c.execute("UPDATE replied_emails SET status='sent', reply_date=? WHERE message_id=?", 
                         (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email['message_id']))
                conn.commit()
                sent_count += 1
            except Exception as e:
                logger.error(f"⚠️⚠️ Error processing email for {email['sender']}: {e}")
                failed_emails.append(email['sender'])

        conn.close()
        if failed_emails:
            return templates.TemplateResponse("bulk.html", {
                "request": request,
                "emails": (await bulk_page(request)).body,
                "message": f"Sent {sent_count} emails successfully. Failed for {len(failed_emails)}: {', '.join(failed_emails)}",
                "message_type": "error"
            })
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.error(f"⚠️ Error during bulk send: {e}")
        return templates.TemplateResponse("bulk.html", {
            "request": request,
            "emails": (await bulk_page(request)).body,
            "message": f"Failed to send emails: {str(e)}.",
            "message_type": "error"
        })