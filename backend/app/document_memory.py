"""Private, persistent page chunks for uploaded learning materials."""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re

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


def _chunks_from_content(name: str, content: bytes) -> list[dict]:
    if Path(name).suffix.lower() == ".pdf":
        pages = [(number, (page.extract_text() or "").strip()) for number, page in enumerate(PdfReader(BytesIO(content)).pages, 1)]
    else:
        pages = [(None, content.decode("utf-8", errors="ignore").strip())]
    chunks: list[dict] = []
    size, overlap = 1800, 180
    chapter = "Introduction"
    for page, text in pages:
        # Keep the latest meaningful heading so later synthesis can preserve
        # the structure of a book instead of mixing unrelated sections.
        for line in text.splitlines()[:18]:
            heading = " ".join(line.split())
            if re.match(r"^(?:chapitre|partie|[IVXLC]+[.-])\s+.{3,120}$", heading, re.IGNORECASE):
                chapter = heading[:160]
                break
        for offset in range(0, len(text), size - overlap):
            excerpt = text[offset:offset + size].strip()
            if excerpt:
                chunks.append({"page": page, "offset": offset, "chapter": chapter, "text": excerpt})
    return chunks


def _preparation(chunks: list[dict]) -> dict:
    """Keep a small, per-document reading card alongside the private index."""
    headings: list[str] = []
    terms: dict[str, int] = {}
    pages = {chunk.get("page") for chunk in chunks if chunk.get("page")}
    ignored = {"avec", "dans", "pour", "mais", "sont", "cette", "document", "chapitre", "cours", "vous", "plus"}
    for chunk in chunks:
        heading = (chunk.get("chapter") or "").strip()
        if heading and heading != "Introduction" and heading not in headings:
            headings.append(heading)
        for term in re.findall(r"[A-Za-zÀ-ÿ]{4,}", chunk.get("text", "").lower()):
            if term not in ignored:
                terms[term] = terms.get(term, 0) + 1
    return {
        "status": "ready",
        "chunks": len(chunks),
        "pages": len(pages) or 1,
        "headings": headings[:6],
        "keywords": [term for term, _ in sorted(terms.items(), key=lambda item: (-item[1], item[0]))[:8]],
    }


def content_has_readable_text(name: str, content: bytes) -> bool:
    """Reject files that can be stored but cannot provide any learning context."""
    return any(len(re.sub(r"\s+", "", chunk.get("text", ""))) >= 3 for chunk in _chunks_from_content(name, content))


def _chunks(path: Path) -> list[dict]:
    return _chunks_from_content(path.name, path.read_bytes())


def build_document_memory(user_id: str, path: Path) -> dict:
    """Build once at import; the content remains scoped to its owner."""
    return build_document_memory_from_content(user_id, _id(path.name), path.name, path.read_bytes())


def build_document_memory_from_content(user_id: str, document_id: str, name: str, content: bytes) -> dict:
    """Index uploaded bytes so document memory survives service restarts."""
    chunks = _chunks_from_content(name, content)
    record = {
        "user_id": user_id, "document_id": document_id, "document_name": name,
        "chunks": chunks, "preparation": _preparation(chunks),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
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
        if row and row[0].get("chunks"):
            return row[0]
    else:
        record = _read().get("documents", {}).get(f"{user_id}:{document_id}")
        if record and record.get("chunks"):
            return record
    return build_document_memory(user_id, path)


def get_document_memory_from_content(user_id: str, document_id: str, name: str, content: bytes) -> dict:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS document_memories (user_id TEXT NOT NULL, document_id TEXT NOT NULL, record JSONB NOT NULL, PRIMARY KEY(user_id, document_id))")
            row = connection.execute("SELECT record FROM document_memories WHERE user_id=%s AND document_id=%s", (user_id, document_id)).fetchone()
        # An interrupted or older import may have left an empty index.  Do not
        # treat that as a readable document: rebuild it from the durable bytes.
        if row and row[0].get("chunks"):
            return row[0]
    else:
        record = _read().get("documents", {}).get(f"{user_id}:{document_id}")
        if record and record.get("chunks"):
            return record
    return build_document_memory_from_content(user_id, document_id, name, content)


def document_preparation(user_id: str, document_id: str) -> dict:
    """Return only the prepared card; never expose another document's record."""
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS document_memories (user_id TEXT NOT NULL, document_id TEXT NOT NULL, record JSONB NOT NULL, PRIMARY KEY(user_id, document_id))")
            row = connection.execute("SELECT record FROM document_memories WHERE user_id=%s AND document_id=%s", (user_id, document_id)).fetchone()
        return (row[0].get("preparation") or {"status": "preparing"}) if row else {"status": "preparing"}
    record = _read().get("documents", {}).get(f"{user_id}:{document_id}", {})
    return record.get("preparation") or {"status": "preparing"}


def mark_document_preparation_error(user_id: str, document_id: str, name: str) -> None:
    """Keep the uploaded file available while making a failed analysis retryable."""
    record = {
        "user_id": user_id, "document_id": document_id, "document_name": name,
        "chunks": [], "preparation": {"status": "error"},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS document_memories (user_id TEXT NOT NULL, document_id TEXT NOT NULL, record JSONB NOT NULL, PRIMARY KEY(user_id, document_id))")
            connection.execute("INSERT INTO document_memories(user_id,document_id,record) VALUES(%s,%s,%s::jsonb) ON CONFLICT(user_id,document_id) DO UPDATE SET record=EXCLUDED.record", (user_id, document_id, json.dumps(record)))
            connection.commit()
        return
    data = _read(); data.setdefault("documents", {})[f"{user_id}:{document_id}"] = record
    atomic_write_json(_path(), data, ensure_ascii=False)


def chapter_groups(record: dict, max_chars: int = 12_000) -> list[tuple[str, str]]:
    """Representative text per chapter for hierarchical AI summaries."""
    grouped: dict[str, list[str]] = {}
    for chunk in record.get("chunks", []):
        grouped.setdefault(chunk.get("chapter") or "Introduction", []).append(chunk.get("text", ""))
    result = []
    for chapter, chunks in grouped.items():
        joined = "\n".join(chunks)
        if len(joined) > max_chars:
            step = max(1, len(chunks) // 6)
            joined = "\n\n".join(chunks[::step])[:max_chars]
        result.append((chapter, joined))
    return result


def forget_document_memory(user_id: str, document_id: str) -> None:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        with psycopg.connect(settings.database_url) as connection:
            connection.execute("DELETE FROM document_memories WHERE user_id=%s AND document_id=%s", (user_id, document_id)); connection.commit()
        return
    data = _read(); data.get("documents", {}).pop(f"{user_id}:{document_id}", None)
    atomic_write_json(_path(), data, ensure_ascii=False)
