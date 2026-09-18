import json
import re
from datetime import datetime, timezone
from uuid import uuid4
from .config import get_settings
from .json_store import atomic_write_json

def _path(): return get_settings().data_dir / "core_memory.json"
def _read():
    p=_path(); return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
def _extract(message: str) -> list[tuple[str, str]]:
    patterns = [
        ("preferred_name", r"(?:appelle[- ]moi|mon prénom est|je m'appelle)\s+([^.!?\n]{2,80})"),
        ("likes", r"(?:j'aime|j’adore|je préfère)\s+([^.!?\n]{2,160})"),
        ("dislikes", r"(?:je n'aime pas|je n’aime pas|je déteste)\s+([^.!?\n]{2,160})"),
        ("goal", r"(?:mon objectif est|je veux|j'aimerais|j’aimerais)\s+([^.!?\n]{2,180})"),
        ("response_style", r"(?:réponds|répondre|parle[- ]moi)\s+(?:de manière|d'une manière|en mode)?\s*([^.!?\n]{2,160})"),
    ]
    result = []
    for key, pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = " ".join(match.group(1).strip().split())
            if value:
                result.append((key, value[:240]))
    return result


def remember(user_id: str, message: str) -> None:
    memories = _extract(message)
    if not memories:
        return
    settings = get_settings()
    if settings.database_url:
        import psycopg
        now = datetime.now(timezone.utc)
        with psycopg.connect(settings.database_url) as connection:
            for key, content in memories:
                connection.execute(
                    "INSERT INTO memories(id,user_id,memory_type,memory_key,content,created_at,updated_at) VALUES(%s,%s,'preference',%s,%s,%s,%s) ON CONFLICT (user_id,memory_key) DO UPDATE SET content=EXCLUDED.content,updated_at=EXCLUDED.updated_at",
                    (str(uuid4()), user_id, key, content, now, now),
                )
            connection.commit()
        return
    data = _read()
    profile = data.setdefault(user_id, {})
    for key, content in memories:
        profile[key] = content
    atomic_write_json(_path(), data)
def relevant(user_id: str, message: str = "") -> str:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            rows = connection.execute("SELECT memory_key,content FROM memories WHERE user_id=%s ORDER BY updated_at DESC LIMIT 12", (user_id,)).fetchall()
        data = rows
    else:
        data = list(_read().get(user_id, {}).items())
    if not data:
        return ""
    lines = "\n".join(f"- {key}: {content}" for key, content in data)
    return f"\n\nMÉMOIRE PERSONNELLE DE L'UTILISATEUR (à utiliser avec discrétion) :\n{lines}"
