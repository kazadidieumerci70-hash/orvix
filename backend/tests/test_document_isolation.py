import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import UploadFile
from starlette.datastructures import Headers
from app import documents


class DocumentIsolationTests(unittest.TestCase):
    def test_users_only_retrieve_owned_documents(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                root = Path(d); owners = root / "owners.json"; deleted = root / "deleted.json"; upload_dir = root / "uploads"; upload_dir.mkdir()
                settings = type("S", (), {"upload_dir": upload_dir, "document_owners_file": owners, "deleted_documents_file": deleted, "max_upload_bytes": 10000})()
                with patch.object(documents, "get_settings", return_value=settings):
                    for user, name, content in (("x", "x.txt", b"ALPHA-123"), ("y", "y.txt", b"BETA-456")):
                        upload = UploadFile(filename=name, file=__import__('io').BytesIO(content), headers=Headers({"content-type":"text/plain"}))
                        await documents.save_document(user, upload)
                    x = documents.list_documents("x"); y = documents.list_documents("y")
                    self.assertEqual(len(x), 1); self.assertEqual(len(y), 1)
                    self.assertEqual(documents.document_context("x", [y[0].id], query="code"), "")
                    self.assertIn("ALPHA-123", documents.document_context("x", [x[0].id], query="code"))
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
