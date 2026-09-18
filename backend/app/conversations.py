from datetime import datetime, timezone
from hashlib import sha256
import json
import secrets
from uuid import uuid4

from fastapi import HTTPException

from .config import get_settings
from .json_store import atomic_write_json
from .schemas import ChatMessage, ConversationDetail, ConversationSummary


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_connect():
    import psycopg
    return psycopg.connect(get_settings().database_url)


def _read_data() -> dict:
    path = get_settings().conversations_file
    if not path.exists():
        return {"conversations": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_data(data: dict) -> None:
    atomic_write_json(get_settings().conversations_file, data, ensure_ascii=True)


def _title_from_message(message: str) -> str:
    title = " ".join(message.strip().split())
    return title[:48] or "Nouvelle discussion"


def list_conversations(user_id: str) -> list[ConversationSummary]:
    if get_settings().database_url:
        with _db_connect() as connection:
            rows = connection.execute(
                "SELECT id,title,updated_at FROM conversations WHERE user_id=%s ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
            if not rows:
                legacy_items = [item for item in _read_data()["conversations"] if item.get("user_id") == user_id]
                for item in legacy_items:
                    connection.execute(
                        "INSERT INTO conversations(id,user_id,title,created_at,updated_at,document_ids) VALUES(%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (id) DO NOTHING",
                        (item["id"], user_id, item.get("title") or "Nouvelle discussion", item.get("created_at") or item["updated_at"], item["updated_at"], json.dumps(item.get("document_ids", []))),
                    )
                    for message in item.get("messages", []):
                        connection.execute(
                            "INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
                            (str(uuid4()), item["id"], message["role"], message["content"], item.get("updated_at")),
                        )
                if legacy_items:
                    connection.commit()
                    rows = connection.execute(
                        "SELECT id,title,updated_at FROM conversations WHERE user_id=%s ORDER BY updated_at DESC",
                        (user_id,),
                    ).fetchall()
        return [ConversationSummary(id=row[0], title=row[1], updated_at=row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2])) for row in rows]
    data = _read_data()
    items = [item for item in data["conversations"] if item["user_id"] == user_id]
    items.sort(key=lambda item: item["updated_at"], reverse=True)
    return [ConversationSummary(id=item["id"], title=item["title"], updated_at=item["updated_at"]) for item in items]


def get_conversation(user_id: str, conversation_id: str) -> ConversationDetail:
    if get_settings().database_url:
        with _db_connect() as connection:
            row = connection.execute(
                "SELECT id,title,updated_at,document_ids FROM conversations WHERE id=%s AND user_id=%s",
                (conversation_id, user_id),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Discussion introuvable.")
            messages = connection.execute(
                "SELECT role,content FROM messages WHERE conversation_id=%s ORDER BY created_at ASC",
                (conversation_id,),
            ).fetchall()
        return ConversationDetail(
            id=row[0],
            title=row[1],
            updated_at=row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
            messages=[ChatMessage(role=item[0], content=item[1]) for item in messages],
            document_ids=row[3] or [],
        )
    for item in _read_data()["conversations"]:
        if item["id"] == conversation_id and item["user_id"] == user_id:
            return ConversationDetail(
                id=item["id"],
                title=item["title"],
                updated_at=item["updated_at"],
                messages=[ChatMessage(**message) for message in item.get("messages", [])],
                document_ids=item.get("document_ids", []),
            )
    raise HTTPException(404, "Discussion introuvable.")


def append_exchange(
    user_id: str,
    conversation_id: str,
    user_message: str,
    assistant_answer: str,
    document_ids: list[str],
) -> ConversationDetail:
    if get_settings().database_url:
        now = datetime.now(timezone.utc)
        with _db_connect() as connection:
            target_id = conversation_id
            if conversation_id:
                owner = connection.execute("SELECT id FROM conversations WHERE id=%s AND user_id=%s", (conversation_id, user_id)).fetchone()
                if not owner:
                    raise HTTPException(404, "Discussion introuvable.")
            else:
                target_id = sha256(f"{user_id}:{secrets.token_urlsafe(10)}".encode("utf-8")).hexdigest()[:16]
                connection.execute(
                    "INSERT INTO conversations(id,user_id,title,created_at,updated_at,document_ids) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",
                    (target_id, user_id, _title_from_message(user_message), now, now, json.dumps(document_ids)),
                )
            connection.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at) VALUES(%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s)",
                (str(uuid4()), target_id, "user", user_message, now, str(uuid4()), target_id, "assistant", assistant_answer, now),
            )
            connection.execute(
                "UPDATE conversations SET updated_at=%s, document_ids=%s::jsonb WHERE id=%s AND user_id=%s",
                (now, json.dumps(document_ids), target_id, user_id),
            )
            connection.commit()
        return get_conversation(user_id, target_id)
    data = _read_data()
    now = _now()
    target = None
    if conversation_id:
        for item in data["conversations"]:
            if item["id"] == conversation_id and item["user_id"] == user_id:
                target = item
                break
        if target is None:
            raise HTTPException(404, "Discussion introuvable.")

    if target is None:
        target = {
            "id": sha256(f"{user_id}:{secrets.token_urlsafe(10)}".encode("utf-8")).hexdigest()[:16],
            "user_id": user_id,
            "title": _title_from_message(user_message),
            "messages": [],
            "document_ids": document_ids,
            "created_at": now,
            "updated_at": now,
        }
        data["conversations"].append(target)

    target["messages"].extend(
        [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_answer},
        ]
    )
    target["document_ids"] = document_ids
    target["updated_at"] = now
    _write_data(data)
    return get_conversation(user_id, target["id"])
