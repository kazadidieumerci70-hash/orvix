import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.ai import OrvixAI
from app.core_engine import OrvixCoreEngine
from app.response_rules import RESPONSE_RULES


def test_core_passes_rules_and_requested_language_to_model():
    gateway = SimpleNamespace(generate=AsyncMock(return_value='Answer'))
    result = asyncio.run(OrvixCoreEngine(gateway).generate(user_id='u', session_id='s', message='Question', language='English'))
    assert RESPONSE_RULES in gateway.generate.call_args.kwargs['system']
    assert 'English' in gateway.generate.call_args.kwargs['system']
    assert result['response']['content'] == 'Answer'


def test_gemini_receives_rules_for_text_and_structured_generation():
    chat = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(text='Réponse')))
    configs = []
    def create(**kwargs):
        configs.append(kwargs['config'])
        return chat
    ai = object.__new__(OrvixAI)
    ai.model = 'test-model'
    ai.models = (ai.model,)
    ai.client = SimpleNamespace(aio=SimpleNamespace(chats=SimpleNamespace(create=create)))
    asyncio.run(ai._generate('Question'))
    asyncio.run(ai._generate('Quiz', json_schema=dict))
    assert all(RESPONSE_RULES in config.system_instruction for config in configs)
    assert configs[0].response_mime_type == 'text/plain'
    assert configs[1].response_mime_type == 'application/json'


def test_student_level_is_available_in_profile_context():
    user = SimpleNamespace(name='Étudiant', level='Deuxième année de licence', subjects=['Biologie'], goal='Réviser', learning_style='Exemples', difficulties='')
    assert 'Deuxième année de licence' in OrvixAI._student_profile(user)
