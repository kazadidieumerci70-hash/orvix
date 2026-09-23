from app.ai import OrvixAI


def test_simple_greeting_is_short_and_does_not_present_orvix():
    response = OrvixAI._social_response("Bonjour")
    assert response == "Bonjour ! Que veux-tu comprendre aujourd'hui ?"
    assert "créé" not in response


def test_social_response_does_not_capture_a_real_question():
    assert OrvixAI._social_response("Bonjour, explique-moi la photosynthèse") is None


def test_thanks_is_answered_without_calling_the_model():
    assert OrvixAI._social_response("Merci beaucoup") == "Avec plaisir."
