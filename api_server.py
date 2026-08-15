"""Servidor REST HTTP em Python puro para a interface revolucionaria do SOFI.IA PREVI (PrevIA)."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import time
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
import document_intelligence
import document_rules
import official_catalog
import office_settings
from flows_data import FLOW_DEFINITIONS
from triage_engine import answer_current_question, create_state, get_current_node, get_result

# Garante inicializacao do banco de dados na partida
database.init_database()
database.register_official_sources(list(official_catalog.OFFICIAL_SOURCE_REGISTRY))


class SofiPreviRequestHandler(SimpleHTTPRequestHandler):
    """Handler HTTP customizado para API REST e arquivos estaticos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, data: dict | list, status_code: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    _rate_windows: dict[str, list[float]] = {}

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
        key = f"{ip}:{self.command}:{urllib.parse.urlparse(self.path).path}"
        recent = [value for value in self._rate_windows.get(key, []) if value > now - window_seconds]
        if len(recent) >= limit:
            self._rate_windows[key] = recent
            self._send_json({"error": "Muitas tentativas. Aguarde um minuto."}, 429)
            return False
        recent.append(now)
        self._rate_windows[key] = recent
        return True

    def _send_session_cookie(self, token: str) -> None:
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        self.send_header("Set-Cookie", f"sofia_session={token}; HttpOnly; SameSite=Strict; Path=/{secure}")

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
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
        if path.startswith("/api/") and path != "/api/auth/status":
            if not self._allow_request() or not self._require_auth():
                return

        # Rotas API
        if path == "/api/auth/status":
            self.handle_get_auth_status()
        elif path == "/api/office":
            self.handle_get_office()
        elif path == "/api/stats":
            self.handle_get_stats()
        elif path == "/api/atendimentos":
            self.handle_get_atendimentos(query)
        elif path == "/api/relacionamento":
            self.handle_get_relacionamento()
        elif path.startswith("/api/atendimentos/") and path.endswith("/documentos"):
            attendance_id = path.split("/")[3]
            self.handle_get_documentos(int(attendance_id))
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
        else:
            if path == "/" or not os.path.exists(os.path.join(BASE_DIR, path.lstrip("/"))):
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        login_limit = 5 if path in {"/api/auth/login", "/api/auth/register"} else 60
        if not self._allow_request(login_limit):
            return
        if path not in {"/api/auth/login", "/api/auth/register"} and not self._require_auth():
            return

        if path == "/api/auth/login":
            self.handle_post_login()
        elif path == "/api/auth/register":
            self.handle_post_register()
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
        elif path == "/api/triagem/executar":
            self.handle_post_triagem_executar()
        elif path == "/api/documentos/analisar":
            self.handle_post_documento_analisar()
        elif path == "/api/catalogo-cnis/monitorar":
            self.handle_post_monitor_official_sources()
        elif path == "/api/catalogo-cnis/importar-planilha":
            self.handle_post_import_catalog_workbook()
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

    def do_PUT(self) -> None:
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
        settings = office_settings.load_office_settings()
        self._send_json({
            "configured": configured,
            "office_name": settings.get("office_name", ""),
            "oab": settings.get("oab", "")
        })

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

        if auth_security.verify_credentials(email, password):
            token = auth_security.create_session()
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
        if auth_security.credentials_configured():
            self._send_json({"error": "Cadastro inicial já concluído."}, 403)
            return

        try:
            auth_security.save_credentials(email, password)
            office_settings.save_office_settings({
                "office_name": office_name,
                "oab": oab,
                "responsavel_email": email
            })
            token = auth_security.create_session()
            self.send_response(201)
            self._send_session_cookie(token)
            payload = json.dumps({"success": True, "office_name": office_name}, ensure_ascii=False).encode("utf-8")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except ValueError as e:
            self._send_json({"error": str(e)}, 400)

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
            item["documents"] = [dict(d) for d in docs]

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
        self._send_json([dict(d) for d in docs])

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
                critical_fields=["nome", "cpf", "nit", "data_nascimento", "competencias", "indicadores", "vinculos"],
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
            cnis_report["metricas"]["alertas_contagem"] = len(catalog_matches)
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
    server_address = ("", port)
    # A leitura de PDF/OCR pode levar alguns segundos. Um servidor concorrente
    # impede que essa tarefa bloqueie CRM, Kanban e o cadastro de novos leads.
    httpd = ThreadingHTTPServer(server_address, SofiPreviRequestHandler)
    print(f"============================================================")
    print(f"  SOFI.IA PREVI (PrevIA) - Servidor Web Revolucionario Rodando!")
    print(f"  Acesse no seu navegador: http://localhost:{port}")
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
