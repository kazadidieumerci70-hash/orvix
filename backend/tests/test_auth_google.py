import os
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


if __name__ == "__main__":
    unittest.main()
