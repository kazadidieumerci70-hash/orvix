import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.ai import OrvixAI
from app.learning_engines import analyze_intent, pedagogical_strategy, verify_answer
from app.schemas import ChatMessage


def test_confusion_and_explicit_length_choose_different_strategies():
    assert analyze_intent("Je n’ai pas compris").name == "simplify"
    assert analyze_intent("En bref").name == "concise"
    assert analyze_intent("Va plus loin").name == "deepen"
    assert analyze_intent("Bonjour, explique les dérivées").name != "social"
    assert "change de méthode" in pedagogical_strategy(analyze_intent("Plus simple"), SimpleNamespace())


def test_multiline_message_and_followup_are_preserved():
    ai = object.__new__(OrvixAI)
    message = "Explique le deuxième\n\nJe n’ai pas compris"
    history = [ChatMessage(role="user", content="Les types de division cellulaire")]
    with patch.object(ai, "_context_with_sources", return_value=("extrait", [])) as retrieve, patch.object(ai, "_student_profile", return_value=""), patch.object(ai, "_generate", new_callable=AsyncMock, return_value="Réponse") as generate:
        asyncio.run(ai.chat(message, history, SimpleNamespace(id="u"), ["doc"], response_instructions="Respond in English"))
    assert message in generate.call_args.args[0]
    assert "division cellulaire" in retrieve.call_args.args[2]
    assert "Respond in English" not in retrieve.call_args.args[2]


def test_missing_source_guard_still_requires_consent():
    answer = verify_answer("Une réponse non étayée", document_mode=True, sources_found=False)
    assert "Souhaites-tu" in answer
    assert "non étayée" not in answer


def test_quiz_uses_existing_memory_without_new_store():
    ai = object.__new__(OrvixAI)
    raw = '{"title":"Cours","questions":[{"question":"Q","choices":["A","B","C","D"],"answer_index":0,"explanation":"E"}]}'
    with patch("app.ai.relevant", return_value="Difficulté déclarée : fractions") as memory, patch.object(ai, "_context", return_value="extrait"), patch.object(ai, "_student_profile", return_value="Niveau : collège"), patch.object(ai, "_generate", new_callable=AsyncMock, return_value=raw) as generate:
        result = asyncio.run(ai.quiz("fractions", 1, "multiple_choice", SimpleNamespace(id="u"), ["doc"]))
    memory.assert_called_once_with("u", "fractions")
    assert "Difficulté déclarée" in generate.call_args.args[0]
    assert len(result.questions) == 1
