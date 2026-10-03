"""Durable learning memory, separate from raw conversation history."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings
from .json_store import atomic_write_json


def _now(): return datetime.now(timezone.utc)
def _key(value: str): return "-".join(re.findall(r"[a-zA-ZÀ-ÿ0-9]+", value.lower()))[:120]
def _path(): return get_settings().data_dir / "learning_memory.json"
def _read():
    try: return json.loads(_path().read_text(encoding="utf-8"))
    except Exception: return {}
def _write(data): atomic_write_json(_path(), data, ensure_ascii=False)


def _schema():
    if not get_settings().database_url: return
    import psycopg
    statements = (
        "CREATE TABLE IF NOT EXISTS learning_profiles (user_id TEXT PRIMARY KEY, preferred_language TEXT, education_level TEXT, general_level TEXT, preferences JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL)",
        "CREATE TABLE IF NOT EXISTS learning_goals (user_id TEXT NOT NULL, goal_key TEXT NOT NULL, content TEXT NOT NULL, horizon TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'normal', status TEXT NOT NULL DEFAULT 'active', confidence REAL NOT NULL DEFAULT 0.8, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(user_id,goal_key))",
        "CREATE TABLE IF NOT EXISTS user_concept_mastery (user_id TEXT NOT NULL, concept_key TEXT NOT NULL, concept TEXT NOT NULL, subject TEXT, mastery_score INTEGER NOT NULL CHECK(mastery_score BETWEEN 0 AND 100), status TEXT NOT NULL, evidence_count INTEGER NOT NULL DEFAULT 0, last_seen_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(user_id,concept_key))",
        "CREATE TABLE IF NOT EXISTS recurring_errors (user_id TEXT NOT NULL, error_key TEXT NOT NULL, concept TEXT NOT NULL, description TEXT NOT NULL, frequency INTEGER NOT NULL DEFAULT 1, first_seen_at TIMESTAMPTZ NOT NULL, last_seen_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(user_id,error_key))",
        "CREATE TABLE IF NOT EXISTS document_progress (user_id TEXT NOT NULL, document_id TEXT NOT NULL, last_topic TEXT, last_section TEXT, updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY(user_id,document_id))",
        "CREATE TABLE IF NOT EXISTS learning_events (id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, event_type TEXT NOT NULL, topic TEXT, document_id TEXT, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL)",
        "CREATE TABLE IF NOT EXISTS learning_memory_notes (user_id TEXT NOT NULL, memory_key TEXT NOT NULL, memory_type TEXT NOT NULL, content TEXT NOT NULL, importance SMALLINT NOT NULL CHECK(importance BETWEEN 0 AND 5), confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1), created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, last_used_at TIMESTAMPTZ, PRIMARY KEY(user_id,memory_key))",
    )
    with psycopg.connect(get_settings().database_url) as conn:
        for sql in statements: conn.execute(sql)
        conn.commit()


def _status(score: int, review=False):
    if review: return "REVIEW_REQUIRED"
    if score <= 20: return "DISCOVERED"
    if score <= 40: return "FRAGILE"
    if score <= 60: return "LEARNING"
    if score <= 80: return "UNDERSTOOD"
    return "MASTERED"


def _topic(value: str):
    value = re.sub(r"\s+", " ", value.strip(" .,:;!?"))
    return re.sub(r"^(?:sur|avec|dans|de|du|des|la|le|les)\s+", "", value, flags=re.I)[:160]


def _signals(message: str):
    prefs, mastery, errors = [], [], []
    for key, pattern in (("examples", r"(?:je préfère|j'aime|j’adore).{0,40}\bexemples?\b"), ("step_by_step", r"(?:pas à pas|étape par étape|etape par etape)"), ("short_explanations", r"(?:réponses?|explications?)\s+(?:courtes?|brèves?)"), ("detailed_explanations", r"(?:réponses?|explications?)\s+(?:détaillées?|complètes?)"), ("analogies", r"\banalogies?\b")):
        if re.search(pattern, message, re.I): prefs.append((key, key.replace("_", " "), .92 if "préfère" in message.lower() else .62))
    match = re.search(r"(?:je (?:ne )?comprends? pas|j.ai du mal|difficile pour moi|je bloque (?:sur|avec))\s+(?:sur|avec)?\s*(.{3,140})", message, re.I)
    if match: mastery.append((_topic(match.group(1)), -6, False))
    match = re.search(r"(?:je comprends? (?:maintenant|bien|très bien)|j.ai compris|c.est clair)\s*(?:le|la|les|sur)?\s*(.{3,140})", message, re.I)
    if match: mastery.append((_topic(match.group(1)), 5, False))
    match = re.search(r"(?:je confonds?|confusion entre)\s+(.{3,140})", message, re.I)
    if match:
        concept = _topic(match.group(1)); mastery.append((concept, -3, True)); errors.append((concept, f"Confusion signalée : {concept}"))
    return prefs, [(topic, delta, review) for topic, delta, review in mastery if topic], errors


def _goals(message: str):
    match = re.search(r"(?:mon objectif (?:est|:)|je (?:veux|souhaite|dois|prépare|prepare))\s+(.{5,180})", message, re.I)
    if not match: return []
    content = _topic(match.group(1))
    if len(content) < 5: return []
    return [(_key(content), content, "temporary" if re.search(r"(?:aujourd'hui|ce soir|cette semaine|chapitre)\b", content, re.I) else "long_term")]


def remember(user_id: str, message: str, document_ids: list[str] | None = None) -> None:
    """Extract only high-value learning signals; never persist the raw message."""
    prefs, mastery, errors, goals = *_signals(message), _goals(message)
    ids = document_ids or []
    if not get_settings().database_url:
        data = _read(); profile = data.setdefault(user_id, {})
        for key, content, _ in prefs: profile[f"preference:{key}"] = content
        for key, content, _ in goals: profile[f"goal:{key}"] = content
        _write(data); return
    if not (prefs or mastery or errors or goals or ids): return
    _schema(); import psycopg; now = _now()
    with psycopg.connect(get_settings().database_url) as conn:
        for key, content, confidence in prefs:
            conn.execute("INSERT INTO learning_memory_notes(user_id,memory_key,memory_type,content,importance,confidence,created_at,updated_at) VALUES(%s,%s,'preference',%s,4,%s,%s,%s) ON CONFLICT(user_id,memory_key) DO UPDATE SET confidence=GREATEST(learning_memory_notes.confidence,EXCLUDED.confidence),updated_at=EXCLUDED.updated_at", (user_id, f"preference:{key}", content, confidence, now, now))
        for key, content, horizon in goals:
            conn.execute("INSERT INTO learning_goals(user_id,goal_key,content,horizon,priority,status,confidence,created_at,updated_at) VALUES(%s,%s,%s,%s,'high','active',.9,%s,%s) ON CONFLICT(user_id,goal_key) DO UPDATE SET status='active',updated_at=EXCLUDED.updated_at", (user_id,key,content,horizon,now,now))
        last_topic = None
        for concept, delta, review in mastery:
            last_topic=concept; key=_key(concept); row=conn.execute("SELECT mastery_score FROM user_concept_mastery WHERE user_id=%s AND concept_key=%s",(user_id,key)).fetchone(); score=max(0,min(100,(row[0] if row else 45)+delta))
            conn.execute("INSERT INTO user_concept_mastery(user_id,concept_key,concept,mastery_score,status,evidence_count,last_seen_at,updated_at) VALUES(%s,%s,%s,%s,%s,1,%s,%s) ON CONFLICT(user_id,concept_key) DO UPDATE SET concept=EXCLUDED.concept,mastery_score=EXCLUDED.mastery_score,status=EXCLUDED.status,evidence_count=user_concept_mastery.evidence_count+1,last_seen_at=EXCLUDED.last_seen_at,updated_at=EXCLUDED.updated_at",(user_id,key,concept,score,_status(score,review and score<=40),now,now))
        for concept, description in errors:
            key=_key(concept); conn.execute("INSERT INTO recurring_errors(user_id,error_key,concept,description,frequency,first_seen_at,last_seen_at) VALUES(%s,%s,%s,%s,1,%s,%s) ON CONFLICT(user_id,error_key) DO UPDATE SET frequency=recurring_errors.frequency+1,description=EXCLUDED.description,last_seen_at=EXCLUDED.last_seen_at",(user_id,key,concept,description,now,now))
        for document_id in ids:
            conn.execute("INSERT INTO document_progress(user_id,document_id,last_topic,updated_at) VALUES(%s,%s,%s,%s) ON CONFLICT(user_id,document_id) DO UPDATE SET last_topic=COALESCE(EXCLUDED.last_topic,document_progress.last_topic),updated_at=EXCLUDED.updated_at",(user_id,document_id,last_topic,now))
            conn.execute("INSERT INTO learning_events(user_id,event_type,topic,document_id,payload,created_at) VALUES(%s,'document_studied',%s,%s,'{}'::jsonb,%s)",(user_id,last_topic,document_id,now))
        conn.commit()


def relevant(user_id: str, message: str = "") -> str:
    """Small relevant context; current conversation always has priority."""
    if not get_settings().database_url:
        values=list(_read().get(user_id,{}).values())[:8]; return f"\n\n[MÉMOIRE D'APPRENTISSAGE]\n"+"\n".join(f"- {x}" for x in values) if values else ""
    _schema(); import psycopg; terms=set(re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}",message.lower()))
    with psycopg.connect(get_settings().database_url) as conn:
        prefs=conn.execute("SELECT content FROM learning_memory_notes WHERE user_id=%s AND memory_type='preference' ORDER BY confidence DESC LIMIT 4",(user_id,)).fetchall(); goals=conn.execute("SELECT content FROM learning_goals WHERE user_id=%s AND status='active' ORDER BY updated_at DESC LIMIT 3",(user_id,)).fetchall(); concepts=conn.execute("SELECT concept,status FROM user_concept_mastery WHERE user_id=%s ORDER BY updated_at DESC LIMIT 20",(user_id,)).fetchall()
    matches=[row for row in concepts if terms & set(re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}",row[0].lower()))] or concepts[:3]
    lines=(["Objectifs : "+"; ".join(x[0] for x in goals)] if goals else [])+(["Préférences : "+", ".join(x[0] for x in prefs)] if prefs else [])+[f"Notion {concept} : {status}" for concept,status in matches[:5]]
    return "\n\n[MÉMOIRE D'APPRENTISSAGE — contexte indicatif, la conversation actuelle prime]\n"+"\n".join(f"- {x}" for x in lines[:12]) if lines else ""


def snapshot(user_id: str) -> dict:
    if not get_settings().database_url: return {"preferences": list(_read().get(user_id,{}).values()), "goals": [], "concepts": [], "errors": [], "documents": []}
    _schema(); import psycopg
    with psycopg.connect(get_settings().database_url) as conn:
        prefs=conn.execute("SELECT memory_key,content,confidence,updated_at FROM learning_memory_notes WHERE user_id=%s ORDER BY updated_at DESC",(user_id,)).fetchall(); goals=conn.execute("SELECT goal_key,content,horizon,priority,status,updated_at FROM learning_goals WHERE user_id=%s ORDER BY updated_at DESC",(user_id,)).fetchall(); concepts=conn.execute("SELECT concept_key,concept,status,mastery_score,evidence_count,updated_at FROM user_concept_mastery WHERE user_id=%s ORDER BY updated_at DESC",(user_id,)).fetchall(); errors=conn.execute("SELECT error_key,concept,description,frequency,last_seen_at FROM recurring_errors WHERE user_id=%s ORDER BY last_seen_at DESC",(user_id,)).fetchall(); docs=conn.execute("SELECT document_id,last_topic,last_section,updated_at FROM document_progress WHERE user_id=%s ORDER BY updated_at DESC",(user_id,)).fetchall()
    return {"preferences":[{"key":r[0],"content":r[1],"confidence":r[2],"updated_at":r[3].isoformat()} for r in prefs],"goals":[{"key":r[0],"content":r[1],"horizon":r[2],"priority":r[3],"status":r[4],"updated_at":r[5].isoformat()} for r in goals],"concepts":[{"key":r[0],"concept":r[1],"status":r[2],"score":r[3],"evidence_count":r[4],"updated_at":r[5].isoformat()} for r in concepts],"errors":[{"key":r[0],"concept":r[1],"description":r[2],"frequency":r[3],"last_seen_at":r[4].isoformat()} for r in errors],"documents":[{"document_id":r[0],"last_topic":r[1],"last_section":r[2],"updated_at":r[3].isoformat()} for r in docs]}


def forget(user_id: str, category: str, key: str) -> None:
    mapping={"preference":("learning_memory_notes","memory_key"),"goal":("learning_goals","goal_key"),"concept":("user_concept_mastery","concept_key"),"error":("recurring_errors","error_key"),"document":("document_progress","document_id")}
    if category not in mapping: raise ValueError("Catégorie de mémoire inconnue.")
    if not get_settings().database_url: data=_read(); data.get(user_id,{}).pop(key,None); _write(data); return
    _schema(); import psycopg; table,field=mapping[category]
    with psycopg.connect(get_settings().database_url) as conn: conn.execute(f"DELETE FROM {table} WHERE user_id=%s AND {field}=%s",(user_id,key)); conn.commit()


def reset(user_id: str) -> None:
    if not get_settings().database_url: data=_read(); data.pop(user_id,None); _write(data); return
    _schema(); import psycopg
    with psycopg.connect(get_settings().database_url) as conn:
        for table in ("learning_profiles","learning_goals","user_concept_mastery","recurring_errors","document_progress","learning_events","learning_memory_notes"): conn.execute(f"DELETE FROM {table} WHERE user_id=%s",(user_id,))
        conn.commit()
