import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    model = genai.GenerativeModel(model_name="gemini-2.0-flash")
    prompt = "Hello, this is a test prompt."
    response = model.generate_content(prompt)
    logger.info(f"✅ Gemini API Response: {response.text[:100]}...")
except Exception as e:
    logger.error(f"⚠️ Gemini API test failed: {e}")
