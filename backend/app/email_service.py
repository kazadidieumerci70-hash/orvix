import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


def _email_address(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1]


async def send_email(*, to: str, subject: str, html: str, text: str) -> bool:
    """Send a transactional email through Resend without breaking the main request."""
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("Resend is not configured; skipped email to %s", to)
        return False
    if not _email_address(to):
        logger.warning("Skipped email with invalid recipient")
        return False
    payload = {
        "from": settings.resend_from_email,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    if settings.resend_reply_to:
        payload["reply_to"] = settings.resend_reply_to
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json"},
            )
        if response.status_code >= 400:
            logger.error("Resend rejected email: status=%s body=%s", response.status_code, response.text[:500])
            return False
        return True
    except httpx.HTTPError as error:
        logger.error("Resend request failed: %s", type(error).__name__)
        return False


async def send_welcome_email(*, email: str, name: str) -> bool:
    safe_name = name or "Etudiant"
    return await send_email(
        to=email,
        subject="Bienvenue sur Orvix",
        text=f"Bonjour {safe_name}, bienvenue sur Orvix. Ton espace d'apprentissage est prêt.",
        html=(
            "<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#17202a'>"
            f"<h1>Bienvenue sur Orvix, {safe_name} !</h1>"
            "<p>Ton espace d'apprentissage est prêt. Tu peux maintenant organiser tes documents, réviser et poser tes questions.</p>"
            "<p>À bientôt,<br>L'équipe Orvix</p></div>"
        ),
    )


async def send_payment_email(*, email: str, name: str, plan_name: str, amount: float, currency: str, transaction_id: str, paid: bool) -> bool:
    status = "confirmé" if paid else "créé"
    subject = f"Orvix — paiement {status} ({transaction_id})"
    text = f"Bonjour {name or 'Etudiant'}, ton paiement Orvix est {status}. Forfait : {plan_name}. Montant : {amount} {currency}. Référence : {transaction_id}."
    html = (
        "<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#17202a'>"
        f"<h1>Paiement {status}</h1><p>Bonjour {name or 'Etudiant'},</p>"
        f"<p>Forfait : <strong>{plan_name}</strong><br>Montant : <strong>{amount} {currency}</strong><br>Référence : <strong>{transaction_id}</strong></p>"
        "<p>Merci pour ta confiance,<br>L'équipe Orvix</p></div>"
    )
    return await send_email(to=email, subject=subject, html=html, text=text)
