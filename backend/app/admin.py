import json
from fastapi import Header, HTTPException
from .auth import _make_token, _decode_token
from .config import get_settings

def admin_login(phone: str, password: str) -> str:
    settings = get_settings()
    if not settings.superadmin_phone or not settings.superadmin_password:
        raise HTTPException(503, "Le super administrateur n'est pas configuré.")
    if phone.strip().lower() != settings.superadmin_phone.lower() or password != settings.superadmin_password:
        raise HTTPException(401, "Identifiants administrateur invalides.")
    return _make_token("superadmin", settings.superadmin_phone)

def require_superadmin(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentification administrateur requise.")
    user_id, phone = _decode_token(authorization[7:].strip())
    settings = get_settings()
    if user_id != "superadmin" or phone.lower() != settings.superadmin_phone.lower():
        raise HTTPException(403, "Accès super administrateur requis.")
    return phone

def _load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def dashboard() -> dict:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            users = connection.execute("SELECT id, phone, name, created_at FROM users ORDER BY created_at DESC").fetchall()
            payments = connection.execute("SELECT transaction_id, user_id, plan_id, billing_cycle, amount, currency, status, simulation, created_at FROM payments ORDER BY created_at DESC").fetchall()
            subscriptions = connection.execute("SELECT user_id, plan_id, status, billing_cycle, started_at, expires_at, last_transaction_id FROM subscriptions ORDER BY started_at DESC").fetchall()
        user_rows = [{"id": row[0], "phone": row[1], "name": row[2], "created_at": row[3].isoformat() if row[3] else None} for row in users]
        payment_rows = [{"transaction_id": row[0], "user_id": row[1], "plan_id": row[2], "billing_cycle": row[3], "amount": float(row[4]), "currency": row[5], "status": row[6], "simulation": row[7], "created_at": row[8].isoformat() if row[8] else None} for row in payments]
        subscription_rows = [{"user_id": row[0], "plan_id": row[1], "status": row[2], "billing_cycle": row[3], "started_at": row[4].isoformat() if row[4] else None, "expires_at": row[5].isoformat() if row[5] else None, "last_transaction_id": row[6]} for row in subscriptions]
        return {"users": user_rows, "payments": payment_rows, "subscriptions": subscription_rows, "stats": {"users": len(user_rows), "payments": len(payment_rows), "subscriptions": len(subscription_rows), "paid_payments": sum(p["status"] == "ACCEPTED" for p in payment_rows)}}
    users = _load(settings.users_file, {"users": []}).get("users", [])
    payments = _load(settings.payments_file, {"payments": {}}).get("payments", {})
    subscriptions = _load(settings.subscriptions_file, {"subscriptions": {}}).get("subscriptions", {})
    return {"users": [{"id": u.get("id"), "phone": u.get("phone"), "name": u.get("name", "Etudiant"), "created_at": u.get("created_at")} for u in users], "payments": list(payments.values()), "subscriptions": [{"user_id": user_id, **value} for user_id, value in subscriptions.items()], "stats": {"users": len(users), "payments": len(payments), "subscriptions": len(subscriptions), "paid_payments": sum(p.get("status") == "ACCEPTED" for p in payments.values())}}
