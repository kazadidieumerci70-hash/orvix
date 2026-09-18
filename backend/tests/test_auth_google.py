import os
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app import auth


class GoogleAuthRegressionTests(unittest.TestCase):
    def test_existing_google_account_is_recognized_on_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = SimpleNamespace(
                database_url="",
                users_file=Path(directory) / "users.json",
                orvix_auth_secret="test-secret",
            )
            google_info = {
                "email": "known@example.com",
                "email_verified": True,
                "name": "Known User",
            }
            with patch.object(auth, "get_settings", return_value=settings), patch.dict(os.environ, {"GOOGLE_CLIENT_ID": "test-client"}), patch(
                "google.oauth2.id_token.verify_oauth2_token", return_value=google_info
            ):
                _, first_user, first_existing = auth.google_login_user("credential")
                _, returning_user, returning_existing = auth.google_login_user("credential")

            self.assertFalse(first_existing)
            self.assertFalse(first_user.onboarding_completed)
            self.assertTrue(returning_existing)
            self.assertTrue(returning_user.onboarding_completed)
            self.assertEqual(first_user.id, returning_user.id)

    def test_file_session_recovers_user_by_google_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            users_file = Path(directory) / "users.json"
            users_file.write_text(
                json.dumps({"users": [{"id": "legacy-id", "phone": "known@example.com", "name": "Known User"}]}),
                encoding="utf-8",
            )
            settings = SimpleNamespace(database_url="", users_file=users_file, orvix_auth_secret="test-secret")
            with patch.object(auth, "get_settings", return_value=settings):
                token = auth._make_token("new-id", "known@example.com")
                profile = auth.current_user(f"Bearer {token}")

            self.assertEqual(profile.id, "legacy-id")
            self.assertEqual(profile.phone, "known@example.com")


if __name__ == "__main__":
    unittest.main()
