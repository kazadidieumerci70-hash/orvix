from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import secrets
from typing import Any

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from .config import get_settings
from .document_memory import build_document_memory, build_document_memory_from_content, chapter_groups, forget_document_memory, get_document_memory, get_document_memory_from_content
from .subscriptions import document_page_limit, document_upload_limit_bytes
from .json_store import atomic_write_json
from .schemas import DocumentInfo

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_PDF_PAGES = 1000


@lru_cache(maxsize=1)
def _r2_client() -> Any:
    """Create the private S3-compatible Cloudflare R2 client lazily."""
    settings = get_settings()
    if not settings.r2_enabled:
        raise RuntimeError("Cloudflare R2 n'est pas configuré.")
    import boto3
    return boto3.client(
        service_name="s3",
        endpoint_url=settings.r2_s3_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _r2_key(user_id: str, document_id: str, suffix: str) -> str:
    # Do not expose account identifiers or original filenames in object keys.
    owner = sha256(user_id.encode()).hexdigest()[:32]
    return f"documents/{owner}/{document_id}{suffix.lower()}"


def _r2_put(key: str, content: bytes, filename: str) -> None:
    import mimetypes
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        _r2_client().put_object(
            Bucket=get_settings().r2_bucket_name,
            Key=key,
            Body=content,
            ContentType=mimetypes.guess_type(filename)[0] or "application/octet-stream",
        )
    except (BotoCoreError, ClientError) as error:
        raise HTTPException(503, "Le stockage des documents est temporairement indisponible.") from error


def _r2_get(key: str) -> bytes:
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        response = _r2_client().get_object(Bucket=get_settings().r2_bucket_name, Key=key)
        return response["Body"].read()
    except (BotoCoreError, ClientError) as error:
        raise HTTPException(404, "Document introuvable dans le stockage sécurisé.") from error


def _r2_delete(key: str) -> None:
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        _r2_client().delete_object(Bucket=get_settings().r2_bucket_name, Key=key)
    except (BotoCoreError, ClientError) as error:
        raise HTTPException(503, "La suppression du document est temporairement indisponible.") from error


def _owners() -> dict[str, str]:
    path = get_settings().document_owners_file
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("owners", {})
    except Exception:
        return {}


def _write_owners(owners: dict[str, str]) -> None:
    atomic_write_json(get_settings().document_owners_file, {"owners": owners}, ensure_ascii=True)


def _deleted_names() -> set[str]:
    path = get_settings().deleted_documents_file
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("names", []))
    except Exception:
        return set()


def _mark_deleted(name: str) -> None:
    path = get_settings().deleted_documents_file
    names = _deleted_names()
    names.add(name)
    atomic_write_json(path, {"names": sorted(names)}, ensure_ascii=True)


def _safe_name(name: str) -> str:
    raw = Path(name).name
    stem = re.sub(r"[^a-zA-Z0-9._ -]", "_", raw).strip(". ")
    return stem[:150] or "document.txt"


def _ensure_database_documents() -> None:
    """Keep files with the user data, not on Railway's ephemeral disk."""
    import psycopg
    with psycopg.connect(get_settings().database_url) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS uploaded_documents ("
            "user_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, content BYTEA, object_key TEXT, "
            "size INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
            "PRIMARY KEY(user_id, id), UNIQUE(user_id, name))"
        )
        connection.execute("ALTER TABLE uploaded_documents ADD COLUMN IF NOT EXISTS object_key TEXT")
        connection.execute("ALTER TABLE uploaded_documents ALTER COLUMN content DROP NOT NULL")
        connection.commit()


