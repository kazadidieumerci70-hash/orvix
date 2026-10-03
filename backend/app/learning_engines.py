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
    if re.fullmatch(r"\s*(?:bonjour|salut|merci(?: beaucoup)?|au revoir)[.!\s]*", text):
        return Intent("social", "simple", False)
    if re.search(r"(?:ne comprends? (?:pas|rien)|n[’']ai pas compris|plus simple|c[’']est compliqué|simplifie)", text):
        return Intent("simplify", "medium", False)
    if re.search(r"(?:en bref|seulement l[’']essentiel)", text):
        return Intent("concise", "simple", False)
    if re.search(r"(?:va plus loin|techniquement|approfondis)", text):
        return Intent("deepen", "complex", True)
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
    if intent.name == "simplify": directives.append("Cible le blocage ; change de méthode par rapport à l'historique, réduis les concepts et donne une étape ou un exemple adapté. Ne répète pas la même explication.")
    if intent.name == "concise": directives.append("Donne uniquement l'essentiel demandé, sans cours complet ni invitation automatique.")
    if intent.name == "deepen": directives.append("Approfondis le point demandé, sans reprendre les bases déjà comprises ; justifie les étapes utiles.")
    if intent.name == "summarize": directives.append("Organise la synthèse dans l'ordre du cours : notions, liens logiques, puis points à retenir.")
    if intent.needs_plan: directives.append("Prépare mentalement une stratégie avant de rédiger ; ne l'affiche que si elle aide réellement l'étudiant.")
    return "\n".join(f"- {item}" for item in directives)


def verify_answer(answer: str, *, document_mode: bool, sources_found: bool) -> str:
    """Final deterministic guard; source assertions stay server-owned."""
    answer = re.sub(r"(?im)^\s*(?:📖\s*)?(?:source dans vos documents|support consulté)\s*:.*(?:\n|$)", "", answer).strip()
    if document_mode and not sources_found:
        return "Je n'ai pas trouvé d'information dans les documents fournis qui permette de répondre à cette question. Souhaites-tu que je te réponde avec mes connaissances générales ?"
    return answer
