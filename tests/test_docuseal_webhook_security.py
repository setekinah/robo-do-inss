from pathlib import Path
import unittest


class DocuSealWebhookSecurityTests(unittest.TestCase):
    def test_verified_webhook_uses_authenticated_payload_digest_for_idempotency(self):
        source = Path("api_server.py").read_text(encoding="utf-8")

        self.assertIn("hashlib.sha256(raw_body).hexdigest()", source)
        self.assertIn('event_key = f"docuseal:{event_type}:{reference}:{payload_digest}"', source)
        self.assertIn("verify_webhook_signature(raw_body", source)


if __name__ == "__main__":
    unittest.main()
