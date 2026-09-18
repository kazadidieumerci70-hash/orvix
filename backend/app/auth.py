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

def _database_url() -> str:
    return get_settings().database_url

def _db_connect():
    import psycopg
    return psycopg.connect(_database_url())

def _db_ready() -> bool:
    return bool(_database_url())

def init_auth_database() -> None:
    if not _db_ready():
        return
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_initial.sql"
    with _db_connect() as connection:
        connection.execute(migration.read_text(encoding="utf-8"))
        connection.commit()

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
    value = phone.strip().lower()
    if "@" in value:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise HTTPException(422, "Adresse e-mail invalide.")
        return value
    cleaned = re.sub(r"[^\d+]", "", value)
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


def _identity_segment(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _identity_from_segment(value: str) -> str:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii")).decode("utf-8")


def _make_token(user_id: str, phone: str = "") -> str:
    expires_at = int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())
    nonce = secrets.token_urlsafe(12)
    payload = f"{user_id}.{expires_at}.{nonce}.{_identity_segment(phone)}" if phone else f"{user_id}.{expires_at}.{nonce}"
    signature = hmac.new(_token_secret(), payload.encode("utf-8"), sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}.{signature}".encode("utf-8")).decode("utf-8")


def _decode_token(token: str) -> tuple[str, str]:
    if token in _revoked_tokens:
        raise HTTPException(401, "Session révoquée.")
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split(".")
        if len(parts) == 5:
            user_id, expires_at, nonce, phone_segment, signature = parts
            phone = _identity_from_segment(phone_segment)
        else:
            user_id, expires_at, nonce, signature = raw.rsplit(".", 3)
            phone = ""
    except Exception as exc:
        raise HTTPException(401, "Session invalide.") from exc

    payload = f"{user_id}.{expires_at}.{nonce}.{_identity_segment(phone)}" if phone else f"{user_id}.{expires_at}.{nonce}"
    expected = hmac.new(_token_secret(), payload.encode("utf-8"), sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Session invalide.")
    if int(expires_at) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(401, "Session expiree.")
    return user_id, phone


def _profile(user: dict) -> UserProfile:
    completed = bool(user.get("onboarding_completed", False)) or _profile_is_complete(user)
    return UserProfile(
        id=user["id"],
        phone=user["phone"],
        name=user.get("name", "Etudiant"),
        onboarding_completed=completed,
        level=user.get("level", ""),
        subjects=user.get("subjects", []),
        goal=user.get("goal", ""),
        learning_style=user.get("learning_style", ""),
        difficulties=user.get("difficulties", ""),
        welcome_seen=bool(user.get("welcome_seen", False)),
    )

def _profile_is_complete(user: dict) -> bool:
    return bool(
        str(user.get("name", "")).strip()
        and str(user.get("name", "")).strip().lower() not in {"etudiant", "étudiant"}
        and str(user.get("level", "")).strip()
        and user.get("subjects")
        and str(user.get("goal", "")).strip()
        and str(user.get("learning_style", "")).strip()
    )

def _db_user(row) -> dict:
    user = {"id": row[0], "phone": row[1], "name": row[2], "password_hash": row[3],
            "onboarding_completed": row[4], "level": row[5], "subjects": row[6] or [],
            "goal": row[7] or "", "learning_style": row[8] or "", "difficulties": row[9] or "",
            "welcome_seen": row[10]}
    user["onboarding_completed"] = bool(user["onboarding_completed"]) or _profile_is_complete(user)
    return user

def _user_select(connection, phone: str):
    return connection.execute("SELECT id,phone,name,password_hash,onboarding_completed,level,subjects,goal,learning_style,difficulties,welcome_seen FROM users WHERE phone=%s", (phone,)).fetchone()

def _user_by_id(connection, user_id: str):
    return connection.execute("SELECT id,phone,name,password_hash,onboarding_completed,level,subjects,goal,learning_style,difficulties,welcome_seen FROM users WHERE id=%s", (user_id,)).fetchone()


def register_user(phone: str, password: str) -> tuple[str, UserProfile]:
    normalized = _normalize_phone(phone)
    if _db_ready():
        with _db_connect() as connection:
            if _user_select(connection, normalized):
                raise HTTPException(409, "Ce numero a deja un compte.")
            user_id = sha256(f"user:{normalized}".encode()).hexdigest()[:16]
            connection.execute("INSERT INTO users(id,phone,name,password_hash,created_at,subjects) VALUES(%s,%s,%s,%s,now(),'[]'::jsonb)", (user_id, normalized, "Etudiant", _hash_password(password)))
            connection.commit()
            user = _db_user(_user_by_id(connection, user_id))
        return _make_token(user_id, normalized), _profile(user)
    data = _read_users()
    if any(user["phone"] == normalized for user in data["users"]):
        raise HTTPException(409, "Ce numero a deja un compte.")
    user = {
        "id": sha256(f"user:{normalized}".encode("utf-8")).hexdigest()[:16],
        "phone": normalized,
        "name": "Etudiant",
        "password_hash": _hash_password(password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data["users"].append(user)
    _write_users(data)
    return _make_token(user["id"], normalized), _profile(user)


def login_user(phone: str, password: str) -> tuple[str, UserProfile]:
    normalized = _normalize_phone(phone)
    if _db_ready():
        with _db_connect() as connection:
            row = _user_select(connection, normalized)
        if row and _verify_password(password, row[3]):
            user = _db_user(row)
            return _make_token(user["id"], normalized), _profile(user)
        raise HTTPException(401, "Numero ou mot de passe incorrect.")
    data = _read_users()
    for user in data["users"]:
        if user["phone"] == normalized and _verify_password(password, user["password_hash"]):
            return _make_token(user["id"], normalized), _profile(user)
    raise HTTPException(401, "Numero ou mot de passe incorrect.")

def google_login_user(credential: str) -> tuple[str, UserProfile, bool]:
    from google.oauth2 import id_token
    from google.auth.transport import requests
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(503, "Google OAuth n'est pas configuré.")
    try:
        info = id_token.verify_oauth2_token(credential, requests.Request(), client_id)
    except Exception as exc:
        raise HTTPException(401, "La connexion Google est invalide.") from exc
    email = str(info.get("email", "")).strip().lower()
    if not email or not info.get("email_verified"):
        raise HTTPException(401, "L'adresse Google n'est pas vérifiée.")
    if not _db_ready():
        data = _read_users()
        row = next((user for user in data["users"] if user.get("phone") == email), None)
        if not row:
            row = {"id": sha256(f"google:{email}".encode()).hexdigest()[:16], "phone": email, "name": str(info.get("name") or "Etudiant")[:160], "password_hash": _hash_password(secrets.token_urlsafe(32)), "created_at": datetime.now(timezone.utc).isoformat()}
            data["users"].append(row); _write_users(data)
        elif not row.get("onboarding_completed"):
            row["onboarding_completed"] = True
            row["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_users(data)
        return _make_token(row["id"], email), _profile(row), existing_account
    with _db_connect() as connection:
        row = _user_select(connection, email)
        if not row:
            user_id = sha256(f"google:{email}".encode()).hexdigest()[:16]
            connection.execute("INSERT INTO users(id,phone,name,password_hash,created_at,subjects) VALUES(%s,%s,%s,%s,now(),'[]'::jsonb)", (user_id, email, str(info.get("name") or "Etudiant")[:160], _hash_password(secrets.token_urlsafe(32))))
            row = _user_by_id(connection, user_id)
        elif not bool(row[4]):
            connection.execute("UPDATE users SET onboarding_completed=TRUE, updated_at=now() WHERE id=%s", (row[0],))
            row = _user_by_id(connection, row[0])
        connection.commit()
    user = _db_user(row)
    return _make_token(user["id"], email), _profile(user), existing_account


def current_user(authorization: str | None = Header(default=None)) -> UserProfile:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Connectez-vous pour continuer.")
    user_id, identity = _decode_token(authorization.removeprefix("Bearer ").strip())
    if _db_ready():
        with _db_connect() as connection:
            row = _user_by_id(connection, user_id)
            if not row and identity:
                row = _user_select(connection, _normalize_phone(identity))
        if row:
            return _profile(_db_user(row))
        raise HTTPException(401, "Utilisateur introuvable.")
    for user in _read_users()["users"]:
        if user["id"] == user_id:
            return _profile(user)
    raise HTTPException(401, "Utilisateur introuvable.")


def mark_welcome_seen(user_id: str) -> UserProfile:
    if _db_ready():
        with _db_connect() as connection:
            connection.execute("UPDATE users SET welcome_seen=TRUE, updated_at=now() WHERE id=%s", (user_id,))
            row = _user_by_id(connection, user_id)
            connection.commit()
        if row:
            return _profile(_db_user(row))
        raise HTTPException(401, "Utilisateur introuvable.")
    data = _read_users()
    for user in data["users"]:
        if user["id"] == user_id:
            user["welcome_seen"] = True
            user["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_users(data)
            return _profile(user)
    raise HTTPException(401, "Utilisateur introuvable.")


def complete_onboarding(user_id: str, payload: OnboardingRequest) -> UserProfile:
    subjects = [subject.strip() for subject in payload.subjects if subject.strip()][:8]
    if _db_ready():
        with _db_connect() as connection:
            connection.execute("UPDATE users SET name=%s, level=%s, subjects=%s::jsonb, goal=%s, learning_style=%s, difficulties=%s, onboarding_completed=TRUE, updated_at=now() WHERE id=%s", (payload.name.strip(), payload.level.strip(), json.dumps(subjects), payload.goal.strip(), payload.learning_style.strip(), payload.difficulties.strip(), user_id))
            row = _user_by_id(connection, user_id)
            connection.commit()
        if row:
            return _profile(_db_user(row))
        raise HTTPException(401, "Utilisateur introuvable.")
    data = _read_users()
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
