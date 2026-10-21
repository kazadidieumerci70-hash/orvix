import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.ai import OrvixAI
from app.learning_engines import analyze_intent, response_blueprint
from app.schemas import ChatMessage


def test_simple_greeting_is_short_and_does_not_present_orvix():
    response = OrvixAI._social_response("Bonjour", user=SimpleNamespace(name="Amina Kabeya"))
    assert response == "Salut Amina 👋 Qu’est-ce qu’on regarde ensemble aujourd’hui ?"
    assert "créé" not in response


def test_repeated_greeting_uses_conversation_instead_of_repeating_itself():
    history = [
        ChatMessage(role="user", content="salut"),
        ChatMessage(role="assistant", content="Salut 👋 Qu’est-ce qu’on regarde ensemble aujourd’hui ?"),
    ]
    assert OrvixAI._social_response("salut", history) == "Re-salut ! On reprend ce qu’on faisait, ou tu as un nouveau sujet ?"


def test_third_greeting_invites_a_direct_request_without_same_question():
    history = [
        ChatMessage(role="user", content="salut"),
        ChatMessage(role="assistant", content="Salut !"),
        ChatMessage(role="user", content="bonjour"),
        ChatMessage(role="assistant", content="Re-salut !"),
    ]
    response = OrvixAI._social_response("salut", history)
    assert response == "Je suis toujours là 🙂 Écris-moi directement ce que tu veux comprendre ou faire."


def test_social_response_does_not_capture_a_real_question():
    assert OrvixAI._social_response("Bonjour, explique-moi la photosynthèse") is None


def test_thanks_is_answered_without_calling_the_model():
    assert OrvixAI._social_response("Merci beaucoup") == "Avec plaisir 🙂"


def test_response_blueprint_avoids_chatbot_endings_and_honors_steps():
    blueprint = response_blueprint("Explique la méthode étape par étape", analyze_intent("Explique la méthode étape par étape"))
    assert "sans formule de chatbot" in blueprint
    assert "ordre numéroté" in blueprint
    assert "proposition automatique" in blueprint


def test_regular_chat_receives_learning_memory_and_current_message_last():
    user = SimpleNamespace(id="u1", name="Amina", level="L2", subjects=["Biologie"], goal="Réviser", learning_style="Exemples", difficulties="")
    ai = object.__new__(OrvixAI)
    ai._generate = AsyncMock(return_value="La réponse utile.")
    with patch("app.ai.relevant", return_value="\n\n[MÉMOIRE]\n- préfère les exemples"):
        answer = asyncio.run(ai.chat("Explique la mitose", [], user, []))
    assert answer == "La réponse utile."
    prompt = ai._generate.await_args.args[0]
    assert "préfère les exemples" in prompt
    assert prompt.index("HISTORIQUE RÉCENT") < prompt.index("DERNIER MESSAGE À TRAITER")
    assert prompt.rstrip().endswith("Rédige maintenant uniquement la réponse destinée à l'étudiant.")


def test_selected_document_without_relevant_source_never_generates_an_answer():
    user = SimpleNamespace(id="u1", name="Amina", level="L2", subjects=[], goal="", learning_style="", difficulties="")
    ai = object.__new__(OrvixAI)
    ai._generate = AsyncMock(return_value="Une connaissance générale interdite")
    with patch.object(ai, "_context_with_sources", return_value=("", [])):
        answer = asyncio.run(ai.chat("Qui a découvert la pénicilline ?", [], user, ["doc-1"]))
    assert answer == "Je n’ai pas trouvé d’informations dans le document sélectionné. Voulez-vous que je réponde avec mes connaissances générales ?"
    assert ai._generate.await_count == 1


def test_semantic_query_can_recover_a_passage_before_answering():
    user = SimpleNamespace(id="u1", name="Amina", level="L2", subjects=[], goal="", learning_style="", difficulties="")
    ai = object.__new__(OrvixAI)
    ai._generate = AsyncMock(side_effect=["pression artérielle hypertension tension sanguine", "La réponse documentée."])
    source = {"id": "d1:1:0", "document_id": "d1", "document_name": "cours.pdf", "page": 1, "excerpt": "pression artérielle"}
    with patch.object(ai, "_context_with_sources", side_effect=[("", []), ("\n\nSUPPORTS DE L'ÉTUDIANT :\npassage", [source])]) as search, patch("app.ai.relevant", return_value=""):
        answer = asyncio.run(ai.chat("Pourquoi la tension monte ?", [], user, ["d1"]))
    assert "La réponse documentée." in answer
    assert "hypertension" in search.call_args_list[1].args[2]
    assert ai._generate.await_count == 2
