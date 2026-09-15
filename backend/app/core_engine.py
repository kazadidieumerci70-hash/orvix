"""Native, provider-independent ORVIX Core Engine.

The engine performs deterministic orchestration (input normalization, intent,
policy and response shaping). Model-based generation remains an optional adapter;
the core itself never requires a cloud provider.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class CoreRequest:
    request_id: str
    user_id: str
    session_id: str
    message: str
    language: str
    intent: str
    entities: dict[str, str]


class OrvixCoreEngine:
    def __init__(self, gateway=None): self.gateway = gateway

    async def generate(self, *, user_id: str, session_id: str, message: str, language: str = "Français", context: str = "") -> dict:
        result = self.process(user_id=user_id, session_id=session_id, message=message, language=language)
        if self.gateway:
            result["response"]["content"] = await self.gateway.generate(f"{context}\n\n{message}", system="Tu es ORVIX, assistant local. Ne te présente jamais comme un service cloud.")
        return result
    def process(self, *, user_id: str, session_id: str, message: str, language: str = "Français") -> dict:
        cleaned = re.sub(r"\s+", " ", message).strip()
        if not cleaned:
            raise ValueError("Le message ne peut pas être vide.")
        intent = self._intent(cleaned)
        request = CoreRequest(uuid4().hex, user_id, session_id or uuid4().hex, cleaned, language, intent, {})
        return {
            "requestId": request.request_id,
            "status": "success",
            "intent": request.intent,
            "response": {"type": "text", "content": cleaned},
            "actions": [],
            "metadata": {"sessionId": request.session_id, "language": language, "processedAt": datetime.now(timezone.utc).isoformat()},
        }

    @staticmethod
    def _intent(message: str) -> str:
        text = message.casefold()
        if any(word in text for word in ("résume", "resume", "summarize", "riassumi")):
            return "résumé"
        if any(word in text for word in ("calcule", "calcul", "compute")):
            return "calcul"
        if any(word in text for word in ("quiz", "question", "réviser", "reviser")):
            return "révision"
        if text.endswith("?") or any(text.startswith(word) for word in ("pourquoi", "comment", "what", "why", "come")):
            return "question"
        return "conversation"
