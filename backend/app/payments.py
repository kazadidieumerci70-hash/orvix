import json
import secrets
import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from .config import get_settings
from .json_store import atomic_write_json
from .subscriptions import activate_subscription, plans_config, subscription_status
from .email_service import send_payment_email

logger = logging.getLogger(__name__)


def _read_payments() -> dict:
    if get_settings().database_url:
        import psycopg
        with psycopg.connect(get_settings().database_url) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS payment_checkout_records (transaction_id TEXT PRIMARY KEY, record JSONB NOT NULL)")
            rows = connection.execute("SELECT transaction_id, record FROM payment_checkout_records").fetchall()
        return {"payments": {key: value for key, value in rows}}
    path = get_settings().payments_file
    if not path.exists():
        return {"payments": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_payments(data: dict) -> None:
    if get_settings().database_url:
        import psycopg
        with psycopg.connect(get_settings().database_url) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS payment_checkout_records (transaction_id TEXT PRIMARY KEY, record JSONB NOT NULL)")
            for key, record in data["payments"].items():
                connection.execute("INSERT INTO payment_checkout_records (transaction_id, record) VALUES (%s, %s::jsonb) ON CONFLICT (transaction_id) DO UPDATE SET record = EXCLUDED.record", (key, json.dumps(record)))
        return
    existing = _read_payments()
    existing.setdefault("payments", {}).update(data.get("payments", {}))
    atomic_write_json(get_settings().payments_file, existing)


def _payment_matches(record: dict, data: dict) -> bool:
    metadata = data.get("metadata") or {}
    if not record.get("provider_reference") or data.get("reference") != record["provider_reference"]:
        return False
    if metadata.get("transaction_id") != record["transaction_id"]:
        return False
    if str(metadata.get("user_id")) != str(record["user_id"]):
        return False
    try:
        same_amount = abs(float(data.get("amount")) - float(record["amount"])) < 0.001
    except (TypeError, ValueError):
        return False
    return same_amount and data.get("currency") == record["currency"]


def _accept_payment(record: dict) -> dict:
    activate_subscription(record["user_id"], record["plan_id"], record["billing_cycle"], record["transaction_id"])
    record["status"] = "ACCEPTED"
    record["verified_at"] = datetime.now(timezone.utc).isoformat()
    _write_payments({"payments": {record["transaction_id"]: record}})
    return record


def _configured() -> bool:
    s = get_settings()
    return bool(s.geniuspay_api_key and s.geniuspay_api_secret)


def valid_geniuspay_signature(raw_body: bytes, signature: str | None, timestamp: str | None) -> bool:
    secret = get_settings().geniuspay_webhook_secret
    if not secret:
        return False
    if not signature or not timestamp:
        return False
    try:
        if abs(datetime.now(timezone.utc).timestamp() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def ensure_checkout_allowed(user_id: str, plan_id: str) -> None:
    current = subscription_status(user_id)
    if plan_id == "student" and current["plan"]["id"] == "pro":
        expiry = current["subscription"].get("expires_at")
        until = f" jusqu’au {datetime.fromisoformat(expiry).strftime('%d/%m/%Y')}" if expiry else ""
        raise HTTPException(409, f"Ton forfait Pro est encore actif{until}. Tu pourras choisir le forfait Étudiant après son expiration. Aucun paiement n’a été lancé.")


def _pending_checkout(user_id: str, plan_id: str, billing_cycle: str, payment_method: str, customer_phone: str) -> dict | None:
    for record in _read_payments()["payments"].values():
        if (record.get("user_id") == user_id and record.get("plan_id") == plan_id
                and record.get("billing_cycle") == billing_cycle and record.get("payment_method") == payment_method
                and record.get("customer_phone", "") == customer_phone and record.get("status") == "PENDING"):
            return record
    return None


def _replace_pending_checkout(record: dict) -> None:
    """Close an unusable checkout so it can never lock a customer out."""
    record["status"] = "REPLACED"
    record["replaced_at"] = datetime.now(timezone.utc).isoformat()
    _write_payments({"payments": {record["transaction_id"]: record}})


def _fail_checkout(record: dict) -> None:
    record["status"] = "FAILED"
    record["failed_at"] = datetime.now(timezone.utc).isoformat()
    _write_payments({"payments": {record["transaction_id"]: record}})


async def create_checkout(user, plan_id: str, billing_cycle: str, customer_email: str, payment_method: str, customer_phone: str = "") -> dict:
    ensure_checkout_allowed(user.id, plan_id)
    customer_email = customer_email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", customer_email):
        raise HTTPException(422, "Indiquez une adresse e-mail valide pour recevoir votre confirmation de paiement.")
    customer_phone = customer_phone.strip().replace(" ", "").replace("-", "")
    if payment_method in {"airtel_money", "orange_money"} and not re.fullmatch(r"\+[1-9]\d{7,14}", customer_phone):
        raise HTTPException(422, "Indique un numéro Mobile Money valide au format international, par exemple +243XXXXXXXXX.")
    if payment_method == "card":
        customer_phone = ""
    config = plans_config()
    plan = next((item for item in config["plans"] if item["id"] == plan_id), None)
    if not plan or plan_id == "free":
        raise HTTPException(422, "Forfait payant invalide.")
    pending = _pending_checkout(user.id, plan_id, billing_cycle, payment_method, customer_phone)
    # If Genius Pay has already given us a secure checkout URL, resume that
    # exact payment instead of making the user wait or exposing a duplicate.
    if pending and pending.get("payment_url"):
        return {"transaction_id": pending["transaction_id"], "payment_url": pending["payment_url"], "simulation": False, "reused": True}
    # A record created before Genius Pay returned a URL is incomplete. It must
    # never block another attempt, including after a network/provider error.
    if pending:
        _replace_pending_checkout(pending)
    amount = plan["annual_price"] if billing_cycle == "annual" else plan["monthly_price"]
    transaction_id = f"ORVIX{datetime.now(timezone.utc):%Y%m%d%H%M%S}{secrets.token_hex(4).upper()}"
    settings = get_settings()
    simulation = get_settings().payment_simulation
    if simulation:
        record = {"transaction_id": transaction_id, "user_id": user.id, "plan_id": plan_id, "billing_cycle": billing_cycle, "amount": amount, "currency": config["currency"], "customer_email": customer_email, "customer_name": user.name, "status": "SIMULATED", "simulation": True, "created_at": datetime.now(timezone.utc).isoformat()}
        _write_payments({"payments": {transaction_id: record}})
        activate_subscription(user.id, plan_id, billing_cycle, transaction_id)
        await send_payment_email(email=customer_email, name=user.name, plan_name=plan["name"], amount=amount, currency=config["currency"], transaction_id=transaction_id, paid=False)
        return {"transaction_id": transaction_id, "payment_url": "", "simulation": True}
    if not _configured():
        raise HTTPException(503, "Le paiement n'est pas encore configuré.")
    record = {"transaction_id": transaction_id, "user_id": user.id, "plan_id": plan_id, "billing_cycle": billing_cycle, "amount": amount, "currency": config["currency"], "customer_email": customer_email, "customer_name": user.name, "customer_phone": customer_phone, "payment_method": payment_method, "status": "PENDING", "simulation": False, "created_at": datetime.now(timezone.utc).isoformat()}
    _write_payments({"payments": {transaction_id: record}})
    customer = {"name": user.name, "email": customer_email}
    if customer_phone:
        customer["phone"] = customer_phone
        customer["country"] = "CD"
    elif user.phone and "@" not in user.phone:
        customer["phone"] = user.phone
    # Force the exact RDC Mobile Money operator selected in ORVIX.  The
    # provider's generic checkout may otherwise pick a different gateway
    # (for example Wave) based on its own routing preferences.
    provider_method = "pawapay" if payment_method in {"airtel_money", "orange_money"} else payment_method
    mmo_provider = {"airtel_money": "AIRTEL_COD", "orange_money": "ORANGE_COD"}.get(payment_method)
    payload = {
        "amount": amount,
        "currency": config["currency"],
        "payment_method": provider_method,
        "description": f"ORVIX {plan['name']} - {billing_cycle}",
        "customer": customer,
        "success_url": f"{settings.public_app_url}/?payment=success&transaction_id={transaction_id}",
        "error_url": f"{settings.public_app_url}/?payment=cancelled&transaction_id={transaction_id}",
        "metadata": {"transaction_id": transaction_id, "user_id": user.id, "plan_id": plan_id, "billing_cycle": billing_cycle},
    }
    if mmo_provider:
        payload["mmo_provider"] = mmo_provider
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(f"{settings.geniuspay_base_url}/v1/merchant/payments", json=payload, headers={"X-API-Key": settings.geniuspay_api_key, "X-API-Secret": settings.geniuspay_api_secret, "Accept": "application/json"})
            try:
                result = response.json()
            except ValueError:
                logger.error("Genius Pay returned non-JSON response (status %s)", response.status_code)
                raise HTTPException(502, "Le service de paiement est temporairement indisponible.")
        if response.status_code in (401, 403):
            logger.error("Genius Pay rejected merchant credentials (status %s)", response.status_code)
            raise HTTPException(503, "Le paiement est temporairement indisponible. Réessayez plus tard.")
        if response.status_code == 422:
            logger.error("Genius Pay rejected checkout fields: %s", list((result.get("errors") or {}).keys()) if isinstance(result.get("errors"), dict) else "validation")
            raise HTTPException(502, "Les informations du paiement doivent être vérifiées. Contactez le support.")
        if response.status_code >= 400:
            logger.error("Genius Pay checkout failed (status %s)", response.status_code)
            raise HTTPException(502, "Le service de paiement est temporairement indisponible.")
        data = result.get("data") or {}
        # A direct method can be accompanied by both URLs.  The generic
        # checkout_url is allowed to auto-select another gateway, whereas
        # payment_url is the URL for the method explicitly requested by the
        # customer.  Always prefer the latter.
        payment_url = data.get("payment_url") or data.get("redirect_url") or data.get("checkout_url")
        if not result.get("success") or not payment_url:
            raise HTTPException(502, result.get("message") or "Le paiement n'a pas pu être créé.")
        record["provider_reference"] = data.get("reference")
        record["payment_url"] = payment_url
        _write_payments({"payments": {transaction_id: record}})
        return {"transaction_id": transaction_id, "payment_url": payment_url, "simulation": False}
    except HTTPException:
        if record.get("status") == "PENDING":
            _fail_checkout(record)
        raise
    except httpx.HTTPError as error:
        logger.error("Genius Pay connection failed: %s", type(error).__name__)
        _fail_checkout(record)
        raise HTTPException(502, "Connexion au service de paiement impossible.") from error


async def _send_confirmation(record: dict) -> None:
    if record.get("status") != "ACCEPTED" or record.get("confirmation_sent_at"):
        return
    plan = next((p for p in plans_config()["plans"] if p["id"] == record["plan_id"]), {})
    sent = await send_payment_email(
        email=record.get("customer_email", ""), name=record.get("customer_name", ""),
        plan_name=plan.get("name", record["plan_id"]), amount=record["amount"],
        currency=record["currency"], transaction_id=record["transaction_id"], paid=True,
        billing_cycle=record["billing_cycle"],
    )
    if sent:
        record["confirmation_sent_at"] = datetime.now(timezone.utc).isoformat()
        _write_payments({"payments": {record["transaction_id"]: record}})


async def apply_geniuspay_webhook(payload: dict) -> dict:
    data = payload.get("data") or {}
    metadata = data.get("metadata") or {}
    transaction_id = metadata.get("transaction_id")
    if not transaction_id:
        raise HTTPException(400, "Transaction absente du webhook.")
    payments = _read_payments(); record = payments["payments"].get(transaction_id)
    if not record:
        raise HTTPException(404, "Transaction inconnue.")
    if record["status"] == "ACCEPTED":
        await _send_confirmation(record)
        return record
    if payload.get("event") == "payment.success" and data.get("status") == "completed":
        if not _payment_matches(record, data):
            logger.error("Payment confirmation did not match order %s", transaction_id)
            raise HTTPException(409, "Confirmation de paiement incohérente.")
        accepted = _accept_payment(record)
        await _send_confirmation(accepted)
        return accepted
    if payload.get("event") in {"payment.failed", "payment.cancelled", "payment.expired"}:
        record["status"] = "FAILED"
        record["verified_at"] = datetime.now(timezone.utc).isoformat()
        _write_payments({"payments": {transaction_id: record}})
    return record


async def reconcile_user_payments(user_id: str) -> None:
    settings = get_settings()
    for record in _read_payments()["payments"].values():
        if record.get("user_id") == user_id and record.get("status") == "ACCEPTED" and not record.get("confirmation_sent_at"):
            await _send_confirmation(record)
    pending = [record for record in _read_payments()["payments"].values()
               if record.get("user_id") == user_id and record.get("status") in {"PENDING", "FAILED"} and record.get("provider_reference")]
    for record in sorted(pending, key=lambda item: item.get("created_at", ""), reverse=True)[:3]:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(
                    f"{settings.geniuspay_base_url}/v1/merchant/payments/{record['provider_reference']}",
                    headers={"X-API-Key": settings.geniuspay_api_key, "X-API-Secret": settings.geniuspay_api_secret, "Accept": "application/json"},
                )
            if response.status_code != 200:
                logger.warning("Payment status lookup returned %s", response.status_code)
                continue
            result = response.json()
            data = result.get("data") or {}
            if result.get("success") and data.get("status") == "completed":
                if _payment_matches(record, data):
                    await _send_confirmation(_accept_payment(record))
                else:
                    logger.error("Completed payment did not match order %s", record["transaction_id"])
        except (httpx.HTTPError, ValueError, KeyError) as error:
            logger.warning("Payment status lookup failed: %s", type(error).__name__)
