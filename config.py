import os
import secrets
from dotenv import load_dotenv

# Load environment variables — root .env first, then chatbot/.env as fallback
load_dotenv()
_chatbot_env = os.path.join(os.path.dirname(__file__), "chatbot", ".env")
if not os.getenv("SUPABASE_URL") and os.path.exists(_chatbot_env):
    load_dotenv(dotenv_path=_chatbot_env)


class Config:
    """Application configuration — optimised for 30 concurrent users."""

    # ── Flask session settings ────────────────────────────────────────────────
    # SECRET_KEY must be stable across Gunicorn workers (env var or fixed value).
    # If not set via .env, fall back to a fixed dev key — change in production!
    SECRET_KEY       = os.getenv('FLASK_SECRET_KEY', 'quota-pro-change-me-in-production')

    # Cookie-based sessions are inherently thread/process-safe.
    # Limit session cookie lifetime so tokens don't linger forever.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8   # 8 hours (seconds)

    # ── Database / Supabase ───────────────────────────────────────────────────
    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

    # ── Groq API ──────────────────────────────────────────────────────────────
    GROQ_API_KEY  = os.getenv('GROQ_API_KEY', '')
    GROQ_API_BASE = "https://api.groq.com/openai/v1"
    GROQ_MODEL    = "llama-3.1-8b-instant"

    # ── File upload settings ──────────────────────────────────────────────────
    UPLOAD_FOLDER       = os.path.join(os.path.dirname(__file__), 'uploads')
    OUTPUT_FOLDER       = os.path.join(os.path.dirname(__file__), 'outputs')
    ALLOWED_EXTENSIONS  = {'pdf', 'docx', 'doc', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'tiff'}
    MAX_CONTENT_LENGTH  = 16 * 1024 * 1024   # 16 MB

    # ── OCR Configuration ─────────────────────────────────────────────────────
    OCR_ENABLED              = False
    OCR_LANGUAGES            = ['en']
    OCR_CONFIDENCE_THRESHOLD = 0.6

    # ── NLP Configuration ─────────────────────────────────────────────────────
    NLP_ENABLED              = True
    NLP_MODEL                = 'en_core_web_sm'
    ENTITY_EXTRACTION_ENABLED = True

    # ── Template settings ─────────────────────────────────────────────────────
    TEMPLATE_TYPES = {
        'type1': 'Detailed Itemized Quotation',
        'type2': 'Executive Summary Style',
    }

    @staticmethod
    def init_app(app):
        """Initialize application directories."""
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)
