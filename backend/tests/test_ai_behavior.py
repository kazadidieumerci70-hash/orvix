from types import SimpleNamespace

from app.ai import OrvixAI
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
