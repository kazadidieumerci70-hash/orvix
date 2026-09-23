import asyncio
import json
import os
import random
import re
import logging

import certifi
from fastapi import HTTPException
from google import genai
from google.genai import types

from .config import get_settings
from .documents import document_context
from .schemas import ChatMessage, ExamModeResponse, QuizResponse, UserProfile, MAX_CONTEXT_MESSAGES

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

ORVIX_PRESENTATION = """Je suis **Orvix**, ton assistant pédagogique.

Je peux expliquer une notion, analyser tes supports, créer des révisions et des quiz, ou t'aider à structurer un projet.

Dis-moi simplement ce que tu veux comprendre ou accomplir."""

SYSTEM_PROMPT = """Tu es Orvix, un assistant pédagogique exigeant, clair, patient et fiable.
Réponds en français sauf demande contraire. Adapte le niveau à l'étudiant.
STYLE DE RÉPONSE : réponds d'abord à la demande, sans préambule ni autopromotion. Pour une question simple, réponds en 1 à 3 phrases. Développe uniquement lorsque la complexité l'exige ou lorsque l'utilisateur le demande.
Ne répète pas la question. Ne commence pas par « Bonjour » à chaque réponse. Ne dis pas « En tant qu'Orvix ». Ne cite jamais ton créateur, ton identité ou tes capacités sans question explicite sur ce sujet.
Si une information indispensable manque, pose une seule question de clarification précise. Sinon, fais une hypothèse raisonnable et signale-la brièvement.
Utilise des titres et des listes seulement lorsqu'ils améliorent réellement la compréhension. Évite les conclusions génériques et les invitations répétitives du type « N'hésite pas ».
MISSION : ORVIX aide à comprendre, rechercher, organiser, analyser et exploiter l'information pour les études, les documents, le travail, les affaires, les projets et la recherche.
Si l'utilisateur demande de te présenter, qui tu es, ce que tu peux faire ou à quoi sert ORVIX, présente ORVIX selon cette mission. Ne dis jamais que tu es dédié au calendrier, aux listes de courses ou uniquement aux tâches quotidiennes.
IDENTITÉ : ORVIX a été créé par DIEU MERCI KAZADI. Si l'utilisateur demande qui t'a créé, qui a créé ORVIX, qui est ton créateur ou qui t'a développé, réponds clairement : « ORVIX a été créé par DIEU MERCI KAZADI. »
Ne présente jamais Google, Gemini, un fournisseur de modèle ou une autre entreprise comme le créateur d'ORVIX. Ne mentionne pas le fournisseur technique sauf si l'utilisateur pose explicitement une question technique à ce sujet.
RÈGLE DE VÉRITÉ : lorsqu'un ou plusieurs supports sont fournis, ils constituent la source principale et autorisée de la réponse.
Appuie chaque affirmation de cours sur leur contenu. N'attribue jamais au support une information qui n'y apparaît pas.
MODE DOCUMENT STRICT : si la réponse n'est pas présente ou ne peut pas être déduite raisonnablement du support, réponds exactement dans cet esprit : « Je n'ai pas trouvé d'information dans les documents fournis qui permette de répondre à cette question. Souhaites-tu que je te réponde avec mes connaissances générales ? »
Dans ce cas, arrête la réponse après cette demande. Ne donne aucun élément de connaissance générale avant l'accord explicite de l'étudiant.
Si l'étudiant accepte ensuite, commence par « Réponse hors documents : » et ne prétends jamais que ces informations proviennent des supports.
Ne fabrique jamais de citation, de chapitre, de page, de définition, de formule, de chiffre ou d'exemple prétendument issu d'un document.
Pour une question pédagogique ou documentaire, commence par une courte ligne « Support consulté : Document N — nom » ou « Hors support » selon le cas.
Pour une salutation, un remerciement, une prise de contact ou une conversation sociale, réponds naturellement et brièvement sans annoncer la lecture d'un support ni écrire « Hors support ».
Ne commence pas chaque réponse par la même salutation ou une présentation. Varie naturellement le ton et la formulation selon le contexte. Présente ORVIX uniquement si l'utilisateur le demande explicitement.
Quand plusieurs documents sont utilisés, indique lesquels. Distingue clairement le contenu du support de ton interprétation pédagogique.
Quand tu expliques un document, découpe la réponse en parties claires avec des titres courts.
Évite le Markdown décoratif inutile. N'utilise le gras que pour des mots vraiment importants.
Structure les explications pour qu'elles soient faciles à réviser et à restituer lors d'un examen.
Tiens compte des 30 derniers messages pour conserver les définitions, les objectifs et les questions déjà traitées sans te répéter inutilement."""

