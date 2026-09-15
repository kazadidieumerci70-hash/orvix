import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from .config import get_settings
from .json_store import atomic_write_json
from .subscriptions import activate_subscription, plans_config

INIT_URL = "https://api-checkout.cinetpay.com/v2/payment"
CHECK_URL = "https://api-checkout.cinetpay.com/v2/payment/check"


def _read_payments() -> dict:
    path = get_settings().payments_file
    if not path.exists():
        return {"payments": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payments(data: dict) -> None:
    atomic_write_json(get_settings().payments_file, data)


def _configured() -> bool:
    s = get_settings()
    return bool(s.cinetpay_api_key and s.cinetpay_site_id and s.cinetpay_secret_key)


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
        raise HTTPException(503, "Le compte marchand CinetPay doit encore être configuré par ORVIX.")
    payload = {
        "apikey": settings.cinetpay_api_key, "site_id": settings.cinetpay_site_id,
        "transaction_id": transaction_id, "amount": amount, "currency": config["currency"],
        "description": f"Abonnement ORVIX {plan['name']} {billing_cycle}",
        "notify_url": f"{settings.public_api_url}/api/v1/payments/cinetpay/notify",
        "return_url": f"{settings.public_frontend_url}/?payment=return",
        "channels": "ALL", "metadata": transaction_id, "lang": "FR",
        "customer_id": user.id, "customer_name": user.name, "customer_surname": "ORVIX",
        "customer_phone_number": user.phone, "customer_country": "CD",
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(INIT_URL, json=payload)
            result = response.json()
        if str(result.get("code")) != "201" or not result.get("data", {}).get("payment_url"):
            raise HTTPException(502, result.get("description") or "CinetPay n'a pas pu créer le paiement.")
        return {"transaction_id": transaction_id, "payment_url": result["data"]["payment_url"], "simulation": False}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(502, "Connexion au service de paiement impossible.") from error


def valid_hmac(form: dict, received: str | None) -> bool:
    if not received or not get_settings().cinetpay_secret_key:
        return False
    fields = ["cpm_site_id", "cpm_trans_id", "cpm_trans_date", "cpm_amount", "cpm_currency", "signature", "payment_method", "cel_phone_num", "cpm_phone_prefixe", "cpm_language", "cpm_version", "cpm_payment_config", "cpm_page_action", "cpm_custom", "cpm_designation", "cpm_error_message"]
    raw = "".join(str(form.get(field, "")) for field in fields)
    expected = hmac.new(get_settings().cinetpay_secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(received.lower(), expected.lower())


async def verify_and_apply(transaction_id: str) -> dict:
    settings = get_settings(); payments = _read_payments(); record = payments["payments"].get(transaction_id)
    if not record:
        raise HTTPException(404, "Transaction inconnue.")
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(CHECK_URL, json={"apikey": settings.cinetpay_api_key, "site_id": settings.cinetpay_site_id, "transaction_id": transaction_id})
        result = response.json()
    data = result.get("data") or {}
    accepted = str(result.get("code")) == "00" and data.get("status") == "ACCEPTED"
    same_amount = abs(float(data.get("amount", -1)) - float(record["amount"])) < 0.001
    same_currency = data.get("currency") == record["currency"]
    record["status"] = "ACCEPTED" if accepted and same_amount and same_currency else data.get("status", "PENDING")
    record["verified_at"] = datetime.now(timezone.utc).isoformat(); payments["payments"][transaction_id] = record; _write_payments(payments)
    if record["status"] == "ACCEPTED":
        activate_subscription(record["user_id"], record["plan_id"], record["billing_cycle"], transaction_id)
    return record
