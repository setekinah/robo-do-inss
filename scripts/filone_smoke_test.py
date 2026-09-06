"""Manual real smoke test for the private Fil One development bucket.

Run only after the ignored .env is configured locally. It never prints keys,
credentials, presigned URLs or object paths, and always attempts cleanup.
"""

from __future__ import annotations

import sys
import urllib.request
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filone_storage import FilOneStorageService, StorageConfigurationError


MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def main() -> int:
    try:
        storage = FilOneStorageService.from_environment()
    except StorageConfigurationError as exc:
        print(f"SMOKE BLOCKED: {exc}")
        return 2

    key = f"smoke-tests/{uuid.uuid4().hex}.pdf"
    exit_code = 0
    try:
        storage._client.head_bucket(Bucket=storage._config.bucket)
        print("PASS: autenticação e acesso ao bucket")

        put_url = storage.create_presigned_upload_url(key=key, content_type="application/pdf", expires_in=120)
        request = urllib.request.Request(put_url, data=MINIMAL_PDF, method="PUT", headers={"Content-Type": "application/pdf"})
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("Presigned PUT não foi aceito.")
        print("PASS: presigned PUT e upload fictício")

        metadata = storage.get_metadata(key=key)
        if metadata["size_bytes"] != len(MINIMAL_PDF):
            raise RuntimeError("HeadObject retornou tamanho inesperado.")
        print("PASS: HeadObject")

        get_url = storage.create_presigned_download_url(key=key, expires_in=120)
        with urllib.request.urlopen(get_url, timeout=30) as response:
            downloaded = response.read()
        if downloaded != MINIMAL_PDF:
            raise RuntimeError("Presigned GET retornou conteúdo diferente.")
        print("PASS: presigned GET e verificação do arquivo")
    except Exception as exc:
        print(f"SMOKE FAILED: {type(exc).__name__}: {exc}")
        exit_code = 1
    finally:
        try:
            storage.delete(key=key)
            if storage.exists(key=key):
                raise RuntimeError("Objeto continuou visível após exclusão.")
            print("PASS: exclusão e confirmação de ausência")
        except Exception as cleanup_error:
            print(f"CLEANUP FAILED: {type(cleanup_error).__name__}: {cleanup_error}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
