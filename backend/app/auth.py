from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
import base64
import hmac
import json
import os
import re
import secrets

from fastapi import Header, HTTPException

from .config import get_settings
from .json_store import atomic_write_json
from .schemas import OnboardingRequest, UserProfile

TOKEN_TTL_HOURS = 24 * 14
_revoked_tokens: set[str] = set()

def revoke_token(token: str) -> None:
    if token:
        _revoked_tokens.add(token)


def _read_users() -> dict:
    path = get_settings().users_file
    if not path.exists():
        return {"users": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_users(data: dict) -> None:
    atomic_write_json(get_settings().users_file, data, ensure_ascii=True)


def _normalize_phone(phone: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if len(cleaned) < 6:
        raise HTTPException(422, "Numero de telephone invalide.")
    return cleaned


def _hash_password(password: str, salt: str | None = None) -> str:
    raw_salt = base64.b64decode(salt) if salt else os.urandom(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, 240_000)
    return f"{base64.b64encode(raw_salt).decode()}:${base64.b64encode(digest).decode()}"


def _verify_password(password: str, stored: str) -> bool:
    salt, expected = stored.split(":", 1)
    actual = _hash_password(password, salt).split(":", 1)[1]
    return hmac.compare_digest(actual, expected)


def _token_secret() -> bytes:
    key = get_settings().orvix_auth_secret
    if not key:
        raise HTTPException(503, "La sécurité de session n'est pas configurée.")
    return sha256(key.encode("utf-8")).digest()


def _make_token(user_id: str) -> str:
    expires_at = int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())
    nonce = secrets.token_urlsafe(12)
    payload = f"{user_id}.{expires_at}.{nonce}"
    signature = hmac.new(_token_secret(), payload.encode("utf-8"), sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{signature}".encode("utf-8")).decode("utf-8")


def _decode_token(token: str) -> str:
    if token in _revoked_tokens:
        raise HTTPException(401, "Session révoquée.")
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        user_id, expires_at, nonce, signature = raw.rsplit(".", 3)
    except Exception as exc:
        raise HTTPException(401, "Session invalide.") from exc

    payload = f"{user_id}.{expires_at}.{nonce}"
    expected = hmac.new(_token_secret(), payload.encode("utf-8"), sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Session invalide.")
    if int(expires_at) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(401, "Session expiree.")
    return user_id


def _profile(user: dict) -> UserProfile:
    return UserProfile(
        id=user["id"],
        phone=user["phone"],
        name=user.get("name", "Etudiant"),
        onboarding_completed=bool(user.get("onboarding_completed", False)),
        level=user.get("level", ""),
        subjects=user.get("subjects", []),
        goal=user.get("goal", ""),
        learning_style=user.get("learning_style", ""),
        difficulties=user.get("difficulties", ""),
        welcome_seen=bool(user.get("welcome_seen", False)),
    )


def register_user(phone: str, password: str) -> tuple[str, UserProfile]:
    normalized = _normalize_phone(phone)
    data = _read_users()
    if any(user["phone"] == normalized for user in data["users"]):
        raise HTTPException(409, "Ce numero a deja un compte.")
    user = {
        "id": sha256(f"{normalized}:{secrets.token_urlsafe(8)}".encode("utf-8")).hexdigest()[:16],
        "phone": normalized,
        "name": "Etudiant",
        "password_hash": _hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data["users"].append(user)
    _write_users(data)
    return _make_token(user["id"]), _profile(user)


def login_user(phone: str, password: str) -> tuple[str, UserProfile]:
    normalized = _normalize_phone(phone)
    data = _read_users()
    for user in data["users"]:
        if user["phone"] == normalized and _verify_password(password, user["password_hash"]):
            return _make_token(user["id"]), _profile(user)
    raise HTTPException(401, "Numero ou mot de passe incorrect.")


def current_user(authorization: str | None = Header(default=None)) -> UserProfile:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Connectez-vous pour continuer.")
    user_id = _decode_token(authorization.removeprefix("Bearer ").strip())
    for user in _read_users()["users"]:
        if user["id"] == user_id:
            return _profile(user)
    raise HTTPException(401, "Utilisateur introuvable.")


def mark_welcome_seen(user_id: str) -> UserProfile:
    data = _read_users()
    for user in data["users"]:
        if user["id"] == user_id:
            user["welcome_seen"] = True
            user["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_users(data)
            return _profile(user)
    raise HTTPException(401, "Utilisateur introuvable.")


def complete_onboarding(user_id: str, payload: OnboardingRequest) -> UserProfile:
    data = _read_users()
    subjects = [subject.strip() for subject in payload.subjects if subject.strip()][:8]
    for user in data["users"]:
        if user["id"] == user_id:
            user.update(
                {
                    "name": payload.name.strip(),
                    "level": payload.level.strip(),
                    "subjects": subjects,
                    "goal": payload.goal.strip(),
                    "learning_style": payload.learning_style.strip(),
                    "difficulties": payload.difficulties.strip(),
                    "onboarding_completed": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            _write_users(data)
            return _profile(user)
    raise HTTPException(401, "Utilisateur introuvable.")
