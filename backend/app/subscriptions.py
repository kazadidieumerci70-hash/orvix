from datetime import date, datetime, timedelta, timezone
import json

from fastapi import HTTPException

from .config import get_settings
from .json_store import atomic_write_json

DEFAULT_PLANS = {
    "currency": "USD",
    "annual_discount_percent": 16.67,
    "plans": [
        {"id": "free", "name": "Gratuit", "monthly_price": 0, "annual_price": 0, "documents": 1, "daily_requests": 9, "features": ["Fonctionnalités essentielles"]},
        {"id": "student", "name": "Étudiant", "monthly_price": 4.99, "annual_price": 49.90, "documents": 10, "daily_requests": 50, "features": ["Fonctionnalités avancées"]},
        {"id": "pro", "name": "Pro", "monthly_price": 9.99, "annual_price": 99.90, "documents": 30, "daily_requests": 150, "features": ["Accès complet aux fonctionnalités avancées"]},
    ],
}


def _read(path, default):
    if not path.exists():
        atomic_write_json(path, default)
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    atomic_write_json(path, data)


def plans_config() -> dict:
    return _read(get_settings().plans_file, DEFAULT_PLANS)


def _plan(plan_id: str) -> dict:
    for plan in plans_config()["plans"]:
        if plan["id"] == plan_id:
            return plan
    return plans_config()["plans"][0]


def subscription_status(user_id: str) -> dict:
    settings = get_settings()
    subscriptions = _read(settings.subscriptions_file, {"subscriptions": {}})
    current = subscriptions["subscriptions"].get(user_id, {"plan_id": "free", "status": "active", "billing_cycle": "monthly", "expires_at": None})
    expires_at = current.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
        current = {"plan_id": "free", "status": "expired", "billing_cycle": "monthly", "expires_at": None}
        subscriptions["subscriptions"][user_id] = current
        _write(settings.subscriptions_file, subscriptions)
    usage = _read(settings.usage_file, {"days": {}})
    used = usage["days"].get(date.today().isoformat(), {}).get(user_id, 0)
    plan = _plan(current["plan_id"])
    return {"subscription": current, "plan": plan, "requests_used_today": used, "requests_remaining_today": max(0, plan["daily_requests"] - used)}


def ensure_ai_quota(user_id: str) -> None:
    status = subscription_status(user_id)
    if status["requests_remaining_today"] <= 0:
        raise HTTPException(429, f"Limite quotidienne atteinte pour le forfait {status['plan']['name']}. Renouvelez demain ou choisissez un forfait supérieur.")


def ensure_document_quota(user_id: str, current_count: int, incoming_count: int = 1) -> None:
    status = subscription_status(user_id)
    limit = int(status["plan"]["documents"])
    if current_count + incoming_count > limit:
        raise HTTPException(403, f"Votre forfait {status['plan']['name']} autorise {limit} document{'s' if limit > 1 else ''}. Supprimez un document ou choisissez un forfait supérieur.")


def record_ai_request(user_id: str) -> None:
    settings = get_settings()
    usage = _read(settings.usage_file, {"days": {}})
    today = date.today().isoformat()
    usage["days"].setdefault(today, {})
    usage["days"][today][user_id] = usage["days"][today].get(user_id, 0) + 1
    # Conservation légère : les 45 derniers jours seulement.
    usage["days"] = dict(sorted(usage["days"].items())[-45:])
    _write(settings.usage_file, usage)


def activate_subscription(user_id: str, plan_id: str, billing_cycle: str, transaction_id: str) -> dict:
    settings = get_settings()
    data = _read(settings.subscriptions_file, {"subscriptions": {}})
    current = data["subscriptions"].get(user_id, {})
    if current.get("last_transaction_id") == transaction_id:
        return subscription_status(user_id)
    now = datetime.now(timezone.utc)
    current_expiry = current.get("expires_at")
    start = now
    if current_expiry:
        parsed = datetime.fromisoformat(current_expiry)
        if parsed > now:
            start = parsed
    duration = timedelta(days=365 if billing_cycle == "annual" else 30)
    data["subscriptions"][user_id] = {
        "plan_id": plan_id, "status": "active", "billing_cycle": billing_cycle,
        "started_at": now.isoformat(), "expires_at": (start + duration).isoformat(),
        "last_transaction_id": transaction_id,
    }
    _write(settings.subscriptions_file, data)
    return subscription_status(user_id)
