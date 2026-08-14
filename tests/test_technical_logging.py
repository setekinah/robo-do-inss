from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.technical_logging import log_technical_event, read_recent_events


class TechnicalLoggingTests(unittest.TestCase):
    def test_log_is_structured_local_and_masks_sensitive_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            record = log_technical_event(
                Path(directory), event="document.processing_failed", level="error", component="document_pipeline",
                correlation_id="case-12", context={"attendance_id": 12, "document_name": "CNIS.pdf", "cpf": "123", "reason": "invalid_pdf"},
            )
            events = read_recent_events(Path(directory))
        self.assertEqual(record["context"]["attendance_id"], 12)
        self.assertEqual(record["context"]["document_name"], "[redacted]")
        self.assertEqual(record["context"]["cpf"], "[redacted]")
        self.assertEqual(events[0]["event"], "document.processing_failed")
        self.assertEqual(events[0]["correlation_id"], "case-12")

    def test_invalid_level_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                log_technical_event(Path(directory), event="test", level="debug", component="tests")


if __name__ == "__main__":
    unittest.main()
