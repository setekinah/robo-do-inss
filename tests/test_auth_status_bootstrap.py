"""Regressão para o bootstrap de autenticação (issue: loadData() podia
disparar antes de a aplicação saber se havia sessão válida).

Cobre o contrato de /api/auth/status usado pelo front-end (app.js:
AppEngine.bootstrap/checkAuthStatus):

- não autenticado -> {"configured": ..., "authenticated": False}, sem dados
  de escritório e sem qualquer token de sessão na resposta;
- autenticado -> {"configured": True, "authenticated": True, "office_name":
  ..., "oab": ...}, ainda sem token de sessão na resposta;
- endpoints protegidos (ex.: /api/stats) continuam recusando acesso sem
  sessão válida com 401 puro, nunca com um corpo que pareça dados reais;
- logout revoga a sessão de fato: uma chamada subsequente a
  /api/auth/status com o mesmo cookie volta a reportar authenticated=False.

Os testes sobem o próprio SofiPreviRequestHandler em uma porta efêmera e
isolam os dados redirecionando auth_security.CREDENTIALS_PATH,
office_settings.SETTINGS_PATH e database.DB_PATH para diretórios
temporários — o mesmo padrão já usado em test_auth_security.py e
test_automation_orchestrator.py.
"""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import api_server
import auth_security
import database
import office_settings


class _ServerFixture:
    """Sobe o SofiPreviRequestHandler real em uma porta livre da máquina de teste."""

    def __init__(self) -> None:
        self.httpd = api_server.ThreadingHTTPServer(("127.0.0.1", 0), api_server.SofiPreviRequestHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def request(self, method: str, path: str, body: dict | None = None, cookie: str | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        try:
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            raw = response.read()
            set_cookie = response.getheader("Set-Cookie")
            return response.status, raw, set_cookie
        finally:
            conn.close()

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def _extract_session_cookie(set_cookie_header: str | None) -> str:
    assert set_cookie_header, "Login/registro deveria definir o cookie sofia_session."
    return set_cookie_header.split(";", 1)[0]


class AuthStatusBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

        self.original_credentials_path = auth_security.CREDENTIALS_PATH
        self.original_settings_path = office_settings.SETTINGS_PATH
        self.original_db_path = database.DB_PATH
        self.original_sessions = dict(auth_security._SESSIONS)

        auth_security.CREDENTIALS_PATH = Path(self.temp_dir.name) / "auth_credentials.json"
        office_settings.SETTINGS_PATH = Path(self.temp_dir.name) / "office_settings.json"
        database.DB_PATH = Path(self.temp_dir.name) / "auth_status_bootstrap.db"
        auth_security._SESSIONS.clear()
        database.init_database()

        self.server = _ServerFixture()

    def tearDown(self) -> None:
        self.server.shutdown()
        auth_security.CREDENTIALS_PATH = self.original_credentials_path
        office_settings.SETTINGS_PATH = self.original_settings_path
        database.DB_PATH = self.original_db_path
        auth_security._SESSIONS.clear()
        auth_security._SESSIONS.update(self.original_sessions)
        self.temp_dir.cleanup()

    def test_status_before_any_account_reports_not_configured_and_not_authenticated(self) -> None:
        status, raw, set_cookie = self.server.request("GET", "/api/auth/status")

        self.assertEqual(status, 200)
        self.assertIsNone(set_cookie, "GET /api/auth/status nunca deve definir cookie.")
        data = json.loads(raw)
        self.assertEqual(data, {"configured": False, "authenticated": False})
        self.assertNotIn("office_name", data)
        self.assertNotIn("oab", data)

    def test_protected_endpoint_rejects_unauthenticated_request_without_fake_data(self) -> None:
        status, raw, _ = self.server.request("GET", "/api/stats")

        self.assertEqual(status, 401)
        data = json.loads(raw)
        # A resposta de 401 deve ser só o erro: nenhuma chave de estatística
        # real (total_atendimentos, stages, ...) pode vazar/ser simulada aqui.
        self.assertEqual(set(data.keys()), {"error"})
        self.assertNotIn("total_atendimentos", data)
        self.assertNotIn("stages", data)

    def test_register_authenticates_session_and_status_reflects_it_without_leaking_token(self) -> None:
        register_status, register_raw, set_cookie = self.server.request(
            "POST",
            "/api/auth/register",
            body={
                "email": "advogada@exemplo.com.br",
                "password": "SenhaForte2026",
                "office_name": "Escritorio Exemplo",
                "oab": "12345",
            },
        )
        self.assertEqual(register_status, 201)
        self.assertTrue(json.loads(register_raw)["success"])
        cookie = _extract_session_cookie(set_cookie)
        session_token = cookie.split("=", 1)[1]

        status, raw, status_set_cookie = self.server.request("GET", "/api/auth/status", cookie=cookie)

        self.assertEqual(status, 200)
        self.assertIsNone(status_set_cookie, "GET /api/auth/status não deve reemitir/expor cookie.")
        data = json.loads(raw)
        self.assertEqual(data["configured"], True)
        self.assertEqual(data["authenticated"], True)
        self.assertEqual(data["office_name"], "Escritorio Exemplo")
        self.assertEqual(data["oab"], "12345")
        # O token de sessão em si nunca deve aparecer no corpo da resposta.
        self.assertNotIn(session_token, raw.decode("utf-8"))

        # Com sessão válida, o endpoint protegido também deve responder de
        # verdade (sem exigir novo login) — dados reais, não simulados.
        stats_status, stats_raw, _ = self.server.request("GET", "/api/stats", cookie=cookie)
        self.assertEqual(stats_status, 200)
        self.assertIn("total_atendimentos", json.loads(stats_raw))

    def test_logout_revokes_session_so_status_reports_not_authenticated_again(self) -> None:
        _, _, set_cookie = self.server.request(
            "POST",
            "/api/auth/register",
            body={
                "email": "advogado2@exemplo.com.br",
                "password": "SenhaForte2026",
                "office_name": "Outro Escritorio",
                "oab": "54321",
            },
        )
        cookie = _extract_session_cookie(set_cookie)

        logout_status, _, _ = self.server.request("POST", "/api/auth/logout", cookie=cookie)
        self.assertEqual(logout_status, 204)

        status, raw, _ = self.server.request("GET", "/api/auth/status", cookie=cookie)
        data = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertFalse(data["authenticated"])
        self.assertNotIn("office_name", data)

        # E a rota protegida volta a recusar a sessão revogada.
        stats_status, _, _ = self.server.request("GET", "/api/stats", cookie=cookie)
        self.assertEqual(stats_status, 401)


if __name__ == "__main__":
    unittest.main()
