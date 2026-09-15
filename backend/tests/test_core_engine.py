import asyncio
import unittest

from app.core_engine import OrvixCoreEngine


class FakeGateway:
    async def generate(self, prompt, *, system=""):
        return "Réponse locale ORVIX"


class CoreEngineTests(unittest.TestCase):
    def test_intents_and_structured_response(self):
        engine = OrvixCoreEngine(FakeGateway())
        result = asyncio.run(engine.generate(user_id="u1", session_id="s1", message="Pourquoi cela ?"))
        self.assertEqual(result["intent"], "question")
        self.assertEqual(result["response"]["content"], "Réponse locale ORVIX")
        self.assertEqual(result["metadata"]["sessionId"], "s1")

    def test_empty_message_rejected(self):
        with self.assertRaises(ValueError):
            OrvixCoreEngine().process(user_id="u1", session_id="s1", message="   ")


if __name__ == "__main__":
    unittest.main()
