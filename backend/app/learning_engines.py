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


def response_blueprint(message: str, intent: Intent) -> str:
    """Build a small, explicit writing contract for the current turn."""
    text = message.casefold()
    directives = [
        "Commence directement par l'information utile, avec une première phrase qui répond à la demande.",
        "Écris comme un professeur attentif dans une vraie conversation : naturel, précis, sans formule de chatbot.",
        "Ne termine pas par une question ou une proposition automatique, sauf si une précision est indispensable.",
    ]
    if intent.complexity == "simple" or intent.name == "concise":
        directives.append("Réponse courte : un petit paragraphe ou quelques points, sans développement annexe.")
    elif intent.complexity == "complex":
        directives.append("Réponse développée : idée centrale, explication structurée, puis éléments à retenir si utile.")
    else:
        directives.append("Réponse de longueur moyenne : explique assez pour comprendre, sans transformer la demande en cours complet.")
    if re.search(r"\b(?:étape|etape|procédure|procedure|méthode|methode)\b", text):
        directives.append("Présente les actions dans un ordre numéroté.")
    if re.search(r"\b(?:compare|comparaison|différence|difference|versus|\bvs\b)\b", text):
        directives.append("Fais ressortir les différences critère par critère ; utilise un tableau seulement s'il clarifie vraiment.")
    if re.search(r"\b(?:exemple|cas concret|illustr)\b", text):
        directives.append("Donne un exemple concret directement relié à l'explication.")
    if re.search(r"\b(?:en (?:\d+|dix|vingt) lignes?|\d+ lignes?)\b", text):
        directives.append("Respecte approximativement le nombre de lignes demandé, sans remplir artificiellement.")
    if intent.name == "simplify":
        directives.append("Utilise des mots plus simples et une nouvelle approche ; n'imite pas la réponse précédente.")
    return "\n".join(f"- {item}" for item in directives)


def verify_answer(answer: str, *, document_mode: bool, sources_found: bool) -> str:
    """Final deterministic guard; source assertions stay server-owned."""
    answer = re.sub(r"(?im)^\s*(?:📖\s*)?(?:source dans vos documents|support consulté)\s*:.*(?:\n|$)", "", answer).strip()
    if document_mode and not sources_found:
        return "Je n'ai pas trouvé d'information dans les documents fournis qui permette de répondre à cette question. Souhaites-tu que je te réponde avec mes connaissances générales ?"
    # A provider occasionally returns an empty shell despite receiving context.
    # Never display that as a completed pedagogical answer.
    if not re.sub(r"[^A-Za-zÀ-ÿ0-9]", "", answer):
        return "Je n'ai pas pu formuler une réponse fiable à partir des éléments disponibles. Peux-tu reformuler ta question ?"
    return answer
