import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import subscriptions


def credit_settings(tmp_path):
    plans = tmp_path / "plans.json"
    plans.write_text(json.dumps(subscriptions.DEFAULT_PLANS), encoding="utf-8")
    subscription_file = tmp_path / "subscriptions.json"
    subscription_file.write_text('{"subscriptions": {}}', encoding="utf-8")
    usage = tmp_path / "usage.json"
    usage.write_text('{"days": {}, "months": {}, "ledger": []}', encoding="utf-8")
    return SimpleNamespace(database_url="", plans_file=plans, subscriptions_file=subscription_file, usage_file=usage)


def test_credit_usage_is_recorded_daily_monthly_and_in_ledger(monkeypatch, tmp_path):
    settings = credit_settings(tmp_path)
    monkeypatch.setattr(subscriptions, "get_settings", lambda: settings)
    subscriptions.record_ai_request("user-1", 5, "quiz_short")
    status = subscriptions.subscription_status("user-1")
    assert status["credits_used_today"] == 5
    assert status["credits_used_month"] == 5
    assert status["credits_remaining"] == 13
    stored = json.loads(settings.usage_file.read_text(encoding="utf-8"))
    assert stored["ledger"][-1]["action"] == "quiz_short"
    assert stored["ledger"][-1]["credits"] == 5


def test_daily_credit_limit_blocks_expensive_action(monkeypatch, tmp_path):
    settings = credit_settings(tmp_path)
    monkeypatch.setattr(subscriptions, "get_settings", lambda: settings)
    subscriptions.record_ai_request("user-1", 10, "test")
    with pytest.raises(HTTPException) as error:
        subscriptions.ensure_ai_quota("user-1", 10)
    assert error.value.status_code == 429
    assert "Crédits du jour" in error.value.detail


def test_configured_action_costs(monkeypatch, tmp_path):
    settings = credit_settings(tmp_path)
    monkeypatch.setattr(subscriptions, "get_settings", lambda: settings)
    assert subscriptions.credit_cost("chat") == 1
    assert subscriptions.credit_cost("chat_with_documents") == 2
    assert subscriptions.credit_cost("revision") == 3
    assert subscriptions.credit_cost("quiz_long") == 8
    assert subscriptions.credit_cost("exam_plan") == 10
