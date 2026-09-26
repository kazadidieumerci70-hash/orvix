from datetime import date, datetime, timedelta, timezone
import json

from fastapi import HTTPException

from .config import get_settings
from .json_store import atomic_write_json

DEFAULT_CREDIT_COSTS = {"chat": 1, "chat_with_documents": 2, "revision": 3, "quiz_short": 5, "quiz_long": 8, "exam_plan": 10}
DEFAULT_PLANS = {
    "currency": "USD", "annual_discount_percent": 16.67, "credit_costs": DEFAULT_CREDIT_COSTS,
    "plans": [
        {"id": "free", "name": "Free", "tagline": "Découvrir ORVIX", "monthly_price": 0, "annual_price": 0, "documents": 1, "daily_credits": 18, "monthly_credits": 540, "daily_safety_limit": 18, "daily_requests": 18, "features": ["Quiz courts", "Fonctions essentielles"]},
        {"id": "student", "name": "Étudiant", "tagline": "Étudier avec ORVIX", "monthly_price": 4.99, "annual_price": 49.90, "documents": 10, "daily_credits": 60, "monthly_credits": 1800, "daily_safety_limit": 150, "daily_requests": 150, "features": ["Quiz et révisions", "Outils étudiants", "Export", "Mémoire standard"]},
        {"id": "pro", "name": "Pro", "tagline": "Utiliser ORVIX intensivement", "monthly_price": 9.99, "annual_price": 99.90, "documents": 30, "daily_credits": 170, "monthly_credits": 5000, "daily_safety_limit": 400, "daily_requests": 400, "features": ["Examens et analyses avancées", "Outils avancés", "Export et rapports", "Mémoire avancée"]},
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
    config = _read(get_settings().plans_file, DEFAULT_PLANS)
    config.setdefault("credit_costs", DEFAULT_CREDIT_COSTS)
    for plan in config.get("plans", []):
        legacy_daily = int(plan.get("daily_requests", 0))
        plan.setdefault("daily_credits", max(18, legacy_daily))
        plan.setdefault("monthly_credits", max(40, legacy_daily * 12))
        plan.setdefault("daily_safety_limit", plan["daily_credits"])
        plan.setdefault("daily_requests", plan["daily_safety_limit"])
    return config


def credit_cost(action: str) -> int:
    costs = plans_config().get("credit_costs", {})
    return max(1, int(costs.get(action, DEFAULT_CREDIT_COSTS.get(action, 1))))


def _plan(plan_id: str) -> dict:
    for plan in plans_config()["plans"]:
        if plan["id"] == plan_id:
            return plan
    return plans_config()["plans"][0]


def _usage_totals(user_id: str) -> tuple[int, int]:
    usage = _read(get_settings().usage_file, {"days": {}, "months": {}, "ledger": []})
    today = date.today().isoformat()
    used_today = int(usage.get("days", {}).get(today, {}).get(user_id, 0))
    used_month = int(usage.get("months", {}).get(today[:7], {}).get(user_id, 0))
    return used_today, used_month


def subscription_status(user_id: str) -> dict:
    settings = get_settings()
    subscriptions = _read(settings.subscriptions_file, {"subscriptions": {}})
    current = subscriptions["subscriptions"].get(user_id, {"plan_id": "free", "status": "active", "billing_cycle": "monthly", "expires_at": None, "bonus_credits": 0})
    expires_at = current.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc):
        current = {"plan_id": "free", "status": "expired", "billing_cycle": "monthly", "expires_at": None, "bonus_credits": 0}
        subscriptions["subscriptions"][user_id] = current
        _write(settings.subscriptions_file, subscriptions)
    plan = _plan(current["plan_id"])
    used_today, used_month = _usage_totals(user_id)
    bonus_credits = max(0, int(current.get("bonus_credits", 0)))
    is_daily_plan = plan["id"] == "free"
    primary_limit = int(plan["daily_credits"] if is_daily_plan else plan["monthly_credits"])
    primary_used = used_today if is_daily_plan else used_month
    daily_limit = int(plan["daily_safety_limit"])
    return {
        "subscription": current, "plan": plan,
        "credits_used_today": used_today, "credits_used_month": used_month,
        "credits_remaining": max(0, primary_limit + bonus_credits - primary_used),
        "credits_limit": primary_limit + bonus_credits,
        "credit_period": "daily" if is_daily_plan else "monthly",
        "bonus_credits": bonus_credits,
        "daily_credits_remaining": max(0, daily_limit - used_today),
        "credit_costs": plans_config()["credit_costs"],
        "requests_used_today": used_today,
        "requests_remaining_today": max(0, daily_limit - used_today),
    }


def ensure_ai_quota(user_id: str, cost: int = 1) -> None:
    status = subscription_status(user_id)
    if status["credits_remaining"] < cost:
        period = "du jour" if status["credit_period"] == "daily" else "du mois"
        renewal = "demain" if status["credit_period"] == "daily" else "au prochain renouvellement mensuel"
        raise HTTPException(429, f"Crédits {period} épuisés pour le forfait {status['plan']['name']}. Ils seront renouvelés {renewal}.")
    if status["credit_period"] == "monthly" and status["daily_credits_remaining"] < cost:
        raise HTTPException(429, "Limite quotidienne de sécurité atteinte. Vos crédits mensuels restants seront de nouveau utilisables demain.")


def join_waitlist(user_id: str, plan_id: str) -> dict:
    if plan_id not in {"student", "pro"}:
        raise HTTPException(400, "Choisissez une offre premium valide.")
    settings = get_settings()
    data = _read(settings.waitlist_file, {"entries": []})
    entries = data.setdefault("entries", [])
    existing = next((entry for entry in entries if entry.get("user_id") == user_id and entry.get("plan_id") == plan_id), None)
    if not existing:
        entries.append({"user_id": user_id, "plan_id": plan_id, "created_at": datetime.now(timezone.utc).isoformat()})
        _write(settings.waitlist_file, data)
    return {"joined": True, "plan_id": plan_id}


def ensure_document_quota(user_id: str, current_count: int, incoming_count: int = 1) -> None:
    status = subscription_status(user_id)
    limit = int(status["plan"]["documents"])
    if current_count + incoming_count > limit:
        raise HTTPException(403, f"Votre forfait {status['plan']['name']} autorise {limit} document{'s' if limit > 1 else ''}. Supprimez un document ou choisissez un forfait supérieur.")


def record_ai_request(user_id: str, cost: int = 1, action: str = "chat") -> None:
    settings = get_settings()
    usage = _read(settings.usage_file, {"days": {}, "months": {}, "ledger": []})
    today = date.today().isoformat()
    month = today[:7]
    usage.setdefault("days", {}).setdefault(today, {})
    usage.setdefault("months", {}).setdefault(month, {})
    usage["days"][today][user_id] = int(usage["days"][today].get(user_id, 0)) + cost
    usage["months"][month][user_id] = int(usage["months"][month].get(user_id, 0)) + cost
    usage.setdefault("ledger", []).append({"user_id": user_id, "action": action, "credits": cost, "created_at": datetime.now(timezone.utc).isoformat()})
    usage["days"] = dict(sorted(usage["days"].items())[-45:])
    usage["months"] = dict(sorted(usage["months"].items())[-14:])
    usage["ledger"] = usage["ledger"][-5000:]
    _write(settings.usage_file, usage)


def activate_subscription(user_id: str, plan_id: str, billing_cycle: str, transaction_id: str) -> dict:
    settings = get_settings()
    data = _read(settings.subscriptions_file, {"subscriptions": {}})
    current = data["subscriptions"].get(user_id, {})
    if current.get("last_transaction_id") == transaction_id:
        return subscription_status(user_id)
    now = datetime.now(timezone.utc)
    start = now
    current_expiry = current.get("expires_at")
    if current_expiry:
        parsed = datetime.fromisoformat(current_expiry)
        if parsed > now and current.get("plan_id") == plan_id:
            start = parsed
    duration = timedelta(days=365 if billing_cycle == "annual" else 30)
    data["subscriptions"][user_id] = {
        "plan_id": plan_id, "status": "active", "billing_cycle": billing_cycle,
        "started_at": now.isoformat(), "expires_at": (start + duration).isoformat(),
        "last_transaction_id": transaction_id, "bonus_credits": int(current.get("bonus_credits", 0)),
    }
    _write(settings.subscriptions_file, data)
    return subscription_status(user_id)
