"""Private, persistent page chunks for uploaded learning materials."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from pypdf import PdfReader

from .config import get_settings
from .json_store import atomic_write_json


def _path() -> Path:
    return get_settings().data_dir / "document_memory.json"


def _read() -> dict:
    path = _path()
    if not path.exists():
        return {"documents": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"documents": {}}


def _id(name: str) -> str:
    return sha256(name.encode()).hexdigest()[:16]


def _chunks(path: Path) -> list[dict]:
    if path.suffix.lower() == ".pdf":
        with path.open("rb") as stream:
            pages = [(number, (page.extract_text() or "").strip()) for number, page in enumerate(PdfReader(stream).pages, 1)]
    else:
        pages = [(None, path.read_text(encoding="utf-8", errors="ignore").strip())]
    chunks: list[dict] = []
    size, overlap = 1800, 180
    for page, text in pages:
        for offset in range(0, len(text), size - overlap):
            excerpt = text[offset:offset + size].strip()
            if excerpt:
                chunks.append({"page": page, "offset": offset, "text": excerpt})
    return chunks


def build_document_memory(user_id: str, path: Path) -> dict:
    """Build once at import; the content remains scoped to its owner."""
    record = {"user_id": user_id, "document_id": _id(path.name), "document_name": path.name, "chunks": _chunks(path), "updated_at": datetime.now(timezone.utc).isoformat()}
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS document_memories (user_id TEXT NOT NULL, document_id TEXT NOT NULL, record JSONB NOT NULL, PRIMARY KEY(user_id, document_id))")
            connection.execute("INSERT INTO document_memories(user_id,document_id,record) VALUES(%s,%s,%s::jsonb) ON CONFLICT(user_id,document_id) DO UPDATE SET record=EXCLUDED.record", (user_id, record["document_id"], json.dumps(record)))
            connection.commit()
        return record
    data = _read(); data.setdefault("documents", {})[f"{user_id}:{record['document_id']}"] = record
    atomic_write_json(_path(), data, ensure_ascii=False)
    return record


def get_document_memory(user_id: str, document_id: str, path: Path) -> dict:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS document_memories (user_id TEXT NOT NULL, document_id TEXT NOT NULL, record JSONB NOT NULL, PRIMARY KEY(user_id, document_id))")
            row = connection.execute("SELECT record FROM document_memories WHERE user_id=%s AND document_id=%s", (user_id, document_id)).fetchone()
        if row:
            return row[0]
    else:
        record = _read().get("documents", {}).get(f"{user_id}:{document_id}")
        if record:
            return record
    return build_document_memory(user_id, path)


def forget_document_memory(user_id: str, document_id: str) -> None:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("DELETE FROM document_memories WHERE user_id=%s AND document_id=%s", (user_id, document_id)); connection.commit()
        return
    data = _read(); data.get("documents", {}).pop(f"{user_id}:{document_id}", None)
    atomic_write_json(_path(), data, ensure_ascii=False)
