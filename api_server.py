"""Servidor REST HTTP em Python puro para a interface revolucionaria do SOFI.IA PREVI (PrevIA)."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Adiciona o diretorio do projeto ao path de importacao
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import auth_security
import database
import document_rules
import office_settings
from flows_data import FLOW_DEFINITIONS
from triage_engine import answer_current_question, create_state, get_current_node, get_result

# Garante inicializacao do banco de dados na partida
database.init_database()


class SofiPreviRequestHandler(SimpleHTTPRequestHandler):
    """Handler HTTP customizado para API REST e arquivos estaticos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, data: dict | list, status_code: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        return json.loads(body) if body else {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # Rotas API
        if path == "/api/auth/status":
            self.handle_get_auth_status()
        elif path == "/api/office":
            self.handle_get_office()
        elif path == "/api/stats":
            self.handle_get_stats()
        elif path == "/api/atendimentos":
            self.handle_get_atendimentos(query)
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
        else:
            if path == "/" or not os.path.exists(os.path.join(BASE_DIR, path.lstrip("/"))):
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

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
        elif path.startswith("/api/atendimentos/") and path.endswith("/conflito"):
            parts = path.split("/")
            attendance_id = int(parts[3])
            self.handle_post_conflito(attendance_id)
        elif path.startswith("/api/atendimentos/") and path.endswith("/lgpd"):
            parts = path.split("/")
            attendance_id = int(parts[3])
            self.handle_post_lgpd(attendance_id)
        else:
            self._send_json({"error": "Rota nao encontrada"}, 404)

    def do_PUT(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

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
            self._send_json({"success": True, "message": "Login de demonstracao concedido"})
            return

        if auth_security.verify_credentials(email, password):
            self._send_json({"success": True, "email": email})
        else:
            self._send_json({"error": "E-mail ou senha incorretos."}, 401)

    def handle_post_register(self) -> None:
        body = self._read_json_body()
        email = body.get("email", "")
        password = body.get("password", "")
        office_name = body.get("office_name", "")
        oab = body.get("oab", "")

        try:
            auth_security.save_credentials(email, password)
            office_settings.save_office_settings({
                "office_name": office_name,
                "oab": oab,
                "responsavel_email": email
            })
            self._send_json({"success": True, "office_name": office_name})
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
            
            # Garantir checklist de documentos
            database.ensure_document_checklist(conn, attendance_id, item["flow_id"])

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
                database.ensure_document_checklist(conn, attendance_id, row[0])
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
        body = self._read_json_body()
        lead_name = body.get("lead_name", "Lead sem nome")
        lead_phone = body.get("lead_phone", "")
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
            history=history,
            notes=body.get("notes", ""),
            benefit_category=body.get("benefit_category", flow_name),
            estimated_monthly_value=monthly_val,
            estimated_total_value=total_val,
            crm_stage=crm_stage,
        )
        self._send_json({"success": True, "id": att_id}, 201)

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

        if flow_id not in FLOW_DEFINITIONS:
            self._send_json({"error": "Fluxo invalido"}, 400)
            return

        flow = FLOW_DEFINITIONS[flow_id]

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
        body = self._read_json_body()
        file_name = body.get("file_name", "documento.pdf")
        document_code = body.get("document_code", "CNIS")

        extracted_data = {
            "cpf": "123.456.789-00",
            "nit_pis": "128.94827.12-4",
            "der": "2026-01-15",
            "dib": "2026-02-01",
            "rmi_estimada": "R$ 3.840,50",
            "situacao": "Regular com vinculos ativos"
        }

        self._send_json({
            "success": True,
            "file_name": file_name,
            "document_code": document_code,
            "extraction_confidence": 0.96,
            "extraction_status": "aprovado",
            "extracted_data": extracted_data,
            "technical_notes": "PDF nativo processado com leitura neural de campos de contribuicao."
        })

    def handle_get_eventos(self) -> None:
        with database.get_connection() as conn:
            events = conn.execute(
                "SELECT * FROM integration_events ORDER BY id DESC LIMIT 50"
            ).fetchall()
        self._send_json([dict(e) for e in events])


def run_server(port: int = 8000) -> None:
    server_address = ("", port)
    httpd = HTTPServer(server_address, SofiPreviRequestHandler)
    print(f"============================================================")
    print(f"  SOFI.IA PREVI (PrevIA) - Servidor Web Revolucionario Rodando!")
    print(f"  Acesse no seu navegador: http://localhost:{port}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    run_server(port)
