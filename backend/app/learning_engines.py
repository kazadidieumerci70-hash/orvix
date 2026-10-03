"""Small deterministic engines orchestrating a safe learning response."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    name: str
    complexity: str
    needs_plan: bool


def analyze_intent(message: str) -> Intent:
    text = message.lower()
    if re.search(r"\b(?:bonjour|salut|merci|au revoir)\b", text) and len(text.split()) <= 5:
        return Intent("social", "simple", False)
    if re.search(r"\b(?:résume|resume|synthèse|synthese)\b", text):
        return Intent("summarize", "complex", True)
    if re.search(r"\b(?:quiz|qcm|questions? d.examen)\b", text):
        return Intent("quiz", "medium", True)
    if re.search(r"\b(?:plan|programme|organise|étapes?|etapes?)\b", text):
        return Intent("plan", "complex", True)
    if re.search(r"\b(?:révise|reviser|révision|revision)\b", text):
        return Intent("revision", "medium", True)
    if re.search(r"\b(?:explique|comprendre|pourquoi|comment|différence|difference)\b", text):
        return Intent("explain", "medium", False)
    return Intent("answer", "complex" if len(text) > 360 else "medium", len(text) > 700)


def pedagogical_strategy(intent: Intent, user) -> str:
    style = (getattr(user, "learning_style", "") or "").lower()
    level = getattr(user, "level", "") or "non précisé"
    directives = [f"Niveau à viser : {level}."]
    if "exemple" in style: directives.append("Utilise un exemple concret après l'idée principale.")
    if "pas" in style or "étape" in style: directives.append("Explique étape par étape, sans sauter de raisonnement.")
    if intent.name == "explain": directives.append("Commence par l'idée centrale, puis développe seulement les points nécessaires.")
    if intent.name == "summarize": directives.append("Organise la synthèse dans l'ordre du cours : notions, liens logiques, puis points à retenir.")
    if intent.needs_plan: directives.append("Prépare mentalement une stratégie avant de rédiger ; ne l'affiche que si elle aide réellement l'étudiant.")
    return "\n".join(f"- {item}" for item in directives)


def verify_answer(answer: str, *, document_mode: bool, sources_found: bool) -> str:
    """Final deterministic guard; source assertions stay server-owned."""
    answer = re.sub(r"(?im)^\s*(?:📖\s*)?(?:source dans vos documents|support consulté)\s*:.*(?:\n|$)", "", answer).strip()
    if document_mode and not sources_found:
        return "Je n'ai pas trouvé d'information dans les documents fournis qui permette de répondre à cette question. Souhaites-tu que je te réponde avec mes connaissances générales ?"
    return answer
