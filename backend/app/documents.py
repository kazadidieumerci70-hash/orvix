from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
import secrets

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from .config import get_settings
from .json_store import atomic_write_json
from .schemas import DocumentInfo

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


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


def list_documents(user_id: str) -> list[DocumentInfo]:
    settings = get_settings()
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
    content = await upload.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Ce fichier dépasse la taille maximale autorisée.")
    # Basic content validation prevents disguised executables/HTML from entering
    # the document store while keeping the existing PDF/TXT/Markdown contract.
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(415, "Le contenu du PDF est invalide.")
    if suffix in {".txt", ".md"} and b"\x00" in content:
        raise HTTPException(415, "Le fichier texte est invalide.")

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


def delete_document(user_id: str, document_id: str) -> None:
    path = _document_path_from_id(user_id, document_id)
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


def document_context(user_id: str, document_ids: list[str] | None = None, max_chars: int = 24_000, query: str = "") -> str:
    context, _ = document_context_with_sources(user_id, document_ids, max_chars=max_chars, query=query)
    return context


def document_context_with_sources(
    user_id: str,
    document_ids: list[str] | None = None,
    max_chars: int = 24_000,
    query: str = "",
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
        path = settings.upload_dir / info.name
        try:
            if path.suffix.lower() == ".pdf":
                with path.open("rb") as pdf_file:
                    pages = [(page_number, (page.extract_text() or "").strip()) for page_number, page in enumerate(PdfReader(pdf_file).pages, start=1)]
            else:
                pages = [(None, path.read_text(encoding="utf-8", errors="ignore").strip())]
        except Exception:
            continue
        candidates: list[tuple[int, int | None, int, str]] = []
        query_terms = _terms(query)
        for page_number, text in pages:
            for offset, passage in _ranked_passages(text, query, per_document_limit):
                score = sum(passage.lower().count(term) for term in query_terms) if query_terms else 1
                candidates.append((score, page_number, offset, passage))
        candidates.sort(key=lambda item: (item[0], -(item[1] or 0), -item[2]), reverse=True)
        used_for_document = 0
        for score, page_number, offset, passage in candidates:
            if query_terms and score == 0 and sources:
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
            if len(sources) >= 5:
                break
        if len(sources) >= 5:
            break
    return "\n\n".join(chunks), sources
