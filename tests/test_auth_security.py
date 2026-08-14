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
        auth_security.CREDENTIALS_PATH = Path(self.temporary_directory.name) / "credentials.json"

    def tearDown(self) -> None:
        auth_security.CREDENTIALS_PATH = self.original_credentials_path
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

    def test_failed_logins_start_a_temporary_lockout(self) -> None:
        attempts = 0
        lockout_until = None
        for _ in range(auth_security.MAX_FAILED_LOGIN_ATTEMPTS):
            attempts, lockout_until = auth_security.register_failed_login(attempts, now=100.0)

        self.assertEqual(attempts, 0)
        self.assertEqual(lockout_until, 100.0 + auth_security.LOGIN_LOCKOUT_SECONDS)
        self.assertEqual(auth_security.get_login_lockout_remaining(lockout_until, now=100.0), 300)
        self.assertEqual(auth_security.get_login_lockout_remaining(lockout_until, now=400.0), 0)

    def test_failed_logins_are_throttled_across_browser_sessions(self) -> None:
        auth_security.save_credentials("advogado@exemplo.com.br", "SenhaForte2026")

        for _ in range(auth_security.MAX_FAILED_LOGIN_ATTEMPTS):
            self.assertFalse(auth_security.verify_credentials("advogado@exemplo.com.br", "SenhaErrada2026"))

        self.assertGreater(auth_security.get_persistent_login_lockout_remaining(), 0)
        self.assertFalse(auth_security.verify_credentials("advogado@exemplo.com.br", "SenhaForte2026"))


if __name__ == "__main__":
    unittest.main()
