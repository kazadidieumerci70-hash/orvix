import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from app import conversations
from app.schemas import ChatRequest

ANSWER = 'Explication détaillée. ' * 700 + '[[ORVIX_SOURCE]]{"excerpt":"passage cité"}[[/ORVIX_SOURCE]]'


def test_long_answer_roundtrip_and_followup_in_file_store():
    with tempfile.TemporaryDirectory() as directory:
        settings = SimpleNamespace(database_url='', conversations_file=Path(directory) / 'conversations.json')
        with patch.object(conversations, 'get_settings', return_value=settings):
            created = conversations.append_exchange('u', '', 'Explique mon cours', ANSWER, [])
            assert conversations.get_conversation('u', created.id).messages[-1].content == ANSWER
            request = ChatRequest(message='Continue', conversation_id=created.id, history=[m.model_dump() for m in created.messages])
            assert request.history == []
            updated = conversations.append_exchange('u', created.id, request.message, 'Suite', [])
            assert updated.messages[1].content == ANSWER
            with pytest.raises(HTTPException) as error:
                conversations.get_conversation('other', created.id)
            assert error.value.status_code == 404


def test_postgres_read_preserves_long_answer():
    connection = MagicMock()
    connection.__enter__.return_value = connection
    row = MagicMock(); row.fetchone.return_value = ('id', 'Cours', datetime.now(timezone.utc), [])
    messages = MagicMock(); messages.fetchall.return_value = [('assistant', ANSWER)]
    connection.execute.side_effect = [row, messages]
    with patch.object(conversations, 'get_settings', return_value=SimpleNamespace(database_url='configured')), patch.object(conversations, '_db_connect', return_value=connection):
        result = conversations.get_conversation('u', 'id')
    assert result.messages[0].content == ANSWER
    assert connection.execute.call_args_list[0].args[1] == ('id', 'u')


def test_incoming_limits_still_apply():
    with pytest.raises(ValidationError):
        ChatRequest(message='Question', history=[{'role': 'assistant', 'content': ANSWER}])
    with pytest.raises(ValidationError):
        ChatRequest(conversation_id='id', message='x' * 8001)