logger = logging.getLogger(__name__)


class OrvixAI:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.gemini_model
        self.models = (self.model, *settings.gemini_fallback_models)
        self.client = (
            genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(
                    client_args={"verify": certifi.where() if settings.gemini_verify_ssl else False},
                    async_client_args={"verify": certifi.where() if settings.gemini_verify_ssl else False},
                ),
            )
            if settings.gemini_api_key
            else None
        )

    async def _generate(self, prompt: str, *, json_schema: type | None = None) -> str:
        if not self.client:
            raise HTTPException(503, "Le serveur Orvix n'a pas encore de clé Gemini configurée.")
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json" if json_schema else "text/plain",
        )
        last_error: Exception | None = None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 35
        # Deux essais rapides par modèle, puis bascule automatique vers un modèle
        # de secours. Un incident de capacité ne doit pas bloquer tout le quiz.
        for model_index, model in enumerate(self.models):
            for attempt in range(2):
                remaining = deadline - loop.time()
                if remaining <= 0:
                    last_error = TimeoutError("Gemini response deadline exceeded")
                    break
                try:
                    chat = self.client.aio.chats.create(
                        model=model,
                        config=config,
                    )
                    response = await asyncio.wait_for(chat.send_message(prompt), timeout=min(12, remaining))
                    if response.text:
                        if model != self.model:
                            logger.warning("Gemini fallback used: %s", model)
                        return response.text.strip()
                    raise RuntimeError("Réponse vide")
                except Exception as error:
                    last_error = error
                    logger.warning(
                        "Gemini request failed (model=%s, attempt=%s): %s",
                        model,
                        attempt + 1,
                        type(error).__name__,
                    )
                    if attempt == 0 and deadline - loop.time() > 1.5:
                        await asyncio.sleep(0.7 + random.random() * 0.5)
            if loop.time() >= deadline:
                break
            if model_index < len(self.models) - 1:
                await asyncio.sleep(0.25)

        raw_detail = str(last_error or "")
        if isinstance(last_error, (TimeoutError, asyncio.TimeoutError)):
            detail = "La réponse de l'intelligence artificielle prend trop de temps. Réessayez dans un instant."
        elif "CERTIFICATE_VERIFY_FAILED" in raw_detail:
            detail = "La connexion sécurisée au service d'intelligence artificielle a échoué. Réessayez dans un instant."
        else:
            detail = "L'intelligence artificielle est momentanément indisponible. Réessayez dans un instant."
        if last_error:
            raise HTTPException(503, detail) from last_error
        raise HTTPException(503, detail)

    @staticmethod
    def _context(user_id: str, document_ids: list[str], query: str, max_chars: int = 16_000) -> str:
        context = document_context(user_id, document_ids, query=query, max_chars=max_chars)
        return f"\n\nSUPPORTS DE L'ÉTUDIANT :\n{context}" if context else ""

    @staticmethod
    def _student_profile(user: UserProfile) -> str:
        subjects = ", ".join(user.subjects) if user.subjects else "non precisees"
        return (
            "\n\nPROFIL DE L'ETUDIANT :"
            f"\nNom : {user.name}"
            f"\nNiveau : {user.level or 'non precise'}"
            f"\nMatieres : {subjects}"
            f"\nObjectif : {user.goal or 'non precise'}"
            f"\nPreference : {user.learning_style or 'non precisee'}"
            f"\nDifficultes : {user.difficulties or 'non precisees'}"
        )

    @staticmethod
    def _needs_document_context(message: str) -> bool:
        normalized = " ".join(re.findall(r"[a-zA-ZÀ-ÿ0-9']+", message.lower())).strip()
        social_messages = {
            "bonjour", "bonsoir", "salut", "coucou", "hello", "hey",
            "merci", "merci beaucoup", "au revoir", "à bientôt", "a bientot",
            "comment vas tu", "comment allez vous", "ça va", "ca va",
            "qui es tu", "comment tu t'appelles", "comment tu t appelles",
        }
        return normalized not in social_messages

    @staticmethod
    def _social_response(message: str) -> str | None:
        normalized = " ".join(re.findall(r"[a-zA-ZÀ-ÿ0-9']+", message.lower())).strip()
        if normalized in {"bonjour", "bonsoir", "salut", "coucou", "hello", "hey"}:
            return "Bonjour ! Que veux-tu comprendre aujourd'hui ?"
        if normalized in {"merci", "merci beaucoup"}:
            return "Avec plaisir."
        if normalized in {"comment vas tu", "comment allez vous", "ça va", "ca va"}:
            return "Je vais bien, merci. Sur quoi veux-tu avancer ?"
        if normalized in {"au revoir", "à bientôt", "a bientot"}:
            return "À bientôt !"
        return None

    @staticmethod
    def _asks_about_creator(message: str) -> bool:
        normalized = " ".join(re.findall(r"[a-zA-ZÀ-ÿ0-9']+", message.lower())).strip()
        creator_terms = ("créé", "cree", "créateur", "createur", "développé", "developpe", "fondateur")
        identity_terms = ("orvix", "t'", "tu", "ton")
        return any(term in normalized for term in creator_terms) and any(term in normalized for term in identity_terms)

    @staticmethod
    def _asks_for_presentation(message: str) -> bool:
        normalized = " ".join(re.findall(r"[a-zA-ZÀ-ÿ0-9']+", message.lower())).strip()
        exact_requests = {
            "presente toi",
            "présente toi",
            "présente-toi",
            "presente-toi",
            "presentez vous",
            "présentez vous",
            "qui es tu",
            "qui êtes vous",
            "qui etes vous",
            "tu es qui",
            "c'est quoi orvix",
            "c est quoi orvix",
            "orvix c'est quoi",
            "orvix c est quoi",
        }
        if normalized in exact_requests:
            return True
        presentation_terms = ("présente", "presente", "présentation", "presentation", "qui es", "qui êtes", "qui etes")
        orvix_terms = ("orvix", "toi", "tu", "vous")
        return any(term in normalized for term in presentation_terms) and any(term in normalized for term in orvix_terms)

    @staticmethod
    def _general_knowledge_authorized(message: str, history: list[ChatMessage]) -> bool:
        normalized = " ".join(re.findall(r"[a-zA-ZÀ-ÿ0-9']+", message.lower())).strip()
        consent = normalized in {
            "oui", "d'accord", "d accord", "ok", "okay", "vas y", "allez",
            "oui réponds", "oui reponds", "avec tes connaissances", "réponds hors document",
            "reponds hors document", "donne moi une réponse générale", "donne moi une reponse generale",
        }
        if not consent or not history:
            return False
        previous = history[-1].content.lower() if history[-1].role == "assistant" else ""
        return "connaissances générales" in previous or "connaissances generales" in previous or "hors document" in previous

    async def chat(self, message: str, history: list[ChatMessage], user: UserProfile, document_ids: list[str]) -> str:
        social_response = self._social_response(message)
        if social_response:
            return social_response
        if self._asks_about_creator(message):
            return "ORVIX a été créé par DIEU MERCI KAZADI."
        if self._asks_for_presentation(message):
            return ORVIX_PRESENTATION
        transcript = "\n".join(f"{item.role}: {item.content}" for item in history[-MAX_CONTEXT_MESSAGES:])
        allow_general = self._general_knowledge_authorized(message, history)
        needs_document = self._needs_document_context(message)
        requested_support = bool(document_ids)
        context = self._context(user.id, document_ids, message) if needs_document and requested_support and not allow_general else ""
        if allow_general:
            mode = "CONNAISSANCES GENERALES AUTORISEES PAR L'ETUDIANT : réponds hors documents et signale-le clairement."
        elif context:
            mode = "DOCUMENT STRICT : réponds uniquement avec les extraits fournis. S'ils sont insuffisants, demande l'autorisation avant toute réponse générale."
        elif needs_document and requested_support:
            mode = "AUCUN SUPPORT EXPLOITABLE : indique que l'information n'a pas été trouvée dans les documents et demande l'autorisation avant toute réponse générale."
        elif needs_document:
            mode = "QUESTION LIBRE : réponds naturellement avec tes connaissances générales, sans prétendre avoir consulté un document."
        else:
            mode = "ECHANGE SOCIAL : ne prétends pas lire un document."
        prompt = f"MODE : {mode}\n\nHISTORIQUE DE CETTE DISCUSSION (30 DERNIERS ÉCHANGES, 60 MESSAGES MAXIMUM) :\n{transcript}\n\nMESSAGE ACTUEL :\n{message}{self._student_profile(user)}{context}"
        return await self._generate(prompt)

    async def revision(self, topic: str, user: UserProfile, document_ids: list[str]) -> str:
        prompt = f"Crée une fiche de révision complète mais concise sur : {topic}. Inclus les notions clés, un résumé, les erreurs fréquentes et 3 questions d'auto-évaluation.{self._student_profile(user)}{self._context(user.id, document_ids, topic, 14_000)}"
        return await self._generate(prompt)

    async def quiz(self, topic: str, count: int, quiz_type: str, user: UserProfile, document_ids: list[str]) -> QuizResponse:
        if quiz_type == "traditional":
            instructions = "Chaque question demande une réponse rédigée courte. Laisse choices vide, mets answer_index à -1, fournis expected_answer avec la réponse attendue et une explication brève."
        else:
            instructions = "Chaque question doit avoir exactement 4 choix, une seule bonne réponse indiquée par answer_index, expected_answer vide et une explication brève."
        context = self._context(user.id, document_ids, topic, 5_500)

        async def generate_batch(batch_count: int, batch_index: int) -> QuizResponse:
            start = batch_index * 10 + 1
            end = start + batch_count - 1
            prompt = f"""Crée le lot {batch_index + 1} d'un quiz pédagogique sur : {topic}.
Génère exactement {batch_count} questions, correspondant aux numéros {start} à {end}.
Varie les notions et évite les formulations répétitives.
{instructions}
Utilise uniquement les notions réellement présentes dans les extraits.
Réponds de façon concise.

Retourne uniquement un JSON valide avec cette forme :
{{
  "title": "Titre du quiz",
  "questions": [
    {{
      "question": "Question",
      "choices": ["A", "B", "C", "D"],
      "answer_index": 0,
      "expected_answer": "",
      "explanation": "Explication courte"
    }}
  ]
}}

Pour les questions traditionnelles, choices doit être [] et answer_index doit être -1.
{self._student_profile(user)}{context}"""
            raw = await self._generate(prompt, json_schema=QuizResponse)
            try:
                return QuizResponse.model_validate(json.loads(raw))
            except Exception as error:
                raise HTTPException(502, "La réponse du modèle n'a pas le format attendu.") from error

        batch_sizes = [min(10, count - start) for start in range(0, count, 10)]
        semaphore = asyncio.Semaphore(3)

        async def limited_batch(size: int, index: int) -> QuizResponse:
            async with semaphore:
                return await generate_batch(size, index)

        batches = await asyncio.gather(*(limited_batch(size, index) for index, size in enumerate(batch_sizes)))
        questions = [question for batch in batches for question in batch.questions][:count]
        title = batches[0].title if batches else f"Quiz sur {topic}"
        return QuizResponse(title=title, questions=questions)

    async def exam_mode(self, exam_date: str, minutes_per_day: int, confidence: int, subject: str, user: UserProfile, document_ids: list[str]) -> ExamModeResponse:
        context = self._context(user.id, document_ids, subject or "notions importantes examen", 14_000)
        if not context:
            raise HTTPException(422, "Aucun contenu exploitable n'a été trouvé dans les supports sélectionnés.")
        prompt = f"""Construis un programme de préparation à un examen strictement à partir des supports fournis.
Date de l'examen : {exam_date}
Temps disponible par jour : {minutes_per_day} minutes
Confiance déclarée : {confidence}/5
Matière ou objectif : {subject or 'à déterminer depuis les documents'}

Retourne : un titre, un score initial prudent de préparation entre 0 et 100, un résumé court, les notions probablement maîtrisées (sans inventer de résultats de test), les priorités, un programme réaliste de 1 à 7 jours avec tâches et durée, puis exactement 5 premières questions à choix multiple avec 4 choix, answer_index et explication. Ne prétends jamais connaître les performances réelles avant que l'étudiant ait répondu. Appuie toutes les notions sur les supports.{self._student_profile(user)}{context}"""
        raw = await self._generate(prompt, json_schema=ExamModeResponse)
        try:
            return ExamModeResponse.model_validate(json.loads(raw))
        except Exception as error:
            raise HTTPException(502, "Le programme d'examen n'a pas le format attendu.") from error
