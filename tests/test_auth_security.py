from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import auth_security


class AuthSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.original_credentials_path = auth_security.CREDENTIALS_PATH
        self.original_sessions = dict(auth_security._SESSIONS)
        auth_security.CREDENTIALS_PATH = Path(self.temporary_directory.name) / "credentials.json"

    def tearDown(self) -> None:
        auth_security.CREDENTIALS_PATH = self.original_credentials_path
        auth_security._SESSIONS.clear()
        auth_security._SESSIONS.update(self.original_sessions)
        self.temporary_directory.cleanup()

    def test_password_is_hashed_and_credentials_are_verified(self) -> None:
        password = "SenhaForte2026"

        auth_security.save_credentials("ADVOGADO@EXEMPLO.COM.BR", password)

        stored = json.loads(auth_security.CREDENTIALS_PATH.read_text(encoding="utf-8"))
        self.assertNotIn(password, auth_security.CREDENTIALS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(stored["email"], "advogado@exemplo.com.br")
        self.assertTrue(auth_security.verify_credentials("advogado@exemplo.com.br", password))
        self.assertFalse(auth_security.verify_credentials("outro@exemplo.com.br", password))
        self.assertFalse(auth_security.verify_credentials("advogado@exemplo.com.br", "SenhaErrada2026"))

    def test_invalid_registration_data_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            auth_security.save_credentials("email-invalido", "SenhaForte2026")
        with self.assertRaises(ValueError):
            auth_security.save_credentials("advogado@exemplo.com.br", "fraca")

    def test_corrupted_credentials_file_is_not_accepted(self) -> None:
        auth_security.CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        auth_security.CREDENTIALS_PATH.write_text("{arquivo-corrompido", encoding="utf-8")

        self.assertFalse(auth_security.credentials_configured())
        self.assertFalse(auth_security.verify_credentials("advogado@exemplo.com.br", "SenhaForte2026"))

    def test_field_validators_cover_common_errors(self) -> None:
        self.assertIsNone(auth_security.validate_email("advogado@exemplo.com.br"))
        self.assertIsNotNone(auth_security.validate_email("advogado"))
        self.assertIsNone(auth_security.validate_password("SenhaForte2026"))
        self.assertIsNotNone(auth_security.validate_password("senhafraca"))
        self.assertIsNone(auth_security.validate_whatsapp("(11) 99999-9999"))
        self.assertIsNotNone(auth_security.validate_whatsapp("123"))

    def test_session_store_is_bounded_and_revocable(self) -> None:
        original_limit = auth_security.MAX_ACTIVE_SESSIONS
        auth_security.MAX_ACTIVE_SESSIONS = 2
        try:
            first = auth_security.create_session()
            auth_security.create_session()
            third = auth_security.create_session()
            self.assertLessEqual(len(auth_security._SESSIONS), 2)
            auth_security.revoke_session(third)
            self.assertFalse(auth_security.verify_session(third))
            self.assertFalse(auth_security.verify_session(first))
        finally:
            auth_security.MAX_ACTIVE_SESSIONS = original_limit


if __name__ == "__main__":
    unittest.main()
