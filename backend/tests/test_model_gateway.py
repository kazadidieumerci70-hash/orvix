import asyncio
import unittest

from app.model_gateway import ModelGateway


class Provider:
    async def generate(self, prompt, *, system=""):
        return "ok"


class FailingProvider:
    async def generate(self, prompt, *, system=""):
        raise RuntimeError("provider unavailable")


class GatewayTests(unittest.TestCase):
    def test_normalizes_and_delegates(self):
        self.assertEqual(asyncio.run(ModelGateway(Provider()).generate(" hello ")), "ok")

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            asyncio.run(ModelGateway(Provider()).generate(" "))

    def test_provider_error_is_not_fallback(self):
        with self.assertRaises(RuntimeError):
            asyncio.run(ModelGateway(FailingProvider()).generate("hello"))


if __name__ == "__main__":
    unittest.main()
