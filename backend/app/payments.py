import json
import secrets
import hashlib
import hmac
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from .config import get_settings
from .json_store import atomic_write_json
from .subscriptions import activate_subscription, plans_config


def _read_payments() -> dict:
    path = get_settings().payments_file
    if not path.exists():
        return {"payments": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payments(data: dict) -> None:
    atomic_write_json(get_settings().payments_file, data)


def _configured() -> bool:
    s = get_settings()
    return bool(s.geniuspay_api_key)


def valid_geniuspay_signature(raw_body: bytes, signature: str | None, timestamp: str | None) -> bool:
    secret = get_settings().geniuspay_webhook_secret
    if not secret:
        return False
    if not signature or not timestamp:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


async def create_checkout(user, plan_id: str, billing_cycle: str) -> dict:
    config = plans_config()
    plan = next((item for item in config["plans"] if item["id"] == plan_id), None)
    if not plan or plan_id == "free":
        raise HTTPException(422, "Forfait payant invalide.")
    amount = plan["annual_price"] if billing_cycle == "annual" else plan["monthly_price"]
    transaction_id = f"ORVIX{datetime.now(timezone.utc):%Y%m%d%H%M%S}{secrets.token_hex(4).upper()}"
    settings = get_settings()
    simulation = get_settings().payment_simulation
    record = {"transaction_id": transaction_id, "user_id": user.id, "plan_id": plan_id, "billing_cycle": billing_cycle, "amount": amount, "currency": config["currency"], "status": "SIMULATED" if simulation else "PENDING", "simulation": simulation, "created_at": datetime.now(timezone.utc).isoformat()}
    payments = _read_payments(); payments["payments"][transaction_id] = record; _write_payments(payments)
    if simulation:
        activate_subscription(user.id, plan_id, billing_cycle, transaction_id)
        return {"transaction_id": transaction_id, "payment_url": "", "simulation": True}
    if not _configured():
        raise HTTPException(503, "Le paiement n'est pas encore configuré.")
    payload = {
        "customer_phone": user.phone, "customer_name": user.name,
        "customer_email": f"{user.id}@orvix.local",
        "plan_name": f"ORVIX {plan['name']}", "amount": amount,
        "currency": config["currency"], "billing_cycle": billing_cycle,
        "payment_method": "stripe_checkout",
        "success_url": f"{settings.public_frontend_url}/?payment=success&transaction_id={transaction_id}",
        "cancel_url": f"{settings.public_frontend_url}/?payment=cancelled&transaction_id={transaction_id}",
        "metadata": {"transaction_id": transaction_id, "user_id": user.id, "plan_id": plan_id, "billing_cycle": billing_cycle},
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(f"{settings.geniuspay_base_url}/v1/merchant/subscriptions", json=payload, headers={"Authorization": f"Bearer {settings.geniuspay_api_key}", "Content-Type": "application/json", "Idempotency-Key": transaction_id})
            result = response.json()
        payment_url = (result.get("data") or {}).get("redirect_url") or (result.get("data") or {}).get("checkout_url")
        if not result.get("success") or not payment_url:
            raise HTTPException(502, result.get("message") or "Le paiement n'a pas pu être créé.")
        return {"transaction_id": transaction_id, "payment_url": payment_url, "simulation": False}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, "Connexion au service de paiement impossible.") from error


async def apply_geniuspay_webhook(payload: dict) -> dict:
    data = payload.get("data") or {}
    metadata = data.get("metadata") or {}
    subscription = data.get("subscription") or {}
    invoice = data.get("invoice") or {}
    transaction_id = metadata.get("transaction_id") or subscription.get("metadata", {}).get("transaction_id") or invoice.get("metadata", {}).get("transaction_id")
    if not transaction_id:
        raise HTTPException(400, "Transaction absente du webhook.")
    settings = get_settings(); payments = _read_payments(); record = payments["payments"].get(transaction_id)
    if not record:
        raise HTTPException(404, "Transaction inconnue.")
    accepted = payload.get("event") in {"payment.success", "payment.completed", "subscription.payment_succeeded"} and data.get("status", invoice.get("status")) in {"completed", "paid", "succeeded", "active"}
    received_amount = data.get("amount", invoice.get("amount", -1))
    received_currency = data.get("currency", invoice.get("currency", record["currency"]))
    same_amount = abs(float(received_amount) - float(record["amount"])) < 0.001
    same_currency = received_currency == record["currency"]
    record["status"] = "ACCEPTED" if accepted and same_amount and same_currency else "FAILED"
    record["verified_at"] = datetime.now(timezone.utc).isoformat(); payments["payments"][transaction_id] = record; _write_payments(payments)
    if record["status"] == "ACCEPTED":
        activate_subscription(record["user_id"], record["plan_id"], record["billing_cycle"], transaction_id)
    return record
