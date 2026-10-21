import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import documents, document_memory


class DocumentSourceTests(unittest.TestCase):
    def test_text_source_keeps_document_and_passage_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upload_dir = root / "uploads"
            upload_dir.mkdir()
            source = upload_dir / "anatomie.txt"
            source.write_text("Le néphron participe à la filtration du sang.", encoding="utf-8")
            settings = type("S", (), {
                "upload_dir": upload_dir, "database_url": "", "data_dir": root,
                "document_owners_file": root / "owners.json",
                "deleted_documents_file": root / "deleted.json",
            })()
            settings.document_owners_file.write_text('{"owners":{"anatomie.txt":"student"}}', encoding="utf-8")
            with patch.object(documents, "get_settings", return_value=settings), patch.object(document_memory, "get_settings", return_value=settings), patch.object(documents, "document_upload_limit_bytes", return_value=10000):
                document = documents.list_documents("student")[0]
                context, sources = documents.document_context_with_sources(
                    "student", [document.id], query="néphron filtration"
                )
            self.assertIn("anatomie.txt", context)
            self.assertEqual(sources[0]["document_name"], "anatomie.txt")
            self.assertEqual(sources[0]["location"], "passage 1")
            self.assertIn("filtration du sang", sources[0]["excerpt"])

    def test_multiple_documents_each_receive_a_source_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); upload_dir = root / "uploads"; upload_dir.mkdir()
            (upload_dir / "bio.txt").write_text("La cellule contient une membrane et un noyau.", encoding="utf-8")
            (upload_dir / "physique.txt").write_text("La force produit une accélération mesurable.", encoding="utf-8")
            settings = type("S", (), {"upload_dir": upload_dir, "database_url": "", "data_dir": root, "document_owners_file": root / "owners.json", "deleted_documents_file": root / "deleted.json"})()
            settings.document_owners_file.write_text('{"owners":{"bio.txt":"student","physique.txt":"student"}}', encoding="utf-8")
            with patch.object(documents, "get_settings", return_value=settings), patch.object(document_memory, "get_settings", return_value=settings):
                ids = [item.id for item in documents.list_documents("student")]
                _, sources = documents.document_context_with_sources("student", ids, query="explique", max_sources=2)
            self.assertEqual({source["document_name"] for source in sources}, {"bio.txt", "physique.txt"})

    def test_unrelated_question_returns_no_document_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); upload_dir = root / "uploads"; upload_dir.mkdir()
            (upload_dir / "bio.txt").write_text("La cellule contient une membrane et un noyau.", encoding="utf-8")
            settings = type("S", (), {"upload_dir": upload_dir, "database_url": "", "data_dir": root, "document_owners_file": root / "owners.json", "deleted_documents_file": root / "deleted.json"})()
            settings.document_owners_file.write_text('{"owners":{"bio.txt":"student"}}', encoding="utf-8")
            with patch.object(documents, "get_settings", return_value=settings), patch.object(document_memory, "get_settings", return_value=settings):
                document = documents.list_documents("student")[0]
                context, sources = documents.document_context_with_sources("student", [document.id], query="Quelle est la capitale du Japon ?")
            self.assertEqual(context, "")
            self.assertEqual(sources, [])


if __name__ == "__main__":
    unittest.main()
