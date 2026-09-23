import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import documents


class DocumentSourceTests(unittest.TestCase):
    def test_text_source_keeps_document_and_passage_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload_dir = root / "uploads"
            upload_dir.mkdir()
            source = upload_dir / "anatomie.txt"
            source.write_text("Le néphron participe à la filtration du sang.", encoding="utf-8")
            settings = type("S", (), {
                "upload_dir": upload_dir,
                "document_owners_file": root / "owners.json",
                "deleted_documents_file": root / "deleted.json",
            })()
            settings.document_owners_file.write_text('{"owners":{"anatomie.txt":"student"}}', encoding="utf-8")
            with patch.object(documents, "get_settings", return_value=settings):
                document = documents.list_documents("student")[0]
                context, sources = documents.document_context_with_sources(
                    "student", [document.id], query="néphron filtration"
                )
            self.assertIn("anatomie.txt", context)
            self.assertEqual(sources[0]["document_name"], "anatomie.txt")
            self.assertEqual(sources[0]["location"], "passage 1")
            self.assertIn("filtration du sang", sources[0]["excerpt"])


if __name__ == "__main__":
    unittest.main()
