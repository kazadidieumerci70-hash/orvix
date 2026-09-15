import httpx
import certifi
from google import genai
from google.genai import types

from .config import get_settings
from .model_provider import ModelProvider

class OllamaModelProvider:
    def __init__(self):
        s = get_settings(); self.base_url = s.ollama_base_url.rstrip('/'); self.model = s.ollama_model; self.timeout = s.model_timeout
    async def generate(self, prompt: str, *, system: str = "") -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self.base_url}/api/generate", json={"model": self.model, "prompt": prompt, "system": system, "stream": False}); r.raise_for_status(); text = str(r.json().get("response", "")).strip()
        if not text: raise RuntimeError("Réponse locale vide")
        return text
    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as c: return (await c.get(f"{self.base_url}/api/tags")).is_success
        except httpx.HTTPError: return False

class GeminiModelProvider:
    def __init__(self):
        s = get_settings()
        self.model = s.gemini_model
        self.timeout = s.model_timeout
        self.client = genai.Client(
            api_key=s.gemini_api_key,
            http_options=types.HttpOptions(
                client_args={"verify": certifi.where() if s.gemini_verify_ssl else False},
                async_client_args={"verify": certifi.where() if s.gemini_verify_ssl else False},
            ),
        ) if s.gemini_api_key else None

    async def generate(self, prompt: str, *, system: str = "") -> str:
        if not self.client:
            raise RuntimeError("Clé Gemini manquante")
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.25,
            response_mime_type="text/plain",
        )
        chat = self.client.aio.chats.create(model=self.model, config=config)
        response = await chat.send_message(prompt)
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Réponse Gemini vide")
        return text

    async def health_check(self) -> bool:
        return bool(self.client)

def create_model_provider() -> ModelProvider:
    settings = get_settings()
    if settings.model_provider.lower() == "gemini":
        return GeminiModelProvider()
    return OllamaModelProvider()

class ModelGateway:
    def __init__(self, provider: ModelProvider): self.provider = provider
    async def generate(self, prompt: str, *, system: str = "") -> str:
        if not prompt.strip(): raise ValueError("Prompt vide")
        return await self.provider.generate(prompt[:16000], system=system[:8000])
