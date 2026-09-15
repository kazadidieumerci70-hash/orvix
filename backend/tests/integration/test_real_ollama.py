import asyncio
import time
import unittest

from app.model_gateway import ModelGateway, OllamaModelProvider


class RealOllamaIntegrationTest(unittest.TestCase):
    def test_real_qwen_generation(self):
        async def run():
            provider = OllamaModelProvider()
            self.assertTrue(await provider.health_check())
            started = time.perf_counter()
            text = await ModelGateway(provider).generate(
                "Bonjour ORVIX, présente-toi en une phrase.",
                system="Tu es ORVIX, assistant local. Ne te présente jamais comme un service cloud.",
            )
            return text, time.perf_counter() - started
        text, elapsed = asyncio.run(run())
        self.assertTrue(text)
        self.assertLess(elapsed, 90)
        print(f"REAL_OLLAMA_TEST latency_seconds={elapsed:.2f}")


if __name__ == "__main__":
    unittest.main()
