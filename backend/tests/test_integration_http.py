import asyncio
import unittest
from httpx import ASGITransport, AsyncClient
from app.main import app


class HttpIntegrationTests(unittest.TestCase):
    def test_health_reports_local_provider(self):
        async def run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.get("/health")
                return r
        response = asyncio.run(run())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["provider"], "ollama")
        self.assertEqual(data["model"], "qwen2.5:3b")

    def test_chat_requires_authentication(self):
        async def run():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                return await c.post("/api/v1/chat", json={"message": "Bonjour ORVIX"})
        self.assertEqual(asyncio.run(run()).status_code, 401)


if __name__ == "__main__":
    unittest.main()
