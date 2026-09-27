import logging
from html import escape

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)
LOGO_URL = "https://app.orvix.work/orvix-logo-transparent.png"


def _template(*, title: str, intro: str, content: str, note: str = "") -> str:
    note_html = f"<tr><td style='padding:26px 48px 34px;color:#536575;font-size:14px;line-height:1.65;border-top:1px solid #dcebea'>{note}</td></tr>" if note else ""
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        f"<title>{escape(title)}</title></head><body style='margin:0;padding:32px 12px;background:#f4f7f7;font-family:Arial,sans-serif;color:#101722'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0'><tr><td align='center'>"
        "<table role='presentation' width='600' cellspacing='0' cellpadding='0' style='width:100%;max-width:600px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 12px 38px rgba(16,23,34,.09)'>"
        f"<tr><td align='center' style='padding:34px 24px 28px;background:#effbf9'><img src='{LOGO_URL}' width='68' height='68' alt='Orvix' style='display:block;object-fit:contain'><div style='margin-top:10px;font-size:25px;font-weight:700;letter-spacing:8px'>ORVIX</div></td></tr>"
        f"<tr><td align='center' style='padding:44px 48px 20px'><h1 style='margin:0 0 16px;font-size:30px;line-height:1.2;color:#101722'>{title}</h1><p style='margin:0;color:#536575;font-size:17px;line-height:1.6'>{intro}</p></td></tr>"
        f"<tr><td align='center' style='padding:12px 48px 34px'>{content}</td></tr>{note_html}"
        "<tr><td align='center' style='padding:22px;background:#effbf9;color:#637481;font-size:13px'>© 2026 Orvix &nbsp;|&nbsp; orvix.work</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def _email_address(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1]


async def send_email(*, to: str, subject: str, html: str, text: str, idempotency_key: str = "") -> bool:
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
                headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json", **({"Idempotency-Key": idempotency_key} if idempotency_key else {})},
            )
        if response.status_code >= 400:
            logger.error("Resend rejected email: status=%s body=%s", response.status_code, response.text[:500])
            return False
        return True
    except httpx.HTTPError as error:
        logger.error("Resend request failed: %s", type(error).__name__)
        return False


async def send_welcome_email(*, email: str, name: str) -> bool:
    safe_name = escape(name or "Étudiant")
    return await send_email(
        to=email,
        subject="Bienvenue sur Orvix",
        text=f"Bonjour {safe_name}, bienvenue sur Orvix. Ton espace d'apprentissage est prêt.",
        html=_template(title=f"Bienvenue sur Orvix, {safe_name} !", intro="Ton espace d’apprentissage est prêt.", content="<p style='margin:0;color:#263746;font-size:16px;line-height:1.7'>Tu peux maintenant organiser tes documents, réviser, créer des quiz et poser toutes tes questions à Orvix.</p><p style='margin:28px 0 0;color:#101722;font-weight:700'>À bientôt,<br>L’équipe Orvix</p>"),
    )


async def send_verification_email(*, email: str, code: str) -> bool:
    return await send_email(
        to=email,
        subject="Ton code de vérification Orvix",
        text=f"Ton code de vérification Orvix est {code}. Il expire dans 10 minutes.",
        html=_template(
            title="Vérifie ton adresse e-mail",
            intro="Merci de t’être inscrit sur Orvix.<br>Utilise ce code pour terminer ton inscription :",
            content=f"<div style='padding:22px 20px;border:2px solid #41c7b8;border-radius:14px;background:#effbf9;color:#101722;font-size:42px;font-weight:800;letter-spacing:10px'>{escape(code[:3])}&nbsp;{escape(code[3:])}</div><p style='margin:22px 0 0;color:#536575;font-size:15px'>◷&nbsp; Ce code est valable pendant 10 minutes.</p>",
            note="Si tu n’es pas à l’origine de cette inscription, tu peux ignorer cet e-mail. Aucun compte actif ne sera créé sans validation du code.",
        ),
    )


async def send_password_reset_email(*, email: str, reset_url: str) -> bool:
    return await send_email(
        to=email,
        subject="Réinitialise ton mot de passe Orvix",
        text=f"Utilise ce lien pour choisir un nouveau mot de passe : {reset_url}\nCe lien expire dans 60 minutes. Si tu n'as rien demandé, ignore cet e-mail.",
        html=_template(title="Réinitialise ton mot de passe", intro="Tu as demandé à modifier ton mot de passe Orvix.", content=f"<a href='{escape(reset_url)}' style='display:inline-block;box-sizing:border-box;padding:15px 24px;background:#078d84;color:#fff;text-decoration:none;border-radius:12px;font-size:16px;font-weight:700'>Choisir un nouveau mot de passe</a><p style='margin:22px 0 0;color:#536575;font-size:15px'>Ce lien expire dans 60 minutes.</p>", note="Si tu n’as rien demandé, ignore simplement cet e-mail. Ton mot de passe actuel restera inchangé."),
    )


async def send_payment_email(*, email: str, name: str, plan_name: str, amount: float, currency: str, transaction_id: str, paid: bool, billing_cycle: str = "monthly") -> bool:
    status = "confirmé" if paid else "créé"
    subject = f"Orvix — paiement {status} ({transaction_id})"
    text = f"Bonjour {name or 'Etudiant'}, ton paiement Orvix est {status}. Forfait : {plan_name}. Montant : {amount} {currency}. Référence : {transaction_id}."
    duration = "Annuel (365 jours)" if billing_cycle == "annual" else "Mensuel (30 jours)"
    app_url = get_settings().public_app_url
    text += f" Durée : {duration}. Ouvrir mon espace : {app_url}"
    html = _template(
        title="Félicitations, ton abonnement est actif !" if paid else "Abonnement de test créé",
        intro=f"Bonjour {escape(name or 'Étudiant')}, " + ("ton paiement a été confirmé. Merci pour ta confiance !" if paid else "ceci est une simulation, aucun paiement réel n’a été effectué."),
        content=f"<p style='font-size:16px;line-height:1.8'>Forfait : <strong>{escape(plan_name)}</strong><br>Durée : {duration}<br>Montant : <strong>{amount:.2f} {escape(currency)}</strong><br>Référence : {escape(transaction_id)}</p><a href='{escape(app_url, quote=True)}' style='display:inline-block;padding:16px 24px;background:#078d84;color:#fff;text-decoration:none;border-radius:12px;font-weight:700'>Accéder à mon dashboard</a>",
    )
    return await send_email(to=email, subject=subject, html=html, text=text, idempotency_key=f"payment-{'confirmed' if paid else 'simulation'}-{transaction_id}")
