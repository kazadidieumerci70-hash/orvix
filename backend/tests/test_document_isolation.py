import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import UploadFile
from starlette.datastructures import Headers
from app import documents, document_memory


class DocumentIsolationTests(unittest.TestCase):
    def test_users_only_retrieve_owned_documents(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); owners = root / "owners.json"; deleted = root / "deleted.json"; upload_dir = root / "uploads"; upload_dir.mkdir()
                settings = type("S", (), {"upload_dir": upload_dir, "database_url": "", "data_dir": root, "document_owners_file": owners, "deleted_documents_file": deleted, "max_upload_bytes": 10000})()
                with patch.object(documents, "get_settings", return_value=settings), patch.object(document_memory, "get_settings", return_value=settings), patch.object(documents, "document_upload_limit_bytes", return_value=10000):
                    for user, name, content in (("x", "x.txt", b"ALPHA-123"), ("y", "y.txt", b"BETA-456")):
                        upload = UploadFile(filename=name, file=__import__('io').BytesIO(content), headers=Headers({"content-type":"text/plain"}))
                        await documents.save_document(user, upload)
                    x = documents.list_documents("x"); y = documents.list_documents("y")
                    self.assertEqual(len(x), 1); self.assertEqual(len(y), 1)
                    self.assertEqual(documents.document_context("x", [y[0].id], query="code"), "")
                    self.assertIn("ALPHA-123", documents.document_context("x", [x[0].id], query="code"))
        asyncio.run(run())

    def test_unreadable_text_document_is_rejected(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); upload_dir = root / "uploads"; upload_dir.mkdir()
                settings = type("S", (), {"upload_dir": upload_dir, "database_url": "", "data_dir": root, "document_owners_file": root / "owners.json", "deleted_documents_file": root / "deleted.json", "max_upload_bytes": 10000})()
                upload = UploadFile(filename="vide.txt", file=__import__('io').BytesIO(b"   \n\t  "), headers=Headers({"content-type":"text/plain"}))
                with patch.object(documents, "get_settings", return_value=settings), patch.object(document_memory, "get_settings", return_value=settings), patch.object(documents, "document_upload_limit_bytes", return_value=10000):
                    with self.assertRaises(__import__('fastapi').HTTPException) as error:
                        await documents.save_document("student", upload)
                    self.assertEqual(error.exception.status_code, 422)
        asyncio.run(run())

    def test_preparation_is_private_to_each_document(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); upload_dir = root / "uploads"; upload_dir.mkdir()
                settings = type("S", (), {"upload_dir": upload_dir, "database_url": "", "data_dir": root, "document_owners_file": root / "owners.json", "deleted_documents_file": root / "deleted.json", "max_upload_bytes": 10000})()
                with patch.object(documents, "get_settings", return_value=settings), patch.object(document_memory, "get_settings", return_value=settings), patch.object(documents, "document_upload_limit_bytes", return_value=10000):
                    for name, content in (("biologie.txt", b"Cellule mitochondrie respiration cellulaire"), ("histoire.txt", b"Revolution empire chronologie historique")):
                        upload = UploadFile(filename=name, file=__import__('io').BytesIO(content), headers=Headers({"content-type":"text/plain"}))
                        await documents.save_document("student", upload)
                    items = documents.list_documents("student")
                cards = {item.name: item.preparation for item in items}
                self.assertEqual(cards["biologie.txt"]["status"], "ready")
                self.assertIn("cellule", cards["biologie.txt"]["keywords"])
                self.assertNotIn("cellule", cards["histoire.txt"]["keywords"])
                self.assertIn("Cellule", cards["biologie.txt"]["overview"])
                self.assertNotIn("Cellule", cards["histoire.txt"]["overview"])
        asyncio.run(run())

    def test_existing_documents_are_prepared_without_crossing_owners(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); upload_dir = root / "uploads"; upload_dir.mkdir()
            (upload_dir / "cours_a.txt").write_text("Cellule et membrane.", encoding="utf-8")
            (upload_dir / "cours_b.txt").write_text("Révolution et chronologie.", encoding="utf-8")
            settings = type("S", (), {"upload_dir": upload_dir, "database_url": "", "data_dir": root, "document_owners_file": root / "owners.json", "deleted_documents_file": root / "deleted.json"})()
            settings.document_owners_file.write_text('{"owners":{"cours_a.txt":"a","cours_b.txt":"b"}}', encoding="utf-8")
            with patch.object(documents, "get_settings", return_value=settings), patch.object(document_memory, "get_settings", return_value=settings):
                documents.prepare_existing_documents()
                a = documents.list_documents("a")[0]
                b = documents.list_documents("b")[0]
            self.assertEqual(a.preparation["status"], "ready")
            self.assertIn("cellule", a.preparation["keywords"])
            self.assertNotIn("cellule", b.preparation["keywords"])


if __name__ == "__main__":
    unittest.main()
