from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import sqlite3
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_data(request: Request):
    conn = sqlite3.connect("replied_emails.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM replied_emails ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "data": rows})
