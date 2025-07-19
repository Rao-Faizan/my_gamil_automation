from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import sqlite3

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_data(request: Request):
    conn = sqlite3.connect("replied_emails.db")
    c = conn.cursor()
    c.execute("SELECT sender, subject, email_date, status, reply, original_body FROM replied_emails ORDER BY email_date DESC")
    rows = c.fetchall()
    conn.close()

    emails = [
        {
            "sender": row[0],
            "subject": row[1],
            "email_date": row[2],
            "status": row[3],
            "reply": row[4],
            "original_body": row[5]
        } for row in rows
    ]

    return templates.TemplateResponse("emails.html", {"request": request, "emails": emails})


@app.post("/send")
def send_email(
    sender: str = Form(...),
    subject: str = Form(...),
    reply: str = Form(...)
):
    print("Body:\n", reply)

    # Update status to 'sent'
    conn = sqlite3.connect("replied_emails.db")
    c = conn.cursor()
    c.execute("UPDATE replied_emails SET status='sent' WHERE sender=? AND subject=?", (sender, subject))
    conn.commit()
    conn.close()

    return {"message": "Email sent!", "sender": sender, "subject": subject, "reply": reply}
