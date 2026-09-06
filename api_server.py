"""Servidor REST HTTP em Python puro para a interface revolucionaria do SOFI.IA PREVI (PrevIA)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.parse
import time
import uuid
from datetime import UTC, datetime, timedelta
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

# Adiciona o diretorio do projeto ao path de importacao
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import auth_security
import cnis_knowledge
import database
import docuseal_integration
import document_audit
import document_intelligence
import document_rules
from filone_storage import FilOneStorageService, StorageConfigurationError, build_storage_key, validate_upload_metadata
import official_catalog
import office_settings
import retirement_prefilter
import retirement_dossier
from modules.pdf_generator import build_review_draft_pdf
from flows_data import FLOW_DEFINITIONS
from triage_engine import answer_current_question, create_state, get_current_node, get_result

# Garante inicializacao do banco de dados na partida
database.init_database()
database.register_official_sources(list(official_catalog.OFFICIAL_SOURCE_REGISTRY))


class SofiPreviRequestHandler(SimpleHTTPRequestHandler):
    """Handler HTTP customizado para API REST e arquivos estaticos."""

    # O servidor web nunca deve funcionar como um explorador do diretório do
    # projeto.  Código, logs, banco, .git e eventuais arquivos de configuração
    # são deliberadamente inacessíveis pela porta HTTP.
    STATIC_FILES = {"/index.html", "/styles.css", "/app.js", "/flows.js", "/portal.html", "/portal.js"}
    MAX_JSON_BODY_BYTES = 256 * 1024
    MAX_RATE_BUCKETS = 2_048

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self) -> None:
        """Add baseline browser protections to every response, including errors."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # Scripts são somente arquivos locais versionados; handlers inline são
        # proibidos para reduzir o impacto de qualquer futura falha de XSS.
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "script-src 'self'; connect-src 'self'",
        )
        super().end_headers()

    def _send_json(self, data: dict | list, status_code: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_pdf(self, payload: bytes, filename: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    _rate_windows: dict[str, list[float]] = {}

    def _rate_bucket(self) -> str:
        """Avoid unbounded memory consumption from attacker-controlled paths."""
        path = urllib.parse.urlparse(self.path).path
        normalized = re.sub(r"/\\d+(?=/|$)", "/:id", path)
        if not normalized.startswith("/api/"):
            normalized = "/static"
        return f"{self.client_address[0]}:{self.command}:{normalized}"

    def _session_token(self) -> str:
        cookies = self.headers.get("Cookie", "")
        for item in cookies.split(";"):
            name, _, value = item.strip().partition("=")
            if name == "sofia_session":
                return value
        return ""

    def _require_auth(self) -> bool:
        if auth_security.verify_session(self._session_token()):
            return True
        self._send_json({"error": "Autenticação necessária."}, 401)
        return False

    def _allow_request(self, limit: int = 60, window_seconds: int = 60) -> bool:
        ip = self.client_address[0]
        now = time.monotonic()
        key = self._rate_bucket()
        if len(self._rate_windows) >= self.MAX_RATE_BUCKETS and key not in self._rate_windows:
            # Descarta janelas expiradas antes de aceitar uma nova chave. Se a
            # pressão persistir, o pedido é rejeitado sem crescer a estrutura.
            self._rate_windows = {
                bucket: values
                for bucket, values in self._rate_windows.items()
                if any(value > now - window_seconds for value in values)
            }
            if len(self._rate_windows) >= self.MAX_RATE_BUCKETS:
                self._send_json({"error": "Servidor temporariamente ocupado."}, 429)
                return False
        recent = [value for value in self._rate_windows.get(key, []) if value > now - window_seconds]
        if len(recent) >= limit:
            self._rate_windows[key] = recent
            self._send_json({"error": "Muitas tentativas. Aguarde um minuto."}, 429)
            return False
        recent.append(now)
        self._rate_windows[key] = recent
        return True

    def _send_session_cookie(self, token: str) -> None:
        secure = "; Secure" if os.environ.get("ROBO_INSS_COOKIE_SECURE") == "1" else ""
        self.send_header(
            "Set-Cookie",
            f"sofia_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={auth_security.SESSION_TTL_SECONDS}{secure}",
        )

    def _read_json_body(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError as exc:
            raise ValueError("Content-Length inválido.") from exc
        if content_length == 0:
            return {}
        if content_length < 0 or content_length > self.MAX_JSON_BODY_BYTES:
            raise ValueError("Corpo JSON excede o limite permitido.")
        body = self.rfile.read(content_length).decode("utf-8")
        return json.loads(body) if body else {}

    def _read_uploaded_document(self) -> tuple[dict[str, str], str, bytes] | None:
        """Lê um único upload multipart, exclusivamente para processamento local."""
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            return None
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if not 0 < content_length <= document_intelligence.MAX_FILE_BYTES + 1024 * 1024:
            return None
        payload = self.rfile.read(content_length)
        message = BytesParser(policy=email_policy).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + payload
        )
        fields: dict[str, str] = {}
        file_name = ""
        file_content = b""
        for part in message.iter_parts():
            field_name = part.get_param("name", header="content-disposition")
            if not field_name:
                continue
            value = part.get_payload(decode=True) or b""
            received_name = part.get_filename()
            if received_name and field_name == "file":
                file_name = Path(received_name).name
                file_content = value
            elif not received_name:
                fields[field_name] = value.decode("utf-8", errors="replace")
        return (fields, file_name, file_content) if file_name and file_content else None

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        public_portal = path == "/api/portal/resumo"
        if path.startswith("/api/") and path != "/api/auth/status" and not public_portal:
            if not self._allow_request() or not self._require_auth():
                return
        if public_portal and not self._allow_request(12):
            return

        # Rotas API
        if path == "/api/auth/status":
            self.handle_get_auth_status()
        elif path == "/api/portal/resumo":
            # O token nunca é aceito por query string: links usam fragmento no
            # navegador para não aparecer em logs do servidor ou Referer.
            self._send_json({"error": "Use POST para consultar o portal."}, 405)
        elif path == "/api/office":
            self.handle_get_office()
        elif path == "/api/stats":
            self.handle_get_stats()
        elif path == "/api/pendencias-inteligentes":
            self.handle_get_intelligent_pending_items()
        elif path == "/api/atendimentos":
            self.handle_get_atendimentos(query)
        elif path == "/api/relacionamento":
            self.handle_get_relacionamento()
        elif path.startswith("/api/atendimentos/") and path.endswith("/auditoria-documental"):
            attendance_id = path.split("/")[3]
            self.handle_get_document_audit(int(attendance_id))
        elif path.startswith("/api/atendimentos/") and path.endswith("/matriz-provas"):
            attendance_id = path.split("/")[3]
            self.handle_get_document_evidence_matrix(int(attendance_id))
        elif path.startswith("/api/atendimentos/") and path.endswith("/dossie-probatorio"):
            attendance_id = path.split("/")[3]
            self.handle_get_retirement_dossier(int(attendance_id))
        elif path.startswith("/api/atendimentos/") and path.endswith("/kit-requerimento.pdf"):
            attendance_id = path.split("/")[3]
            self.handle_get_review_draft_pdf(int(attendance_id))
        elif path.startswith("/api/atendimentos/") and path.endswith("/documentos"):
            attendance_id = path.split("/")[3]
            self.handle_get_documentos(int(attendance_id))
        elif path.startswith("/api/atendimentos/") and path.endswith("/download-url"):
            parts = path.split("/")
            self.handle_get_document_download_url(int(parts[3]), parts[5])
        elif path.startswith("/api/atendimentos/") and path.endswith("/contrato"):
            attendance_id = path.split("/")[3]
            self.handle_get_contrato(int(attendance_id))
        elif path.startswith("/api/atendimentos/"):
            attendance_id = path.split("/")[3]
            self.handle_get_atendimento(int(attendance_id))
        elif path == "/api/triagem/fluxos":
            self.handle_get_fluxos()
        elif path == "/api/eventos/fila":
            self.handle_get_eventos()
        elif path == "/api/catalogo-cnis/status":
            self.handle_get_catalog_status()
        elif path == "/api/catalogo-cnis/versoes":
            self.handle_get_catalog_versions()
        elif path == "/api/assinatura/status":
            self._send_json(docuseal_integration.status())
        else:
            requested = "/index.html" if path == "/" else path
            if requested not in self.STATIC_FILES:
                self._send_json({"error": "Recurso não encontrado."}, 404)
                return
            self.path = requested
            super().do_GET()

    def do_POST(self) -> None:
        try:
            self._do_post()
        except (ValueError, json.JSONDecodeError) as exc:
            self.close_connection = True
            status = 413 if "limite" in str(exc).lower() else 400
            self._send_json({"error": str(exc) or "Requisição inválida."}, status)

    def _do_post(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        if path.startswith("/api/assinatura/webhook/"):
            if self._allow_request(30):
                self.handle_post_docuseal_webhook(path.rsplit("/", 1)[-1])
            return
        public_portal = path == "/api/portal/resumo"
        login_limit = 5 if path in {"/api/auth/login", "/api/auth/register"} else (12 if public_portal else 60)
        if not self._allow_request(login_limit):
            return
        if path not in {"/api/auth/login", "/api/auth/register", "/api/portal/resumo"} and not self._require_auth():
            return

        if path == "/api/auth/login":
            self.handle_post_login()
        elif path == "/api/auth/register":
            self.handle_post_register()
        elif path == "/api/auth/logout":
            self.handle_post_logout()
        elif path == "/api/portal/resumo":
            self.handle_post_client_portal_summary()
        elif path == "/api/office":
            self.handle_post_office()
        elif path == "/api/atendimentos":
            self.handle_post_atendimento()
        elif path.startswith("/api/atendimentos/") and path.endswith("/atividades"):
            parts = path.split("/")
            attendance_id = int(parts[3])
            self.handle_post_atividade(attendance_id)
        elif path.startswith("/api/atendimentos/") and path.endswith("/tarefas"):
            parts = path.split("/")
            attendance_id = int(parts[3])
            self.handle_post_tarefa(attendance_id)
        elif path.startswith("/api/atendimentos/") and path.endswith("/assinatura"):
            self.handle_post_assinatura(int(path.split("/")[3]))
        elif path.startswith("/api/atendimentos/") and path.endswith("/portal-acesso"):
            self.handle_post_client_portal_access(int(path.split("/")[3]))
        elif path.startswith("/api/atendimentos/") and path.endswith("/auditoria-documental"):
            self.handle_post_document_audit(int(path.split("/")[3]))
        elif path.startswith("/api/atendimentos/") and path.endswith("/dossie-probatorio"):
            self.handle_post_retirement_dossier(int(path.split("/")[3]))
        elif path.startswith("/api/atendimentos/") and path.endswith("/upload-intents"):
            self.handle_post_document_upload_intent(int(path.split("/")[3]))
        elif path.startswith("/api/documentos/upload-intents/") and path.endswith("/complete"):
            self.handle_post_document_upload_complete(path.split("/")[4])
        elif path == "/api/triagem/executar":
            self.handle_post_triagem_executar()
        elif path == "/api/triagem/aposentadoria/pre-filtro":
            self.handle_post_retirement_prefilter()
        elif path == "/api/documentos/analisar":
            self.handle_post_documento_analisar()
        elif path == "/api/catalogo-cnis/monitorar":
            self.handle_post_monitor_official_sources()
        elif path == "/api/assinatura/verificar":
            self._send_json(docuseal_integration.verify_connection())
        elif path == "/api/catalogo-cnis/importar-planilha":
            self.handle_post_import_catalog_workbook()
        elif path == "/api/catalogo-cnis/importar-anexo-oficial":
            self.handle_post_import_official_indicator_catalog()
        elif path.startswith("/api/catalogo-cnis/versoes/") and path.endswith("/ativar"):
            version_id = int(path.split("/")[4])
            self.handle_post_activate_catalog_version(version_id)
        elif path.startswith("/api/atendimentos/") and path.endswith("/conflito"):
            parts = path.split("/")
            attendance_id = int(parts[3])
            self.handle_post_conflito(attendance_id)
        elif path.startswith("/api/atendimentos/") and path.endswith("/lgpd"):
            parts = path.split("/")
            attendance_id = int(parts[3])
            self.handle_post_lgpd(attendance_id)
        elif path.startswith("/api/atendimentos/") and path.endswith("/reativar"):
            parts = path.split("/")
            self.handle_post_reativar_lead(int(parts[3]))
        else:
            self._send_json({"error": "Rota nao encontrada"}, 404)

    def handle_post_docuseal_webhook(self, path_token: str) -> None:
        """Receive only verified DocuSeal events; no browser session is accepted here."""
        if not docuseal_integration.verify_webhook_path_token(path_token):
            self._send_json({"error": "Webhook não autorizado."}, 401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= self.MAX_JSON_BODY_BYTES:
            self._send_json({"error": "Payload inválido."}, 400)
            return
        raw_body = self.rfile.read(length)
        if not docuseal_integration.verify_webhook_signature(raw_body, self.headers.get("X-Docuseal-Signature", "")):
            self._send_json({"error": "Assinatura do webhook inválida."}, 401)
            return
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "JSON inválido."}, 400)
            return
        event_type = str(payload.get("event_type", ""))
        allowed = {"form.completed", "form.declined", "submission.completed", "submission.expired"}
        if event_type not in allowed:
            self._send_json({"success": True, "ignored": True})
            return
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        submission = data.get("submission") if isinstance(data.get("submission"), dict) else data
        reference = str(submission.get("id") or data.get("submission_id") or data.get("id") or "unknown")
        # O identificador do fornecedor pode chegar novamente com um timestamp
        # de entrega diferente. O hash do corpo autenticado torna o replay da
        # mesma transição idempotente sem guardar o conteúdo sensível no banco.
        payload_digest = hashlib.sha256(raw_body).hexdigest()
        event_key = f"docuseal:{event_type}:{reference}:{payload_digest}"
        safe_payload = {"event_type": event_type, "submission_id": reference, "status": submission.get("status"), "timestamp": payload.get("timestamp")}
        event_id, created = database.enqueue_integration_event(
            event_key=event_key, event_type=event_type, source="docuseal", attendance_id=None,
            external_reference=reference, payload=safe_payload, priority="alta", requires_review=True,
            occurred_at=str(payload.get("timestamp") or ""),
        )
        self._send_json({"success": True, "event_id": event_id, "created": created})

    def do_PUT(self) -> None:
        try:
            self._do_put()
        except (ValueError, json.JSONDecodeError) as exc:
            self.close_connection = True
            status = 413 if "limite" in str(exc).lower() else 400
            self._send_json({"error": str(exc) or "Requisição inválida."}, status)

    def _do_put(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        if not self._allow_request() or not self._require_auth():
            return

        if path.startswith("/api/atendimentos/") and path.endswith("/stage"):
            parts = path.split("/")
            attendance_id = int(parts[3])
            self.handle_put_stage(attendance_id)
        elif path.startswith("/api/documentos/") and path.endswith("/status"):
            parts = path.split("/")
            doc_id = int(parts[3])
            self.handle_put_documento_status(doc_id)
        else:
            self._send_json({"error": "Rota nao encontrada"}, 404)

    # --- Handlers de Autenticacao & Escritorio ---

    def handle_get_auth_status(self) -> None:
        configured = auth_security.credentials_configured()
        self._send_json({"configured": configured})

    def handle_get_office(self) -> None:
        settings = office_settings.load_office_settings()
        self._send_json(settings)

    def handle_post_office(self) -> None:
        body = self._read_json_body()
        office_settings.save_office_settings(body)
        self._send_json({"success": True, "settings": office_settings.load_office_settings()})

    def handle_post_login(self) -> None:
        body = self._read_json_body()
        email = body.get("email", "")
        password = body.get("password", "")

        if not auth_security.credentials_configured():
            self._send_json({"error": "Conta ainda não configurada. Faça o cadastro inicial."}, 403)
            return

        user_email = auth_security.authenticate(email, password)
        if user_email:
            token = auth_security.create_session(user_email)
            self.send_response(200)
            self._send_session_cookie(token)
            payload = json.dumps({"success": True, "email": email}, ensure_ascii=False).encode("utf-8")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self._send_json({"error": "E-mail ou senha incorretos."}, 401)

    def handle_post_register(self) -> None:
        body = self._read_json_body()
        email = body.get("email", "")
        password = body.get("password", "")
        office_name = body.get("office_name", "")
        oab = body.get("oab", "")
        if auth_security.credentials_configured() and self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._send_json({"error": "Cadastros adicionais só podem ser feitos no computador local."}, 403)
            return

        try:
            is_first_user = not auth_security.credentials_configured()
            user_email = auth_security.create_user(email, password)
            if is_first_user:
                office_settings.save_office_settings({
                    "office_name": office_name,
                    "oab": oab,
                    "responsavel_email": user_email
                })
            token = auth_security.create_session(user_email)
            self.send_response(201)
            self._send_session_cookie(token)
            payload = json.dumps({"success": True, "office_name": office_name, "email": user_email}, ensure_ascii=False).encode("utf-8")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)

    def handle_post_logout(self) -> None:
        """Revoke the current server-side session and expire its browser cookie."""
        auth_security.revoke_session(self._session_token())
        self.send_response(204)
        self.send_header(
            "Set-Cookie",
            "sofia_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0",
        )
        self.end_headers()

    # --- Handlers Principais & Novos Módulos ---

    def handle_get_stats(self) -> None:
        with database.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
            stage_rows = conn.execute(
                "SELECT crm_stage, COUNT(*), SUM(COALESCE(estimated_total_value, 0)) FROM atendimentos GROUP BY crm_stage"
            ).fetchall()
            
            stages = {
                "triagem": {"count": 0, "value": 0},
                "qualificacao": {"count": 0, "value": 0},
                "conflito": {"count": 0, "value": 0},
                "proposta": {"count": 0, "value": 0},
                "documentos": {"count": 0, "value": 0},
                "concluido": {"count": 0, "value": 0},
                "perdido": {"count": 0, "value": 0},
            }
            
            total_estimated_value = 0
            for r in stage_rows:
                st = r[0] or "triagem"
                cnt = r[1]
                val = r[2] or 0
                if st in stages:
                    stages[st]["count"] = cnt
                    stages[st]["value"] = val
                total_estimated_value += val

            recent_events = conn.execute(
                "SELECT COUNT(*) FROM integration_events WHERE status = 'pendente'"
            ).fetchone()[0]

            docs_pending = conn.execute(
                "SELECT COUNT(*) FROM atendimento_documentos WHERE status = 'pendente'"
            ).fetchone()[0]

        self._send_json({
            "total_atendimentos": total,
            "total_estimated_value": total_estimated_value,
            "events_pending": recent_events,
            "docs_pending": docs_pending,
            "stages": stages
        })

    def handle_get_intelligent_pending_items(self) -> None:
        """Return an explainable operational queue; never infer legal deadlines."""
        self._send_json(database.list_intelligent_pending_items())

    def handle_get_atendimentos(self, query: dict) -> None:
        search = query.get("q", [""])[0].lower()
        stage_filter = query.get("stage", [""])[0]

        with database.get_connection() as conn:
            sql = "SELECT * FROM atendimentos"
            params = []
            conditions = []

            if stage_filter:
                conditions.append("crm_stage = ?")
                params.append(stage_filter)
            
            if search:
                conditions.append("(LOWER(lead_name) LIKE ? OR LOWER(lead_phone) LIKE ? OR LOWER(flow_name) LIKE ?)")
                params.append(f"%{search}%")
                params.append(f"%{search}%")
                params.append(f"%{search}%")

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            sql += " ORDER BY id DESC"
            rows = conn.execute(sql, params).fetchall()

            result = []
            for r in rows:
                item = dict(r)
                if item.get("history_json"):
                    try:
                        item["history"] = json.loads(item["history_json"])
                    except Exception:
                        item["history"] = []
                result.append(item)

        self._send_json(result)

    def handle_get_atendimento(self, attendance_id: int) -> None:
        with database.get_connection() as conn:
            row = conn.execute("SELECT * FROM atendimentos WHERE id = ?", (attendance_id,)).fetchone()
            if not row:
                self._send_json({"error": "Atendimento nao encontrado"}, 404)
                return
            
            item = dict(row)
            if item.get("history_json"):
                try:
                    item["history"] = json.loads(item["history_json"])
                except Exception:
                    item["history"] = []
            if item.get("triage_profile_json"):
                try:
                    item["triage_profile"] = json.loads(item["triage_profile_json"])
                except Exception:
                    item["triage_profile"] = {}
            else:
                item["triage_profile"] = {}
            item["document_strategy"] = document_rules.get_flow_document_strategy(item["flow_id"])
            
            # Garantir checklist de documentos
            database.seed_document_checklist(
                conn,
                attendance_id=attendance_id,
                flow_id=item["flow_id"],
            )

            # Buscar tarefas
            tasks = conn.execute(
                "SELECT * FROM crm_tarefas WHERE attendance_id = ? ORDER BY id DESC", (attendance_id,)
            ).fetchall()
            item["tasks"] = [dict(t) for t in tasks]

            # Buscar atividades
            activities = conn.execute(
                "SELECT * FROM crm_atividades WHERE attendance_id = ? ORDER BY id DESC", (attendance_id,)
            ).fetchall()
            item["activities"] = [dict(a) for a in activities]

            # Buscar checklist de documentos
            docs = conn.execute(
                "SELECT * FROM atendimento_documentos WHERE attendance_id = ?", (attendance_id,)
            ).fetchall()
            evidence = database.document_evidence_summary(attendance_id)
            item["documents"] = [
                {**dict(d), **evidence.get(int(d["id"]), {"version_count": 0, "latest_version_id": None})}
                for d in docs
            ]

        self._send_json(item)

    def handle_get_documentos(self, attendance_id: int) -> None:
        with database.get_connection() as conn:
            row = conn.execute("SELECT flow_id FROM atendimentos WHERE id = ?", (attendance_id,)).fetchone()
            if row:
                database.seed_document_checklist(
                    conn,
                    attendance_id=attendance_id,
                    flow_id=row[0],
                )
            docs = conn.execute(
                "SELECT * FROM atendimento_documentos WHERE attendance_id = ?", (attendance_id,)
            ).fetchall()
        evidence = database.document_evidence_summary(attendance_id)
        self._send_json([
            {**dict(d), **evidence.get(int(d["id"]), {"version_count": 0, "latest_version_id": None})}
            for d in docs
        ])

    def handle_get_document_audit(self, attendance_id: int) -> None:
        audit = database.get_attendance_audit(
            attendance_id, document_audit.AUDIT_TYPE_CNIS_CTPS
        )
        if not audit:
            self._send_json(
                {
                    "success": False,
                    "error": "Ainda não há auditoria CNIS × CTPS para este dossiê.",
                    "requires_generation": True,
                },
                404,
            )
            return
        self._send_json({"success": True, **audit})

    def handle_get_document_evidence_matrix(self, attendance_id: int) -> None:
        with database.get_connection() as conn:
            exists = conn.execute("SELECT 1 FROM atendimentos WHERE id = ?", (attendance_id,)).fetchone()
        if not exists:
            self._send_json({"success": False, "error": "Atendimento não encontrado."}, 404)
            return
        self._send_json({"success": True, "matriz": database.build_document_evidence_matrix(attendance_id)})

    def handle_post_document_audit(self, attendance_id: int) -> None:
        """Generate an evidence-only CNIS × CTPS audit for an existing dossier."""
        documents = [dict(item) for item in database.list_attendance_documents(attendance_id)]
        report = document_audit.build_cnis_ctps_audit_from_documents(documents)
        database.save_attendance_audit(
            attendance_id=attendance_id,
            audit_type=document_audit.AUDIT_TYPE_CNIS_CTPS,
            status=str(report["status"]),
            report=report,
        )
        self._send_json(
            {
                "success": True,
                "attendance_id": attendance_id,
                "audit": report,
                "message": "Auditoria documental gerada. Ela não substitui revisão técnica ou decisão previdenciária.",
            }
        )

    def handle_get_retirement_dossier(self, attendance_id: int) -> None:
        audit = database.get_attendance_audit(
            attendance_id, retirement_dossier.AUDIT_TYPE_RETIREMENT_DOSSIER
        )
        if not audit:
            self._send_json(
                {
                    "success": False,
                    "error": "Ainda não há dossiê probatório para este caso.",
                    "requires_generation": True,
                },
                404,
            )
            return
        self._send_json({"success": True, **audit})

    def handle_post_retirement_dossier(self, attendance_id: int) -> None:
        attendance = database.get_attendance_details(attendance_id)
        if not attendance:
            self._send_json({"success": False, "error": "Atendimento não encontrado."}, 404)
            return
        if str(attendance["flow_id"]) != "aposentadoria":
            self._send_json(
                {"success": False, "error": "O dossiê probatório atual é exclusivo para aposentadoria."},
                422,
            )
            return
        body = self._read_json_body()
        existing = database.get_attendance_audit(
            attendance_id, retirement_dossier.AUDIT_TYPE_RETIREMENT_DOSSIER
        )
        if body.get("action") == "registrar_decisao":
            if not existing:
                self._send_json({"success": False, "error": "Gere o dossiê antes de registrar uma decisão."}, 409)
                return
            report = retirement_dossier.apply_human_decision(
                dict(existing["report"]),
                status=str(body.get("status") or ""),
                responsible=str(body.get("responsavel") or ""),
                note=str(body.get("nota") or ""),
            )
        else:
            try:
                profile = json.loads(attendance["triage_profile_json"] or "{}")
            except json.JSONDecodeError:
                profile = {}
            report = retirement_dossier.build_retirement_dossier(
                documents=[dict(item) for item in database.list_attendance_documents(attendance_id)],
                triage_profile=profile,
            )
        database.save_attendance_audit(
            attendance_id=attendance_id,
            audit_type=retirement_dossier.AUDIT_TYPE_RETIREMENT_DOSSIER,
            status=str(report["status"]),
            report=report,
        )
        self._send_json(
            {
                "success": True,
                "attendance_id": attendance_id,
                "dossie": report,
                "message": "Dossiê probatório atualizado. A decisão previdenciária continua sujeita à revisão humana.",
            }
        )

    def handle_get_review_draft_pdf(self, attendance_id: int) -> None:
        """Return an in-memory review draft only when a current dossier exists."""
        attendance = database.get_attendance_details(attendance_id)
        if not attendance:
            self._send_json({"success": False, "error": "Atendimento não encontrado."}, 404)
            return
        audit = database.get_attendance_audit(attendance_id, retirement_dossier.AUDIT_TYPE_RETIREMENT_DOSSIER)
        if not audit:
            self._send_json({"success": False, "error": "Gere o dossiê antes de baixar o rascunho."}, 409)
            return
        try:
            payload = build_review_draft_pdf(attendance=dict(attendance), dossier=dict(audit["report"]))
        except (ImportError, OSError, ValueError) as exc:
            self._send_json({"success": False, "error": f"Não foi possível gerar o PDF: {exc}"}, 500)
            return
        self._send_pdf(payload, f"kit-previdenciario-revisao-{attendance_id}.pdf")

    def handle_put_documento_status(self, doc_id: int) -> None:
        body = self._read_json_body()
        new_status = body.get("status", "aprovado")
        
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE atendimento_documentos SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_status, doc_id)
            )
        self._send_json({"success": True, "id": doc_id, "status": new_status})

    def handle_post_atividade(self, attendance_id: int) -> None:
        body = self._read_json_body()
        activity_type = body.get("activity_type", "nota")
        activity_body = body.get("body", "Interacao registrada")

        with database.get_connection() as conn:
            conn.execute(
                "INSERT INTO crm_atividades (attendance_id, activity_type, body) VALUES (?, ?, ?)",
                (attendance_id, activity_type, activity_body)
            )
        self._send_json({"success": True, "attendance_id": attendance_id})

    def handle_post_tarefa(self, attendance_id: int) -> None:
        body = self._read_json_body()
        title = body.get("title", "Retornar ao cliente")
        due_at = body.get("due_at", "")
        priority = body.get("priority", "media")

        with database.get_connection() as conn:
            conn.execute(
                "INSERT INTO crm_tarefas (attendance_id, title, due_at, priority, status) VALUES (?, ?, ?, ?, 'aberta')",
                (attendance_id, title, due_at, priority)
            )
        self._send_json({"success": True, "attendance_id": attendance_id})

    def handle_get_contrato(self, attendance_id: int) -> None:
        settings = office_settings.load_office_settings()
        with database.get_connection() as conn:
            row = conn.execute("SELECT * FROM atendimentos WHERE id = ?", (attendance_id,)).fetchone()
            if not row:
                self._send_json({"error": "Atendimento nao encontrado"}, 404)
                return
            att = dict(row)

        office_name = settings.get("office_name", "PrevIA Advocacia Previdenciaria")
        oab = settings.get("oab", "524387")
        fee_pct = office_settings.resolve_fee_percentage(att["flow_name"], settings)
        client_name = att["lead_name"]
        flow_name = att["flow_name"]
        estimated_val = (att.get("estimated_total_value") or 15000.0)

        contract_text = f"""
CONTRATO DE PRESTAÇÃO DE SERVIÇOS ADVOCATÍCIOS PREVIDENCIÁRIOS

CONTRATADA: {office_name}, inscrita na OAB sob nº {oab}.
CONTRATANTE: {client_name}, cliente cadastrado sob ID #{attendance_id}.

CLÁUSULA PRIMEIRA - DO OBJETO:
O presente contrato tem como objeto a prestação de serviços advocatícios para a tutela dos direitos previdenciários do CONTRATANTE referentes ao benefício de {flow_name} junto ao INSS e/ou Poder Judiciário.

CLÁUSULA SEGUNDA - DOS HONORÁRIOS ADVOCATÍCIOS:
Pelos serviços prestados, o CONTRATANTE pagará à CONTRATADA o percentual de {fee_pct}% ({fee_pct} por cento) sobre o valor total do proveito econômico obtido (atrasados e/ou parcelas vincendas estimadas em R$ {estimated_val:,.2f}).

CLÁUSULA TERCEIRA - DA PRIVACIDADE E LGPD:
O CONTRATANTE autoriza o tratamento de seus dados pessoais e documentos estritamente para o cumprimento das obrigações contratuais e instrução previdenciária.

São Paulo, 14 de Agosto de 2026.

___________________________________________________
{office_name} (OAB: {oab})

___________________________________________________
{client_name} (Contratante)
"""
        self._send_json({
            "attendance_id": attendance_id,
            "office_name": office_name,
            "oab": oab,
            "client_name": client_name,
            "flow_name": flow_name,
            "fee_percentage": fee_pct,
            "contract_text": contract_text.strip()
        })

    def handle_post_client_portal_summary(self) -> None:
        body = self._read_json_body()
        portal = database.get_client_portal_view(str(body.get("token") or ""))
        if not portal:
            # Não diferenciamos token expirado, revogado ou inexistente para
            # impedir enumeração de acessos temporários.
            self._send_json({"error": "Acesso indisponível. Solicite um novo link ao escritório."}, 404)
            return
        self._send_json({"success": True, "portal": portal})

    def handle_post_client_portal_access(self, attendance_id: int) -> None:
        body = self._read_json_body()
        try:
            ttl_days = int(body.get("ttl_days", 7))
        except (TypeError, ValueError):
            ttl_days = 0
        try:
            access = database.create_client_portal_access(attendance_id, ttl_days=ttl_days)
        except ValueError as exc:
            self._send_json({"success": False, "error": str(exc)}, 400)
            return
        self._send_json({"success": True, **access}, 201)

    def handle_post_assinatura(self, attendance_id: int) -> None:
        body = self._read_json_body()
        with database.get_connection() as conn:
            row = conn.execute("SELECT * FROM atendimentos WHERE id = ?", (attendance_id,)).fetchone()
            if not row:
                self._send_json({"error": "Atendimento não encontrado."}, 404); return
            att = dict(row)
            client_email = str(body.get("client_email") or att.get("lead_email") or "").strip().lower()
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", client_email):
                self._send_json({"error": "Informe um e-mail válido do contratante."}, 400); return
            conn.execute("UPDATE atendimentos SET lead_email = ? WHERE id = ?", (client_email, attendance_id))
        settings = office_settings.load_office_settings()
        office_email = str(settings.get("responsavel_email") or "").strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", office_email):
            self._send_json({"error": "Configure o e-mail responsável do escritório antes de enviar."}, 400); return
        try:
            result = docuseal_integration.create_submission(
                client_name=att["lead_name"], client_email=client_email,
                office_name=settings.get("office_name") or "SOF.IA", office_email=office_email,
                attendance_id=attendance_id,
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400); return
        submission = result[0] if isinstance(result, list) and result else result
        reference = str(submission.get("id") or submission.get("submission_id") or "") if isinstance(submission, dict) else ""
        with database.get_connection() as conn:
            conn.execute("INSERT INTO crm_atividades (attendance_id, activity_type, body) VALUES (?, 'contrato', ?)",
                         (attendance_id, f"Solicitação de assinatura criada no DocuSeal{f' (#{reference})' if reference else ''}."))
        self._send_json({"success": True, "submission_id": reference, "message": "Solicitação enviada para assinatura."}, 201)

    def handle_get_fluxos(self) -> None:
        fluxos = []
        for fid, fdef in FLOW_DEFINITIONS.items():
            fluxos.append({
                "id": fid,
                "name": fdef["name"],
                "start": fdef["start"],
                "total_nodes": len(fdef["nodes"]),
                "results": list(fdef["results"].keys())
            })
        self._send_json(fluxos)

    def handle_post_atendimento(self) -> None:
        try:
            body = self._read_json_body()
            lead_name = str(body.get("lead_name", "")).strip()
            lead_phone = str(body.get("lead_phone", "")).strip()
            if not lead_name or not lead_phone:
                self._send_json({"success": False, "error": "Nome e WhatsApp são obrigatórios."}, 400)
                return

            flow_id = body.get("flow_id", "aposentadoria")
            history = body.get("history", [])
            result_title = body.get("result_title", "Triagem em Andamento")
            summary = body.get("summary", "Criado via Web App")
            next_step = body.get("next_step", "Verificar documentos iniciais")
            status = body.get("status", "aprovado")
            crm_stage = body.get("crm_stage", "triagem")
            monthly_val = float(body.get("estimated_monthly_value", 0))
            total_val = float(body.get("estimated_total_value", 0))
            flow_name = FLOW_DEFINITIONS.get(flow_id, {}).get("name", flow_id)

            att_id = database.save_attendance(
                lead_name=lead_name,
                lead_phone=lead_phone,
                flow_id=flow_id,
                flow_name=flow_name,
                status=status,
                result_title=result_title,
                summary=summary,
                next_step=next_step,
                history=history if isinstance(history, list) else [],
                notes=str(body.get("notes", "")),
                benefit_category=body.get("benefit_category", flow_name),
                estimated_monthly_value=monthly_val,
                estimated_total_value=total_val,
                crm_stage=crm_stage,
                lead_email=str(body.get("lead_email", "")),
                lead_source=str(body.get("lead_source", "")),
                privacy_notice_acknowledged=bool(body.get("privacy_notice_acknowledged", False)),
                privacy_legal_basis=str(body.get("privacy_legal_basis", "")),
                triage_profile=body.get("triage_profile") if isinstance(body.get("triage_profile"), dict) else {},
                relationship_status=str(body.get("relationship_status", "nao_aplicavel")),
                relationship_next_review_at=body.get("relationship_next_review_at"),
                remarketing_opt_in=bool(body.get("remarketing_opt_in", False)),
            )
            self._send_json({"success": True, "id": att_id}, 201)
        except (TypeError, ValueError) as exc:
            self._send_json({"success": False, "error": f"Dados inválidos para o lead: {exc}"}, 400)
        except Exception as exc:
            print(f"Erro ao criar atendimento: {exc}", file=sys.stderr)
            self._send_json({"success": False, "error": "Não foi possível salvar o lead. Tente novamente."}, 500)

    def handle_get_relacionamento(self) -> None:
        """Base separada para leads sem elegibilidade atual, nunca exposta como venda de dados."""
        with database.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, lead_name, lead_phone, flow_name, result_title, summary,
                       next_step, created_at, relationship_status,
                       relationship_next_review_at, remarketing_opt_in
                FROM atendimentos
                WHERE crm_stage = 'relacionamento' OR status = 'desqualificado'
                ORDER BY COALESCE(relationship_next_review_at, created_at) ASC, id DESC
                """
            ).fetchall()
        self._send_json([dict(row) for row in rows])

    def handle_post_reativar_lead(self, attendance_id: int) -> None:
        with database.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE atendimentos
                SET status = 'revisao', crm_stage = 'triagem',
                    relationship_status = 'reativado',
                    relationship_next_review_at = NULL,
                    next_action = 'Refazer triagem guiada com dados atualizados',
                    crm_stage_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (attendance_id,),
            )
        if cursor.rowcount == 0:
            self._send_json({"success": False, "error": "Lead não encontrado."}, 404)
            return
        self._send_json({"success": True, "id": attendance_id})

    def handle_put_stage(self, attendance_id: int) -> None:
        body = self._read_json_body()
        new_stage = body.get("stage", "triagem")
        
        with database.get_connection() as conn:
            conn.execute(
                "UPDATE atendimentos SET crm_stage = ?, crm_stage_updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_stage, attendance_id)
            )
            conn.execute(
                "INSERT INTO crm_atividades (attendance_id, activity_type, body) VALUES (?, 'estagio_alterado', ?)",
                (attendance_id, f"Estágio do CRM alterado para: {new_stage.upper()}")
            )
        self._send_json({"success": True, "id": attendance_id, "stage": new_stage})

    def handle_post_conflito(self, attendance_id: int) -> None:
        body = self._read_json_body()
        status = body.get("status", "liberado")
        notes = body.get("notes", "Sem conflito de interesse detectado")
        parties = body.get("parties", "")

        database.update_conflict_check(
            attendance_id=attendance_id,
            status=status,
            notes=notes,
            parties=parties
        )
        self._send_json({"success": True, "id": attendance_id, "conflict_status": status})

    def handle_post_lgpd(self, attendance_id: int) -> None:
        body = self._read_json_body()
        legal_basis = body.get("legal_basis", "Execucao de Contrato / Tutela da Saude")
        
        database.register_privacy_acknowledgement(
            attendance_id=attendance_id,
            legal_basis=legal_basis
        )
        self._send_json({"success": True, "id": attendance_id, "privacy_legal_basis": legal_basis})

    def handle_post_triagem_executar(self) -> None:
        body = self._read_json_body()
        flow_id = body.get("flow_id", "auxilioAcidente")
        node_id = body.get("node_id")
        answer_label = body.get("answer_label")
        history = body.get("history", [])
        preview = bool(body.get("preview"))

        if flow_id not in FLOW_DEFINITIONS:
            self._send_json({"error": "Fluxo invalido"}, 400)
            return

        flow = FLOW_DEFINITIONS[flow_id]

        if preview and node_id:
            node = flow["nodes"].get(node_id)
            if node is None:
                self._send_json({"error": "Pergunta invalida"}, 400)
                return
            self._send_json({
                "flow_id": flow_id,
                "is_finished": False,
                "current_node": node,
                "history": history,
            })
            return

        if not node_id:
            start_node = flow["nodes"][flow["start"]]
            self._send_json({
                "flow_id": flow_id,
                "is_finished": False,
                "current_node": start_node,
                "history": []
            })
            return

        state = create_state(flow_id, flow)
        state.current_node_id = node_id
        state.history = history

        new_state, result = answer_current_question(state, flow, answer_label)

        if result:
            self._send_json({
                "flow_id": flow_id,
                "is_finished": True,
                "result": result,
                "history": new_state.history
            })
        else:
            next_node = get_current_node(new_state, flow)
            self._send_json({
                "flow_id": flow_id,
                "is_finished": False,
                "current_node": next_node,
                "history": new_state.history
            })

    def handle_post_retirement_prefilter(self) -> None:
        """Evaluate the mandatory retirement gate before opening the decision tree."""
        body = self._read_json_body()
        try:
            self._send_json(retirement_prefilter.evaluate_retirement_prefilter(body))
        except ValueError as exc:
            self._send_json({"error": str(exc)}, 400)

    def handle_post_documento_analisar(self) -> None:
        self._handle_uploaded_document_analysis()
        return

        body = self._read_json_body()
        file_name = body.get("file_name", "05-CNIS Extrato Previdenciário.pdf")
        document_code = body.get("document_code", "CNIS")

        segurado = {
            "nome": "MARIA DAS DORES SILVA",
            "cpf": "384.912.847-19",
            "nit_pis": "128.94827.12-4",
            "data_nascimento": "12/04/1968",
            "nome_mae": "TERESA DE JESUS SILVA",
            "status_cadastral": "Regular (Sem divergências no CADAUD)"
        }

        metricas = {
            "tempo_contribuicao_total": "32 anos, 2 meses e 15 dias",
            "tempo_contribuicao_dias": 11755,
            "carencia_cumprida": 386,
            "carencia_minima_exigida": 180,
            "carencia_status": "Aprovado (Carência 100% cumprida)",
            "rmi_estimada": "R$ 3.840,50",
            "diagnostico_principal": "Apto para Aposentadoria por Idade Urbana (Art. 48/8213)",
            "diagnostico_subtitulo": "Direito Adquirido (Regra Geral - Idade 62 anos + 15 anos de contribuição)",
            "alertas_contagem": 2
        }

        vinculos = [
            {
                "seq": 1,
                "empregador": "Indústria Metalgrafica S/A",
                "cnpj": "43.194.821/0001-92",
                "tipo_filiacao": "Empregado Urbano",
                "data_inicio": "01/03/1992",
                "data_fim": "15/08/2005",
                "duracao": "13 anos, 5 meses e 14 dias",
                "status": "regular",
                "indicadores": [],
                "remuneracao_ultima": "R$ 1.850,00"
            },
            {
                "seq": 2,
                "empregador": "Comércio de Confecções Silva Ltda",
                "cnpj": "08.412.938/0001-10",
                "tipo_filiacao": "Empregado Urbano",
                "data_inicio": "01/10/2005",
                "data_fim": "30/11/2012",
                "duracao": "7 anos, 2 meses e 0 dias",
                "status": "regular",
                "indicadores": [],
                "remuneracao_ultima": "R$ 2.400,00"
            },
            {
                "seq": 3,
                "empregador": "Prefeitura Municipal de São Paulo",
                "cnpj": "46.392.148/0001-00",
                "tipo_filiacao": "Servidor Público / Contratado Temporário",
                "data_inicio": "10/01/2013",
                "data_fim": "28/02/2018",
                "duracao": "5 anos, 1 mês e 18 dias",
                "status": "atencao",
                "indicadores": [
                    {"codigo": "PEXT", "descricao": "Pendência de Extinção de Vínculo (Falta Data de Rescisão Formal no CADAUD)"}
                ],
                "remuneracao_ultima": "R$ 3.100,00"
            },
            {
                "seq": 4,
                "empregador": "Contribuinte Individual / MEI",
                "cnpj": "NIT 128.94827.12-4",
                "tipo_filiacao": "Autônomo (Carnê / Guia GPS)",
                "data_inicio": "01/04/2018",
                "data_fim": "31/12/2021",
                "duracao": "3 anos, 8 meses e 30 dias",
                "status": "atencao",
                "indicadores": [
                    {"codigo": "PREM", "descricao": "Remuneração Extemporânea (GPS pagas em atraso sem validação de recolhimento)"}
                ],
                "remuneracao_ultima": "R$ 1.320,00"
            },
            {
                "seq": 5,
                "empregador": "Serviços de Conservação Eireli",
                "cnpj": "29.841.092/0001-44",
                "tipo_filiacao": "Empregado Urbano",
                "data_inicio": "01/02/2022",
                "data_fim": "Em Aberto (Ativo)",
                "duracao": "2 anos, 6 meses (Em andamento)",
                "status": "ativo",
                "indicadores": [],
                "remuneracao_ultima": "R$ 3.950,00"
            }
        ]

        self._send_json({
            "success": True,
            "file_name": file_name,
            "document_code": document_code,
            "extraction_confidence": 0.987,
            "extraction_status": "aprovado",
            "segurado": segurado,
            "metricas": metricas,
            "vinculos": vinculos,
            "technical_notes": "Extrato CNIS NATIVO processado com OCR Neural + Resolução Automática de Indicadores INSS (PEXT/PREM)."
        })

    def _get_owned_document(self, attendance_id: int, document_id: int):
        with database.get_connection() as conn:
            return conn.execute(
                "SELECT id, document_code FROM atendimento_documentos WHERE id = ? AND attendance_id = ?",
                (document_id, attendance_id),
            ).fetchone()

    def handle_post_document_upload_intent(self, attendance_id: int) -> None:
        body = self._read_json_body()
        try:
            document_id = int(body.get("document_id"))
            filename = validate_upload_metadata(
                filename=str(body.get("filename", "")), mime_type=str(body.get("mime_type", "")),
                size_bytes=body.get("size_bytes"),
            )
        except (TypeError, ValueError) as exc:
            self._send_json({"success": False, "error": str(exc)}, 400)
            return
        if not self._get_owned_document(attendance_id, document_id):
            self._send_json({"success": False, "error": "Documento não encontrado no caso autorizado."}, 404)
            return
        try:
            storage = FilOneStorageService.from_environment()
        except StorageConfigurationError as exc:
            self._send_json({"success": False, "error": str(exc)}, 503)
            return
        mime_type = str(body["mime_type"]).lower().split(";", 1)[0].strip()
        intent_id = uuid.uuid4().hex
        key = build_storage_key(attendance_id=attendance_id, document_id=document_id, filename=filename)
        expires_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        database.create_document_upload_intent(
            intent_id=intent_id, attendance_id=attendance_id, document_id=document_id,
            original_filename=filename, mime_type=mime_type, size_bytes=int(body["size_bytes"]),
            bucket=storage._config.bucket, storage_key=key, expires_at=expires_at,
        )
        # A URL é devolvida somente nesta resposta autenticada; não vai para logs nem banco.
        self._send_json({"success": True, "intent_id": intent_id, "upload_url": storage.create_presigned_upload_url(key=key, content_type=mime_type, expires_in=600), "expires_in": 600})

    def handle_post_document_upload_complete(self, intent_id: str) -> None:
        intent = database.get_document_upload_intent(intent_id)
        if not intent or intent["status"] != "PENDING_UPLOAD":
            self._send_json({"success": False, "error": "Upload pendente não encontrado."}, 404)
            return
        if datetime.fromisoformat(intent["expires_at"]).astimezone(UTC) < datetime.now(UTC):
            self._send_json({"success": False, "error": "Autorização de upload expirada."}, 409)
            return
        if not self._get_owned_document(int(intent["attendance_id"]), int(intent["document_id"])):
            self._send_json({"success": False, "error": "Documento não encontrado no caso autorizado."}, 404)
            return
        try:
            storage = FilOneStorageService.from_environment()
            if not storage.exists(key=str(intent["storage_key"])):
                raise ValueError("Objeto não encontrado no storage privado.")
            metadata = storage.get_metadata(key=str(intent["storage_key"]))
            if metadata["size_bytes"] != int(intent["size_bytes"]) or metadata["mime_type"].lower().split(";", 1)[0] != str(intent["mime_type"]):
                raise ValueError("Metadados do objeto não correspondem ao upload autorizado.")
        except StorageConfigurationError as exc:
            self._send_json({"success": False, "error": str(exc)}, 503)
            return
        except ValueError as exc:
            self._send_json({"success": False, "error": str(exc)}, 409)
            return
        storage_etag = str(metadata.get("etag") or "")
        # content_hash is a legacy NOT NULL column for OCR-derived content
        # hashes. A remote object was not hashed by this backend, so preserve a
        # unique storage version identifier rather than mislabeling it as a
        # document-content SHA-256. The provider ETag lives in storage_etag.
        content_hash = f"storage-object:{intent_id}"
        version_id = database.record_document_version(
            attendance_id=int(intent["attendance_id"]), document_id=int(intent["document_id"]),
            content_hash=content_hash, original_name=str(intent["original_filename"]), stored_path="",
            raw_text="", extracted_data={}, source_type="filone_private_storage", extraction_status="nao_processado",
            extraction_confidence=0.0, technical_notes="Armazenado privadamente; leitura técnica não executada nesta etapa.",
            storage_provider="filone", bucket=str(intent["bucket"]), storage_key=str(intent["storage_key"]),
            mime_type=str(intent["mime_type"]), size_bytes=int(intent["size_bytes"]), storage_etag=storage_etag,
            processing_status="UPLOADED", metadata=metadata,
        )
        database.update_attendance_document(
            document_id=int(intent["document_id"]), status="recebido",
            notes="Arquivo privado recebido; aguardando leitura técnica.",
            uploaded_files=[f"filone://{intent['bucket']}/{intent['storage_key']}"]
        )
        database.complete_document_upload_intent(intent_id)
        database.invalidate_attendance_document_audits(int(intent["attendance_id"]))
        self._send_json({"success": True, "document_id": int(intent["document_id"]), "version_id": version_id, "status": "UPLOADED"})

    def handle_get_document_download_url(self, attendance_id: int, document_id_text: str) -> None:
        try:
            document_id = int(document_id_text)
        except ValueError:
            self._send_json({"success": False, "error": "Documento inválido."}, 400)
            return
        with database.get_connection() as conn:
            version = conn.execute(
                """SELECT v.storage_key FROM atendimento_documento_versoes v
                   JOIN atendimento_documentos d ON d.id = v.document_id
                   WHERE v.document_id = ? AND d.attendance_id = ? AND v.storage_provider = 'filone'
                   ORDER BY v.id DESC LIMIT 1""",
                (document_id, attendance_id),
            ).fetchone()
        if not version:
            self._send_json({"success": False, "error": "Arquivo privado não encontrado."}, 404)
            return
        try:
            url = FilOneStorageService.from_environment().create_presigned_download_url(key=str(version["storage_key"]), expires_in=300)
        except StorageConfigurationError as exc:
            self._send_json({"success": False, "error": str(exc)}, 503)
            return
        self._send_json({"success": True, "download_url": url, "expires_in": 300})

    def _handle_uploaded_document_analysis(self) -> None:
        uploaded = self._read_uploaded_document()
        if uploaded is None:
            self._send_json({"success": False, "error": "Envie um arquivo PDF ou imagem no campo 'file'."}, 400)
            return

        fields, file_name, file_content = uploaded
        document_code = (fields.get("document_code") or "CNIS").upper()
        suffix = Path(file_name).suffix.lower()
        supported_suffixes = {".pdf", *document_intelligence.SUPPORTED_IMAGE_SUFFIXES}
        if suffix not in supported_suffixes:
            self._send_json({"success": False, "error": "Formato não suportado. Use PDF ou imagem."}, 415)
            return
        if len(file_content) > document_intelligence.MAX_FILE_BYTES:
            self._send_json({"success": False, "error": "Arquivo excede o limite do OCR local."}, 413)
            return

        with TemporaryDirectory(prefix="sofia-previ-ocr-") as temporary_dir:
            local_file = Path(temporary_dir) / f"documento{suffix}"
            local_file.write_bytes(file_content)
            analysis = document_intelligence.analyze_document_bundle(
                document_code=document_code,
                uploaded_files=[str(local_file)],
                # A primeira passagem é neutra: o tipo só é conhecido depois
                # da leitura. Campos de CNIS não podem reduzir a confiança de
                # uma CNH, laudo, CAT ou documento de identidade legítimo.
                critical_fields=[],
            )

        extracted = analysis["extracted_data"]
        classification = document_intelligence.classify_document(file_name, analysis["raw_text"])
        document_fields = document_intelligence.extract_document_fields(
            classification["code"], analysis["raw_text"]
        )
        field_values = {
            field["key"]: field["value"]
            for field in document_fields
            if field["value"] != "Nao identificado"
        }
        extracted = {**extracted, **field_values}
        assessment = document_intelligence.assess_document_extraction(
            classification,
            document_fields,
            raw_text=analysis["raw_text"],
            source_confidence=float(analysis["extraction_confidence"]),
        )
        if assessment["missing_fields"]:
            analysis["technical_notes"] += (
                " | Campos do tipo documental ainda pendentes: "
                + ", ".join(assessment["missing_fields"])
                + "."
            )
        if classification["code"] == "CNIS":
            cnis_report = document_intelligence.build_cnis_report(analysis["raw_text"], extracted)
            catalog_matches = cnis_knowledge.build_indicator_matches(
                analysis["raw_text"], database.get_active_cnis_indicator_definitions()
            )
            cnis_report["indicator_matches"] = catalog_matches
            cnis_report["action_plan"] = cnis_knowledge.action_plan(catalog_matches)
            # Sem catálogo oficial ativo, os códigos extraídos continuam sendo
            # pendências visíveis. Catálogo só refina a análise; não apaga o
            # sinal documental que exige conferência humana.
            cnis_report["metricas"]["alertas_contagem"] = max(
                int(cnis_report["metricas"].get("alertas_contagem") or 0),
                len(catalog_matches),
            )
            cnis_report["metricas"]["alertas_nota"] = (
                "Indicadores localizados no catálogo ativo; revisão jurídica obrigatória."
                if catalog_matches else cnis_report["metricas"]["alertas_nota"]
            )
        else:
            cnis_report = {
                "segurado": {
                    "nome": field_values.get("nome", "Nao identificado no documento"),
                    "cpf": field_values.get("cpf", "Nao identificado"),
                    "nit_pis": field_values.get("nit", "Nao aplicavel"),
                    "data_nascimento": field_values.get("data_nascimento", "Nao identificada"),
                },
                "metricas": {
                    "tempo_contribuicao_total": "Nao aplicavel a este documento",
                    "tempo_contribuicao_dias": None,
                    "tempo_nota": "Envie CNIS, CTPS ou PPP para analise contributiva.",
                    "carencia_cumprida": "Nao aplicavel a este documento",
                    "carencia_nota": "A carencia so pode ser analisada com documento contributivo.",
                    "rmi_estimada": "Nao calculada",
                    "rmi_nota": "A RMI exige base contributiva validada e calculo tecnico.",
                    "diagnostico_principal": classification["label"],
                    "diagnostico_subtitulo": "Campos direcionados aos modulos: " + ", ".join(classification["modules"]),
                    "alertas_contagem": 0,
                    "alertas_nota": "Nenhum indicador INSS se aplica a este tipo documental.",
                },
                "vinculos": [],
                "competencias_identificadas": [],
            }
        status = assessment["status"]
        success = status in {"extraido", "parcial"}
        dossier_document: dict | None = None
        attendance_value = fields.get("attendance_id", "").strip()
        document_value = fields.get("document_id", "").strip()
        if attendance_value or document_value:
            try:
                attendance_id = int(attendance_value)
                document_id = int(document_value)
            except ValueError:
                self._send_json({"success": False, "error": "Dossiê documental inválido."}, 400)
                return
            with database.get_connection() as conn:
                document_row = conn.execute(
                    "SELECT id, document_code FROM atendimento_documentos WHERE id = ? AND attendance_id = ?",
                    (document_id, attendance_id),
                ).fetchone()
            if not document_row:
                self._send_json({"success": False, "error": "Item documental não encontrado no dossiê."}, 404)
                return
            document_status = "recebido" if success else "ilegivel"
            content_hash = hashlib.sha256(file_content).hexdigest()
            existing_version = database.get_document_version_by_hash(document_id, content_hash)
            if existing_version:
                stored_path = str(existing_version["stored_path"])
                version_id = int(existing_version["id"])
                duplicate_upload = True
            else:
                # O analisador trabalha somente no diretório temporário acima.
                # Arquivos vinculados ao dossiê devem chegar pelo fluxo Fil One;
                # nenhum PDF é persistido no notebook por esta rota.
                stored_path = ""
                version_id = database.record_document_version(
                    attendance_id=attendance_id,
                    document_id=document_id,
                    content_hash=content_hash,
                    original_name=file_name,
                    stored_path=stored_path,
                    raw_text=str(analysis["raw_text"]),
                    extracted_data=extracted,
                    source_type=str(analysis["source_type"]),
                    extraction_status=status,
                    extraction_confidence=float(assessment["confidence"]),
                    technical_notes=str(analysis["technical_notes"]),
                )
                duplicate_upload = False
            database.update_attendance_document(
                document_id=document_id,
                status=document_status,
                notes=str(analysis["technical_notes"]),
                uploaded_files=[stored_path],
                raw_text=str(analysis["raw_text"]),
                extracted_data=extracted,
                source_type=str(analysis["source_type"]),
                extraction_status=status,
                extraction_confidence=float(assessment["confidence"]),
                technical_notes=str(analysis["technical_notes"]),
            )
            # Uma nova evidência altera a base de prova. Reenvio idêntico é
            # idempotente e não deve invalidar um relatório já revisado.
            if not duplicate_upload:
                database.invalidate_attendance_document_audits(attendance_id)
            dossier_document = {
                "attendance_id": attendance_id,
                "document_id": document_id,
                "version_id": version_id,
                "duplicate_upload": duplicate_upload,
                "status": document_status,
                "stored": True,
            }
        self._send_json(
            {
                "success": success,
                "file_name": file_name,
                "document_code": classification["code"],
                "requested_document_code": document_code,
                "extraction_status": status,
                "extraction_confidence": assessment["confidence"],
                "requires_review": status != "extraido",
                "classification": classification,
                "document_fields": document_fields,
                "segurado": {
                    "nome": extracted.get("nome", "") or "Não identificado no documento",
                    "cpf": extracted.get("cpf", "") or "Não identificado",
                    "nit_pis": extracted.get("nit", "") or "Não identificado",
                    "data_nascimento": extracted.get("data_nascimento", "") or "Não identificada",
                },
                "metricas": {
                    "tempo_contribuicao_total": "Não apurado automaticamente",
                    "tempo_contribuicao_dias": None,
                    "carencia_cumprida": "Não apurada automaticamente",
                    "carencia_minima_exigida": 180,
                    "carencia_status": "Revisão humana necessária",
                    "rmi_estimada": "Não calculada",
                    "diagnostico_principal": "Sem diagnóstico automático",
                    "diagnostico_subtitulo": "A leitura não substitui a conferência técnica do CNIS.",
                    "alertas_contagem": 0,
                },
                "vinculos": [],
                # These keys deliberately override the former placeholder payload above.
                # Keep the UI tied only to evidence found in the uploaded document.
                "segurado": cnis_report["segurado"],
                "metricas": cnis_report["metricas"],
                "vinculos": cnis_report["vinculos"],
                "competencias_identificadas": cnis_report["competencias_identificadas"],
                "indicator_matches": cnis_report.get("indicator_matches", []),
                "action_plan": cnis_report.get("action_plan", []),
                "cnis_catalog": database.get_cnis_catalog_status(),
                "extracted_data": extracted,
                "raw_text": analysis["raw_text"][:50000],
                "technical_notes": analysis["technical_notes"],
                "dossier_document": dossier_document,
            },
            200 if success else 422,
        )

    def handle_get_eventos(self) -> None:
        with database.get_connection() as conn:
            events = conn.execute(
                "SELECT * FROM integration_events ORDER BY id DESC LIMIT 50"
            ).fetchall()
        self._send_json([dict(e) for e in events])

    # --- Catálogo oficial Portal IN ---

    def handle_get_catalog_status(self) -> None:
        self._send_json({
            "catalog": database.get_cnis_catalog_status(),
            "sources": database.list_official_sources(),
            "policy": "Fontes oficiais são monitoradas por hash. Mudanças exigem revisão jurídica antes de ativar regras.",
        })

    def handle_get_catalog_versions(self) -> None:
        self._send_json({"versions": database.list_cnis_catalog_versions()})

    def handle_post_monitor_official_sources(self) -> None:
        outcomes: list[dict] = []
        for source in official_catalog.OFFICIAL_SOURCE_REGISTRY:
            try:
                snapshot = official_catalog.fetch_official_source(source)
                outcomes.append(database.record_official_source_snapshot(snapshot))
            except Exception as error:  # a fonte não pode derrubar o CRM
                database.record_official_source_failure(source, str(error))
                outcomes.append({"source_key": source["key"], "source_url": source["url"], "success": False, "error": str(error)[:300]})
        self._send_json({
            "success": True,
            "outcomes": outcomes,
            "sources": database.list_official_sources(),
            "notice": "Nenhuma alteração de fonte foi ativada automaticamente.",
        })

    def handle_post_import_catalog_workbook(self) -> None:
        uploaded = self._read_uploaded_document()
        if uploaded is None:
            self._send_json({"success": False, "error": "Envie a planilha XLSX no campo 'file'."}, 400)
            return
        _, file_name, file_content = uploaded
        if Path(file_name).suffix.lower() != ".xlsx":
            self._send_json({"success": False, "error": "Envie a planilha de indicadores no formato XLSX."}, 415)
            return
        with TemporaryDirectory(prefix="sofia-previ-catalog-") as temporary_dir:
            workbook_path = Path(temporary_dir) / Path(file_name).name
            workbook_path.write_bytes(file_content)
            try:
                imported = official_catalog.import_indicator_workbook(workbook_path)
                result = database.create_cnis_catalog_version(
                    source_name=imported.source_name,
                    source_url=imported.source_url,
                    source_hash=imported.source_hash,
                    definitions=imported.definitions,
                    review_notes="Importação local vinculada ao PT 990 — Anexo V; requer conferência jurídica.",
                )
            except (ValueError, RuntimeError) as error:
                self._send_json({"success": False, "error": str(error)}, 400)
                return
        self._send_json({
            "success": True,
            "created": result["created"],
            "version": result["version"],
            "message": "Versão importada e mantida em revisão. Ela não é usada pelo OCR até ativação manual.",
        }, 201 if result["created"] else 200)

    def handle_post_import_official_indicator_catalog(self) -> None:
        """Refresh and structure PT 990 Annex V as a review-only catalog version."""
        source = official_catalog.OFFICIAL_SOURCE_REGISTRY[0]
        try:
            snapshot = official_catalog.fetch_official_source(source)
            database.record_official_source_snapshot(snapshot)
            imported = official_catalog.import_official_indicator_pdf(Path(snapshot["local_path"]))
            result = database.create_cnis_catalog_version(
                source_name=imported.source_name,
                source_url=imported.source_url,
                source_hash=imported.source_hash,
                definitions=imported.definitions,
                review_notes=(
                    "Extração local do PT 990 — Anexo V oficial do Portal IN. "
                    "Versão aguardando revisão jurídica; não ativada automaticamente."
                ),
            )
        except (ValueError, RuntimeError, OSError) as error:
            self._send_json({"success": False, "error": str(error)}, 400)
            return
        self._send_json({
            "success": True,
            "created": result["created"],
            "version": result["version"],
            "indicators_extracted": len(imported.definitions),
            "message": "Anexo V oficial estruturado e mantido em revisão jurídica.",
        }, 201 if result["created"] else 200)

    def handle_post_activate_catalog_version(self, version_id: int) -> None:
        body = self._read_json_body()
        settings = office_settings.load_office_settings()
        reviewer = str(body.get("reviewer") or settings.get("responsavel_nome") or settings.get("office_name") or "Responsável do escritório")
        note = str(body.get("note") or "")
        try:
            version = database.activate_cnis_catalog_version(version_id, reviewer, note)
        except ValueError as error:
            self._send_json({"success": False, "error": str(error)}, 400)
            return
        self._send_json({"success": True, "version": version, "message": "Versão ativada após revisão jurídica registrada."})


def run_server(port: int = 8000) -> None:
    # Dados previdenciários não devem ser publicados na rede por acidente.
    # Para expor o robô atrás de um proxy HTTPS, configure explicitamente:
    # ROBO_INSS_BIND_HOST, ROBO_INSS_ALLOW_NETWORK=1 e ROBO_INSS_COOKIE_SECURE=1.
    host = os.environ.get("ROBO_INSS_BIND_HOST", "127.0.0.1")
    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    if host not in loopback_hosts and os.environ.get("ROBO_INSS_ALLOW_NETWORK") != "1":
        raise RuntimeError(
            "Exposição em rede bloqueada. Use ROBO_INSS_ALLOW_NETWORK=1 somente atrás de HTTPS."
        )
    if host not in loopback_hosts and os.environ.get("ROBO_INSS_COOKIE_SECURE") != "1":
        raise RuntimeError(
            "Exposição em rede exige ROBO_INSS_COOKIE_SECURE=1 e um proxy HTTPS confiável."
        )
    server_address = (host, port)
    # A leitura de PDF/OCR pode levar alguns segundos. Um servidor concorrente
    # impede que essa tarefa bloqueie CRM, Kanban e o cadastro de novos leads.
    httpd = ThreadingHTTPServer(server_address, SofiPreviRequestHandler)
    print(f"============================================================")
    print(f"  SOFI.IA PREVI (PrevIA) - Servidor Web Revolucionario Rodando!")
    print(f"  Acesse no seu navegador: http://{host}:{port}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    # A porta pode ser passada como argumento para o launcher local, evitando
    # depender de estado global do ambiente durante reinicializações.
    requested_port = sys.argv[1] if len(sys.argv) > 1 else os.getenv("PORT", 8000)
    port = int(requested_port)
    run_server(port)
