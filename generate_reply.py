import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# Check if API Key exists
if not GEMINI_API_KEY:
    raise ValueError("❌ GOOGLE_API_KEY not found in environment")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Gemini Flash 2.0 model
model = genai.GenerativeModel(model_name="gemini-2.0-flash")

# Email response generator
def generate_email_reply(subject: str, body: str) -> str:
    try:
        if not subject or not body:
            raise ValueError("Subject and body are required")

        prompt = f"""
        You are an assistant for Rao Faizan Raza, an IT Instructor at Al-Khair Institute.
        Here's an email with subject: "{subject}" and body: "{body}".

        Reply professionally including this signature:

        Sincerely,
        Rao Faizan Raza
        IT Instructor at Al-Khair Institute
        Next.js & TypeScript | Passionate about EdTech & AI | Cloud & GenAI Student at GIAIC
        """

        # Generate the reply
        response = model.generate_content(prompt)

        # Check if Gemini responded correctly
        if not response or not getattr(response, 'text', '').strip():
            raise ValueError("Empty response from Gemini")

        logger.info("✅ Reply generated successfully")
        return response.text.strip()

    except Exception as e:
        logger.error(f"⚠️ Failed to generate reply: {e}")
        return "Sorry, something went wrong while generating the reply."