def _database_document(user_id: str, document_id: str) -> tuple[str, bytes]:
    import psycopg
    _ensure_database_documents()
    with psycopg.connect(get_settings().database_url) as connection:
        row = connection.execute(
            "SELECT name, content, object_key FROM uploaded_documents WHERE user_id=%s AND id=%s",
            (user_id, document_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Document introuvable.")
    name, content, object_key = row
    if object_key:
        return name, _r2_get(object_key)
    if content is None:
        raise HTTPException(404, "Document introuvable.")
    raw_content = bytes(content)
    # Existing PostgreSQL documents are migrated only when read, avoiding a
    # disruptive all-at-once transfer.
    if get_settings().r2_enabled:
        key = _r2_key(user_id, document_id, Path(name).suffix)
        _r2_put(key, raw_content, name)
        with psycopg.connect(get_settings().database_url) as connection:
            connection.execute("UPDATE uploaded_documents SET object_key=%s, content=NULL WHERE user_id=%s AND id=%s", (key, user_id, document_id))
            connection.commit()
    return name, raw_content


def _migrate_legacy_documents(user_id: str) -> None:
    """Copy any pre-Postgres uploads once, while the old volume is still available."""
    settings = get_settings()
    owners = _owners()
    legacy = [path for path in settings.upload_dir.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS and owners.get(path.name) == user_id]
    if not legacy:
        return
    import psycopg
    with psycopg.connect(settings.database_url) as connection:
        for path in legacy:
            content = path.read_bytes()
            document_id = sha256(path.name.encode()).hexdigest()[:16]
            connection.execute(
                "INSERT INTO uploaded_documents(user_id,id,name,content,size,created_at) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(user_id, name) DO NOTHING",
                (user_id, document_id, path.name, content, len(content), datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)),
            )
        connection.commit()


def list_documents(user_id: str) -> list[DocumentInfo]:
    settings = get_settings()
    if settings.database_url:
        import psycopg
        _ensure_database_documents()
        _migrate_legacy_documents(user_id)
        with psycopg.connect(settings.database_url) as connection:
            rows = connection.execute(
                "SELECT id, name, size, created_at FROM uploaded_documents WHERE user_id=%s ORDER BY created_at, name",
                (user_id,),
            ).fetchall()
        return [DocumentInfo(id=row[0], number=index, name=row[1], size=row[2], created_at=row[3].isoformat()) for index, row in enumerate(rows, 1)]
    result = []
    deleted = _deleted_names()
    owners = _owners()
    files = [
        path
        for path in sorted(settings.upload_dir.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS and path.name not in deleted and owners.get(path.name) == user_id
    ]
    for index, path in enumerate(files, start=1):
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
            stat = path.stat()
            result.append(DocumentInfo(
                id=sha256(path.name.encode()).hexdigest()[:16],
                number=index,
                name=path.name,
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            ))
    return result


def _document_path_from_id(user_id: str, document_id: str) -> Path:
    settings = get_settings()
    for info in list_documents(user_id):
        if info.id == document_id:
            return settings.upload_dir / info.name
    raise HTTPException(404, "Document introuvable.")


async def save_document(user_id: str, upload: UploadFile) -> None:
    settings = get_settings()
    filename = _safe_name(upload.filename or "")
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Formats acceptés : PDF, TXT et Markdown.")
    plan_limit = min(settings.max_upload_bytes, document_upload_limit_bytes(user_id))
    content = await upload.read(plan_limit + 1)
    if not content:
        raise HTTPException(422, "Le fichier est vide.")
    if len(content) > plan_limit:
        raise HTTPException(413, f"Ce fichier dépasse la limite de votre forfait ({plan_limit // (1024 * 1024)} Mo par document).")
    # Basic content validation prevents disguised executables/HTML from entering
    # the document store while keeping the existing PDF/TXT/Markdown contract.
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(415, "Le contenu du PDF est invalide.")
    if suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            page_limit = min(MAX_PDF_PAGES, document_page_limit(user_id))
            if reader.is_encrypted:
                raise HTTPException(422, "Le PDF est chiffré.")
            if len(reader.pages) > page_limit:
                raise HTTPException(422, f"Ce PDF dépasse la limite de votre forfait ({page_limit} pages par document).")
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(415, "Le PDF est endommagé ou non lisible.") from error
    if suffix in {".txt", ".md"} and b"\x00" in content:
        raise HTTPException(415, "Le fichier texte est invalide.")

    if settings.database_url:
        import psycopg
        _ensure_database_documents()
        with psycopg.connect(settings.database_url) as connection:
            existing_names = {row[0] for row in connection.execute("SELECT name FROM uploaded_documents WHERE user_id=%s", (user_id,)).fetchall()}
            candidate = filename
            stem, extension, index = Path(filename).stem, Path(filename).suffix, 2
            while candidate in existing_names:
                candidate = f"{stem}_{index}{extension}"
                index += 1
            document_id = secrets.token_hex(16)
            object_key = _r2_key(user_id, document_id, Path(candidate).suffix) if settings.r2_enabled else ""
            if settings.r2_enabled:
                _r2_put(object_key, content, candidate)
            try:
                connection.execute(
                    "INSERT INTO uploaded_documents(user_id,id,name,content,object_key,size) VALUES(%s,%s,%s,%s,%s,%s)",
                    (user_id, document_id, candidate, None if settings.r2_enabled else content, object_key or None, len(content)),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                if object_key:
                    try:
                        _r2_delete(object_key)
                    except HTTPException:
                        pass
                raise
        try:
            build_document_memory_from_content(user_id, document_id, candidate, content)
        except Exception:
            # The upload is durable even if indexing must be retried later.
            pass
        return

    target = settings.upload_dir / filename
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        index = 2
        while target.exists():
            target = settings.upload_dir / f"{stem}_{index}{suffix}"
            index += 1

    target.write_bytes(content)
    owners = _owners()
    owners[target.name] = user_id
    _write_owners(owners)
    build_document_memory(user_id, target)


def delete_document(user_id: str, document_id: str) -> None:
    if get_settings().database_url:
        import psycopg
        _ensure_database_documents()
        with psycopg.connect(get_settings().database_url) as connection:
            row = connection.execute("SELECT object_key FROM uploaded_documents WHERE user_id=%s AND id=%s", (user_id, document_id)).fetchone()
            if not row:
                raise HTTPException(404, "Document introuvable.")
            if row[0]:
                _r2_delete(row[0])
            deleted = connection.execute("DELETE FROM uploaded_documents WHERE user_id=%s AND id=%s", (user_id, document_id)).rowcount
            connection.commit()
        if not deleted:
            raise HTTPException(404, "Document introuvable.")
        forget_document_memory(user_id, document_id)
        return
    path = _document_path_from_id(user_id, document_id)
    forget_document_memory(user_id, document_id)
    owners = _owners()
    owners.pop(path.name, None)
    _write_owners(owners)
    tombstone = path.with_name(f".orvix-deleted-{secrets.token_hex(6)}.tmp")
    try:
        path.replace(tombstone)
    except PermissionError as error:
        _mark_deleted(path.name)
        return
    try:
        tombstone.unlink()
    except PermissionError:
        # The file is already absent from the library. Windows can release the
        # last handle a little later; a future cleanup can remove the tombstone.
        pass


def _terms(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-zA-ZÀ-ÿ0-9]+", value.lower()) if len(word) >= 3}


def _relevant_excerpts(text: str, query: str, limit: int) -> list[str]:
    chunk_size = 3_200
    overlap = 320
    chunks = [text[start:start + chunk_size] for start in range(0, len(text), chunk_size - overlap)]
    if not chunks:
        return []
    query_terms = _terms(query)
    if not query_terms:
        return chunks[:max(1, limit // chunk_size)]
    ranked = sorted(
        enumerate(chunks),
        key=lambda item: (sum(item[1].lower().count(term) for term in query_terms), -item[0]),
        reverse=True,
    )
    selected: list[tuple[int, str]] = []
    used = 0
    for index, chunk in ranked:
        if used + len(chunk) > limit and selected:
            continue
        selected.append((index, chunk))
        used += len(chunk)
        if used >= limit:
            break
    selected.sort(key=lambda item: item[0])
    return [chunk for _, chunk in selected]


def _ranked_passages(text: str, query: str, limit: int) -> list[tuple[int, str]]:
    """Return relevant passages with their zero-based character offsets."""
    chunk_size = 2_200
    overlap = 260
    passages = [(start, text[start:start + chunk_size]) for start in range(0, len(text), chunk_size - overlap)]
    if not passages:
        return []
    query_terms = _terms(query)
    ranked = sorted(
        passages,
        key=lambda item: (sum(item[1].lower().count(term) for term in query_terms), -item[0]),
        reverse=True,
    ) if query_terms else passages
    selected: list[tuple[int, str]] = []
    used = 0
    for offset, passage in ranked:
        if used + len(passage) > limit and selected:
            continue
        selected.append((offset, passage.strip()))
        used += len(passage)
        if used >= limit:
            break
    return selected


@lru_cache(maxsize=32)
def _extract_document_text(path_value: str, modified_ns: int) -> str:
    path = Path(path_value)
    if path.suffix.lower() == ".pdf":
        with path.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8", errors="ignore")


def document_context(user_id: str, document_ids: list[str] | None = None, max_chars: int = 24_000, query: str = "", max_sources: int = 5) -> str:
    context, _ = document_context_with_sources(user_id, document_ids, max_chars=max_chars, query=query, max_sources=max_sources)
    return context


def document_chapters(user_id: str, document_id: str) -> list[tuple[str, str]]:
    info = next((item for item in list_documents(user_id) if item.id == document_id), None)
    if not info:
        raise HTTPException(404, "Document introuvable.")
    if get_settings().database_url:
        name, content = _database_document(user_id, info.id)
        return chapter_groups(get_document_memory_from_content(user_id, info.id, name, content))
    return chapter_groups(get_document_memory(user_id, info.id, get_settings().upload_dir / info.name))


def document_context_with_sources(
    user_id: str,
    document_ids: list[str] | None = None,
    max_chars: int = 24_000,
    query: str = "",
    max_sources: int = 5,
) -> tuple[str, list[dict]]:
    settings = get_settings()
    chunks: list[str] = []
    sources: list[dict] = []
    remaining = max_chars
    selected = set(document_ids or [])
    documents = [info for info in list_documents(user_id) if info.id in selected]
    per_document_limit = max(3_200, max_chars // max(1, len(documents)))
    for info in documents:
        if remaining <= 0:
            break
        try:
            if settings.database_url:
                name, content = _database_document(user_id, info.id)
                memory = get_document_memory_from_content(user_id, info.id, name, content)
            else:
                memory = get_document_memory(user_id, info.id, settings.upload_dir / info.name)
            pages = [(chunk.get("page"), int(chunk.get("offset", 0)), chunk.get("text", "")) for chunk in memory.get("chunks", [])]
        except Exception:
            continue
        candidates: list[tuple[int, int | None, int, str]] = []
        query_terms = _terms(query)
        for page_number, chunk_offset, text in pages:
            for offset, passage in _ranked_passages(text, query, per_document_limit):
                offset += chunk_offset
                score = sum(passage.lower().count(term) for term in query_terms) if query_terms else 1
                candidates.append((score, page_number, offset, passage))
        candidates.sort(key=lambda item: (item[0], -(item[1] or 0), -item[2]), reverse=True)
        # "Résume" is a task, not necessarily a word found in the support.
        # For an overview request with no matching terms, sample the document
        # from beginning to end instead of only sending its cover page.
        has_matching_passage = any(score > 0 for score, _, _, _ in candidates)
        if query_terms and candidates and not has_matching_passage:
            candidates.sort(key=lambda item: ((item[1] or 0), item[2]))
            sample_count = min(max_sources, len(candidates))
            if sample_count > 1:
                positions = {round(index * (len(candidates) - 1) / (sample_count - 1)) for index in range(sample_count)}
                candidates = [candidate for index, candidate in enumerate(candidates) if index in positions]
        used_for_document = 0
        for score, page_number, offset, passage in candidates:
            if query_terms and has_matching_passage and score == 0 and sources:
                continue
            if not passage or remaining <= 0 or used_for_document >= per_document_limit:
                break
            excerpt = passage[: min(len(passage), remaining, per_document_limit - used_for_document)]
            location = f"page {page_number}" if page_number else f"passage {offset // 1940 + 1}"
            source_id = f"{info.id}:{page_number or 0}:{offset}"
            chunks.append(f"--- SOURCE {source_id} | Document {info.number}: {info.name} | {location} ---\n{excerpt}")
            sources.append({
                "id": source_id,
                "document_id": info.id,
                "document_number": info.number,
                "document_name": info.name,
                "page": page_number,
                "location": location,
                "excerpt": excerpt[:900].strip(),
            })
            remaining -= len(excerpt)
            used_for_document += len(excerpt)
            if len(sources) >= max_sources:
                break
        if len(sources) >= max_sources:
            break
    return "\n\n".join(chunks), sources
