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
        + ["https://app.orvix.work", "https://banze.orvix.work"]
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
    geniuspay_api_secret = os.getenv("GENIUSPAY_API_SECRET", "").strip()
    geniuspay_webhook_secret = os.getenv("GENIUSPAY_WEBHOOK_SECRET", "").strip()
    geniuspay_base_url = os.getenv("GENIUSPAY_BASE_URL", "https://geniuspay.ci/api").rstrip("/")
    payment_simulation = os.getenv("PAYMENT_SIMULATION", "false").strip().lower() == "true"
    public_api_url = os.getenv("PUBLIC_API_URL", "http://127.0.0.1:8010").rstrip("/")
    public_frontend_url = os.getenv("PUBLIC_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")
    public_app_url = os.getenv("PUBLIC_APP_URL", "https://app.orvix.work").rstrip("/")
    superadmin_phone = os.getenv("SUPERADMIN_PHONE", "").strip()
    superadmin_password = os.getenv("SUPERADMIN_PASSWORD", "")
    max_upload_bytes = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    resend_from_email = os.getenv("RESEND_FROM_EMAIL", "Orvix <noreply@orvix.work>").strip()
    resend_reply_to = os.getenv("RESEND_REPLY_TO", "").strip()
    # Cloudflare R2 is S3-compatible. These values must remain server-only.
    r2_account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
    r2_access_key_id = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    r2_secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
    r2_bucket_name = os.getenv("R2_BUCKET_NAME", "").strip()
    r2_endpoint_url = os.getenv("R2_ENDPOINT_URL", "").strip()

    @property
    def r2_enabled(self) -> bool:
        return bool(self.r2_bucket_name and self.r2_access_key_id and self.r2_secret_access_key and (self.r2_endpoint_url or self.r2_account_id))

    @property
    def r2_s3_endpoint(self) -> str:
        return self.r2_endpoint_url or f"https://{self.r2_account_id}.r2.cloudflarestorage.com"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.users_file.parent.mkdir(parents=True, exist_ok=True)
    return settings
