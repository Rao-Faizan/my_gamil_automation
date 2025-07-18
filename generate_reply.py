import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Load Gemini API Key from .env
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Use Gemini 1.5 Pro (latest stable version)
model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

def generate_email_reply(subject: str, body: str) -> str:
    prompt = f"""You are an assistant. Here's an email with subject: "{subject}" and body: "{body}". Reply to it professionally."""
    response = model.generate_content(prompt)
    return response.text
