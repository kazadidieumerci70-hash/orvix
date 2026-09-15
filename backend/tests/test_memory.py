import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import memory


class MemoryTests(unittest.TestCase):
    def test_persistence_and_user_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            with patch.object(memory, "_path", return_value=path):
                memory.remember("a", "Je m'appelle Alice.")
                self.assertIn("Alice", memory.relevant("a", "Comment je m'appelle ?"))
                self.assertEqual(memory.relevant("b", "Comment je m'appelle ?"), "")
                self.assertEqual(json.loads(path.read_text())["a"]["prenom"], "Alice")


if __name__ == "__main__":
    unittest.main()
