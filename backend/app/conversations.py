from datetime import datetime, timezone
from hashlib import sha256
import json
import secrets

from fastapi import HTTPException

from .config import get_settings
from .json_store import atomic_write_json
from .schemas import ChatMessage, ConversationDetail, ConversationSummary


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    data = _read_data()
    items = [item for item in data["conversations"] if item["user_id"] == user_id]
    items.sort(key=lambda item: item["updated_at"], reverse=True)
    return [ConversationSummary(id=item["id"], title=item["title"], updated_at=item["updated_at"]) for item in items]


def get_conversation(user_id: str, conversation_id: str) -> ConversationDetail:
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
