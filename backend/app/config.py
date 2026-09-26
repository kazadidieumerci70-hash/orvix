from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")


class Settings:
    app_name = "Orvix API"
    api_prefix = "/api/v1"
    database_url = next((os.getenv(name, "").strip() for name in ("DATABASE_URL", "DATABASE_PRIVATE_URL", "DATABASE_PUBLIC_URL", "POSTGRES_URL") if os.getenv(name, "").strip()), "")
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip().replace("\\_", "_")
    orvix_auth_secret = os.getenv("ORVIX_AUTH_SECRET", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_fallback_models = tuple(
        model.strip()
        for model in os.getenv(
            "GEMINI_FALLBACK_MODELS",
            "gemini-2.5-flash-lite,gemini-2.0-flash",
        ).split(",")
        if model.strip() and model.strip() != os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    )
    gemini_verify_ssl = os.getenv("GEMINI_VERIFY_SSL", "true").strip().lower() != "false"
    model_provider = os.getenv("MODEL_PROVIDER", "ollama")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    model_timeout = float(os.getenv("MODEL_TIMEOUT", "90"))
    frontend_origins = tuple(dict.fromkeys(
        [origin.strip() for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://192.168.170.33:5173",
        ).split(",") if origin.strip()]
        + ["https://orvix-ai.pages.dev", "https://orvix-super-admin.nexikarmotor.chatgpt.site"]
    ))
    upload_dir = BACKEND_DIR / "data" / "uploads"
    data_dir = BACKEND_DIR / "data"
    users_file = BACKEND_DIR / "data" / "users.json"
    conversations_file = BACKEND_DIR / "data" / "conversations.json"
    deleted_documents_file = BACKEND_DIR / "data" / "deleted_documents.json"
    document_owners_file = BACKEND_DIR / "data" / "document_owners.json"
    plans_file = BACKEND_DIR / "data" / "plans.json"
    subscriptions_file = BACKEND_DIR / "data" / "subscriptions.json"
    usage_file = BACKEND_DIR / "data" / "usage.json"
    payments_file = BACKEND_DIR / "data" / "payments.json"
    waitlist_file = BACKEND_DIR / "data" / "subscription_waitlist.json"
    geniuspay_api_key = os.getenv("GENIUSPAY_API_KEY", "").strip()
    geniuspay_webhook_secret = os.getenv("GENIUSPAY_WEBHOOK_SECRET", "").strip()
    geniuspay_base_url = os.getenv("GENIUSPAY_BASE_URL", "https://api.geniuspay.ci").rstrip("/")
    payment_simulation = os.getenv("PAYMENT_SIMULATION", "true").strip().lower() == "true"
    public_api_url = os.getenv("PUBLIC_API_URL", "http://127.0.0.1:8010").rstrip("/")
    public_frontend_url = os.getenv("PUBLIC_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
    superadmin_phone = os.getenv("SUPERADMIN_PHONE", "").strip()
    superadmin_password = os.getenv("SUPERADMIN_PASSWORD", "")
    max_upload_bytes = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.users_file.parent.mkdir(parents=True, exist_ok=True)
    return settings
