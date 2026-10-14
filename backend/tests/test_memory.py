import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from app import memory


class MemoryTests(unittest.TestCase):
    def test_persistence_and_user_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            with patch.object(memory, "_path", return_value=path), patch.object(memory, "get_settings", return_value=SimpleNamespace(database_url="")):
                memory.remember("a", "Je préfère apprendre avec des exemples.")
                self.assertIn("examples", memory.relevant("a", "Comment je m'appelle ?"))
                self.assertEqual(memory.relevant("b", "Comment je m'appelle ?"), "")
                self.assertEqual(json.loads(path.read_text())["a"]["preference:examples"], "examples")

    def test_explicit_fact_survives_between_conversations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            with patch.object(memory, "_path", return_value=path), patch.object(memory, "get_settings", return_value=SimpleNamespace(database_url="")):
                memory.remember("student", "Retiens que mon examen de biologie est le 12 novembre")
                context = memory.relevant("student", "Quand est mon examen de biologie ?")
                self.assertIn("examen de biologie est le 12 novembre", context)
                self.assertEqual(memory.snapshot("student")["facts"][0]["content"], "mon examen de biologie est le 12 novembre")

    def test_secrets_are_never_saved_as_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            with patch.object(memory, "_path", return_value=path), patch.object(memory, "get_settings", return_value=SimpleNamespace(database_url="")):
                memory.remember("student", "Retiens que mon mot de passe est azerty123")
                self.assertEqual(memory.relevant("student", "mot de passe"), "")


if __name__ == "__main__":
    unittest.main()
