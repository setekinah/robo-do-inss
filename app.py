from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from automation_orchestrator import (
    EVENT_RULES,
    process_event,
    process_pending_events,
    receive_and_process_event,
    receive_event,
)
from auth_security import (
    credentials_configured,
    save_credentials,
    validate_email,
    validate_password,
    validate_whatsapp,
    verify_credentials,
)
from database import (
    add_crm_activity,
    complete_crm_task,
    create_crm_task,
    get_document_pipeline_summary,
    get_integration_summary,
    get_crm_summary,
    get_crm_performance,
    get_attendance_details,
    get_dashboard_summary,
    init_database,
    list_attendance_documents,
    list_crm_activities,
    list_crm_tasks,
    list_document_pipeline_attendances,
    list_integration_audit,
    list_integration_events,
    list_recent_attendances,
    load_history,
    retry_integration_event,
    review_crm_task,
    save_attendance,
    search_attendances,
    update_crm_case,
    update_attendance_document,
)
from document_intelligence import analyze_document_bundle, get_ocr_capabilities
from document_rules import get_flow_document_strategy
from document_storage import save_uploaded_document
from flows_data import FLOW_DEFINITIONS
from office_settings import load_office_settings, resolve_fee_percentage, save_office_settings
from repositories.calculation_repository import CalculationRepository
from repositories.reference_data_repository import ReferenceDataRepository
from repositories.cnis_import_repository import CnisImportRepository
from services.contract_service import build_fee_contract_preview as build_contract_preview
from services.document_score_service import build_document_case_score as calculate_document_case_score
from services.maternity_benefit_service import clamp_benefit_value as clamp_maternity_benefit_value
from services.rgps_planning_service import RgpsPlanningInput, RULESET_VERSION, screen_rgps_planning, serialize_planning_result
from services.reference_data_service import ReferenceDataset
from services.date_calculation_service import calculate_day_interval
from services.cnis_import_service import build_cnis_preview
from services.crm_ux_catalog import CRM_UX_CATALOG
from triage_engine import answer_current_question, create_state, get_current_node, get_result, step_back


st.set_page_config(
    page_title="SOFI.IA PREVI",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)


STATUS_STYLE = {
    "aprovado": ("Qualificado", "#e8fff1", "#18794e"),
    "revisao": ("Em revisao", "#fff6df", "#9a6700"),
    "desqualificado": ("Desqualificado", "#fff1f1", "#b42318"),
}
DOCUMENT_STATUS_STYLE = {
    "pendente": ("Pendente", "#fff7e8", "#9a6408"),
    "recebido": ("Recebido", "#eef5ff", "#1d4f91"),
    "em_validacao": ("Em validacao", "#f4efff", "#6941c6"),
    "validado": ("Validado", "#edf7f0", "#1f6a3d"),
    "ilegivel": ("Ilegivel", "#fff1f1", "#b42318"),
    "inconsistente": ("Inconsistente", "#ffe9e7", "#c4320a"),
    "dispensado": ("Dispensado", "#f3f4f6", "#475467"),
}
EXTRACTION_STATUS_STYLE = {
    "nao_processado": ("Nao processado", "#f3f4f6", "#475467"),
    "extraido": ("Texto extraido", "#edf7f0", "#1f6a3d"),
    "parcial": ("Extracao parcial", "#fff7e8", "#9a6408"),
    "sem_texto": ("Sem texto util", "#fff1f1", "#b42318"),
    "dependencia_ausente": ("Dependencia ausente", "#f4efff", "#6941c6"),
    "erro": ("Erro tecnico", "#ffe9e7", "#c4320a"),
}

SALARIO_MINIMO_2026 = 1621.00
TETO_INSS_2026 = 8537.55
APP_VERSION = "v1.2.1"
BRAND_NAME = "SOFI.IA PREVI"
AGENT_NAME = "Sofia"
BRAND_SLOGAN = "o seu conhecimento juridico no mundo previdenciario"
NAV_ITEMS = [
    ("dashboard", "Visão geral", "📊"),
    ("leads", "Atendimentos", "👥"),
    ("crm", "Carteira", "📋"),
    ("contratos", "Contratos", "📄"),
    ("configuracoes", "Configurações", "⚙️"),
]
NAV_MATERIAL_ICONS = {
    "dashboard": ":material/dashboard:",
    "leads": ":material/groups:",
    "crm": ":material/view_kanban:",
    "contratos": ":material/description:",
    "configuracoes": ":material/settings:",
}

NAV_ITEMS.append(("calculos", "Cálculos", "🧮"))
NAV_MATERIAL_ICONS["calculos"] = ":material/calculate:"

CRM_STAGES = [
    ("novo_contato", "Novo contato"),
    ("conflito", "Conflito pendente"),
    ("triagem", "Triagem"),
    ("reuniao", "Reunião"),
    ("proposta", "Proposta / contrato"),
    ("documentos", "Documentos"),
    ("caso_ativo", "Caso ativo"),
    ("encerrado", "Encerrado"),
    ("perdido", "Perdido"),
]
CONFLICT_STATUS = {
    "pendente": "Pendente de checagem",
    "liberado": "Liberado",
    "conflito": "Conflito identificado",
}

FEATURE_CARDS = [
    (
        "🎙️",
        "Responde em audio",
        "Se o lead manda audio, a Sofia responde em audio com voz personalizada e conduz o atendimento com naturalidade.",
    ),
    (
        "🧠",
        "Motor de elegibilidade com IA",
        "A Sofia cobre os principais beneficios previdenciarios e calcula score de exito com checklist documental.",
    ),
    (
        "🧾",
        "Contrato pelo celular",
        "Contrato, procuracao e declaracao enviados por WhatsApp com assinatura digital.",
    ),
    (
        "📊",
        "Dashboard de metricas",
        "Acompanhe taxas de conversao, tempo de resposta, leads por campanha e desempenho do escritorio em tempo real.",
    ),
    (
        "🔔",
        "Follow-up automatizado",
        "O sistema identifica leads parados e prepara lembretes automaticos para nao perder oportunidades.",
    ),
    (
        "📷",
        "Transcricao de imagem e PDF",
        "O lead manda foto do documento e o sistema transcreve automaticamente para leitura tecnica.",
    ),
    (
        "⚡",
        "Triagem em 3 minutos",
        "Perguntas dinamicas pulam etapas irrelevantes e aceleram a entrada do caso no funil.",
    ),
    (
        "🗂️",
        "CRM Kanban integrado",
        "Visao completa do funil: triagem, analise, contrato, documentos e caso ativo.",
    ),
    (
        "🔄",
        "Recupera leads perdidos",
        "Lead sem aderencia ao beneficio A pode ser redirecionado automaticamente para outro fluxo viavel.",
    ),
]
PROCESS_STEPS = [
    (
        "1",
        "Lead chega pelo WhatsApp",
        "Trafego pago, link na bio e QR code direcionam o lead para a esteira automatizada da Sofia.",
    ),
    (
        "2",
        "IA faz a triagem",
        "Perguntas dinamicas identificam beneficio, score de exito e checklist inicial sem sobrecarregar o lead.",
    ),
    (
        "3",
        "Voce valida com 1 clique",
        "O painel operacional concentra beneficio sugerido, status documental e priorizacao do escritorio.",
    ),
    (
        "4",
        "Contrato assinado pelo celular",
        "Contrato, procuracao e declaracoes saem para assinatura digital assim que o caso for aprovado.",
    ),
]
PLAN_OPTIONS = [
    {
        "id": "Essencial",
        "price": "R$ 297",
        "caption": "Ate 50 triagens/mes, 1 usuario, dashboard",
    },
    {
        "id": "Profissional",
        "price": "R$ 497",
        "caption": "Ilimitado, CRM, follow-up e transcricao de imagem",
    },
    {
        "id": "Premium",
        "price": "R$ 997",
        "caption": "Tudo + voz personalizada + API + onboarding",
    },
]
AUTH_HIGHLIGHTS = [
    ("01", "Triagem inteligente", "Sofia qualifica o lead, calcula aderencia e monta o proximo passo do caso."),
    ("02", "Documentos orquestrados", "Checklist, OCR e leitura tecnica entram no fluxo sem depender de operacao manual repetitiva."),
    ("03", "Contrato sem friccao", "O escritorio aprova e a esteira segue para assinatura, coleta e acompanhamento."),
]
PIPELINE_COLUMNS = [
    ("novo_contato", "Novo contato", "Entrada e retorno", "soft-blue"),
    ("conflito", "Conflito", "Checagem obrigatória", "soft-yellow"),
    ("triagem", "Triagem", "Entender o caso", "soft-purple"),
    ("reuniao", "Reunião", "Análise com advogado", "soft-teal"),
    ("proposta", "Proposta", "Contrato e contratação", "soft-green"),
    ("documentos", "Documentos", "Checklist e validação", "soft-orange"),
    ("caso_ativo", "Caso Ativo", "Com o advogado", "soft-teal"),
    ("encerrado", "Encerrado", "Atendimento concluído", "soft-neutral"),
    ("perdido", "Perdido", "Sem contratação", "soft-red"),
]
PIPELINE_PHASES = {
    "entrada": {
        "label": "Entrada e qualificação",
        "icon": "🧭",
        "stages": ["novo_contato", "conflito", "triagem"],
    },
    "conversao": {
        "label": "Conversão e contratação",
        "icon": "🤝",
        "stages": ["reuniao", "proposta", "documentos"],
    },
    "gestao": {
        "label": "Gestão e encerramento",
        "icon": "⚖️",
        "stages": ["caso_ativo", "encerrado", "perdido"],
    },
}
PRIVACY_LEGAL_BASES = {
    "procedimentos_preliminares": "Procedimentos preliminares ou contrato a pedido do titular",
    "exercicio_regular_direitos": "Exercício regular de direitos em processo judicial ou administrativo",
    "consentimento": "Consentimento específico do titular",
}
PIPELINE_STAGE_ICONS = {
    "novo_contato": ":material/person_add:",
    "conflito": ":material/gpp_maybe:",
    "triagem": ":material/fact_check:",
    "reuniao": ":material/event:",
    "proposta": ":material/handshake:",
    "documentos": ":material/folder_open:",
    "caso_ativo": ":material/work:",
    "encerrado": ":material/check_circle:",
    "perdido": ":material/cancel:",
}
INTEGRATION_SOURCE_LABELS = {
    "triagem_crm": "Triagem interna",
    "whatsapp": "WhatsApp",
    "datajud": "DataJud",
    "publicacoes": "Publicações",
    "meu_inss": "Meu INSS",
}
INTEGRATION_STATUS_LABELS = {
    "pendente": "Na fila",
    "processando": "Processando",
    "concluido": "Concluído",
    "falhou": "Falhou",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700;9..144,800&family=Manrope:wght@400;500;600;700;800&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0,0&display=swap');
        :root {
            --bg: #f6f8fc;
            --panel: rgba(255, 255, 255, 0.94);
            --panel-strong: #fbfdff;
            --border: rgba(27, 38, 52, 0.11);
            --text: #1f2430;
            --muted: #68758b;
            --navy: #152235;
            --navy-soft: #22324a;
            --navy-deep: #0f1827;
            --gold: #2f5bea;
            --gold-soft: #a9c2ff;
            --gold-pale: #edf3ff;
            --success-bg: #edf7f0;
            --success-text: #1f6a3d;
            --warning-bg: #fff7e8;
            --warning-text: #9a6408;
            --danger-bg: #fff0ef;
            --danger-text: #a23a31;
        }
        .stApp {
            background: #f6f8fc;
            color: var(--text);
        }
        html, body, [class*="css"], [data-testid="stAppViewContainer"] {
            font-family: "Manrope", "Segoe UI", sans-serif;
        }
        p, label, input, textarea, button {
            font-family: "Manrope", "Segoe UI", sans-serif !important;
        }
        [data-testid="stIconMaterial"] {
            font-family: "Material Symbols Rounded" !important;
            font-weight: normal !important;
            font-style: normal !important;
            font-size: 1.1rem !important;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            direction: ltr !important;
            -webkit-font-smoothing: antialiased;
            font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
        }
        .workspace-shell {
            display: grid;
            grid-template-columns: 300px minmax(0, 1fr);
            gap: 1.2rem;
            align-items: start;
        }
        .workspace-sidebar {
            position: sticky;
            top: 1rem;
            border-radius: 24px;
            padding: 1.2rem 1.1rem;
            background: linear-gradient(180deg, #142033 0%, #0d1725 100%);
            border: 1px solid rgba(181, 139, 71, 0.20);
            box-shadow: 0 18px 40px rgba(12, 20, 32, 0.18);
            color: #f4ecdf;
        }
        .workspace-sidebar h3 {
            margin: 0 0 0.35rem 0;
            color: #f7f1e8;
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1.45rem;
        }
        .workspace-sidebar p {
            color: rgba(244, 236, 223, 0.74);
            line-height: 1.6;
            font-size: 0.93rem;
        }
        .workspace-main {
            min-width: 0;
        }
        .workspace-kpis {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.9rem;
            margin-bottom: 1rem;
        }
        .kpi-card {
            border-radius: 22px;
            padding: 1rem 1.05rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(249,246,241,0.95) 100%);
            border: 1px solid rgba(21, 34, 53, 0.10);
            box-shadow: 0 14px 32px rgba(17, 25, 36, 0.06);
        }
        .kpi-label {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--muted);
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .kpi-value {
            color: var(--navy);
            font-family: Georgia, "Times New Roman", serif;
            font-size: 2rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 0.3rem;
        }
        .kpi-note {
            color: var(--muted);
            font-size: 0.86rem;
        }
        .triage-grid {
            display: grid;
            grid-template-columns: 320px minmax(0, 1fr) 360px;
            gap: 1rem;
            align-items: start;
        }
        .panel-box {
            border-radius: 24px;
            padding: 1.15rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(251,248,243,0.96) 100%);
            border: 1px solid rgba(21, 34, 53, 0.10);
            box-shadow: 0 16px 34px rgba(17, 25, 36, 0.06);
        }
        .queue-item {
            padding: 0.9rem 0.95rem;
            border-radius: 16px;
            background: rgba(255,255,255,0.78);
            border: 1px solid rgba(21, 34, 53, 0.08);
            margin-bottom: 0.7rem;
        }
        .queue-item strong {
            color: var(--navy);
        }
        .queue-item-meta {
            color: var(--muted);
            font-size: 0.86rem;
            margin-top: 0.2rem;
        }
        @media (max-width: 1200px) {
            .workspace-shell {
                grid-template-columns: 1fr;
            }
            .workspace-sidebar {
                position: static;
            }
            .triage-grid {
                grid-template-columns: 1fr;
            }
            .workspace-kpis {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 720px) {
            .workspace-kpis {
                grid-template-columns: 1fr;
            }
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #172235 0%, #101927 100%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        [data-testid="stSidebar"] * {
            color: #f5efe6 !important;
        }
        [data-testid="stHeader"] {
            background: rgba(247, 244, 238, 0.72);
            backdrop-filter: blur(10px);
        }
        [data-testid="stMetricValue"] {
            color: var(--navy);
            font-family: Georgia, "Times New Roman", serif;
        }
        [data-baseweb="tab-list"] {
            gap: 0.5rem;
            border-bottom: 1px solid rgba(24, 38, 58, 0.10);
            padding-bottom: 0.6rem;
        }
        button[kind="secondary"], button[kind="primary"] {
            border-radius: 999px !important;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(255,255,255,0.72);
            border: 1px solid rgba(24, 38, 58, 0.10);
            border-radius: 999px;
            padding: 0.5rem 1rem;
            color: var(--navy);
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, var(--navy) 0%, var(--navy-soft) 100%) !important;
            color: #ffffff !important;
            border-color: rgba(181, 139, 71, 0.35) !important;
        }
        .hero-card, .surface-card {
            border: 1px solid var(--border);
            border-radius: 26px;
            padding: 1.45rem 1.55rem;
            background: linear-gradient(180deg, var(--panel) 0%, var(--panel-strong) 100%);
            box-shadow: 0 18px 50px rgba(17, 25, 36, 0.08);
            position: relative;
            overflow: hidden;
        }
        .hero-card {
            background: linear-gradient(135deg, var(--navy-deep) 0%, var(--navy) 55%, var(--navy-soft) 100%);
            border: 1px solid rgba(181, 139, 71, 0.24);
            box-shadow: 0 22px 70px rgba(13, 21, 34, 0.26);
        }
        .hero-card::before, .surface-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 5px;
            background: linear-gradient(90deg, var(--gold) 0%, var(--navy) 100%);
        }
        .hero-card::after {
            content: "";
            position: absolute;
            width: 220px;
            height: 220px;
            right: -60px;
            top: -70px;
            background: radial-gradient(circle, rgba(181, 139, 71, 0.18) 0%, rgba(181, 139, 71, 0.02) 70%);
            border-radius: 50%;
        }
        .hero-title {
            font-size: 3rem;
            font-weight: 700;
            line-height: 1.02;
            margin: 0 0 0.5rem 0;
            color: #f8f3ea;
            font-family: Georgia, "Times New Roman", serif;
            letter-spacing: -0.02em;
        }
        .eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.22em;
            font-size: 0.70rem;
            font-weight: 700;
            color: var(--gold);
            margin-bottom: 0.75rem;
        }
        .hero-copy {
            color: rgba(245, 239, 230, 0.86);
            line-height: 1.72;
            margin-bottom: 0;
            font-size: 1rem;
        }
        .surface-card .hero-copy {
            color: var(--muted);
        }
        .surface-card .eyebrow {
            color: var(--gold);
        }
        .hero-note {
            margin-top: 1.1rem;
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            padding: 0.5rem 0.85rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.10);
            color: #f6efe4;
            font-size: 0.88rem;
            font-weight: 600;
        }
        .status-chip {
            display: inline-block;
            padding: 0.42rem 0.82rem;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.82rem;
            margin-bottom: 0.9rem;
            border: 1px solid rgba(0,0,0,0.05);
        }
        .history-item {
            border-left: 4px solid var(--gold);
            padding: 0.8rem 0.95rem;
            margin-bottom: 0.7rem;
            background: rgba(255,255,255,0.78);
            border-radius: 14px;
            box-shadow: inset 0 0 0 1px rgba(24, 38, 58, 0.06);
        }
        .muted {
            color: var(--muted);
        }
        .section-title {
            color: var(--navy);
            font-family: Georgia, "Times New Roman", serif;
            font-size: 2rem;
            margin-bottom: 0.25rem;
        }
        .section-kicker {
            text-transform: uppercase;
            letter-spacing: 0.18em;
            color: var(--gold);
            font-size: 0.74rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 16px !important;
            border: 1px solid rgba(24, 38, 58, 0.12) !important;
            background: rgba(255,255,255,0.86) !important;
        }
        .stButton > button {
            background: linear-gradient(180deg, var(--navy) 0%, var(--navy-soft) 100%);
            color: #ffffff;
            border: 1px solid rgba(0,0,0,0.05);
            font-weight: 600;
            box-shadow: 0 10px 20px rgba(24, 38, 58, 0.14);
            border-radius: 14px !important;
            min-height: 2.9rem;
        }
        .stButton > button:hover {
            border-color: rgba(176, 138, 74, 0.40);
            color: #ffffff;
        }
        .stButton > button:disabled,
        .stButton > button[disabled] {
            background: linear-gradient(180deg, #d9d6d0 0%, #cfc9c0 100%) !important;
            color: #6e675d !important;
            border: 1px solid rgba(24, 38, 58, 0.10) !important;
            box-shadow: none !important;
            cursor: not-allowed !important;
            opacity: 1 !important;
        }
        .stAlert {
            border-radius: 16px;
            border: 1px solid rgba(24, 38, 58, 0.08);
        }
        .stMarkdown h3, .stMarkdown h4 {
            color: var(--navy);
            font-family: Georgia, "Times New Roman", serif;
        }
        .stSubheader, h2 {
            color: var(--navy) !important;
            font-family: Georgia, "Times New Roman", serif !important;
            letter-spacing: -0.01em;
        }
        [data-testid="stMetric"] {
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(21, 34, 53, 0.08);
            border-radius: 18px;
            padding: 0.65rem 0.85rem;
            box-shadow: 0 10px 24px rgba(17, 25, 36, 0.04);
        }
        [data-testid="stMetric"]:first-child {
            border-top: 3px solid var(--gold);
        }
        [data-testid="stMetricLabel"] {
            color: var(--muted);
            font-weight: 600;
        }
        .main .block-container {
            max-width: 1420px;
            padding-top: 1.8rem;
            padding-bottom: 3rem;
        }
        .app-ribbon {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 1rem 1.15rem;
            margin-bottom: 1.2rem;
            border-radius: 20px;
            background: linear-gradient(90deg, #132033 0%, #1d2e45 100%);
            color: #f6efe4;
            border: 1px solid rgba(181, 139, 71, 0.22);
            box-shadow: 0 16px 40px rgba(13, 21, 34, 0.16);
        }
        .app-ribbon-title {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .app-ribbon-copy {
            color: rgba(246, 239, 228, 0.78);
            font-size: 0.92rem;
            margin-top: 0.1rem;
        }
        .app-ribbon-badge {
            padding: 0.4rem 0.8rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            font-size: 0.82rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .panel-heading {
            margin-bottom: 1rem;
        }
        .panel-kicker {
            text-transform: uppercase;
            letter-spacing: 0.18em;
            color: var(--gold);
            font-size: 0.72rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }
        .panel-title {
            color: var(--navy);
            font-family: Georgia, "Times New Roman", serif;
            font-size: 2rem;
            line-height: 1.05;
            margin: 0;
        }
        .panel-subtitle {
            color: var(--muted);
            margin-top: 0.45rem;
            font-size: 0.96rem;
        }
        .history-item strong {
            color: var(--navy);
        }
        hr {
            border-color: rgba(24, 38, 58, 0.08);
        }
        [data-testid="stSidebar"] {
            display: none;
        }
        [data-testid="collapsedControl"] {
            display: none;
        }
        .stApp {
            background: #f5f7fb;
        }
        .main .block-container {
            max-width: 100%;
            padding: 1rem 1.2rem 2rem;
        }
        .pre-shell {
            display: grid;
            grid-template-columns: 272px minmax(0, 1fr);
            gap: 1.35rem;
            min-height: calc(100vh - 2rem);
        }
        .pre-sidebar {
            position: sticky;
            top: 1rem;
            min-height: calc(100vh - 2rem);
            background:
                radial-gradient(circle at top right, rgba(96, 165, 250, 0.16) 0%, rgba(96, 165, 250, 0.00) 32%),
                linear-gradient(180deg, #0f172a 0%, #13233c 100%);
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 24px;
            padding: 1.3rem 1rem;
            box-shadow: 0 22px 46px rgba(15, 23, 42, 0.18);
        }
        .pre-brand {
            margin-bottom: 1rem;
        }
        .pre-brand h1 {
            margin: 0;
            color: #f8fafc;
            font-size: 1.9rem;
            font-family: "Fraunces", Georgia, serif;
            font-weight: 800;
        }
        .pre-brand p {
            margin: 0.1rem 0 0;
            color: rgba(226, 232, 240, 0.72);
            font-size: 0.92rem;
            line-height: 1.55;
        }
        .pre-sidebar-panel {
            margin-bottom: 1.1rem;
            padding: 0.95rem 1rem;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
        }
        .pre-sidebar-label {
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: rgba(191, 219, 254, 0.78);
            font-size: 0.68rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
        }
        .pre-sidebar-value {
            color: #f8fafc;
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.18rem;
        }
        .pre-sidebar-caption {
            color: rgba(226, 232, 240, 0.68);
            font-size: 0.85rem;
            line-height: 1.55;
        }
        .pre-nav-item {
            padding: 0.9rem 1rem;
            border-radius: 14px;
            margin-bottom: 0.45rem;
            background: #ffffff;
            border: 1px solid transparent;
            color: #1f2a44;
            font-weight: 600;
        }
        .pre-nav-item.active {
            background: #edf3ff;
            color: #2f5bea;
            border-color: #dbe5ff;
        }
        .pre-content {
            min-width: 0;
        }
        .pre-sidebar .stButton > button {
            width: 100%;
            justify-content: flex-start;
            text-align: left;
            border-radius: 14px !important;
            min-height: 48px;
            box-shadow: none;
            font-weight: 700;
        }
        .pre-sidebar .stButton > button[kind="secondary"] {
            background: rgba(255,255,255,0.04) !important;
            color: rgba(241,245,249,0.92) !important;
            border: 1px solid rgba(255,255,255,0.06) !important;
        }
        .pre-sidebar .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, rgba(47,91,234,0.92) 0%, rgba(59,130,246,0.96) 100%) !important;
            color: #ffffff !important;
            border: 1px solid rgba(96,165,250,0.75) !important;
            box-shadow: 0 14px 28px rgba(37, 99, 235, 0.20) !important;
        }
        button[kind="secondary"] {
            background: #ffffff !important;
            color: #1f2a44 !important;
            border: 1px solid #d7dfec !important;
            box-shadow: none !important;
        }
        button[kind="primary"] {
            background: #2f5bea !important;
            color: #ffffff !important;
            border: 1px solid #2f5bea !important;
            box-shadow: none !important;
        }
        button[kind="secondary"]:hover,
        button[kind="primary"]:hover {
            transform: translateY(-1px);
        }
        button[kind="secondary"][disabled],
        button[kind="primary"][disabled] {
            background: #edf1f7 !important;
            color: #94a3b8 !important;
            border: 1px solid #d7dfec !important;
            box-shadow: none !important;
            cursor: not-allowed !important;
        }
        .stTextInput input,
        .stTextArea textarea,
        .stNumberInput input,
        .stSelectbox div[data-baseweb="select"] > div {
            border: 1px solid #d7dfec !important;
            background: #ffffff !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }
        .pre-page-header {
            margin: 0.4rem 0 1.4rem;
        }
        .pre-page-header h2 {
            margin: 0;
            color: #111827;
            font-size: 2.15rem;
            font-family: "Fraunces", Georgia, serif;
            font-weight: 800;
        }
        .pre-page-header p {
            margin: 0.25rem 0 0;
            color: #73819c;
            font-size: 1rem;
        }
        .pre-card {
            background: #ffffff;
            border: 1px solid #e7edf6;
            border-radius: 20px;
            padding: 1.2rem 1.25rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
        }
        .pre-spotlight {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
            color: #ffffff;
            border: 1px solid rgba(59, 130, 246, 0.18);
            border-radius: 24px;
            padding: 1.45rem 1.5rem;
            box-shadow: 0 22px 46px rgba(37, 99, 235, 0.16);
        }
        .pre-spotlight::after {
            content: "";
            position: absolute;
            inset: auto -60px -80px auto;
            width: 220px;
            height: 220px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(255,255,255,0.22) 0%, rgba(255,255,255,0.02) 70%);
        }
        .pre-spotlight .eyebrow {
            color: rgba(191, 219, 254, 0.92);
            margin-bottom: 0.9rem;
        }
        .pre-spotlight h3 {
            margin: 0;
            font-size: 2.15rem;
            line-height: 1.08;
            color: #ffffff;
            font-family: "Fraunces", Georgia, serif;
            max-width: 11ch;
        }
        .pre-spotlight p {
            margin: 0.8rem 0 0;
            color: rgba(255,255,255,0.84);
            line-height: 1.72;
            max-width: 60ch;
        }
        .pre-inline-stats {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 1.2rem;
        }
        .pre-inline-stat {
            border-radius: 18px;
            padding: 0.9rem 1rem;
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.14);
            backdrop-filter: blur(8px);
        }
        .pre-inline-stat strong {
            display: block;
            color: #ffffff;
            font-size: 1.55rem;
            font-weight: 800;
        }
        .pre-inline-stat span {
            color: rgba(255,255,255,0.76);
            font-size: 0.86rem;
        }
        .pre-meta-list {
            display: grid;
            gap: 0.75rem;
        }
        .pre-meta-item {
            padding: 0.95rem 1rem;
            border-radius: 16px;
            background: #f8fbff;
            border: 1px solid #e6eefb;
        }
        .pre-meta-item strong {
            display: block;
            color: #111827;
            margin-bottom: 0.2rem;
            font-size: 0.95rem;
        }
        .pre-meta-item span {
            color: #667085;
            line-height: 1.6;
            font-size: 0.9rem;
        }
        .pre-metric-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.95rem;
            margin-bottom: 1rem;
        }
        .pre-metric-card {
            border-radius: 18px;
            padding: 1rem 1rem 0.95rem;
            min-height: 92px;
            border: 1px solid transparent;
        }
        .pre-metric-card h3 {
            margin: 0;
            color: #111827;
            font-size: 2rem;
            font-family: "Segoe UI", "Inter", sans-serif;
            font-weight: 800;
        }
        .pre-metric-card p {
            margin: 0.35rem 0 0;
            color: #6b7280;
            font-size: 0.95rem;
        }
        .soft-neutral { background: #f3f4f6; }
        .soft-yellow { background: #fff4bf; }
        .soft-blue { background: #dceafe; }
        .soft-green { background: #d9fbe5; }
        .soft-orange { background: #fde9cf; }
        .soft-teal { background: #d6f5e7; }
        .soft-purple { background: #efe7ff; }
        .pre-chip-row {
            display: flex;
            gap: 0.7rem;
            flex-wrap: wrap;
            margin-bottom: 1rem;
        }
        .pre-chip {
            border: 1px solid #dbe5ff;
            background: #ffffff;
            color: #304156;
            border-radius: 12px;
            padding: 0.55rem 0.95rem;
            font-size: 0.92rem;
            font-weight: 600;
        }
        .pre-chip.active {
            background: #2f5bea;
            color: #ffffff;
            border-color: #2f5bea;
        }
        .pre-empty-state {
            color: #99a3ba;
            font-size: 1.1rem;
            text-align: center;
            padding: 4rem 1rem 2rem;
        }
        .pre-feature-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1.5rem;
        }
        .pre-feature-card {
            background: #ffffff;
            border: 1px solid #edf1f7;
            border-radius: 20px;
            padding: 1.4rem;
            min-height: 205px;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.04);
        }
        .pre-feature-card .icon {
            font-size: 1.55rem;
            margin-bottom: 0.75rem;
        }
        .pre-feature-card h4 {
            margin: 0 0 0.6rem 0;
            color: #0f172a;
            font-size: 1.18rem;
            font-family: "Fraunces", Georgia, serif;
            font-weight: 700;
        }
        .pre-feature-card p {
            margin: 0;
            color: #667085;
            line-height: 1.65;
        }
        .pre-process-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin: 1rem 0 1.3rem;
        }
        .pre-process-card {
            background: #ffffff;
            border: 1px solid #ebf0f7;
            border-radius: 22px;
            padding: 1.2rem;
            box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
        }
        .pre-process-index {
            width: 42px;
            height: 42px;
            border-radius: 14px;
            background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
            color: #1d4ed8;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            margin-bottom: 0.9rem;
        }
        .pre-process-card h4 {
            margin: 0 0 0.5rem;
            color: #0f172a;
            font-size: 1.05rem;
            font-family: "Fraunces", Georgia, serif;
        }
        .pre-process-card p {
            margin: 0;
            color: #667085;
            line-height: 1.7;
            font-size: 0.92rem;
        }
        .pre-kanban-grid {
            display: grid;
            grid-template-columns: repeat(6, minmax(220px, 1fr));
            gap: 0.85rem;
            align-items: start;
            overflow-x: auto;
            padding-bottom: 0.3rem;
        }
        .pre-kanban-column {
            background: #ffffff;
            border: 1px solid #e9edf5;
            border-radius: 18px;
            min-height: 420px;
            overflow: hidden;
        }
        .pre-kanban-header {
            padding: 0.9rem 0.95rem 0.75rem;
            border-bottom: 1px solid #edf1f7;
        }
        .pre-kanban-header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.75rem;
            font-weight: 700;
            color: #111827;
        }
        .pre-kanban-header-top span:last-child {
            background: rgba(255,255,255,0.88);
            border-radius: 999px;
            min-width: 26px;
            height: 26px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.83rem;
        }
        .pre-kanban-subtitle {
            color: #6b7280;
            font-size: 0.8rem;
            margin-top: 0.35rem;
        }
        .pre-kanban-body {
            padding: 0.9rem;
        }
        .pre-lead-card {
            background: #ffffff;
            border: 1px solid #eef2f7;
            border-radius: 14px;
            padding: 0.85rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
        }
        .pre-lead-card.selected {
            border-color: #bfd3ff;
            background: linear-gradient(180deg, #eff4ff 0%, #ffffff 100%);
            box-shadow: 0 12px 26px rgba(47, 91, 234, 0.10);
        }
        .pre-lead-card h5 {
            margin: 0 0 0.35rem 0;
            color: #162033;
            font-size: 1rem;
            font-weight: 700;
        }
        .pre-lead-card p {
            margin: 0.14rem 0;
            color: #667085;
            font-size: 0.88rem;
        }
        .pre-section-title {
            margin: 0 0 0.8rem 0;
            color: #111827;
            font-size: 1.55rem;
            font-family: "Fraunces", Georgia, serif;
            font-weight: 800;
        }
        .pre-toolbar {
            display: grid;
            grid-template-columns: minmax(0, 1.45fr) minmax(240px, 0.72fr);
            gap: 0.95rem;
            margin-bottom: 1rem;
        }
        .pre-stage-strip {
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 0.95rem;
            margin-bottom: 1rem;
        }
        .pre-stage-card {
            background: #ffffff;
            border: 1px solid #e7edf6;
            border-radius: 20px;
            padding: 1rem 1rem 0.95rem;
            box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
        }
        .pre-stage-card strong {
            display: block;
            color: #111827;
            font-size: 1.9rem;
            font-weight: 800;
            line-height: 1;
        }
        .pre-stage-card h4 {
            margin: 0.25rem 0 0.2rem;
            color: #162033;
            font-size: 1rem;
            font-family: "Fraunces", Georgia, serif;
        }
        .pre-stage-card span {
            color: #667085;
            font-size: 0.84rem;
            line-height: 1.55;
        }
        .pre-card-stack {
            display: grid;
            gap: 1rem;
        }
        .pre-task-list {
            display: grid;
            gap: 0.8rem;
        }
        .pre-task-item {
            border: 1px solid #e8edf6;
            border-radius: 18px;
            padding: 1rem;
            background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        }
        .pre-task-priority {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.3rem 0.7rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        }
        .pre-task-priority.alta {
            background: #fff0ef;
            color: #b42318;
        }
        .pre-task-priority.media {
            background: #fff7e8;
            color: #9a6408;
        }
        .pre-task-priority.baixa {
            background: #edf7f0;
            color: #1f6a3d;
        }
        .pre-task-item h4 {
            margin: 0 0 0.3rem;
            color: #0f172a;
            font-size: 1rem;
            font-family: "Fraunces", Georgia, serif;
        }
        .pre-task-item p {
            margin: 0;
            color: #667085;
            line-height: 1.65;
            font-size: 0.9rem;
        }
        .pre-focus-hero {
            position: relative;
            overflow: hidden;
            border-radius: 20px;
            padding: 1.15rem 1.2rem;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #ffffff;
            margin-bottom: 1rem;
        }
        .pre-focus-hero::after {
            content: "";
            position: absolute;
            inset: auto -44px -56px auto;
            width: 180px;
            height: 180px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.00) 70%);
        }
        .pre-focus-hero h3 {
            margin: 0.2rem 0 0.35rem;
            color: #ffffff;
            font-size: 1.8rem;
            font-family: "Fraunces", Georgia, serif;
        }
        .pre-focus-hero p {
            margin: 0;
            color: rgba(226, 232, 240, 0.82);
            line-height: 1.65;
        }
        .pre-focus-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
            margin: 1rem 0;
        }
        .pre-focus-stat {
            padding: 0.9rem 0.95rem;
            border-radius: 16px;
            background: #f8fbff;
            border: 1px solid #e6eefb;
        }
        .pre-focus-stat strong {
            display: block;
            color: #111827;
            font-size: 1.1rem;
            margin-bottom: 0.18rem;
        }
        .pre-focus-stat span {
            color: #667085;
            font-size: 0.84rem;
            line-height: 1.55;
        }
        .pre-detail-list {
            display: grid;
            gap: 0.7rem;
            margin: 0.9rem 0 0;
        }
        .pre-detail-row {
            padding: 0.88rem 0.95rem;
            border-radius: 16px;
            background: #f8fafc;
            border: 1px solid #ecf0f5;
        }
        .pre-detail-row strong {
            display: block;
            color: #0f172a;
            margin-bottom: 0.2rem;
        }
        .pre-detail-row span {
            color: #667085;
            line-height: 1.6;
            font-size: 0.9rem;
        }
        .pre-action-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 1rem;
        }
        .pre-dataframe-card [data-testid="stDataFrame"] {
            border: 1px solid #e7edf6;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.02);
        }
        .pre-two-column {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
        }
        .pre-plan-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.95rem;
        }
        .pre-plan-card {
            background: #ffffff;
            border: 1px solid #dce5f2;
            border-radius: 20px;
            padding: 1.1rem;
            min-height: 170px;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
        }
        .pre-plan-card.active {
            border-color: #2f5bea;
            background: linear-gradient(180deg, #eff4ff 0%, #ffffff 100%);
            box-shadow: 0 14px 28px rgba(47, 91, 234, 0.10);
        }
        .pre-plan-card h4 {
            margin: 0 0 0.55rem;
            color: #111827;
            font-size: 1.2rem;
            font-family: "Fraunces", Georgia, serif;
        }
        .pre-plan-price {
            color: #0f172a;
            font-size: 1.95rem;
            font-weight: 800;
            margin-bottom: 0.35rem;
        }
        .pre-plan-card p {
            margin: 0;
            color: #667085;
            line-height: 1.7;
            font-size: 0.92rem;
        }
        .auth-hero-panel {
            position: relative;
            overflow: hidden;
            border-radius: 34px;
            min-height: 760px;
            background:
                radial-gradient(circle at 20% 18%, rgba(0, 229, 255, 0.18) 0%, rgba(0, 229, 255, 0.02) 32%),
                radial-gradient(circle at 82% 22%, rgba(96, 165, 250, 0.22) 0%, rgba(96, 165, 250, 0.02) 28%),
                linear-gradient(145deg, #07111f 0%, #0c1729 48%, #111f38 100%);
            border: 1px solid rgba(102, 190, 255, 0.18);
            box-shadow: 0 28px 90px rgba(4, 14, 28, 0.34);
            padding: 2rem 2rem 1.8rem;
        }
        .auth-hero-panel::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(96, 165, 250, 0.07) 1px, transparent 1px),
                linear-gradient(90deg, rgba(96, 165, 250, 0.07) 1px, transparent 1px);
            background-size: 34px 34px;
            mask-image: linear-gradient(180deg, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0.08) 100%);
            pointer-events: none;
        }
        .auth-hero-panel::after {
            content: "";
            position: absolute;
            right: -70px;
            top: -70px;
            width: 260px;
            height: 260px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(0,229,255,0.34) 0%, rgba(0,229,255,0.02) 70%);
            filter: blur(10px);
            pointer-events: none;
        }
        .auth-kicker {
            position: relative;
            z-index: 1;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.46rem 0.9rem;
            border-radius: 999px;
            border: 1px solid rgba(126, 211, 255, 0.22);
            background: rgba(11, 27, 45, 0.62);
            color: #a5f3fc;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-size: 0.72rem;
            font-weight: 700;
            backdrop-filter: blur(14px);
        }
        .auth-brand-stack {
            position: relative;
            z-index: 1;
            margin-top: 1.55rem;
        }
        .auth-brand-stack h1 {
            margin: 0;
            color: #f8fbff;
            font-size: 4rem;
            line-height: 0.98;
            font-family: "Fraunces", Georgia, serif;
            letter-spacing: -0.04em;
        }
        .auth-agent-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            margin-top: 1rem;
            padding: 0.6rem 0.95rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(147, 197, 253, 0.16);
            color: #dbeafe;
            font-weight: 700;
            backdrop-filter: blur(10px);
        }
        .auth-brand-stack p {
            max-width: 58ch;
            margin: 1rem 0 0;
            color: rgba(222, 234, 248, 0.82);
            line-height: 1.78;
            font-size: 1rem;
        }
        .auth-signal-row {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.95rem;
            margin-top: 1.55rem;
        }
        .auth-signal-card {
            border-radius: 20px;
            border: 1px solid rgba(147, 197, 253, 0.12);
            background: rgba(7, 22, 38, 0.52);
            padding: 1rem 1rem 0.95rem;
            backdrop-filter: blur(12px);
        }
        .auth-signal-card strong {
            display: block;
            color: #f8fbff;
            font-size: 1.7rem;
            font-weight: 800;
        }
        .auth-signal-card span {
            color: rgba(222, 234, 248, 0.68);
            font-size: 0.86rem;
        }
        .auth-highlight-grid {
            position: relative;
            z-index: 1;
            display: grid;
            gap: 0.95rem;
            margin-top: 1.7rem;
        }
        .auth-highlight-card {
            display: grid;
            grid-template-columns: 54px minmax(0, 1fr);
            gap: 0.95rem;
            align-items: start;
            border-radius: 22px;
            border: 1px solid rgba(147, 197, 253, 0.12);
            background: rgba(9, 24, 41, 0.48);
            padding: 1.05rem 1.1rem;
            backdrop-filter: blur(16px);
        }
        .auth-highlight-index {
            width: 54px;
            height: 54px;
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(96, 165, 250, 0.16) 0%, rgba(34, 211, 238, 0.16) 100%);
            border: 1px solid rgba(125, 211, 252, 0.22);
            color: #e0f2fe;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 1rem;
        }
        .auth-highlight-copy h4 {
            margin: 0 0 0.32rem;
            color: #f8fbff;
            font-size: 1.06rem;
            font-family: "Fraunces", Georgia, serif;
        }
        .auth-highlight-copy p {
            margin: 0;
            color: rgba(221, 230, 241, 0.72);
            line-height: 1.7;
            font-size: 0.92rem;
        }
        .auth-mode-switch {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
            margin-bottom: 1rem;
        }
        .auth-form-marker { display:none; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.auth-form-marker) {
            border-radius:24px !important;
            padding:1.35rem 1.4rem !important;
            border:1px solid rgba(148,163,184,.20) !important;
            background:linear-gradient(180deg,#ffffff 0%,#f8faff 100%) !important;
            box-shadow:0 18px 54px rgba(15,23,42,.09) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.auth-form-marker) [data-testid="stForm"] {
            border:0 !important;
            background:transparent !important;
            padding:0 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.auth-form-marker) button[kind="primary"],
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.auth-form-marker) button[kind="primaryFormSubmit"] {
            background:#2448a8 !important;
            color:#ffffff !important;
            border-color:#2448a8 !important;
            border-radius:8px !important;
            box-shadow:none !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.auth-form-marker) button[kind="secondary"] {
            border-radius:8px !important;
        }
        .auth-step-title {
            margin: 0.1rem 0 0.35rem;
            color: #0f172a;
            font-size: 2rem;
            font-family: "Fraunces", Georgia, serif;
            letter-spacing: -0.03em;
        }
        .auth-step-copy {
            color: #64748b;
            margin-bottom: 1rem;
            line-height: 1.72;
            max-width: 54ch;
        }
        .auth-stepper-wrap {
            margin: 1.1rem 0 1.3rem;
        }
        .auth-stepper-bar {
            display: grid;
            grid-template-columns: 56px 1fr 56px 1fr 56px;
            align-items: center;
            gap: 0.65rem;
            margin-bottom: 0.65rem;
        }
        .auth-step-node {
            width: 56px;
            height: 56px;
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #e2e8f0;
            color: #64748b;
            font-size: 1rem;
            font-weight: 800;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.18);
        }
        .auth-step-node.active,
        .auth-step-node.done {
            background: linear-gradient(135deg, #2563eb 0%, #06b6d4 100%);
            color: #ffffff;
            box-shadow: 0 14px 36px rgba(37, 99, 235, 0.24);
        }
        .auth-step-line {
            height: 4px;
            border-radius: 999px;
            background: #e2e8f0;
        }
        .auth-step-line.done {
            background: linear-gradient(90deg, #2563eb 0%, #06b6d4 100%);
        }
        .auth-step-labels {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.65rem;
        }
        .auth-step-labels div {
            color: #64748b;
            font-size: 0.84rem;
            text-align: center;
            font-weight: 700;
        }
        .auth-step-labels div.active {
            color: #1d4ed8;
        }
        .auth-note {
            margin-top: 0.4rem;
            color: #64748b;
            font-size: 0.88rem;
        }
        .auth-action-row {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 1rem;
        }
        .auth-footer-note {
            text-align: center;
            color: #64748b;
            margin-top: 1rem;
            font-size: 0.92rem;
        }
        .auth-footer-note a {
            color: #2563eb;
            font-weight: 700;
            text-decoration: none;
        }
        .auth-login-meta {
            display: grid;
            gap: 0.85rem;
            margin: 1rem 0 0.2rem;
        }
        .auth-login-strip {
            border-radius: 18px;
            padding: 0.95rem 1rem;
            border: 1px solid #dbe7ff;
            background: linear-gradient(180deg, #eff6ff 0%, #f8fbff 100%);
        }
        .auth-login-strip strong {
            display: block;
            color: #0f172a;
            margin-bottom: 0.2rem;
        }
        .auth-login-strip span {
            color: #64748b;
            font-size: 0.9rem;
            line-height: 1.6;
        }
        .pre-stepper {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.85rem;
            margin: 1rem 0 1.8rem;
        }
        .pre-step {
            width: 42px;
            height: 42px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1rem;
            color: #64748b;
            background: #edf1f7;
        }
        .pre-step.active,
        .pre-step.done {
            color: #ffffff;
            background: #2f5bea;
        }
        .pre-step-line {
            width: 52px;
            height: 4px;
            border-radius: 999px;
            background: #e5e7eb;
        }
        .pre-step-line.done {
            background: #2f5bea;
        }
        .pre-onboarding-shell {
            max-width: 720px;
            margin: 0 auto 1.5rem;
        }
        .pre-onboarding-card {
            background: #ffffff;
            border: 1px solid #e8edf6;
            border-radius: 24px;
            padding: 1.6rem 1.75rem;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.05);
        }
        .pre-contract-layout {
            display: grid;
            grid-template-columns: 320px minmax(0, 1fr);
            gap: 1rem;
        }
        .pre-mini-list {
            display: grid;
            gap: 0.8rem;
        }
        .workspace-kpis {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.9rem;
            margin-bottom: 1rem;
        }
        .kpi-card, .panel-box, .surface-card, .queue-item, .history-item {
            border-radius: 20px;
            border: 1px solid #e7edf6;
            background: #ffffff;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
        }
        .kpi-card {
            padding: 1rem 1.05rem;
        }
        .kpi-label, .panel-kicker {
            color: #5b6b8a;
            letter-spacing: 0.12em;
        }
        .kpi-value, .panel-title {
            color: #111827;
            font-family: "Fraunces", Georgia, serif;
        }
        .kpi-note, .panel-subtitle, .queue-item-meta {
            color: #667085;
        }
        .panel-title,
        .stMarkdown h3,
        .stMarkdown h4,
        .stSubheader,
        h2 {
            font-family: "Fraunces", Georgia, serif !important;
        }
        .hero-card {
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 60%, #2563eb 100%);
            border: 1px solid rgba(59, 130, 246, 0.18);
            box-shadow: 0 22px 56px rgba(37, 99, 235, 0.16);
        }
        .hero-card::before,
        .surface-card::before {
            background: linear-gradient(90deg, #60a5fa 0%, #2f5bea 100%);
        }
        .hero-title {
            font-family: "Fraunces", Georgia, serif;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.55rem;
            background: transparent;
            border-bottom: 0;
            padding-bottom: 0.2rem;
        }
        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border: 1px solid #d7dfec;
            border-radius: 14px;
            padding: 0.52rem 0.95rem;
            color: #304156;
            font-weight: 700;
        }
        .stTabs [aria-selected="true"] {
            background: #2f5bea !important;
            color: #ffffff !important;
            border-color: #2f5bea !important;
        }
        @media (max-width: 1280px) {
            .auth-grid { grid-template-columns: 1fr; }
            .auth-hero-panel { min-height: auto; }
            .pre-metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            .pre-feature-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .pre-contract-layout { grid-template-columns: 1fr; }
            .pre-process-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .pre-plan-grid { grid-template-columns: 1fr; }
            .pre-stage-strip { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        }
        @media (max-width: 980px) {
            .auth-signal-row,
            .auth-action-row,
            .auth-mode-switch { grid-template-columns: 1fr; }
            .auth-stepper-bar { grid-template-columns: 48px 1fr 48px 1fr 48px; }
            .auth-step-node { width: 48px; height: 48px; border-radius: 16px; }
            .pre-shell { grid-template-columns: 1fr; }
            .pre-sidebar { position: static; min-height: auto; border-radius: 20px; }
            .pre-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .pre-feature-grid { grid-template-columns: 1fr; }
            .pre-two-column { grid-template-columns: 1fr; }
            .pre-inline-stats,
            .workspace-kpis,
            .pre-process-grid,
            .pre-stage-strip,
            .pre-focus-grid,
            .pre-action-grid,
            .pre-toolbar { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_lawfirm_admin_theme() -> None:
    """Apply the visual language of the selected law-firm admin reference."""
    st.markdown(
        """
        <style>
        :root {
            --admin-blue: #2448a8;
            --admin-coral: #f22f5d;
            --admin-green: #42b83f;
            --admin-amber: #ffae19;
            --admin-ink: #17243b;
            --admin-muted: #8290a6;
            --admin-bg: #f6f8fc;
        }
        .stApp { background: var(--admin-bg) !important; }
        [data-testid="stHeader"] { background: rgba(255,255,255,.94) !important; border-bottom: 1px solid #edf0f6; }
        [data-testid="stDecoration"], footer { display: none !important; }
        .block-container { max-width: 1500px; padding-top: 1.1rem; padding-bottom: 3rem; }
        .law-admin-topbar {
            display:flex; align-items:center; justify-content:space-between; gap:1rem;
            background:#fff; border:1px solid #edf0f6; border-radius:8px;
            padding:.75rem 1rem; margin-bottom:1rem; box-shadow:0 4px 16px rgba(35,55,95,.05);
        }
        .law-admin-topbar strong { color:var(--admin-ink); font-size:1rem; }
        .law-admin-topbar span { color:var(--admin-muted); font-size:.84rem; }
        .law-admin-search { min-width:280px; background:#f7f8fb; border:1px solid #edf0f6; border-radius:6px; padding:.55rem .8rem; color:#9aa5b6; }
        .law-admin-nav-marker { display:none !important; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.law-admin-nav-marker) {
            background:#ffffff !important;
            border:1px solid #edf0f6 !important;
            border-radius:8px !important;
            padding:.45rem .6rem !important;
            margin-bottom:.55rem !important;
            box-shadow:0 4px 16px rgba(35,55,95,.05) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.law-admin-nav-marker) [data-testid="stVerticalBlock"] {
            gap:.25rem !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.law-admin-nav-marker) .stButton > button {
            min-height:2.3rem !important;
            padding:.35rem .55rem !important;
            justify-content:center;
            font-size:.76rem;
            white-space:nowrap;
        }
        .law-admin-brand-compact strong { display:block; color:var(--admin-blue); font-size:.88rem; }
        .law-admin-brand-compact span { color:var(--admin-muted); font-size:.7rem; }
        .law-admin-status-compact { text-align:right; }
        .law-admin-status-compact strong { display:block; color:#268c3a; font-size:.78rem; }
        .law-admin-status-compact span { color:var(--admin-muted); font-size:.68rem; }
        .law-dashboard-primary {
            display:grid; grid-template-columns:1.05fr 1fr 1fr; gap:1rem; margin:0 0 1rem;
        }
        .law-results-card {
            display:grid; grid-template-columns:1fr 1fr; min-height:224px; overflow:hidden;
            border-radius:8px; box-shadow:0 6px 20px rgba(35,55,95,.10);
        }
        .law-result-segment {
            display:flex; flex-direction:column; align-items:center; justify-content:center;
            padding:1.25rem .75rem; color:#fff; text-align:center;
        }
        .law-result-segment.lost { background:var(--admin-coral); }
        .law-result-segment.won { background:var(--admin-blue); }
        .law-result-label { font-size:1.2rem; font-weight:600; letter-spacing:.01em; }
        .law-result-icon { font-size:2rem; line-height:1; margin:.7rem 0; opacity:.9; }
        .law-result-value { font-size:2rem; font-weight:800; line-height:1; }
        .law-result-rate { font-size:.83rem; margin-top:.5rem; opacity:.72; }
        .law-stat-panel, .law-funnel-panel, .law-revenue-panel {
            background:#fff; border:1px solid #edf0f6; border-radius:8px;
            box-shadow:0 5px 18px rgba(35,55,95,.07); padding:1.25rem 1.35rem;
        }
        .law-panel-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
        .law-panel-heading h3 { margin:0; color:var(--admin-ink); font:700 1.05rem/1.25 "Manrope",sans-serif !important; }
        .law-panel-heading span { color:var(--admin-muted); font-size:.76rem; }
        .law-stat-value { color:var(--admin-ink); font-size:2.15rem; font-weight:800; margin-top:.9rem; }
        .law-panel-legend { display:flex; flex-wrap:wrap; gap:.8rem; margin-top:.45rem; color:var(--admin-muted); font-size:.75rem; }
        .law-panel-legend i { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:.3rem; }
        .law-mini-chart { height:76px; display:flex; align-items:flex-end; gap:7px; margin-top:1rem; padding-top:.35rem; border-bottom:1px solid #edf0f6; }
        .law-mini-chart span { flex:1; min-width:5px; border-radius:5px 5px 0 0; opacity:.86; }
        .law-dashboard-secondary { display:grid; grid-template-columns:.72fr 1.48fr; gap:1rem; margin-bottom:1rem; }
        .law-side-stack { display:grid; gap:1rem; }
        .law-revenue-value { color:var(--admin-ink); font-size:1.8rem; font-weight:800; margin:.95rem 0 .15rem; }
        .law-revenue-note { color:var(--admin-muted); font-size:.78rem; }
        .law-alert-card {
            display:flex; align-items:center; justify-content:space-between; gap:1rem;
            min-height:92px; padding:1rem 1.2rem; border-radius:8px;
            background:#dceeff; color:#24579a; border:1px solid #c9e3fc;
        }
        .law-alert-card strong { display:block; font-size:1.45rem; }
        .law-alert-card span { font-size:.82rem; }
        .law-alert-icon { font-size:1.45rem; opacity:.75; }
        .law-funnel-panel { min-height:100%; }
        .law-funnel-list { display:grid; gap:.67rem; margin-top:1.05rem; }
        .law-funnel-row { display:grid; grid-template-columns:115px 1fr 32px; align-items:center; gap:.8rem; }
        .law-funnel-label { color:#59667a; font-size:.77rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .law-funnel-track { height:15px; overflow:hidden; background:#f0f2f7; border-radius:3px; }
        .law-funnel-fill { display:block; height:100%; min-width:0; border-radius:3px; }
        .law-funnel-count { color:var(--admin-ink); font-size:.78rem; font-weight:700; text-align:right; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.pre-sidebar-marker) {
            background:#fff !important; color:var(--admin-ink) !important; border:1px solid #edf0f6 !important;
            border-radius:8px !important; box-shadow:0 4px 18px rgba(35,55,95,.06) !important;
            min-height:calc(100vh - 7rem) !important; padding:1rem .8rem !important;
        }
        .pre-sidebar-marker { display:none; }
        .pre-brand h1, .pre-sidebar-value { color:var(--admin-blue) !important; }
        .pre-brand p, .pre-sidebar-label, .pre-sidebar-caption { color:var(--admin-muted) !important; }
        .pre-sidebar-panel { background:#f7f8fb !important; border:1px solid #edf0f6 !important; border-radius:7px !important; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.pre-sidebar-marker) .stButton > button { border-radius:6px !important; min-height:2.6rem !important; text-align:left !important; box-shadow:none !important; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.pre-sidebar-marker) .stButton > button[kind="primary"] { background:var(--admin-blue) !important; color:#fff !important; border-color:var(--admin-blue) !important; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.pre-sidebar-marker) .stButton > button[kind="secondary"] { background:#fff !important; color:#59667a !important; border-color:transparent !important; }
        .pre-content { padding:0 !important; }
        .pre-page-header { background:transparent !important; border:0 !important; box-shadow:none !important; padding:.3rem 0 1rem !important; }
        .pre-page-header h2 { color:var(--admin-ink) !important; font-family:"Manrope", sans-serif !important; font-size:1.55rem !important; }
        .pre-page-header p { color:var(--admin-muted) !important; }
        .pre-section-title { font-family:"Manrope", sans-serif !important; }
        .pre-card, .pre-metric-card, .pre-stage-card, .panel-box, .surface-card {
            background:#fff !important; border:1px solid #edf0f6 !important; border-radius:8px !important;
            box-shadow:0 5px 18px rgba(35,55,95,.07) !important;
        }
        .pre-metric-card h3 { color:var(--admin-blue) !important; font-family:"Manrope", sans-serif !important; }
        .pre-metric-card.soft-green h3, .pre-stage-card.soft-green strong { color:var(--admin-green) !important; }
        .pre-metric-card.soft-orange h3, .pre-stage-card.soft-orange strong { color:var(--admin-amber) !important; }
        .pre-metric-card.soft-red h3, .pre-task-priority.alta { color:var(--admin-coral) !important; }
        .pre-spotlight { background:linear-gradient(135deg,#2448a8,#18347f) !important; border-radius:8px !important; box-shadow:0 8px 24px rgba(36,72,168,.18) !important; }
        .pre-kanban-column, [data-testid="stDataFrame"] { border-radius:8px !important; border-color:#edf0f6 !important; box-shadow:0 4px 14px rgba(35,55,95,.05) !important; }
        [data-testid="stMetric"] { background:#fff; border:1px solid #edf0f6; padding:.8rem; border-radius:8px; box-shadow:0 4px 14px rgba(35,55,95,.05); }
        .stTabs [data-baseweb="tab"] { border-radius:6px !important; }
        button[kind="primary"] { background:var(--admin-blue) !important; border-color:var(--admin-blue) !important; }

        /* Controles nativos e popovers ficam na mesma paleta fria do painel. */
        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="menu"],
        [role="listbox"] {
            background:#ffffff !important;
            color:var(--admin-ink) !important;
            border-color:#dfe6f1 !important;
        }
        [data-baseweb="popover"] {
            border:1px solid #dfe6f1 !important;
            border-radius:8px !important;
            box-shadow:0 12px 28px rgba(35,55,95,.14) !important;
        }
        [role="option"] {
            background:#ffffff !important;
            color:#44516a !important;
        }
        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background:#edf3ff !important;
            color:var(--admin-blue) !important;
        }

        /* Densidade operacional: mais informacao visivel e menos rolagem. */
        .stApp:has(.law-admin-topbar) .block-container {
            max-width:1580px !important;
            padding-top:.55rem !important;
            padding-bottom:1.25rem !important;
        }
        .stApp:has(.law-admin-topbar) [data-testid="stVerticalBlock"] { gap:.72rem; }
        .stApp:has(.law-admin-topbar) [data-testid="stHorizontalBlock"] { gap:.8rem; }
        .stApp:has(.law-admin-topbar) .law-admin-topbar {
            padding:.5rem .75rem;
            margin-bottom:.55rem;
        }
        .stApp:has(.law-admin-topbar) .pre-page-header {
            margin:.05rem 0 .65rem !important;
            padding:.1rem 0 .35rem !important;
        }
        .stApp:has(.law-admin-topbar) .pre-page-header h2 { font-size:1.35rem !important; }
        .stApp:has(.law-admin-topbar) .pre-page-header p { margin-top:.1rem; font-size:.84rem; }
        .stApp:has(.law-admin-topbar) .panel-heading { margin-bottom:.55rem; }
        .stApp:has(.law-admin-topbar) .panel-title { font-size:1.35rem; }
        .stApp:has(.law-admin-topbar) .panel-subtitle { margin-top:.2rem; font-size:.82rem; }
        .stApp:has(.law-admin-topbar) .pre-section-title {
            font-size:1.12rem !important;
            margin-bottom:.35rem !important;
        }
        .stApp:has(.law-admin-topbar) .pre-card,
        .stApp:has(.law-admin-topbar) .panel-box,
        .stApp:has(.law-admin-topbar) .surface-card { padding:.8rem .9rem !important; }
        .stApp:has(.law-admin-topbar) .pre-metric-grid { gap:.65rem; margin-bottom:.55rem; }
        .stApp:has(.law-admin-topbar) .pre-metric-card {
            min-height:68px;
            padding:.65rem .75rem;
        }
        .stApp:has(.law-admin-topbar) .pre-metric-card h3 { font-size:1.45rem; }
        .stApp:has(.law-admin-topbar) .pre-metric-card p { margin-top:.18rem; font-size:.78rem; }
        .stApp:has(.law-admin-topbar) .workspace-kpis { gap:.65rem; margin-bottom:.25rem; }
        .stApp:has(.law-admin-topbar) .kpi-card { border-radius:8px; padding:.65rem .75rem; }
        .stApp:has(.law-admin-topbar) .kpi-value { font:800 1.45rem/1 "Manrope",sans-serif; }
        .stApp:has(.law-admin-topbar) .kpi-label { margin-bottom:.2rem; }
        .stApp:has(.law-admin-topbar) .kpi-note { font-size:.75rem; line-height:1.35; }
        .stApp:has(.law-admin-topbar) .pre-lead-card {
            border-radius:8px;
            padding:.65rem .7rem;
            margin-bottom:.5rem;
        }
        .stApp:has(.law-admin-topbar) .pre-focus-hero {
            border-radius:8px;
            padding:.75rem .85rem;
            margin-bottom:.6rem;
        }
        .stApp:has(.law-admin-topbar) .pre-focus-hero h3 { font-size:1.35rem; }
        .stApp:has(.law-admin-topbar) .pre-focus-grid { gap:.55rem; margin:.55rem 0; }
        .stApp:has(.law-admin-topbar) .pre-focus-stat { border-radius:8px; padding:.6rem .7rem; }
        .stApp:has(.law-admin-topbar) .pre-detail-list { gap:.45rem; margin:.55rem 0 0; }
        .stApp:has(.law-admin-topbar) .pre-detail-row { border-radius:8px; padding:.55rem .65rem; }
        .stApp:has(.law-admin-topbar) .pre-task-list { gap:.5rem; }
        .stApp:has(.law-admin-topbar) .pre-task-item { border-radius:8px; padding:.65rem .7rem; }
        .stApp:has(.law-admin-topbar) .status-chip { margin-bottom:.45rem; padding:.3rem .6rem; }
        .stApp:has(.law-admin-topbar) .stButton > button { min-height:2.25rem; border-radius:6px !important; }
        .stApp:has(.law-admin-topbar) .stTextInput input,
        .stApp:has(.law-admin-topbar) .stNumberInput input,
        .stApp:has(.law-admin-topbar) .stSelectbox div[data-baseweb="select"] > div {
            min-height:2.35rem !important;
            border-radius:6px !important;
        }
        .stApp:has(.law-admin-topbar) [data-testid="stMetric"] { padding:.55rem .65rem; }
        .stApp:has(.law-admin-topbar) [data-testid="stDataFrame"] { min-height:0 !important; }
        .stApp:has(.law-admin-topbar) [data-testid="stVegaLiteChart"] {
            background:#ffffff !important;
            border:1px solid #edf0f6;
            border-radius:8px;
            padding:.35rem;
        }

        /* O HTML aberto em uma chamada e fechado em outra vira um card vazio no Streamlit. */
        .pre-card:empty,
        .panel-box:empty,
        div[data-testid="stMarkdown"]:has(.pre-card:empty),
        div[data-testid="stMarkdown"]:has(.panel-box:empty) {
            display:none !important;
            margin:0 !important;
            padding:0 !important;
            min-height:0 !important;
        }

        .stApp:has(.law-admin-topbar) .law-dashboard-primary { gap:.7rem; margin-bottom:.65rem; }
        .stApp:has(.law-admin-topbar) .law-results-card { min-height:150px; }
        .stApp:has(.law-admin-topbar) .law-result-segment { padding:.75rem .55rem; }
        .stApp:has(.law-admin-topbar) .law-result-icon { font-size:1.35rem; margin:.35rem 0; }
        .stApp:has(.law-admin-topbar) .law-result-value { font-size:1.55rem; }
        .stApp:has(.law-admin-topbar) .law-stat-panel,
        .stApp:has(.law-admin-topbar) .law-funnel-panel,
        .stApp:has(.law-admin-topbar) .law-revenue-panel { padding:.8rem .9rem; }
        .stApp:has(.law-admin-topbar) .law-stat-value { font-size:1.55rem; margin-top:.5rem; }
        .stApp:has(.law-admin-topbar) .law-mini-chart { height:48px; margin-top:.5rem; }
        .stApp:has(.law-admin-topbar) .law-dashboard-secondary { gap:.7rem; margin-bottom:.1rem; }
        .stApp:has(.law-admin-topbar) .law-side-stack { gap:.7rem; }
        .stApp:has(.law-admin-topbar) .law-alert-card { min-height:64px; padding:.65rem .8rem; }
        .stApp:has(.law-admin-topbar) .law-funnel-list { gap:.42rem; margin-top:.65rem; }
        .stApp:has(.law-admin-topbar) .stTabs [data-baseweb="tab-list"] {
            gap:.35rem;
            padding-bottom:.35rem;
        }
        .stApp:has(.law-admin-topbar) .stTabs [data-baseweb="tab"] {
            min-height:2.2rem;
            padding:.32rem .7rem;
            font-size:.8rem;
        }
        .law-dashboard-details {
            margin:0 0 .65rem;
            border:1px solid #e5ebf4;
            border-radius:8px;
            background:#ffffff;
        }
        .law-dashboard-details summary {
            padding:.65rem .8rem;
            color:#40506a;
            font-size:.83rem;
            font-weight:700;
            cursor:pointer;
            list-style-position:inside;
        }
        .law-dashboard-details[open] summary { border-bottom:1px solid #edf0f6; }
        .law-dashboard-details .law-dashboard-secondary { padding:.7rem; }
        .law-pulse-inline {
            display:flex;
            flex-wrap:wrap;
            gap:.45rem .7rem;
            margin:-.15rem 0 .45rem;
        }
        .law-pulse-inline span {
            display:inline-flex;
            align-items:center;
            gap:.3rem;
            padding:.34rem .55rem;
            border:1px solid #dfe7f4;
            border-radius:999px;
            background:#ffffff;
            color:#647089;
            font-size:.76rem;
        }
        .law-pulse-inline strong { color:var(--admin-blue); }
        .crm-stage-heading {
            min-height:72px;
            border-radius:8px 8px 0 0;
            padding:.65rem .7rem;
            border:1px solid #e5ebf4;
            border-bottom:0;
        }
        .crm-stage-heading strong { display:block; color:#17243b; font-size:.9rem; }
        .crm-stage-heading span { color:#68758b; font-size:.72rem; line-height:1.35; }
        .crm-stage-heading b {
            float:right;
            min-width:24px;
            height:24px;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            border-radius:999px;
            background:rgba(255,255,255,.84);
            color:#17243b;
            font-size:.72rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.crm-stage-scroll-marker) {
            border-radius:0 0 8px 8px !important;
            border-color:#e5ebf4 !important;
            background:#ffffff !important;
            padding:.55rem !important;
        }
        .crm-stage-scroll-marker { display:none; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.crm-stage-scroll-marker) .stButton > button {
            align-items:flex-start;
            justify-content:flex-start;
            text-align:left;
            min-height:2.75rem !important;
            padding:.48rem .58rem !important;
            white-space:normal;
            line-height:1.25;
        }
        .stApp:has(.law-admin-topbar) .stMarkdown h1 a,
        .stApp:has(.law-admin-topbar) .stMarkdown h2 a,
        .stApp:has(.law-admin-topbar) .stMarkdown h3 a,
        .stApp:has(.law-admin-topbar) [data-testid="stHeaderActionElements"] {
            display:none !important;
        }
        @media (max-width: 1100px) {
            .law-dashboard-primary { grid-template-columns:1fr 1fr; }
            .law-results-card { grid-column:span 2; }
            .law-dashboard-secondary { grid-template-columns:1fr; }
        }
        @media (max-width: 900px) {
            .law-admin-search { display:none; }
            div[data-testid="stVerticalBlockBorderWrapper"]:has(.pre-sidebar-marker) { min-height:auto !important; }
        }
        @media (max-width: 680px) {
            .law-dashboard-primary { grid-template-columns:1fr; }
            .law-results-card { grid-column:span 1; }
            .law-funnel-row { grid-template-columns:92px 1fr 28px; gap:.5rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_admin_topbar() -> None:
    with st.container(border=True):
        st.markdown(
            "<span class='law-admin-topbar law-admin-nav-marker'></span>",
            unsafe_allow_html=True,
        )
        nav_columns = st.columns([1.45, 1, 1.08, 1, 1, 1, 1.08, 0.78, 0.58], gap="small")
        with nav_columns[0]:
            st.markdown(
                "<div class='law-admin-brand-compact'><strong>SOFI.IA PREVI</strong><span>Administração jurídica</span></div>",
                unsafe_allow_html=True,
            )
        for column, (view_id, label, _emoji) in zip(nav_columns[1:7], NAV_ITEMS):
            with column:
                if st.button(
                    label,
                    key=f"topnav_{view_id}",
                    icon=NAV_MATERIAL_ICONS[view_id],
                    type="primary" if st.session_state.current_view == view_id else "tertiary",
                    help=f"Abrir {label.lower()}",
                    use_container_width=True,
                ):
                    set_current_view(view_id)
                    st.rerun()
        with nav_columns[7]:
            st.markdown(
                "<div class='law-admin-status-compact'><strong>● Ativo</strong><span>Dados locais</span></div>",
                unsafe_allow_html=True,
            )
        with nav_columns[8]:
            if st.button(
                "Sair",
                key="auth_logout_top",
                icon=":material/logout:",
                type="tertiary",
                help="Sair da conta",
                use_container_width=True,
            ):
                st.session_state.is_authenticated = False
                st.session_state.auth_mode = "login"
                st.session_state.auth_login_password = ""
                st.rerun()


def ensure_session_defaults() -> None:
    if "selected_flow_id" not in st.session_state:
        st.session_state.selected_flow_id = next(iter(FLOW_DEFINITIONS.keys()))
    if "triage_state" not in st.session_state:
        flow_id = st.session_state.selected_flow_id
        st.session_state.triage_state = create_state(flow_id, FLOW_DEFINITIONS[flow_id])
    if "saved_result_id" not in st.session_state:
        st.session_state.saved_result_id = None
    if "sm_estimate" not in st.session_state:
        st.session_state.sm_estimate = None
    if "selected_attendance_id" not in st.session_state:
        st.session_state.selected_attendance_id = None
    if "selected_document_attendance_id" not in st.session_state:
        st.session_state.selected_document_attendance_id = None
    if "selected_contract_attendance_id" not in st.session_state:
        st.session_state.selected_contract_attendance_id = None
    if "selected_dashboard_case_id" not in st.session_state:
        st.session_state.selected_dashboard_case_id = None
    if "selected_crm_case_id" not in st.session_state:
        st.session_state.selected_crm_case_id = None
    if "current_view" not in st.session_state:
        st.session_state.current_view = "dashboard"
    if "office_settings" not in st.session_state:
        st.session_state.office_settings = load_office_settings()
    if "settings_plan" not in st.session_state:
        st.session_state.settings_plan = st.session_state.office_settings.get("plano", "Essencial")
    if "is_authenticated" not in st.session_state:
        st.session_state.is_authenticated = False
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login" if credentials_configured() else "signup"
    if "auth_step" not in st.session_state:
        st.session_state.auth_step = 1
    if "auth_signup_data" not in st.session_state:
        st.session_state.auth_signup_data = {
            "responsavel_nome": st.session_state.office_settings.get("responsavel_nome", ""),
            "responsavel_email": st.session_state.office_settings.get("responsavel_email", ""),
            "responsavel_whatsapp": st.session_state.office_settings.get("responsavel_whatsapp", ""),
            "password": "",
            "password_confirm": "",
            "lgpd_consent": False,
            "office_name": st.session_state.office_settings.get("office_name", ""),
            "oab": st.session_state.office_settings.get("oab", ""),
        }
    if "auth_login_email" not in st.session_state:
        st.session_state.auth_login_email = st.session_state.office_settings.get("responsavel_email", "")
    if "auth_login_password" not in st.session_state:
        st.session_state.auth_login_password = ""
    if "last_automation_notice" not in st.session_state:
        st.session_state.last_automation_notice = ""
    if "crm_section" not in st.session_state:
        st.session_state.crm_section = "funil"
    if "crm_pipeline_phase" not in st.session_state:
        st.session_state.crm_pipeline_phase = "entrada"
    if "crm_pipeline_page" not in st.session_state:
        st.session_state.crm_pipeline_page = 1
    if "crm_stage_filter" not in st.session_state:
        st.session_state.crm_stage_filter = "todos"


def render_panel_header(kicker: str, title: str, subtitle: str = "") -> None:
    subtitle_markup = f'<div class="panel-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="panel-heading">
          <div class="panel-kicker">{kicker}</div>
          <h2 class="panel-title">{title}</h2>
          {subtitle_markup}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_operation_kpis() -> None:
    dashboard = get_dashboard_summary()
    approved = next((int(row["total"]) for row in dashboard["by_status"] if row["status"] == "aprovado"), 0)
    revision = next((int(row["total"]) for row in dashboard["by_status"] if row["status"] == "revisao"), 0)
    document_backlog = int(dashboard.get("document_backlog", 0))
    recent_rows = list_recent_attendances(limit=1)
    latest = recent_rows[0]["lead_name"] if recent_rows else "Sem registros"
    st.markdown(
        f"""
        <div class="workspace-kpis">
          <div class="kpi-card soft-neutral">
            <div class="kpi-label">Atendimentos</div>
            <div class="kpi-value">{int(dashboard["total"])}</div>
            <div class="kpi-note">Base total registrada</div>
          </div>
          <div class="kpi-card soft-green">
            <div class="kpi-label">Aprovados</div>
            <div class="kpi-value">{approved}</div>
            <div class="kpi-note">Triagens qualificadas</div>
          </div>
          <div class="kpi-card soft-blue">
            <div class="kpi-label">Em revisao</div>
            <div class="kpi-value">{revision}</div>
            <div class="kpi-note">Pendencias operacionais</div>
          </div>
          <div class="kpi-card soft-orange">
            <div class="kpi-label">Fase documental</div>
            <div class="kpi-value">{document_backlog}</div>
            <div class="kpi-note">Obrigatorios ainda nao validados | Ultimo lead: {latest}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_recent_queue() -> None:
    render_panel_header("Fila", "Atendimentos recentes", "Acesso rapido aos ultimos registros salvos.")
    recent_rows = list_recent_attendances(limit=3)
    if not recent_rows:
        st.info("Ainda nao ha atendimentos salvos.")
        return

    for row in recent_rows:
        label, background, color = STATUS_STYLE.get(row["status"], ("Status", "#f4f4f4", "#555555"))
        selected_class = (
            " selected"
            if int(st.session_state.selected_attendance_id or 0) == int(row["id"])
            else ""
        )
        st.markdown(
            (
                f"<div class='pre-lead-card{selected_class}'>"
                f"<h5>#{row['id']} - {row['lead_name']}</h5>"
                f"<p>{row['flow_name']} | {row['created_at']}</p>"
                f"<p><span class='status-chip' style='background:{background}; color:{color};'>{label}</span></p>"
                f"<p>{row['result_title']}</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def render_active_case_panel(flow: dict[str, Any], form_data: dict[str, Any]) -> None:
    render_panel_header("Contexto", "Painel do atendimento", "Resumo operacional do lead e do fluxo em andamento.")
    triage_state = st.session_state.triage_state
    current_node = get_current_node(triage_state, flow)
    current_step = current_node["code"] if current_node else "Concluido"
    current_question = current_node["title"] if current_node else "Triagem finalizada"

    st.markdown(
        f"""
        <div class="pre-focus-hero">
          <div class="eyebrow">Lead ativo</div>
          <h3>{form_data['lead_name'] or 'Nao informado'}</h3>
          <p>{flow['name']} | {current_step}</p>
        </div>
        <div class="pre-focus-grid">
          <div class="pre-focus-stat"><strong>{form_data['lead_phone'] or '-'}</strong><span>Contato principal</span></div>
          <div class="pre-focus-stat"><strong>{len(triage_state.history)}</strong><span>Respostas registradas</span></div>
          <div class="pre-focus-stat"><strong>{current_step}</strong><span>Etapa corrente</span></div>
          <div class="pre-focus-stat"><strong>{'Concluindo' if current_node is None else 'Em triagem'}</strong><span>Status da sessao</span></div>
        </div>
        <div class="pre-detail-list">
          <div class="pre-detail-row"><strong>Pergunta atual</strong><span>{current_question}</span></div>
          <div class="pre-detail-row"><strong>Fluxo monitorado</strong><span>{flow['name']}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def reset_triage(flow_id: str | None = None) -> None:
    target_flow_id = flow_id or st.session_state.selected_flow_id
    st.session_state.selected_flow_id = target_flow_id
    st.session_state.triage_state = create_state(target_flow_id, FLOW_DEFINITIONS[target_flow_id])
    st.session_state.saved_result_id = None
    st.session_state.sm_estimate = None


def render_header() -> None:
    total_flows = len(FLOW_DEFINITIONS)
    flow_names = ", ".join(flow["name"] for flow in FLOW_DEFINITIONS.values())
    st.markdown(
        f"""
        <div class="app-ribbon">
          <div>
            <div class="app-ribbon-title">{BRAND_NAME} | Plataforma de Inteligencia Previdenciaria</div>
            <div class="app-ribbon-copy">{AGENT_NAME}, {BRAND_SLOGAN}.</div>
          </div>
          <div class="app-ribbon-badge">Build {APP_VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns([1.4, 1.0], gap="large")
    with col1:
        st.markdown(
            f"""
            <div class="hero-card">
              <div class="eyebrow">Plataforma Previdenciaria</div>
              <div class="hero-title">{BRAND_NAME}</div>
              <p class="hero-copy">
                {AGENT_NAME} conduz a triagem previdenciaria com padrao corporativo premium,
                atendimento guiado e registro operacional centralizado.
              </p>
              <div class="hero-note">{BRAND_SLOGAN}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="surface-card">
              <div class="eyebrow">Cobertura Operacional</div>
              <p class="hero-copy">
                O sistema esta com {total_flows} fluxos ativos no momento.
              </p>
              <p class="hero-copy">{flow_names}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar() -> None:
    st.sidebar.title("Operacao")
    st.sidebar.caption(f"Build carregada: {APP_VERSION}")
    st.sidebar.caption("Historico salvo localmente em SQLite")

    for row in list_recent_attendances(limit=8):
        label, _, color = STATUS_STYLE.get(row["status"], ("Status", "#f4f4f4", "#555555"))
        st.sidebar.markdown(
            (
                f"**#{row['id']} - {row['lead_name']}**  \n"
                f"{row['flow_name']}  \n"
                f":{color}[{label}]  \n"
                f"{row['created_at']}"
            )
        )
        st.sidebar.divider()


def render_lead_form() -> dict[str, Any]:
    render_panel_header("Atendimento", "Cadastro do atendimento", "Preencha os dados basicos e selecione o fluxo mais aderente ao caso.")
    options = {flow["name"]: flow_id for flow_id, flow in FLOW_DEFINITIONS.items()}
    flow_names = list(options.keys())
    current_flow_name = FLOW_DEFINITIONS[st.session_state.selected_flow_id]["name"]
    current_index = flow_names.index(current_flow_name)

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Nome do lead", key="lead_name", placeholder="Ex.: Maria da Silva")
        phone = st.text_input("Telefone", key="lead_phone", placeholder="(11) 99999-9999")
        email = st.text_input("E-mail", key="lead_email", placeholder="cliente@email.com")
    with col2:
        chosen_flow_name = st.selectbox("Tipo de atendimento", flow_names, index=current_index)
        source = st.selectbox(
            "Origem do lead",
            ["WhatsApp", "Site", "Indicação", "E-mail", "Outro"],
            key="lead_source",
        )
        notes = st.text_area("Observacoes", key="lead_notes", placeholder="Contexto rapido do caso", height=103)

    selected_flow_id = options[chosen_flow_name]
    if selected_flow_id != st.session_state.selected_flow_id:
        reset_triage(selected_flow_id)
        st.rerun()

    triage_profile: dict[str, Any] = {}
    if selected_flow_id == "aposentadoria":
        with st.expander("Dados previdenciários essenciais", expanded=False):
            st.caption(
                "Registre o mínimo necessário para cálculo e estratégia. A triagem não substitui a análise do CNIS."
            )
            profile_left, profile_right = st.columns(2, gap="medium")
            with profile_left:
                birth_date = st.date_input(
                    "Data de nascimento",
                    value=None,
                    key="retirement_birth_date",
                )
                calculation_criterion = st.selectbox(
                    "Critério de cálculo a verificar",
                    ["Não informado", "Mulher", "Homem", "Análise individualizada"],
                    key="retirement_calculation_criterion",
                )
                contribution_estimate = st.text_input(
                    "Tempo de contribuição estimado",
                    key="retirement_contribution_estimate",
                    placeholder="Ex.: 28 anos e 6 meses",
                )
            with profile_right:
                cnis_status = st.selectbox(
                    "Situação do CNIS",
                    [
                        "Não analisado",
                        "Não apresentado",
                        "Sem divergências aparentes",
                        "Com divergências",
                    ],
                    key="retirement_cnis_status",
                )
                relevant_periods = st.multiselect(
                    "Períodos ou vínculos relevantes",
                    ["Urbano", "Rural", "Especial", "RPPS/CTC", "Professor", "PCD", "Militar", "Exterior"],
                    key="retirement_relevant_periods",
                )
                retirement_objective = st.text_area(
                    "Objetivo previdenciário",
                    key="retirement_objective",
                    placeholder="Benefício imediato, planejamento, acerto de CNIS ou averbação.",
                    height=82,
                )
        triage_profile = {
            "birth_date": birth_date.isoformat() if birth_date else "",
            "calculation_criterion": calculation_criterion,
            "contribution_estimate": contribution_estimate.strip(),
            "cnis_status": cnis_status,
            "relevant_periods": relevant_periods,
            "objective": retirement_objective.strip(),
        }

    privacy_left, privacy_right = st.columns([1.1, 0.9], gap="medium")
    with privacy_left:
        privacy_notice_acknowledged = st.checkbox(
            "Confirmo que o titular foi informado sobre finalidade, acesso restrito e retenção dos dados.",
            key="lead_privacy_notice_acknowledged",
        )
        st.caption("Colete somente dados necessários ao atendimento e à análise jurídica solicitada.")
    with privacy_right:
        privacy_legal_basis = st.selectbox(
            "Base legal do tratamento",
            options=list(PRIVACY_LEGAL_BASES),
            format_func=lambda value: PRIVACY_LEGAL_BASES[value],
            key="lead_privacy_legal_basis",
        )

    return {
        "lead_name": name.strip(),
        "lead_phone": phone.strip(),
        "lead_email": email.strip(),
        "lead_source": source,
        "lead_notes": notes.strip(),
        "flow_id": selected_flow_id,
        "privacy_notice_acknowledged": bool(privacy_notice_acknowledged),
        "privacy_legal_basis": privacy_legal_basis,
        "triage_profile": triage_profile,
    }


def render_history(history: list[dict[str, str]]) -> None:
    render_panel_header("Sessao", "Historico da sessao", "Acompanhe as respostas registradas durante a triagem atual.")
    if not history:
        st.info("Nenhuma resposta registrada ainda.")
        return

    for index, item in enumerate(history, start=1):
        st.markdown(
            (
                '<div class="history-item">'
                f"<strong>{index}. {item['node_code']}</strong><br>"
                f"{item['question']}<br>"
                f"<span class='muted'>Resposta: {item['answer']}</span>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def format_document_status(status: str) -> str:
    return DOCUMENT_STATUS_STYLE.get(status, ("Status", "#f4f4f4", "#555555"))[0]


def format_extraction_status(status: str) -> str:
    return EXTRACTION_STATUS_STYLE.get(status, ("Indefinido", "#f4f4f4", "#555555"))[0]


def normalize_triage_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    aliases = {
        "aprovado": "aprovado",
        "qualificado": "aprovado",
        "revisao": "revisao",
        "em revisao": "revisao",
        "desqualificado": "desqualificado",
    }
    return aliases.get(normalized, normalized)


def render_document_status_chip(status: str) -> str:
    label, background, color = DOCUMENT_STATUS_STYLE.get(status, ("Status", "#f4f4f4", "#555555"))
    return (
        f"<span class='status-chip' style='background:{background}; color:{color};'>{label}</span>"
    )


def render_extraction_status_chip(status: str) -> str:
    label, background, color = EXTRACTION_STATUS_STYLE.get(
        status,
        ("Indefinido", "#f4f4f4", "#555555"),
    )
    return (
        f"<span class='status-chip' style='background:{background}; color:{color};'>{label}</span>"
    )


def render_triage_status_chip(status: str) -> str:
    normalized = normalize_triage_status(status)
    default_label = (status or "Sem status").replace("_", " ").strip().title() or "Sem status"
    label, background, color = STATUS_STYLE.get(
        normalized,
        (default_label, "#f4f4f4", "#555555"),
    )
    return (
        f"<span class='status-chip' style='background:{background}; color:{color};'>{label}</span>"
    )


def get_document_progress(documents: list[Any]) -> tuple[int, int]:
    required_total = sum(int(row["required"]) for row in documents)
    validated_total = sum(
        1 for row in documents if int(row["required"]) == 1 and row["status"] == "validado"
    )
    return required_total, validated_total


def build_document_case_score(documents: list[Any]) -> dict[str, Any]:
    """Compatibilidade da interface; a regra de domínio vive no serviço."""
    return calculate_document_case_score(documents)


def persist_document_uploads(
    *,
    attendance_id: int,
    document_code: str,
    current_files: list[str],
    uploaded_batch: list[Any] | None,
) -> list[str]:
    stored_files = list(current_files)
    for uploaded_file in uploaded_batch or []:
        saved_path = save_uploaded_document(attendance_id, document_code, uploaded_file)
        if saved_path not in stored_files:
            stored_files.append(saved_path)
    return stored_files


def format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def set_current_view(view_id: str) -> None:
    st.session_state.current_view = view_id


def render_shell_page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="pre-page-header">
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_all_attendance_rows(limit: int = 200) -> list[Any]:
    return search_attendances(limit=limit)


def parse_triage_profile(raw_profile: Any) -> dict[str, Any]:
    """Return a safe structured profile from the persisted JSON payload."""
    if isinstance(raw_profile, dict):
        return raw_profile
    try:
        parsed = json.loads(str(raw_profile or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def get_contract_block_reasons(row: Any) -> list[str]:
    """Describe every governance gate preventing a contract from being released."""
    reasons: list[str] = []
    triage_status = normalize_triage_status(str(row["status"] or ""))
    conflict_status = str(row["conflict_status"] or "pendente")
    if triage_status != "aprovado":
        reasons.append(
            "Triagem pendente de revisão jurídica"
            if triage_status == "revisao"
            else "Triagem não qualificada para contratação"
        )
    if conflict_status != "liberado":
        reasons.append(
            "Conflito de interesse identificado"
            if conflict_status == "conflito"
            else "Checagem de conflito pendente"
        )
    if not bool(int(row["privacy_notice_acknowledged"] or 0)):
        reasons.append("Aviso de privacidade/LGPD não registrado")
    return reasons


def summarize_triage_profile(profile: dict[str, Any]) -> str:
    """Build a compact lawyer-facing summary of structured previdentiary facts."""
    if not profile:
        return "Perfil previdenciário estruturado ainda não preenchido."
    relevant_periods = profile.get("relevant_periods") or []
    parts = [
        f"Nascimento: {profile.get('birth_date') or 'não informado'}",
        f"Critério: {profile.get('calculation_criterion') or 'não informado'}",
        f"Contribuição estimada: {profile.get('contribution_estimate') or 'não informada'}",
        f"CNIS: {profile.get('cnis_status') or 'não analisado'}",
        f"Períodos: {', '.join(str(item) for item in relevant_periods) if relevant_periods else 'nenhum indicado'}",
        f"Objetivo: {profile.get('objective') or 'não informado'}",
    ]
    return " · ".join(parts)


def build_pipeline_records(limit: int = 200) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in get_all_attendance_rows(limit=limit):
        documents = list_attendance_documents(int(row["id"]))
        required_total, validated_total = get_document_progress(documents)
        uploaded_total = sum(
            len(json.loads(document["uploaded_files_json"] or "[]"))
            for document in documents
        )
        score = build_document_case_score(documents)
        inferred_stage = infer_pipeline_stage(
            status=str(row["status"]),
            required_total=required_total,
            validated_total=validated_total,
            uploaded_total=uploaded_total,
        )
        valid_stages = {column_id for column_id, *_ in PIPELINE_COLUMNS}
        configured_stage = str(row["crm_stage"] or "")
        stage = configured_stage if configured_stage in valid_stages else inferred_stage
        records.append(
            {
                "id": int(row["id"]),
                "lead_name": row["lead_name"],
                "lead_phone": row["lead_phone"],
                "flow_name": row["flow_name"],
                "status": row["status"],
                "result_title": row["result_title"],
                "benefit_category": row["benefit_category"],
                "estimated_monthly_value": row["estimated_monthly_value"],
                "estimated_total_value": row["estimated_total_value"],
                "required_total": required_total,
                "validated_total": validated_total,
                "uploaded_total": uploaded_total,
                "score": score["score"],
                "score_label": score["label"],
                "stage": stage,
                "conflict_status": row["conflict_status"],
                "assigned_to": row["assigned_to"],
                "next_action": row["next_action"],
                "next_action_at": row["next_action_at"],
                "privacy_notice_acknowledged": bool(
                    int(row["privacy_notice_acknowledged"] or 0)
                ),
                "privacy_legal_basis": row["privacy_legal_basis"],
                "triage_profile": parse_triage_profile(row["triage_profile_json"]),
            }
        )
    return records


def infer_pipeline_stage(
    *,
    status: str,
    required_total: int,
    validated_total: int,
    uploaded_total: int,
) -> str:
    normalized = normalize_triage_status(status)
    if normalized == "revisao":
        return "documentos"
    if normalized == "desqualificado":
        return "perdido"
    if required_total == 0:
        return "triagem"
    if uploaded_total == 0:
        return "documentos"
    if validated_total == 0:
        return "documentos"
    if validated_total < required_total:
        return "documentos"
    return "caso_ativo"


def build_dashboard_metrics() -> list[dict[str, Any]]:
    pipeline_records = build_pipeline_records()
    totals = {column_id: 0 for column_id, *_ in PIPELINE_COLUMNS}
    for item in pipeline_records:
        totals[item["stage"]] = totals.get(item["stage"], 0) + 1

    return [
        {"label": "Total", "value": len(pipeline_records), "tone": "soft-neutral"},
        {"label": "Conflitos", "value": totals["conflito"], "tone": "soft-yellow"},
        {"label": "Triagem", "value": totals["triagem"], "tone": "soft-blue"},
        {"label": "Propostas", "value": totals["proposta"], "tone": "soft-green"},
        {"label": "Documentos", "value": totals["documentos"], "tone": "soft-orange"},
        {"label": "Casos Ativos", "value": totals["caso_ativo"], "tone": "soft-teal"},
    ]


def get_stage_label(stage: str) -> str:
    for column_id, label, _subtitle, _tone in PIPELINE_COLUMNS:
        if column_id == stage:
            return label
    return stage.replace("_", " ").strip().title()


def build_revenue_snapshot(
    pipeline_records: list[dict[str, Any]],
    office_settings: dict[str, Any],
) -> dict[str, float | int]:
    potential_total = 0.0
    potential_monthly = 0.0
    tracked_cases = 0

    for item in pipeline_records:
        total_value = float(item.get("estimated_total_value") or 0.0)
        monthly_value = float(item.get("estimated_monthly_value") or 0.0)
        if total_value <= 0 and monthly_value <= 0:
            continue

        tracked_cases += 1
        fee_percentage = resolve_fee_percentage(str(item["flow_name"]), office_settings) / 100
        potential_total += total_value * fee_percentage
        potential_monthly += monthly_value * fee_percentage

    average_ticket = potential_total / tracked_cases if tracked_cases else 0.0
    return {
        "potential_total": round(potential_total, 2),
        "potential_monthly": round(potential_monthly, 2),
        "average_ticket": round(average_ticket, 2),
        "tracked_cases": tracked_cases,
    }


def build_source_breakdown_dataframe(dashboard: dict[str, Any]) -> pd.DataFrame:
    conversion_map: dict[str, dict[str, int]] = {}
    for row in dashboard["conversion_by_flow"]:
        flow_name = str(row["flow_name"])
        status = str(row["status"])
        total = int(row["total"])
        conversion_map.setdefault(
            flow_name,
            {"Qualificados": 0, "Em revisao": 0, "Desqualificados": 0},
        )
        if status == "aprovado":
            conversion_map[flow_name]["Qualificados"] = total
        elif status == "revisao":
            conversion_map[flow_name]["Em revisao"] = total
        elif status == "desqualificado":
            conversion_map[flow_name]["Desqualificados"] = total

    rows = [{"Fonte": flow_name, **totals} for flow_name, totals in conversion_map.items()]
    return pd.DataFrame(rows)


def build_recent_activity_dataframe(dashboard: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {"Dia": row["day"], "Casos": int(row["total"])}
        for row in dashboard["recent_days"]
    ]
    return pd.DataFrame(rows)


def build_stage_distribution_dataframe(pipeline_records: list[dict[str, Any]]) -> pd.DataFrame:
    stage_totals: dict[str, int] = {}
    for record in pipeline_records:
        label = get_stage_label(str(record["stage"]))
        stage_totals[label] = stage_totals.get(label, 0) + 1
    rows = [{"Etapa": label, "Casos": total} for label, total in stage_totals.items()]
    return pd.DataFrame(rows)


def build_case_dataframe(
    pipeline_records: list[dict[str, Any]],
    office_settings: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in pipeline_records:
        fee_percentage = resolve_fee_percentage(str(item["flow_name"]), office_settings) / 100
        fee_total = float(item.get("estimated_total_value") or 0.0) * fee_percentage
        rows.append(
            {
                "Caso": f"#{item['id']}",
                "Lead": item["lead_name"],
                "Fluxo": item["flow_name"],
                "Etapa": get_stage_label(str(item["stage"])),
                "Status": STATUS_STYLE.get(
                    normalize_triage_status(str(item["status"])),
                    ("Status", "", ""),
                )[0],
                "Score": int(item["score"]),
                "Docs": f"{item['validated_total']}/{item['required_total']}",
                "Honorarios": format_currency(fee_total) if fee_total > 0 else "-",
                "Telefone": item["lead_phone"] or "-",
            }
        )
    return pd.DataFrame(rows)


def build_recent_task_rows(
    pipeline_records: list[dict[str, Any]],
    limit: int = 6,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    priority_weight = {"Alta": 0, "Media": 1, "Baixa": 2}

    for item in pipeline_records:
        case_id = int(item["id"])
        documents = list_attendance_documents(case_id)
        pending_required = [
            doc for doc in documents
            if int(doc["required"]) == 1 and doc["status"] != "validado"
        ]
        stage = str(item["stage"])
        conflict_status = str(item.get("conflict_status") or "pendente")
        triage_status = normalize_triage_status(str(item.get("status") or ""))
        registered_next_action = str(item.get("next_action") or "").strip()

        if conflict_status != "liberado" and stage not in {"encerrado", "perdido"}:
            title = (
                "Resolver conflito de interesse identificado"
                if conflict_status == "conflito"
                else "Concluir checagem de conflito"
            )
            description = registered_next_action or (
                "Verifique cliente, partes, empresas e interessados antes de orientar ou contratar."
            )
            priority = "Alta"
        elif stage == "reuniao":
            title = "Realizar reunião de análise"
            description = "Confirmar fatos, estratégia inicial e próximos documentos."
            priority = "Alta"
        elif stage == "proposta":
            title = "Acompanhar proposta ou contrato"
            description = "Confirmar aceite antes de avançar para a coleta documental."
            priority = "Alta"
        elif stage == "documentos":
            missing_names = ", ".join(doc["document_name"] for doc in pending_required[:2])
            title = "Cobrar documentos obrigatorios"
            description = (
                f"{len(pending_required)} item(ns) pendente(s). "
                f"{missing_names or 'Checklist ainda incompleto.'}"
            )
            priority = "Alta"
        elif stage == "caso_ativo":
            title = "Conduzir estrategia do caso ativo"
            description = "Caso com triagem e documentos em nivel operacional."
            priority = "Media"
        elif stage == "novo_contato":
            title = "Concluir triagem inicial"
            description = "Lead ainda depende de respostas para sair do filtro inicial."
            priority = "Baixa"
        elif stage == "triagem" and triage_status == "revisao":
            title = "Revisar estratégia e pendências da triagem"
            description = registered_next_action or (
                "A triagem foi concluída em revisão; complemente fatos, documentos e cálculo."
            )
            priority = "Alta"
        elif stage == "triagem" and triage_status == "aprovado":
            title = "Validar parecer inicial e encaminhamento"
            description = registered_next_action or (
                "A triagem foi concluída; confirme a estratégia jurídica e o próximo movimento."
            )
            priority = "Media"
        elif stage == "triagem":
            title = "Concluir triagem inicial"
            description = "Lead ainda depende de respostas para sair do filtro inicial."
            priority = "Baixa"
        else:
            title = "Registrar próximo passo"
            description = "Atualize o histórico e defina a ação de acompanhamento do caso."
            priority = "Baixa"

        tasks.append(
            {
                "case_id": case_id,
                "lead_name": item["lead_name"],
                "flow_name": item["flow_name"],
                "title": title,
                "description": description,
                "priority": priority,
            }
        )

    tasks.sort(key=lambda item: (priority_weight[item["priority"]], -item["case_id"]))
    return tasks[:limit]


def build_document_hotspot_dataframe(
    pipeline_records: list[dict[str, Any]],
    limit: int = 5,
) -> pd.DataFrame:
    ranked_candidates = sorted(
        [
            item
            for item in pipeline_records
            if int(item["required_total"]) > int(item["validated_total"])
        ],
        key=lambda item: (
            -(int(item["required_total"]) - int(item["validated_total"])),
            int(item["score"]),
            -int(item["id"]),
        ),
    )
    rows: list[dict[str, Any]] = []
    for item in ranked_candidates:
        documents = list_attendance_documents(int(item["id"]))
        pending_required = [
            str(document["document_name"])
            for document in documents
            if int(document["required"]) == 1 and str(document["status"]) != "validado"
        ]
        if not pending_required:
            continue

        preview = ", ".join(pending_required[:2])
        if len(pending_required) > 2:
            preview += f" +{len(pending_required) - 2}"
        rows.append(
            {
                "Caso": f"#{item['id']}",
                "Lead": item["lead_name"],
                "Etapa": get_stage_label(str(item["stage"])),
                "Score": f"{int(item['score'])}/100",
                "Pendencias": preview,
            }
        )
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows)


def count_pipeline_by_stage(pipeline_records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        column_id: len([record for record in pipeline_records if record["stage"] == column_id])
        for column_id, *_ in PIPELINE_COLUMNS
    }


def render_feature_cards_grid() -> None:
    cards_markup = "".join(
        (
            "<div class='pre-feature-card'>"
            f"<div class='icon'>{icon}</div>"
            f"<h4>{title}</h4>"
            f"<p>{description}</p>"
            "</div>"
        )
        for icon, title, description in FEATURE_CARDS
    )
    st.markdown(f"<div class='pre-feature-grid'>{cards_markup}</div>", unsafe_allow_html=True)


def render_process_steps() -> None:
    steps_markup = "".join(
        (
            "<div class='pre-process-card'>"
            f"<div class='pre-process-index'>{step}</div>"
            f"<h4>{title}</h4>"
            f"<p>{description}</p>"
            "</div>"
        )
        for step, title, description in PROCESS_STEPS
    )
    st.markdown(f"<div class='pre-process-grid'>{steps_markup}</div>", unsafe_allow_html=True)


def render_plan_selector(selected_plan: str) -> str:
    current_plan = st.session_state.get("settings_plan", selected_plan)
    st.markdown("<h3 class='pre-section-title'>Escolha seu plano</h3>", unsafe_allow_html=True)
    st.caption("14 dias gratis em qualquer plano. Cancele quando quiser.")
    plan_cols = st.columns(3, gap="medium")
    for column, plan in zip(plan_cols, PLAN_OPTIONS):
        active = current_plan == plan["id"]
        with column:
            st.markdown(
                (
                    f"<div class='pre-plan-card{' active' if active else ''}'>"
                    f"<h4>{plan['id']}</h4>"
                    f"<div class='pre-plan-price'>{plan['price']}<span style='font-size:0.95rem;font-weight:600;color:#667085;'> /mes</span></div>"
                    f"<p>{plan['caption']}</p>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            if st.button(
                "Plano ativo" if active else f"Selecionar {plan['id']}",
                key=f"select_plan_{plan['id']}",
                use_container_width=True,
                type="primary" if active else "secondary",
                disabled=active,
            ):
                st.session_state.settings_plan = plan["id"]
                st.rerun()
    return st.session_state.get("settings_plan", current_plan)


def persist_auth_profile_to_settings(selected_plan: str) -> None:
    signup_data = st.session_state.auth_signup_data
    updated_settings = {
        "responsavel_nome": signup_data["responsavel_nome"].strip(),
        "responsavel_email": signup_data["responsavel_email"].strip(),
        "responsavel_whatsapp": signup_data["responsavel_whatsapp"].strip(),
        "plano": selected_plan,
        "office_name": signup_data["office_name"].strip(),
        "oab": signup_data["oab"].strip(),
        "tutorial_video_url": st.session_state.office_settings.get("tutorial_video_url", ""),
        "fee_percentages": dict(st.session_state.office_settings.get("fee_percentages", {})),
    }
    save_office_settings(updated_settings)
    save_credentials(
        signup_data["responsavel_email"],
        signup_data["password"],
    )
    st.session_state.office_settings = load_office_settings()
    st.session_state.settings_plan = selected_plan


def render_auth_stepper(active_step: int) -> None:
    labels = ["Seus dados", "Seu escritorio", "Plano"]
    bar_parts: list[str] = []
    for index, _label in enumerate(labels, start=1):
        node_class = "done" if index < active_step else "active" if index == active_step else ""
        node_label = "&#10003;" if index < active_step else str(index)
        bar_parts.append(f"<div class='auth-step-node {node_class}'>{node_label}</div>")
        if index < len(labels):
            line_class = "done" if index < active_step else ""
            bar_parts.append(f"<div class='auth-step-line {line_class}'></div>")
    labels_markup = "".join(
        f"<div class='{'active' if index == active_step else ''}'>{label}</div>"
        for index, label in enumerate(labels, start=1)
    )
    st.markdown(
        (
            "<div class='auth-stepper-wrap'>"
            f"<div class='auth-stepper-bar'>{''.join(bar_parts)}</div>"
            f"<div class='auth-step-labels'>{labels_markup}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_auth_hero_panel() -> None:
    signal_rows = [
        ("11", "fluxos estrategicos"),
        ("OCR", "leitura documental"),
        ("24/7", "captura comercial"),
    ]
    highlight_markup = "".join(
        (
            "<div class='auth-highlight-card'>"
            f"<div class='auth-highlight-index'>{index}</div>"
            "<div class='auth-highlight-copy'>"
            f"<h4>{title}</h4>"
            f"<p>{description}</p>"
            "</div>"
            "</div>"
        )
        for index, title, description in AUTH_HIGHLIGHTS
    )
    signals_markup = "".join(
        (
            "<div class='auth-signal-card'>"
            f"<strong>{value}</strong>"
            f"<span>{label}</span>"
            "</div>"
        )
        for value, label in signal_rows
    )
    st.markdown(
        f"""
        <div class="auth-hero-panel">
          <div class="auth-kicker">Agente previdenciaria proprietaria</div>
          <div class="auth-brand-stack">
            <h1>{BRAND_NAME}</h1>
            <div class="auth-agent-chip">Sofia | IA de relacionamento e elegibilidade</div>
            <p>{BRAND_SLOGAN}. Uma camada de atendimento, triagem e operacao pensada para escritorios que querem parecer o futuro do previdenciario.</p>
          </div>
          <div class="auth-signal-row">{signals_markup}</div>
          <div class="auth-highlight-grid">{highlight_markup}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_auth_login() -> None:
    st.markdown("<div class='panel-kicker'>Acesso seguro</div>", unsafe_allow_html=True)
    st.markdown("<h2 class='auth-step-title'>Entrar no painel da Sofia</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p class='auth-step-copy'>Acesse o escritório com suas credenciais locais protegidas e retome a operação exatamente de onde parou.</p>",
        unsafe_allow_html=True,
    )
    account_ready = credentials_configured()
    if not account_ready:
        st.info("Nenhuma conta foi configurada neste computador. Use Criar conta para concluir o primeiro acesso.")
    with st.form("auth_login_form"):
        login_email = st.text_input(
            "Email profissional",
            key="auth_login_email",
            placeholder="voce@escritorio.com.br",
        )
        login_password = st.text_input(
            "Senha",
            key="auth_login_password",
            type="password",
            placeholder="Digite sua senha",
        )
        st.markdown(
            """
            <div class="auth-login-meta">
              <div class="auth-login-strip">
                <strong>Proteção das credenciais</strong>
                <span>A senha é validada localmente por hash criptográfico e não é armazenada em texto aberto.</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        login_submit = st.form_submit_button("Entrar", use_container_width=True, type="primary")
    if login_submit:
        email_error = validate_email(login_email)
        if not login_email.strip() or not login_password.strip():
            st.warning("Preencha e-mail e senha para acessar o painel.")
        elif email_error:
            st.warning(email_error)
        elif not account_ready:
            st.error("Não existe uma conta local configurada. Selecione Criar conta.")
        elif not verify_credentials(login_email, login_password):
            st.error("E-mail ou senha inválidos. Verifique os dados e tente novamente.")
        else:
            st.session_state.is_authenticated = True
            st.session_state.current_view = "dashboard"
            st.rerun()
    st.caption("Primeiro acesso? Use Criar conta no seletor acima.")


def render_auth_signup() -> None:
    current_step = st.session_state.auth_step
    signup_data = st.session_state.auth_signup_data
    st.markdown("<div class='panel-kicker'>Onboarding inteligente</div>", unsafe_allow_html=True)
    st.markdown("<h2 class='auth-step-title'>Configure o primeiro acesso</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p class='auth-step-copy'>{AGENT_NAME} prepara o ambiente em três passos: responsável, escritório e plano operacional.</p>",
        unsafe_allow_html=True,
    )
    render_auth_stepper(current_step)

    if current_step == 1:
        step_one_defaults = {
            "auth_signup_name_input": signup_data["responsavel_nome"],
            "auth_signup_email_input": signup_data["responsavel_email"],
            "auth_signup_whatsapp_input": signup_data["responsavel_whatsapp"],
            "auth_signup_password_input": signup_data["password"],
            "auth_signup_password_confirm_input": signup_data["password_confirm"],
            "auth_signup_lgpd_input": signup_data["lgpd_consent"],
        }
        for widget_key, default_value in step_one_defaults.items():
            if widget_key not in st.session_state:
                st.session_state[widget_key] = default_value
        with st.form("auth_step_one_form"):
            responsavel_nome = st.text_input(
                "Nome completo",
                key="auth_signup_name_input",
                placeholder="Seu nome completo",
            )
            responsavel_email = st.text_input(
                "Email",
                key="auth_signup_email_input",
                placeholder="voce@escritorio.com.br",
            )
            responsavel_whatsapp = st.text_input(
                "WhatsApp",
                key="auth_signup_whatsapp_input",
                placeholder="(11) 99999-9999",
            )
            auth_password = st.text_input(
                "Senha",
                key="auth_signup_password_input",
                type="password",
                placeholder="Mínimo de 10 caracteres",
            )
            auth_password_confirm = st.text_input(
                "Confirmar senha",
                key="auth_signup_password_confirm_input",
                type="password",
                placeholder="Digite a senha novamente",
            )
            lgpd_consent = st.checkbox(
                "Confirmo que os dados serão usados para configurar o acesso local ao CRM.",
                key="auth_signup_lgpd_input",
            )
            st.markdown("<div class='auth-note'>Use uma senha com letras maiúsculas, minúsculas e número. Ela não será salva em texto aberto.</div>", unsafe_allow_html=True)
            submit_step_one = st.form_submit_button("Continuar", use_container_width=True, type="primary")
        if submit_step_one:
            email_error = validate_email(responsavel_email)
            whatsapp_error = validate_whatsapp(responsavel_whatsapp)
            password_error = validate_password(auth_password)
            if not all(
                [
                    responsavel_nome.strip(),
                    responsavel_email.strip(),
                    responsavel_whatsapp.strip(),
                    auth_password.strip(),
                    auth_password_confirm.strip(),
                ]
            ):
                st.warning("Preencha todos os campos do responsável para seguir.")
            elif email_error:
                st.warning(email_error)
            elif whatsapp_error:
                st.warning(whatsapp_error)
            elif password_error:
                st.warning(password_error)
            elif auth_password != auth_password_confirm:
                st.warning("As senhas informadas não coincidem.")
            elif not lgpd_consent:
                st.warning("Confirme o uso dos dados para concluir a configuração local.")
            else:
                st.session_state.auth_signup_data = {
                    **signup_data,
                    "responsavel_nome": responsavel_nome.strip(),
                    "responsavel_email": responsavel_email.strip(),
                    "responsavel_whatsapp": responsavel_whatsapp.strip(),
                    "password": auth_password,
                    "password_confirm": auth_password_confirm,
                    "lgpd_consent": bool(lgpd_consent),
                }
                st.session_state.auth_step = 2
                st.rerun()

    elif current_step == 2:
        step_two_defaults = {
            "auth_signup_office_input": signup_data["office_name"],
            "auth_signup_oab_input": signup_data["oab"],
        }
        for widget_key, default_value in step_two_defaults.items():
            if widget_key not in st.session_state:
                st.session_state[widget_key] = default_value
        with st.form("auth_step_two_form"):
            auth_office_name = st.text_input(
                "Nome do escritório",
                key="auth_signup_office_input",
                placeholder="Ex.: Silva Advocacia Previdenciária",
            )
            auth_oab = st.text_input(
                "Numero da OAB",
                key="auth_signup_oab_input",
                placeholder="Ex.: OAB/SP 123456",
            )
            st.markdown("<div class='auth-note'>Esses dados alimentam contratos, documentos e a identificação institucional do produto.</div>", unsafe_allow_html=True)
            action_cols = st.columns(2, gap="medium")
            with action_cols[0]:
                back_step_two = st.form_submit_button("Voltar", use_container_width=True, type="secondary")
            with action_cols[1]:
                submit_step_two = st.form_submit_button("Continuar", use_container_width=True, type="primary")
        if back_step_two:
            st.session_state.auth_step = 1
            st.rerun()
        if submit_step_two:
            if not auth_office_name.strip() or not auth_oab.strip():
                st.warning("Preencha o nome do escritório e o número da OAB para seguir.")
            else:
                st.session_state.auth_signup_data = {
                    **signup_data,
                    "office_name": auth_office_name.strip(),
                    "oab": auth_oab.strip(),
                }
                st.session_state.auth_step = 3
                st.rerun()

    else:
        selected_plan = render_plan_selector(st.session_state.get("settings_plan", "Essencial"))
        st.markdown("<div class='auth-note'>Escolha o plano compatível com o volume e a operação do escritório.</div>", unsafe_allow_html=True)
        action_cols = st.columns(2, gap="medium")
        with action_cols[0]:
            if st.button("Voltar", key="auth_step_3_back", use_container_width=True, type="secondary"):
                st.session_state.auth_step = 2
                st.rerun()
        with action_cols[1]:
            if st.button("Criar conta", key="auth_finish_signup", use_container_width=True, type="primary"):
                try:
                    persist_auth_profile_to_settings(selected_plan)
                except ValueError as exc:
                    st.error(str(exc))
                except OSError:
                    st.error("Não foi possível salvar a conta local. Verifique as permissões da pasta de dados.")
                else:
                    st.session_state.auth_signup_data = {
                        **st.session_state.auth_signup_data,
                        "password": "",
                        "password_confirm": "",
                    }
                    st.session_state.is_authenticated = True
                    st.session_state.current_view = "dashboard"
                    st.rerun()

    st.caption("Já possui uma conta configurada? Use Entrar no seletor acima.")


def render_auth_screen() -> None:
    account_ready = credentials_configured()
    if account_ready and st.session_state.auth_mode == "signup":
        st.session_state.auth_mode = "login"

    auth_left, auth_right = st.columns([1.08, 0.92], gap="large")
    with auth_left:
        render_auth_hero_panel()
    with auth_right:
        with st.container(border=True):
            st.markdown("<span class='auth-form-marker'></span>", unsafe_allow_html=True)
            switch_cols = st.columns(2, gap="medium")
            with switch_cols[0]:
                if st.button(
                    "Criar conta",
                    key="auth_switch_signup",
                    use_container_width=True,
                    type="primary" if st.session_state.auth_mode == "signup" else "secondary",
                    disabled=account_ready,
                ):
                    st.session_state.auth_mode = "signup"
                    st.session_state.auth_step = 1
                    st.rerun()
            with switch_cols[1]:
                if st.button(
                    "Entrar",
                    key="auth_switch_login",
                    use_container_width=True,
                    type="primary" if st.session_state.auth_mode == "login" else "secondary",
                ):
                    st.session_state.auth_mode = "login"
                    st.rerun()

            if st.session_state.auth_mode == "login":
                render_auth_login()
            else:
                render_auth_signup()


def render_dashboard_view() -> None:
    render_shell_page_header(
        "Dashboard Executivo",
        "Comando executivo com carteira, priorizacao e risco documental da operacao previdenciaria.",
    )
    office_settings = st.session_state.get("office_settings", load_office_settings())
    dashboard = get_dashboard_summary()
    pipeline_records = build_pipeline_records(limit=200)
    revenue_snapshot = build_revenue_snapshot(pipeline_records, office_settings)
    source_df = build_source_breakdown_dataframe(dashboard)
    activity_df = build_recent_activity_dataframe(dashboard)
    case_df = build_case_dataframe(pipeline_records[:18], office_settings)
    task_rows = build_recent_task_rows(pipeline_records, limit=3)
    document_hotspot_df = build_document_hotspot_dataframe(pipeline_records, limit=6)

    approved_total = next(
        (int(row["total"]) for row in dashboard["by_status"] if row["status"] == "aprovado"),
        0,
    )
    revision_total = next(
        (int(row["total"]) for row in dashboard["by_status"] if row["status"] == "revisao"),
        0,
    )
    disqualified_total = next(
        (int(row["total"]) for row in dashboard["by_status"] if row["status"] == "desqualificado"),
        0,
    )
    total_cases = int(dashboard["total"])
    conversion_rate = (approved_total / total_cases * 100) if total_cases else 0.0
    average_ticket = format_currency(float(revenue_snapshot["average_ticket"]))
    stage_totals = {
        column_id: len([record for record in pipeline_records if record["stage"] == column_id])
        for column_id, *_ in PIPELINE_COLUMNS
    }
    won_total = stage_totals.get("caso_ativo", 0) + stage_totals.get("encerrado", 0)
    lost_total = stage_totals.get("perdido", 0)
    settled_total = stage_totals.get("encerrado", 0)
    active_total = max(total_cases - settled_total - lost_total, 0)
    won_rate = (won_total / total_cases * 100) if total_cases else 0.0
    lost_rate = (lost_total / total_cases * 100) if total_cases else 0.0

    recent_values = activity_df["Casos"].astype(int).tolist() if not activity_df.empty else []
    activity_values = ([0] * 7 + recent_values)[-7:]
    cumulative_values: list[int] = []
    running_total = max(total_cases - sum(activity_values), 0)
    for value in activity_values:
        running_total += value
        cumulative_values.append(running_total)

    def render_mini_bars(values: list[int], color: str) -> str:
        chart_max = max(values, default=0) or 1
        return "".join(
            f"<span style='height:{max(10, round(value / chart_max * 68))}px;background:{color}'></span>"
            for value in values
        )

    activity_bars = render_mini_bars(activity_values, "#42b83f")
    cumulative_bars = render_mini_bars(cumulative_values, "#3f9fe8")
    revenue_bars = render_mini_bars(activity_values, "#f22f5d")
    stage_palette = ["#2448a8", "#42b83f", "#ffae19", "#f22f5d"]
    maximum_stage_total = max(stage_totals.values(), default=0) or 1
    funnel_rows_markup = "".join(
        (
            "<div class='law-funnel-row'>"
            f"<span class='law-funnel-label'>{label}</span>"
            "<span class='law-funnel-track'>"
            f"<span class='law-funnel-fill' style='width:{max(0, round(stage_totals[column_id] / maximum_stage_total * 100))}%;background:{stage_palette[index % len(stage_palette)]}'></span>"
            "</span>"
            f"<span class='law-funnel-count'>{stage_totals[column_id]}</span>"
            "</div>"
        )
        for index, (column_id, label, _subtitle, _tone) in enumerate(PIPELINE_COLUMNS)
    )

    st.markdown(
        (
            "<div class='law-dashboard-primary'>"
            "<div class='law-results-card'>"
            "<div class='law-result-segment lost'>"
            "<span class='law-result-label'>Perdidos</span><span class='law-result-icon'>&#8595;</span>"
            f"<span class='law-result-value'>{lost_total}</span><span class='law-result-rate'>{lost_rate:.1f}% da carteira</span>"
            "</div>"
            "<div class='law-result-segment won'>"
            "<span class='law-result-label'>Contratados</span><span class='law-result-icon'>&#8593;</span>"
            f"<span class='law-result-value'>{won_total}</span><span class='law-result-rate'>{won_rate:.1f}% da carteira</span>"
            "</div></div>"
            "<div class='law-stat-panel'>"
            "<div class='law-panel-heading'><h3>Casos concluídos</h3><span>Últimos registros</span></div>"
            f"<div class='law-stat-value'>{settled_total}</div>"
            f"<div class='law-panel-legend'><span><i style='background:#42b83f'></i>Encerrados</span><span>{conversion_rate:.0f}% qualificados</span></div>"
            f"<div class='law-mini-chart'>{activity_bars}</div>"
            "</div>"
            "<div class='law-stat-panel'>"
            "<div class='law-panel-heading'><h3>Carteira total</h3><span>Visão consolidada</span></div>"
            f"<div class='law-stat-value'>{total_cases}</div>"
            f"<div class='law-panel-legend'><span><i style='background:#3f9fe8'></i>{active_total} em andamento</span><span><i style='background:#42b83f'></i>{settled_total} encerrados</span></div>"
            f"<div class='law-mini-chart'>{cumulative_bars}</div>"
            "</div></div>"
            "<details class='law-dashboard-details'>"
            "<summary>Honorários e desempenho do funil</summary>"
            "<div class='law-dashboard-secondary'>"
            "<div class='law-side-stack'>"
            "<div class='law-revenue-panel'>"
            "<div class='law-panel-heading'><h3>Honorários em carteira</h3><span>Potencial</span></div>"
            f"<div class='law-revenue-value'>{format_currency(float(revenue_snapshot['potential_total']))}</div>"
            f"<div class='law-revenue-note'>Ticket médio {average_ticket}</div>"
            f"<div class='law-mini-chart'>{revenue_bars}</div>"
            "</div>"
            "<div class='law-alert-card'>"
            f"<div><span>Pendências documentais</span><strong>{int(dashboard['document_backlog'])}</strong></div>"
            "<div class='law-alert-icon'>&#9888;</div>"
            "</div></div>"
            "</details>"
            "<div class='law-funnel-panel'>"
            "<div class='law-panel-heading'><h3>Desempenho do funil jurídico</h3><span>Casos por etapa</span></div>"
            f"<div class='law-funnel-list'>{funnel_rows_markup}</div>"
            "</div></div>"
        ),
        unsafe_allow_html=True,
    )

    if not pipeline_records:
        st.markdown(
            "<div class='pre-empty-state'>Ainda não há atendimentos. Comece registrando o primeiro contato na área de Atendimentos.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Iniciar novo atendimento", key="dashboard_start_attendance", type="primary"):
            set_current_view("leads")
            st.rerun()
        st.markdown("<h3 class='pre-section-title'>Como usar o sistema</h3>", unsafe_allow_html=True)
        render_process_steps()
        return

    available_case_ids = [int(record["id"]) for record in pipeline_records]
    pending_focus_case_id = st.session_state.pop("pending_dashboard_case_id", None)
    if pending_focus_case_id in available_case_ids:
        st.session_state.selected_dashboard_case_id = int(pending_focus_case_id)
    if st.session_state.selected_dashboard_case_id not in available_case_ids:
        st.session_state.selected_dashboard_case_id = available_case_ids[0]

    focus_case_id = st.selectbox(
        "Caso-chave da carteira",
        options=available_case_ids,
        format_func=lambda case_id: next(
            (
                f"#{item['id']} | {item['lead_name']} | {item['flow_name']}"
                for item in pipeline_records
                if int(item["id"]) == int(case_id)
            ),
            f"Caso #{case_id}",
        ),
        key="selected_dashboard_case_id",
    )
    st.markdown(
        (
            "<div class='law-pulse-inline'>"
            f"<span><strong>{len(pipeline_records)}</strong> casos monitorados</span>"
            f"<span><strong>{int(dashboard['document_backlog'])}</strong> pendências documentais</span>"
            f"<span><strong>{disqualified_total}</strong> desqualificados</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    focus_record = next(
        record for record in pipeline_records if int(record["id"]) == int(focus_case_id)
    )
    focus_details = get_attendance_details(int(focus_case_id))
    focus_documents = list_attendance_documents(int(focus_case_id))
    focus_required_total, focus_validated_total = get_document_progress(focus_documents)
    pending_required_names = [
        str(document["document_name"])
        for document in focus_documents
        if int(document["required"]) == 1 and str(document["status"]) != "validado"
    ]
    normalized_status = normalize_triage_status(str(focus_record["status"]))
    status_label, status_background, status_color = STATUS_STYLE.get(
        normalized_status,
        ("Status", "#f4f4f4", "#555555"),
    )
    fee_percentage = resolve_fee_percentage(str(focus_record["flow_name"]), office_settings) / 100
    potential_fee_total = float(focus_record.get("estimated_total_value") or 0.0) * fee_percentage
    potential_fee_monthly = float(focus_record.get("estimated_monthly_value") or 0.0) * fee_percentage
    focus_benefit_label = (
        focus_details["benefit_category"]
        if focus_details and focus_details["benefit_category"]
        else str(focus_record["flow_name"])
    )
    action_tab, insight_tab, portfolio_tab = st.tabs(
        ["Ação prioritária", "Indicadores", "Carteira e risco"]
    )

    with action_tab:
        tactical_cols = st.columns([0.92, 1.08], gap="medium")
        with tactical_cols[0]:
            with st.container(border=True):
                st.markdown("<h3 class='pre-section-title'>Fila prioritária</h3>", unsafe_allow_html=True)
                st.caption("O que merece ação humana agora, ordenado por urgência operacional.")
                if not task_rows:
                    st.info("Nenhuma tarefa crítica foi identificada nesta carteira.")
                else:
                    for task in task_rows:
                        priority_class = str(task["priority"]).lower()
                        st.markdown(
                            (
                                "<div class='pre-task-item'>"
                                f"<div class='pre-task-priority {priority_class}'>{task['priority']}</div>"
                                f"<h4>#{task['case_id']} | {task['lead_name']}</h4>"
                                f"<p><strong>{task['title']}</strong></p>"
                                f"<p>{task['description']}</p>"
                                "</div>"
                            ),
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            f"Trazer para o centro #{task['case_id']}",
                            key=f"dashboard_focus_task_{task['case_id']}",
                            use_container_width=True,
                        ):
                            st.session_state.pending_dashboard_case_id = int(task["case_id"])
                            st.rerun()

        with tactical_cols[1]:
            with st.container(border=True):
                st.markdown(
                    (
                        "<div class='pre-focus-hero'>"
                        f"<div class='eyebrow'>{get_stage_label(str(focus_record['stage']))}</div>"
                        f"<h3>#{focus_record['id']} | {focus_record['lead_name']}</h3>"
                        f"<p>{focus_record['flow_name']} | {status_label}</p>"
                        "</div>"
                        "<div class='pre-focus-grid'>"
                        f"<div class='pre-focus-stat'><strong>{focus_record['score']}/100</strong><span>Score documental atual</span></div>"
                        f"<div class='pre-focus-stat'><strong>{focus_validated_total}/{focus_required_total}</strong><span>Obrigatórios validados</span></div>"
                        f"<div class='pre-focus-stat'><strong>{format_currency(potential_fee_total) if potential_fee_total > 0 else '-'}</strong><span>Honorário potencial</span></div>"
                        f"<div class='pre-focus-stat'><strong>{format_currency(potential_fee_monthly) if potential_fee_monthly > 0 else '-'}</strong><span>Recorrência mensal estimada</span></div>"
                        "</div>"
                        f"<div class='status-chip' style='background:{status_background}; color:{status_color};'>{status_label}</div>"
                        "<div class='pre-detail-list'>"
                        f"<div class='pre-detail-row'><strong>Benefício dominante</strong><span>{focus_benefit_label}</span></div>"
                        f"<div class='pre-detail-row'><strong>Resumo executivo</strong><span>{focus_details['summary'] if focus_details and focus_details['summary'] else 'Caso pronto para leitura executiva dentro do painel.'}</span></div>"
                        f"<div class='pre-detail-row'><strong>Próximo passo</strong><span>{focus_details['next_step'] if focus_details and focus_details['next_step'] else 'Sem orientação registrada ainda.'}</span></div>"
                        f"<div class='pre-detail-row'><strong>Risco documental</strong><span>{', '.join(pending_required_names[:3]) if pending_required_names else 'Sem pendências críticas nos documentos obrigatórios.'}</span></div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
                action_cols = st.columns(2, gap="small")
                with action_cols[0]:
                    if st.button("Abrir no CRM", key="dashboard_open_crm_focus", use_container_width=True):
                        st.session_state.selected_crm_case_id = int(focus_record["id"])
                        set_current_view("crm")
                        st.rerun()
                with action_cols[1]:
                    secondary_label = "Abrir contratos" if normalized_status == "aprovado" else "Abrir dossiê"
                    if st.button(secondary_label, key="dashboard_open_workspace_focus", use_container_width=True):
                        if normalized_status == "aprovado":
                            st.session_state.selected_contract_attendance_id = int(focus_record["id"])
                            set_current_view("contratos")
                        else:
                            st.session_state.selected_attendance_id = int(focus_record["id"])
                            st.session_state.selected_document_attendance_id = int(focus_record["id"])
                            set_current_view("leads")
                        st.rerun()

    with insight_tab:
        insight_cols = st.columns(2, gap="medium")
        with insight_cols[0]:
            st.markdown("<h3 class='pre-section-title'>Origem e resultado</h3>", unsafe_allow_html=True)
            st.caption("Conversão por fluxo monitorado no escritório.")
            if source_df.empty:
                st.info("Ainda não há volume suficiente para distribuir resultados por fluxo.")
            else:
                st.bar_chart(
                    source_df,
                    x="Fonte",
                    y=["Qualificados", "Em revisao", "Desqualificados"],
                    horizontal=True,
                    color=["#42b83f", "#66b5e8", "#f22f5d"],
                    height=205,
                )
        with insight_cols[1]:
            st.markdown("<h3 class='pre-section-title'>Ritmo da carteira</h3>", unsafe_allow_html=True)
            st.caption("Entradas recentes e tração comercial monitoradas dia a dia.")
            if activity_df.empty:
                st.info("Sem movimentação recente suficiente para o gráfico diário.")
            else:
                st.line_chart(activity_df, x="Dia", y="Casos", color="#2448a8", height=205)
            st.caption(f"Taxa global de qualificação: {conversion_rate:.1f}%")

    with portfolio_tab:
        lower_cols = st.columns([1.08, 0.92], gap="medium")
        with lower_cols[0]:
            st.markdown("<h3 class='pre-section-title'>Mesa executiva da carteira</h3>", unsafe_allow_html=True)
            st.caption("Leads recentes com etapa, score, documentos e honorário potencial.")
            st.dataframe(case_df, hide_index=True, use_container_width=True, height=230)
            quick_cases = pipeline_records[:4]
            if quick_cases:
                quick_cols = st.columns(len(quick_cases))
                for col, item in zip(quick_cols, quick_cases):
                    with col:
                        if st.button(
                            f"Focar #{item['id']}",
                            key=f"dashboard_quick_focus_{item['id']}",
                            use_container_width=True,
                        ):
                            st.session_state.pending_dashboard_case_id = int(item["id"])
                            st.rerun()

        with lower_cols[1]:
            st.markdown("<h3 class='pre-section-title'>Risco documental</h3>", unsafe_allow_html=True)
            st.caption("Casos com maior gap documental para ação preventiva.")
            if document_hotspot_df.empty:
                st.info("Não há backlog documental relevante neste momento.")
            else:
                st.dataframe(document_hotspot_df, hide_index=True, use_container_width=True, height=230)
            st.markdown(
                (
                    "<div class='law-pulse-inline'>"
                    f"<span><strong>{revenue_snapshot['tracked_cases']}</strong> casos com estimativa</span>"
                    f"<span><strong>{format_currency(float(revenue_snapshot['potential_monthly']))}</strong> receita mensal acompanhada</span>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def render_crm_case_management(attendance_id: int, details: Any) -> None:
    """Render the auditable operational controls for one legal CRM record."""
    stage_ids = [stage_id for stage_id, _ in CRM_STAGES]
    stage_labels = {stage_id: label for stage_id, label in CRM_STAGES}
    current_stage = str(details["crm_stage"] or "triagem")
    if current_stage not in stage_ids:
        current_stage = "triagem"
    current_conflict = str(details["conflict_status"] or "pendente")
    if current_conflict not in CONFLICT_STATUS:
        current_conflict = "pendente"
    current_privacy_ack = bool(int(details["privacy_notice_acknowledged"] or 0))
    current_privacy_basis = str(
        details["privacy_legal_basis"] or "procedimentos_preliminares"
    )
    if current_privacy_basis not in PRIVACY_LEGAL_BASES:
        current_privacy_basis = "procedimentos_preliminares"

    next_action_date = date.today()
    stored_next_action_at = str(details["next_action_at"] or "")
    try:
        next_action_date = date.fromisoformat(stored_next_action_at[:10])
    except ValueError:
        pass

    st.markdown("<h3 class='pre-section-title'>Gestão do caso</h3>", unsafe_allow_html=True)
    if current_conflict != "liberado":
        st.warning(
            "Cheque conflito de interesse antes de orientar juridicamente, enviar proposta ou liberar contrato."
        )
    if not current_privacy_ack:
        st.warning(
            "Registre a entrega do aviso de privacidade e a base legal antes da contratação."
        )

    with st.form(f"crm_case_management_{attendance_id}"):
        control_cols = st.columns(2, gap="medium")
        with control_cols[0]:
            selected_stage = st.selectbox(
                "Etapa do caso",
                stage_ids,
                index=stage_ids.index(current_stage),
                format_func=lambda item: stage_labels[item],
            )
            selected_conflict = st.selectbox(
                "Checagem de conflito",
                list(CONFLICT_STATUS),
                index=list(CONFLICT_STATUS).index(current_conflict),
                format_func=lambda item: CONFLICT_STATUS[item],
            )
            conflict_parties = st.text_area(
                "Partes verificadas no conflito",
                value=str(details["conflict_checked_parties"] or ""),
                placeholder="Cliente, parte contrária, empresa e demais envolvidos.",
            )
            conflict_notes = st.text_area(
                "Registro da checagem", value=str(details["conflict_notes"] or "")
            )
            assigned_to = st.text_input(
                "Responsável", value=str(details["assigned_to"] or "")
            )
        with control_cols[1]:
            next_action = st.text_input(
                "Próxima ação", value=str(details["next_action"] or "")
            )
            selected_next_date = st.date_input("Data da próxima ação", value=next_action_date)
            lost_reason = st.text_input(
                "Motivo da perda/encerramento", value=str(details["lost_reason"] or "")
            )
        st.markdown("**Privacidade e LGPD**")
        privacy_cols = st.columns([1.15, 0.85], gap="medium")
        with privacy_cols[0]:
            selected_privacy_ack = st.checkbox(
                "Aviso de privacidade apresentado ao titular",
                value=current_privacy_ack,
                help=(
                    "Registra ciência sobre finalidade, dados necessários, acesso restrito, "
                    "retenção e canais para exercício de direitos."
                ),
            )
        with privacy_cols[1]:
            privacy_basis_ids = list(PRIVACY_LEGAL_BASES)
            selected_privacy_basis = st.selectbox(
                "Base legal predominante",
                privacy_basis_ids,
                index=privacy_basis_ids.index(current_privacy_basis),
                format_func=lambda value: PRIVACY_LEGAL_BASES[value],
            )
        saved_case = st.form_submit_button("Salvar gestão do caso", type="primary")

    if saved_case:
        try:
            update_crm_case(
                attendance_id=attendance_id,
                crm_stage=selected_stage,
                conflict_status=selected_conflict,
                assigned_to=assigned_to,
                next_action=next_action,
                next_action_at=selected_next_date.isoformat() if next_action else None,
                lost_reason=lost_reason,
                conflict_checked_parties=conflict_parties,
                conflict_notes=conflict_notes,
                privacy_notice_acknowledged=selected_privacy_ack,
                privacy_legal_basis=selected_privacy_basis,
            )
        except ValueError as error:
            st.error(str(error))
            return
        add_crm_activity(
            attendance_id=attendance_id,
            activity_type="Atualização do CRM",
            body=(
                f"Etapa: {stage_labels[selected_stage]}. "
                f"Conflito: {CONFLICT_STATUS[selected_conflict]}. "
                f"Privacidade: {'aviso registrado' if selected_privacy_ack else 'pendente'}."
            ),
        )
        st.success("Gestão do caso atualizada.")
        st.rerun()

    task_col, timeline_col = st.columns([0.92, 1.08], gap="large")
    with task_col:
        st.markdown("<h3 class='pre-section-title'>Tarefas abertas</h3>", unsafe_allow_html=True)
        with st.form(f"crm_task_{attendance_id}", clear_on_submit=True):
            task_title = st.text_input("Nova tarefa", placeholder="Ex.: Retornar ligação para a cliente")
            task_description = st.text_area(
                "Descrição da tarefa",
                placeholder="Registre o objetivo, o contexto e o resultado esperado.",
            )
            task_due = st.date_input("Prazo", value=date.today())
            task_owner = st.text_input("Responsável pela tarefa", value=str(details["assigned_to"] or ""))
            task_priority = st.selectbox(
                "Prioridade",
                options=["baixa", "media", "alta", "critica"],
                index=1,
                format_func=lambda value: value.capitalize(),
            )
            new_task = st.form_submit_button("Adicionar tarefa")
        if new_task:
            try:
                create_crm_task(
                    attendance_id=attendance_id,
                    title=task_title,
                    description=task_description,
                    due_at=task_due.isoformat(),
                    assigned_to=task_owner,
                    priority=task_priority,
                )
                add_crm_activity(
                    attendance_id=attendance_id,
                    activity_type="Tarefa criada",
                    body=task_title,
                )
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        tasks = list_crm_tasks(attendance_id)
        if not tasks:
            st.caption("Nenhuma tarefa aberta para este caso.")
        for task in tasks:
            priority_label = str(task["priority"] or "media").capitalize()
            source_label = "Automática" if task["source_event_id"] is not None else "Manual"
            st.markdown(
                (
                    f"**{task['title']}**  \n"
                    f"{task['description'] or 'Sem descrição.'}  \n"
                    f"Prazo operacional: {task['due_at'] or 'Não definido'} · "
                    f"{task['assigned_to'] or 'Sem responsável'} · {priority_label} · {source_label}"
                )
            )
            if int(task["requires_review"] or 0) and str(task["review_status"]) == "pendente":
                st.warning(
                    "Revisão humana obrigatória: confirme o termo inicial, a contagem e o calendário antes de aprovar."
                )
                review_due = st.date_input(
                    "Prazo confirmado",
                    value=date.fromisoformat(str(task["due_at"])[:10]) if task["due_at"] else date.today(),
                    key=f"crm_task_review_due_{task['id']}",
                )
                review_cols = st.columns(2)
                with review_cols[0]:
                    if st.button("Aprovar tarefa", key=f"crm_task_approve_{task['id']}", use_container_width=True):
                        review_crm_task(
                            task_id=int(task["id"]),
                            approved=True,
                            due_at=review_due.isoformat(),
                        )
                        add_crm_activity(
                            attendance_id=attendance_id,
                            activity_type="Revisão humana",
                            body=f"Tarefa aprovada: {task['title']}. Prazo confirmado: {review_due.isoformat()}.",
                        )
                        st.rerun()
                with review_cols[1]:
                    if st.button("Descartar tarefa", key=f"crm_task_reject_{task['id']}", use_container_width=True):
                        review_crm_task(task_id=int(task["id"]), approved=False)
                        add_crm_activity(
                            attendance_id=attendance_id,
                            activity_type="Revisão humana",
                            body=f"Tarefa automática descartada: {task['title']}.",
                        )
                        st.rerun()
            else:
                if st.button("Concluir", key=f"crm_task_done_{task['id']}"):
                    try:
                        complete_crm_task(int(task["id"]))
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        add_crm_activity(
                            attendance_id=attendance_id,
                            activity_type="Tarefa concluída",
                            body=str(task["title"]),
                        )
                        st.rerun()
            st.divider()

    with timeline_col:
        st.markdown("<h3 class='pre-section-title'>Histórico de relacionamento</h3>", unsafe_allow_html=True)
        with st.form(f"crm_activity_{attendance_id}", clear_on_submit=True):
            activity_type = st.selectbox(
                "Tipo de interação",
                ["Ligação", "WhatsApp", "E-mail", "Reunião", "Nota interna"],
            )
            activity_body = st.text_area(
                "Registro", placeholder="Registre o que foi combinado e o próximo contexto útil."
            )
            new_activity = st.form_submit_button("Registrar interação")
        if new_activity:
            add_crm_activity(
                attendance_id=attendance_id,
                activity_type=activity_type,
                body=activity_body,
            )
            st.rerun()
        activities = list_crm_activities(attendance_id)
        if not activities:
            st.caption("Nenhuma interação registrada ainda.")
        for activity in activities:
            st.markdown(
                f"**{activity['activity_type']}** · {activity['created_at']}  \n{activity['body']}"
            )
            st.divider()


def render_automation_center(pipeline_records: list[dict[str, Any]]) -> None:
    summary = get_integration_summary()
    st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
    render_panel_header(
        "Orquestração",
        "Central de automações",
        "Eventos idempotentes alimentam tarefas internas; prazos jurídicos permanecem sujeitos à validação humana.",
    )
    metric_cols = st.columns(5)
    metric_cols[0].metric("Na fila", summary["pending"])
    metric_cols[1].metric("Processando", summary["processing"])
    metric_cols[2].metric("Concluídos", summary["completed"])
    metric_cols[3].metric("Falhas", summary["failed"])
    metric_cols[4].metric("Revisões humanas", summary["pending_review"])

    action_cols = st.columns([0.34, 0.66], gap="medium")
    with action_cols[0]:
        if st.button("Processar fila agora", key="process_integration_queue", use_container_width=True):
            results = process_pending_events(limit=50)
            failed = len([result for result in results if result.status == "falhou"])
            if failed:
                st.error(f"{failed} evento(s) falharam. Consulte a trilha abaixo.")
            else:
                st.success(f"{len(results)} evento(s) processados com segurança.")
            st.rerun()
    with action_cols[1]:
        st.info(
            "Publicações, movimentações e exigências criam tarefas bloqueadas até um responsável confirmar o prazo."
        )

    with st.expander("Entrada assistida de evento", expanded=False):
        st.caption(
            "Use este formulário enquanto os conectores externos não estão habilitados. A referência evita duplicidade."
        )
        if not pipeline_records:
            st.warning("Cadastre ao menos um atendimento antes de registrar eventos.")
        else:
            case_options = [int(record["id"]) for record in pipeline_records]
            event_labels = {
                event_type: str(rule["label"])
                for event_type, rule in EVENT_RULES.items()
                if event_type != "lead.qualified"
            }
            with st.form("manual_integration_event", clear_on_submit=True):
                event_case_id = st.selectbox(
                    "Caso vinculado",
                    options=case_options,
                    format_func=lambda case_id: next(
                        (
                            f"#{record['id']} | {record['lead_name']} | {record['flow_name']}"
                            for record in pipeline_records
                            if int(record["id"]) == int(case_id)
                        ),
                        f"Caso #{case_id}",
                    ),
                )
                event_type = st.selectbox(
                    "Tipo de evento",
                    options=list(event_labels),
                    format_func=lambda value: event_labels[value],
                )
                source = st.selectbox(
                    "Origem",
                    options=["publicacoes", "datajud", "meu_inss", "whatsapp"],
                    format_func=lambda value: INTEGRATION_SOURCE_LABELS[value],
                )
                external_reference = st.text_input(
                    "Referência única",
                    placeholder="Ex.: publicação 12345 ou movimentação 85-2026",
                )
                event_summary = st.text_area(
                    "Resumo recebido",
                    placeholder="Cole o teor essencial para a triagem e para a tarefa.",
                )
                suggested_due_at = st.text_input(
                    "Data operacional sugerida (opcional)",
                    placeholder="AAAA-MM-DD — será confirmada por um responsável",
                )
                event_owner = st.text_input(
                    "Responsável sugerido (opcional)",
                    placeholder="Se vazio, usa o responsável do caso.",
                )
                submit_event = st.form_submit_button(
                    "Registrar e processar evento", type="primary", use_container_width=True
                )
            if submit_event:
                invalid_suggested_date = False
                if suggested_due_at.strip():
                    try:
                        date.fromisoformat(suggested_due_at.strip())
                    except ValueError:
                        invalid_suggested_date = True
                if not external_reference.strip() or not event_summary.strip():
                    st.error("Informe a referência única e o resumo do evento.")
                elif invalid_suggested_date:
                    st.error("A data operacional sugerida deve usar o formato AAAA-MM-DD.")
                else:
                    receipt = receive_event(
                        event_type=event_type,
                        source=source,
                        attendance_id=int(event_case_id),
                        external_reference=external_reference,
                        payload={
                            "summary": event_summary,
                            "suggested_due_at": suggested_due_at,
                            "assigned_to": event_owner,
                        },
                    )
                    if not receipt.created:
                        st.warning("Esse evento já havia sido recebido; nenhuma tarefa duplicada foi criada.")
                    else:
                        result = process_event(receipt.event_id)
                        if result.status == "concluido":
                            st.success(f"Evento processado e tarefa #{result.task_id} criada.")
                        else:
                            st.error(f"O evento foi registrado, mas falhou: {result.error}")
                    st.rerun()

    events = list_integration_events(limit=20)
    if events:
        event_rows = [
            {
                "ID": int(event["id"]),
                "Evento": str(EVENT_RULES.get(str(event["event_type"]), {}).get("label", event["event_type"])),
                "Origem": INTEGRATION_SOURCE_LABELS.get(str(event["source"]), str(event["source"])),
                "Caso": f"#{event['attendance_id']} | {event['lead_name'] or 'Não localizado'}",
                "Prioridade": str(event["priority"]).capitalize(),
                "Status": INTEGRATION_STATUS_LABELS.get(str(event["status"]), str(event["status"])),
                "Revisão": str(event["task_review_status"] or "-").replace("_", " ").capitalize(),
                "Recebido": str(event["received_at"]),
            }
            for event in events
        ]
        st.dataframe(pd.DataFrame(event_rows), hide_index=True, use_container_width=True)

        failed_events = [event for event in events if str(event["status"]) == "falhou"]
        if failed_events:
            failed_id = st.selectbox(
                "Evento com falha",
                options=[int(event["id"]) for event in failed_events],
                format_func=lambda event_id: next(
                    f"#{event['id']} | {event['last_error']}"
                    for event in failed_events
                    if int(event["id"]) == event_id
                ),
            )
            if st.button("Reenfileirar evento", key="retry_integration_event"):
                retry_integration_event(int(failed_id))
                st.success("Evento devolvido à fila.")
                st.rerun()

        with st.expander("Trilha de auditoria", expanded=False):
            audit_event_id = st.selectbox(
                "Evento",
                options=[int(event["id"]) for event in events],
                key="automation_audit_event_id",
            )
            audit_rows = list_integration_audit(int(audit_event_id))
            if audit_rows:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Quando": row["created_at"],
                                "Ação": str(row["action"]).replace("_", " ").capitalize(),
                                "Detalhes": row["details_json"],
                            }
                            for row in audit_rows
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
    else:
        st.caption("Nenhum evento de integração foi recebido ainda.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_crm_indicators(crm_summary: dict[str, Any], crm_performance: dict[str, Any]) -> None:
    metric_cols = st.columns(5)
    metric_cols[0].metric("Tarefas abertas", crm_summary["open_tasks"])
    metric_cols[1].metric("Tarefas vencidas", crm_summary["overdue_tasks"])
    metric_cols[2].metric("Conflitos pendentes", crm_summary["pending_conflicts"])
    metric_cols[3].metric("Vencem hoje", crm_summary["due_today"])
    metric_cols[4].metric("Sem próxima ação", crm_summary["stalled_leads"])
    st.caption(
        f"Tempo médio até contratação: {crm_performance['average_days_to_contract']:.1f} dia(s)."
    )
    if crm_performance["by_source"]:
        source_rows = [
            {
                "Origem": row["source"],
                "Leads": int(row["total"]),
                "Contratados": int(row["contracted"] or 0),
            }
            for row in crm_performance["by_source"]
        ]
        st.dataframe(
            pd.DataFrame(source_rows),
            hide_index=True,
            use_container_width=True,
            height=min(300, 42 + len(source_rows) * 36),
        )


def render_crm_pipeline_board(
    filtered_records: list[dict[str, Any]],
    all_pipeline_records: list[dict[str, Any]],
) -> None:
    stage_filter = str(st.session_state.get("crm_stage_filter", "todos"))
    if stage_filter != "todos":
        for phase_id, phase in PIPELINE_PHASES.items():
            if stage_filter in phase["stages"]:
                st.session_state.crm_pipeline_phase = phase_id
                break

    phase_id = st.radio(
        "Fase do funil",
        options=list(PIPELINE_PHASES),
        format_func=lambda value: (
            f"{PIPELINE_PHASES[value]['icon']} {PIPELINE_PHASES[value]['label']}"
        ),
        key="crm_pipeline_phase",
        horizontal=True,
        label_visibility="collapsed",
        width="stretch",
    )
    phase_stage_ids = list(PIPELINE_PHASES[phase_id]["stages"])
    stage_definition = {
        column_id: (label, subtitle, tone)
        for column_id, label, subtitle, tone in PIPELINE_COLUMNS
    }

    if stage_filter == "todos":
        phase_records = [
            record for record in filtered_records if str(record["stage"]) in phase_stage_ids
        ]
    else:
        phase_records = [
            record for record in filtered_records if str(record["stage"]) == stage_filter
        ]

    page_size = 9
    page_count = max(1, (len(phase_records) + page_size - 1) // page_size)
    if int(st.session_state.get("crm_pipeline_page", 1)) > page_count:
        st.session_state.crm_pipeline_page = 1

    page_tools = st.columns([0.62, 0.23, 0.15], gap="small")
    with page_tools[0]:
        if stage_filter == "todos":
            st.caption(
                f"{len(phase_records)} cliente(s) nesta fase. Clique em uma etapa ou em um cliente para abrir o recorte."
            )
        elif st.button(
            "Mostrar as três etapas da fase",
            key="crm_clear_stage_filter",
            icon=":material/filter_alt_off:",
            use_container_width=True,
        ):
            st.session_state.pending_crm_stage_filter = "todos"
            st.rerun()
    with page_tools[1]:
        st.caption(f"{len(phase_records)} cliente(s) · {page_count} página(s)")
    with page_tools[2]:
        selected_page = st.selectbox(
            "Página",
            options=list(range(1, page_count + 1)),
            key="crm_pipeline_page",
            label_visibility="collapsed",
        )

    page_start = (int(selected_page) - 1) * page_size
    page_records = phase_records[page_start : page_start + page_size]
    stage_columns = st.columns(3, gap="medium")
    for stage_column, stage_id in zip(stage_columns, phase_stage_ids):
        label, subtitle, tone = stage_definition[stage_id]
        total_in_stage = len(
            [record for record in all_pipeline_records if str(record["stage"]) == stage_id]
        )
        visible_items = [
            record for record in page_records if str(record["stage"]) == stage_id
        ]
        with stage_column:
            if st.button(
                f"{label} · {total_in_stage}",
                key=f"crm_filter_stage_{stage_id}",
                icon=PIPELINE_STAGE_ICONS[stage_id],
                type="primary" if stage_filter == stage_id else "secondary",
                help=f"Filtrar por {label.lower()}: {subtitle}",
                use_container_width=True,
            ):
                st.session_state.pending_crm_stage_filter = stage_id
                st.rerun()
            st.caption(subtitle)
            with st.container(border=True, height=315):
                st.markdown(
                    "<span class='crm-stage-scroll-marker'></span>",
                    unsafe_allow_html=True,
                )
                if not visible_items:
                    st.caption("Nenhum cliente nesta página.")
                for item in visible_items:
                    if st.button(
                        f"#{item['id']} · {item['lead_name']}",
                        key=f"crm_open_pipeline_case_{phase_id}_{selected_page}_{item['id']}",
                        icon=":material/person:",
                        help=f"Abrir {item['flow_name']} no caso em foco",
                        use_container_width=True,
                    ):
                        st.session_state.pending_crm_case_id = int(item["id"])
                        st.session_state.pending_crm_section = "caso"
                        st.rerun()
                    st.caption(
                        f"{item['flow_name']} · Score {item['score']}/100 · "
                        f"{item['validated_total']}/{item['required_total']} documentos"
                    )


def render_crm_ux_map() -> None:
    st.info("Inventário funcional do CRM atual para orientar fluxos, telas, estados e protótipos de UI/UX.")
    for title, capability, interactions in CRM_UX_CATALOG:
        with st.container(border=True):
            left, right = st.columns([0.9, 1.1])
            with left:
                st.markdown(f"#### {title}")
                st.write(capability)
            with right:
                st.caption("Interações e estados a projetar")
                st.write(interactions)


def render_crm_view() -> None:
    render_shell_page_header(
        "CRM Juridico",
        "Mesa tatica do funil com prioridade, leitura do caso e organizacao executiva da operacao previdenciaria.",
    )
    office_settings = st.session_state.get("office_settings", load_office_settings())
    all_pipeline_records = build_pipeline_records(limit=200)
    crm_summary = get_crm_summary()
    crm_performance = get_crm_performance()
    pending_section = st.session_state.pop("pending_crm_section", None)
    if pending_section in {"funil", "caso", "automacoes", "indicadores", "mapa_ux"}:
        st.session_state.crm_section = pending_section
    pending_case_id = st.session_state.pop("pending_crm_case_id", None)
    if pending_case_id is not None:
        st.session_state.selected_crm_case_id = int(pending_case_id)
    pending_stage_filter = st.session_state.pop("pending_crm_stage_filter", None)
    if pending_stage_filter in {"todos", *[column_id for column_id, *_ in PIPELINE_COLUMNS]}:
        st.session_state.crm_stage_filter = pending_stage_filter
        st.session_state.crm_pipeline_page = 1

    crm_section = st.radio(
        "Área do CRM",
        options=["funil", "caso", "automacoes", "indicadores", "mapa_ux"],
        format_func=lambda value: {
            "funil": "🗂️ Funil e clientes",
            "caso": "👤 Caso em foco",
            "automacoes": "⚡ Automações",
            "indicadores": "📈 Indicadores",
        }.get(value, "🧩 Mapa UX"),
        key="crm_section",
        horizontal=True,
        label_visibility="collapsed",
        width="stretch",
    )
    if crm_section == "mapa_ux":
        render_crm_ux_map()
        return
    if crm_section == "automacoes":
        render_automation_center(all_pipeline_records)
        return
    if crm_section == "indicadores":
        render_crm_indicators(crm_summary, crm_performance)
        return

    search_value = ""
    stage_filter = "todos"

    toolbar_left, toolbar_right = st.columns([1.35, 0.65], gap="medium")
    with toolbar_left:
        search_value = st.text_input(
            "Buscar por nome, telefone ou beneficio",
            key="crm_search_query",
            placeholder="Ex.: Maria, aposentadoria, (11) 9...",
        ).strip().lower()
    with toolbar_right:
        stage_filter = st.selectbox(
            "Recorte operacional",
            ["todos"] + [column_id for column_id, *_ in PIPELINE_COLUMNS],
            format_func=lambda value: "Todas as etapas" if value == "todos" else get_stage_label(value),
            key="crm_stage_filter",
        )

    filtered_records = list(all_pipeline_records)
    if search_value:
        filtered_records = [
            record
            for record in filtered_records
            if search_value in str(record["lead_name"] or "").lower()
            or search_value in str(record["lead_phone"] or "").lower()
            or search_value in str(record["flow_name"] or "").lower()
        ]
    if stage_filter != "todos":
        filtered_records = [
            record for record in filtered_records if str(record["stage"]) == stage_filter
        ]

    if not all_pipeline_records:
        st.markdown(
            "<div class='pre-empty-state'>Ainda nao ha leads no CRM. Assim que a operacao registrar os primeiros atendimentos, a mesa juridica aparece aqui.</div>",
            unsafe_allow_html=True,
        )
        return

    if not filtered_records:
        st.markdown(
            "<div class='pre-empty-state'>Nenhum caso encontrado para esse recorte. Ajuste a busca ou a etapa para retomar a visualizacao.</div>",
            unsafe_allow_html=True,
        )
        return

    available_case_ids = [int(record["id"]) for record in filtered_records]
    if st.session_state.selected_crm_case_id not in available_case_ids:
        st.session_state.selected_crm_case_id = available_case_ids[0]

    focus_case_id = st.selectbox(
        "Cliente no recorte",
        options=available_case_ids,
        format_func=lambda case_id: next(
            (
                f"#{item['id']} | {item['lead_name']} | {item['flow_name']}"
                for item in filtered_records
                if int(item["id"]) == int(case_id)
            ),
            f"Caso #{case_id}",
        ),
        key="selected_crm_case_id",
    )
    focus_record = next(
        record for record in filtered_records if int(record["id"]) == int(focus_case_id)
    )
    if crm_section == "funil":
        render_crm_pipeline_board(filtered_records, all_pipeline_records)
        return

    focus_details = get_attendance_details(int(focus_case_id))
    if focus_details is None:
        st.error("Não foi possível carregar o caso selecionado.")
        return
    focus_documents = list_attendance_documents(int(focus_case_id))
    focus_required_total, focus_validated_total = get_document_progress(focus_documents)
    pending_required_names = [
        str(document["document_name"])
        for document in focus_documents
        if int(document["required"]) == 1 and str(document["status"]) != "validado"
    ]
    normalized_status = normalize_triage_status(str(focus_record["status"]))
    status_label, status_background, status_color = STATUS_STYLE.get(
        normalized_status,
        ("Status", "#f4f4f4", "#555555"),
    )
    fee_percentage = resolve_fee_percentage(str(focus_record["flow_name"]), office_settings) / 100
    potential_fee_total = float(focus_record.get("estimated_total_value") or 0.0) * fee_percentage
    focus_benefit_label = (
        focus_details["benefit_category"]
        if focus_details and focus_details["benefit_category"]
        else str(focus_record["flow_name"])
    )
    focus_triage_profile = parse_triage_profile(focus_details["triage_profile_json"])
    privacy_basis_id = str(focus_details["privacy_legal_basis"] or "")
    privacy_status = (
        "Aviso registrado"
        if bool(int(focus_details["privacy_notice_acknowledged"] or 0))
        else "Pendente de registro"
    )
    if privacy_basis_id in PRIVACY_LEGAL_BASES:
        privacy_status = f"{privacy_status} · {PRIVACY_LEGAL_BASES[privacy_basis_id]}"
    task_rows = build_recent_task_rows(filtered_records, limit=5)
    case_df = build_case_dataframe(filtered_records[:24], office_settings)

    render_crm_case_management(int(focus_case_id), focus_details)
    st.divider()

    tactical_cols = st.columns([0.92, 1.08], gap="large")
    with tactical_cols[0]:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Fila prioritaria</h3>", unsafe_allow_html=True)
        st.caption(
            f"{len(filtered_records)} caso(s) no recorte atual. As tarefas abaixo refletem o que exige decisao humana agora."
        )
        if not task_rows:
            st.info("Nenhuma tarefa critica foi identificada neste recorte.")
        else:
            st.markdown("<div class='pre-task-list'>", unsafe_allow_html=True)
            for task in task_rows:
                priority_class = str(task["priority"]).lower()
                st.markdown(
                    (
                        "<div class='pre-task-item'>"
                        f"<div class='pre-task-priority {priority_class}'>{task['priority']}</div>"
                        f"<h4>#{task['case_id']} | {task['lead_name']}</h4>"
                        f"<p><strong>{task['title']}</strong></p>"
                        f"<p>{task['description']}</p>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
                if st.button(
                    f"Trazer para foco #{task['case_id']}",
                    key=f"crm_focus_task_{task['case_id']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_crm_case_id = int(task["case_id"])
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tactical_cols[1]:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown(
            (
                "<div class='pre-focus-hero'>"
                f"<div class='eyebrow'>{get_stage_label(str(focus_record['stage']))}</div>"
                f"<h3>#{focus_record['id']} | {focus_record['lead_name']}</h3>"
                f"<p>{focus_record['flow_name']} | {status_label}</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-focus-grid'>"
                f"<div class='pre-focus-stat'><strong>{focus_record['score']}/100</strong><span>Score documental atual</span></div>"
                f"<div class='pre-focus-stat'><strong>{focus_validated_total}/{focus_required_total}</strong><span>Obrigatorios validados</span></div>"
                f"<div class='pre-focus-stat'><strong>{format_currency(potential_fee_total) if potential_fee_total > 0 else '-'}</strong><span>Honorario potencial</span></div>"
                f"<div class='pre-focus-stat'><strong>{focus_benefit_label}</strong><span>Beneficio sugerido</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                f"<div class='status-chip' style='background:{status_background}; color:{status_color};'>{status_label}</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-detail-list'>"
                f"<div class='pre-detail-row'><strong>Resumo executivo</strong><span>{focus_details['summary'] if focus_details and focus_details['summary'] else 'Caso pronto para leitura operacional dentro do CRM.'}</span></div>"
                f"<div class='pre-detail-row'><strong>Proximo passo</strong><span>{focus_details['next_step'] if focus_details and focus_details['next_step'] else 'Sem orientacao registrada ainda.'}</span></div>"
                f"<div class='pre-detail-row'><strong>Pendencia documental</strong><span>{', '.join(pending_required_names[:3]) if pending_required_names else 'Nenhuma pendencia critica nos documentos obrigatorios.'}</span></div>"
                f"<div class='pre-detail-row'><strong>Perfil previdenciario</strong><span>{summarize_triage_profile(focus_triage_profile)}</span></div>"
                f"<div class='pre-detail-row'><strong>Privacidade e LGPD</strong><span>{privacy_status}</span></div>"
                f"<div class='pre-detail-row'><strong>Telefone e contato</strong><span>{focus_record['lead_phone'] or 'Nao informado'}</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        action_cols = st.columns(2, gap="small")
        with action_cols[0]:
            if st.button("Abrir no workspace", key="crm_focus_open_workspace", use_container_width=True):
                st.session_state.selected_attendance_id = int(focus_record["id"])
                st.session_state.selected_document_attendance_id = int(focus_record["id"])
                set_current_view("leads")
                st.rerun()
        with action_cols[1]:
            secondary_label = "Abrir contratos" if normalized_status == "aprovado" else "Preparar dossie"
            if st.button(secondary_label, key="crm_focus_open_contracts", use_container_width=True):
                if normalized_status == "aprovado":
                    st.session_state.selected_contract_attendance_id = int(focus_record["id"])
                    set_current_view("contratos")
                else:
                    st.session_state.selected_attendance_id = int(focus_record["id"])
                    st.session_state.selected_document_attendance_id = int(focus_record["id"])
                    set_current_view("leads")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='pre-card pre-dataframe-card'>", unsafe_allow_html=True)
    st.markdown("<h3 class='pre-section-title'>Mesa de casos</h3>", unsafe_allow_html=True)
    st.caption("Leitura rapida do portifolio com lead, etapa, score, documentos e potencial economico.")
    st.dataframe(case_df, hide_index=True, use_container_width=True)
    quick_focus_cols = st.columns(min(len(filtered_records[:4]), 4) or 1)
    for col, item in zip(quick_focus_cols, filtered_records[:4]):
        with col:
            if st.button(
                f"Focar #{item['id']}",
                key=f"crm_focus_case_{item['id']}",
                use_container_width=True,
            ):
                st.session_state.selected_crm_case_id = int(item["id"])
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def render_operational_workspace() -> None:
    operational_tabs = st.tabs(["1. Nova triagem", "2. Documentos", "3. Casos salvos"])
    with operational_tabs[0]:
        render_operation_kpis()
        left, center, right = st.columns([0.78, 1.48, 0.94], gap="medium")
        with left:
            with st.container(border=True):
                render_recent_queue()
        with center:
            with st.container(border=True):
                form_data = render_lead_form()
                st.divider()
                flow = FLOW_DEFINITIONS[st.session_state.selected_flow_id]
                render_question_panel(flow, form_data)
        with right:
            flow = FLOW_DEFINITIONS[st.session_state.selected_flow_id]
            with st.container(border=True):
                render_active_case_panel(flow, form_data)
                if st.session_state.selected_flow_id == "salarioMaternidade":
                    with st.expander("Calculadora de salário-maternidade", expanded=False):
                        render_salario_maternidade_calculator()
                with st.expander("Histórico da sessão", expanded=False):
                    render_history(st.session_state.triage_state.history)

    with operational_tabs[1]:
        render_document_pipeline()

    with operational_tabs[2]:
        render_attendance_consultation()


def render_leads_view() -> None:
    render_shell_page_header(
        "Atendimentos",
        "Siga a sequência: registre o contato, conclua a triagem e acompanhe documentos e casos salvos.",
    )
    pipeline_records = build_pipeline_records(limit=200)
    dashboard = get_dashboard_summary()
    current_flow = FLOW_DEFINITIONS[st.session_state.selected_flow_id]
    triage_state = st.session_state.triage_state
    current_node = get_current_node(triage_state, current_flow)
    current_step = current_node["code"] if current_node else "Concluido"
    task_rows = build_recent_task_rows(pipeline_records, limit=3)
    stage_totals = count_pipeline_by_stage(pipeline_records)
    stage_cards_markup = "".join(
        (
            f"<div class='pre-stage-card {tone}'>"
            f"<strong>{stage_totals[column_id]}</strong>"
            f"<h4>{label}</h4>"
            f"<span>{subtitle}</span>"
            "</div>"
        )
        for column_id, label, subtitle, tone in PIPELINE_COLUMNS
    )

    with st.expander("Resumo do fluxo e da operação", expanded=False):
        next_priority = task_rows[0]["title"] if task_rows else "Sem fila critica imediata."
        st.markdown(
            (
                "<div class='law-pulse-inline'>"
                f"<span><strong>{current_flow['name']}</strong> benefício selecionado</span>"
                f"<span><strong>{current_step}</strong> pergunta atual</span>"
                f"<span><strong>{next((int(row['total']) for row in dashboard['by_status'] if row['status'] == 'aprovado'), 0)}</strong> casos qualificados</span>"
                f"<span><strong>Próxima:</strong> {next_priority}</span>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='pre-stage-strip'>{stage_cards_markup}</div>", unsafe_allow_html=True)
    render_operational_workspace()


def render_contracts_view() -> None:
    render_shell_page_header(
        "Contratos",
        "Fila de contratos pronta para validacao, assinatura e avancos comerciais do escritorio.",
    )
    all_rows = get_all_attendance_rows(limit=200)
    contract_candidates = [
        row
        for row in all_rows
        if normalize_triage_status(str(row["status"])) in {"aprovado", "revisao"}
        and str(row["crm_stage"] or "triagem") not in {"encerrado", "perdido"}
    ]
    blocked_cases = [
        (row, get_contract_block_reasons(row))
        for row in contract_candidates
        if get_contract_block_reasons(row)
    ]
    rows = [row for row in contract_candidates if not get_contract_block_reasons(row)]

    with st.expander(
        f"Casos bloqueados para contratação ({len(blocked_cases)})",
        expanded=bool(blocked_cases) and not rows,
        icon=":material/lock:",
    ):
        if not blocked_cases:
            st.success("Nenhum caso está retido pelos controles de triagem, conflito ou privacidade.")
        for blocked_row, reasons in blocked_cases:
            blocker_left, blocker_right = st.columns([1.55, 0.45], gap="medium")
            with blocker_left:
                st.markdown(
                    f"**#{blocked_row['id']} · {blocked_row['lead_name']}** — {blocked_row['flow_name']}  \n"
                    f"Bloqueios: {'; '.join(reasons)}.  \n"
                    f"Próxima ação: {blocked_row['next_action'] or 'definir providência e responsável no CRM'}."
                )
            with blocker_right:
                if st.button(
                    f"Regularizar no CRM #{blocked_row['id']}",
                    key=f"contract_resolve_{blocked_row['id']}",
                    icon=":material/rule:",
                    use_container_width=True,
                ):
                    st.session_state.selected_crm_case_id = int(blocked_row["id"])
                    st.session_state.pending_crm_case_id = int(blocked_row["id"])
                    st.session_state.pending_crm_section = "caso"
                    set_current_view("crm")
                    st.rerun()
            st.divider()

    if not rows:
        st.markdown(
            (
                "<div class='pre-empty-state'>Nenhuma minuta está liberada. "
                "Regularize a triagem, a checagem de conflito e o aviso de privacidade "
                "nos casos listados acima.</div>"
            ),
            unsafe_allow_html=True,
        )
        return

    if not st.session_state.selected_contract_attendance_id:
        st.session_state.selected_contract_attendance_id = int(rows[0]["id"])

    approved_records = [
        record for record in build_pipeline_records(limit=200)
        if int(record["id"]) in {int(row["id"]) for row in rows}
    ]
    total_fee_potential = 0.0
    avg_fee_potential = 0.0
    ready_document_total = 0
    for record in approved_records:
        fee_percentage = resolve_fee_percentage(str(record["flow_name"]), st.session_state.office_settings) / 100
        total_fee_potential += float(record.get("estimated_total_value") or 0.0) * fee_percentage
        if int(record["required_total"]) > 0 and int(record["validated_total"]) >= int(record["required_total"]):
            ready_document_total += 1
    if approved_records:
        avg_fee_potential = total_fee_potential / len(approved_records)

    contract_metrics = [
        {"label": "Minutas liberadas", "value": len(rows), "tone": "soft-green"},
        {"label": "Casos bloqueados", "value": len(blocked_cases), "tone": "soft-red"},
        {"label": "Honorarios potenciais", "value": format_currency(total_fee_potential), "tone": "soft-purple"},
        {"label": "Dossies completos", "value": ready_document_total, "tone": "soft-yellow"},
    ]
    metric_markup = "".join(
        (
            f"<div class='pre-metric-card {metric['tone']}'>"
            f"<h3>{metric['value']}</h3>"
            f"<p>{metric['label']}</p>"
            "</div>"
        )
        for metric in contract_metrics
    )
    st.markdown(f"<div class='pre-metric-grid'>{metric_markup}</div>", unsafe_allow_html=True)

    if st.session_state.selected_contract_attendance_id not in [int(row["id"]) for row in rows]:
        st.session_state.selected_contract_attendance_id = int(rows[0]["id"])

    details = get_attendance_details(int(st.session_state.selected_contract_attendance_id))
    if details is None:
        st.info("Selecione um contrato para visualizar.")
        return

    documents = list_attendance_documents(int(details["id"]))
    required_total, validated_total = get_document_progress(documents)
    fee_percentage = resolve_fee_percentage(str(details["flow_name"]), st.session_state.office_settings)
    tutorial_video_url = st.session_state.office_settings.get("tutorial_video_url", "")

    spotlight_cols = st.columns([1.08, 0.92], gap="large")
    with spotlight_cols[0]:
        st.markdown(
            (
                "<div class='pre-spotlight'>"
                "<div class='eyebrow'>Esteira de assinatura</div>"
                "<h3>Contrato bom e contrato enviado na hora certa.</h3>"
                f"<p>{AGENT_NAME} deixa a fila de honorarios sob controle: caso aprovado, dossie acompanhado e minuta pronta para a etapa de assinatura e onboarding do cliente.</p>"
                "<div class='pre-inline-stats'>"
                f"<div class='pre-inline-stat'><strong>{len(rows)}</strong><span>casos aptos</span></div>"
                f"<div class='pre-inline-stat'><strong>{ready_document_total}</strong><span>dossies completos</span></div>"
                f"<div class='pre-inline-stat'><strong>{format_currency(total_fee_potential)}</strong><span>potencial monitorado</span></div>"
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
    with spotlight_cols[1]:
        st.markdown(
            (
                "<div class='pre-card'>"
                "<h3 class='pre-section-title'>Preparacao de assinatura</h3>"
                "<div class='pre-meta-list'>"
                f"<div class='pre-meta-item'><strong>Cliente em foco</strong><span>#{details['id']} | {details['lead_name']}</span></div>"
                f"<div class='pre-meta-item'><strong>Fluxo aprovado</strong><span>{details['flow_name']}</span></div>"
                f"<div class='pre-meta-item'><strong>Honorario contratado</strong><span>{fee_percentage}% sobre o proveito economico do caso.</span></div>"
                f"<div class='pre-meta-item'><strong>Tutorial de assinatura</strong><span>{tutorial_video_url or 'Ainda nao configurado nas preferencias do escritorio.'}</span></div>"
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    left, right = st.columns([0.95, 1.35], gap="large")
    with left:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Fila de contratos</h3>", unsafe_allow_html=True)
        st.caption("Casos aprovados prontos para validacao comercial e envio da minuta.")
        for row in rows:
            selected_class = (
                " selected"
                if int(st.session_state.selected_contract_attendance_id or 0) == int(row["id"])
                else ""
            )
            st.markdown(
                (
                    f"<div class='pre-lead-card{selected_class}'>"
                    f"<h5>#{row['id']} - {row['lead_name']}</h5>"
                    f"<p>{row['flow_name']}</p>"
                    f"<p>{row['result_title']}</p>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            if st.button(
                f"Visualizar contrato #{row['id']}",
                key=f"contract_open_{row['id']}",
                use_container_width=True,
            ):
                st.session_state.selected_contract_attendance_id = int(row["id"])
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown(
            (
                "<div class='pre-focus-hero'>"
                f"<div class='eyebrow'>{details['flow_name']}</div>"
                f"<h3>#{details['id']} | {details['lead_name']}</h3>"
                f"<p>{details['result_title']} | Caso aprovado para contratacao</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-focus-grid'>"
                f"<div class='pre-focus-stat'><strong>{fee_percentage}%</strong><span>Honorario parametrizado</span></div>"
                f"<div class='pre-focus-stat'><strong>{validated_total}/{required_total}</strong><span>Obrigatorios validados</span></div>"
                f"<div class='pre-focus-stat'><strong>{format_currency(details['estimated_total_value']) if details['estimated_total_value'] else '-'}</strong><span>Base economica estimada</span></div>"
                f"<div class='pre-focus-stat'><strong>{details['lead_phone'] or '-'}</strong><span>Contato principal</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-detail-list'>"
                f"<div class='pre-detail-row'><strong>Resumo executivo</strong><span>{details['summary']}</span></div>"
                f"<div class='pre-detail-row'><strong>Proximo passo</strong><span>{details['next_step']}</span></div>"
                f"<div class='pre-detail-row'><strong>Observacoes</strong><span>{details['notes'] or 'Sem observacoes adicionais registradas.'}</span></div>"
                f"<div class='pre-detail-row'><strong>Status documental</strong><span>{validated_total}/{required_total} obrigatorios validados para sustentar a assinatura.</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        action_cols = st.columns(2, gap="small")
        with action_cols[0]:
            if st.button("Abrir no CRM", key="contract_open_crm", use_container_width=True):
                st.session_state.selected_crm_case_id = int(details["id"])
                set_current_view("crm")
                st.rerun()
        with action_cols[1]:
            if st.button("Abrir workspace", key="contract_open_workspace", use_container_width=True):
                st.session_state.selected_attendance_id = int(details["id"])
                st.session_state.selected_document_attendance_id = int(details["id"])
                set_current_view("leads")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='pre-card' style='margin-top:1rem;'>", unsafe_allow_html=True)
        render_panel_header(
            "Contrato",
            f"#{details['id']} - {details['lead_name']}",
            "Minuta automatica de honorarios com base nas configuracoes do escritorio.",
        )
        contract_block_reasons = get_contract_block_reasons(details)
        if contract_block_reasons:
            st.error(
                f"Minuta bloqueada: {'; '.join(contract_block_reasons)}. Regularize o caso no CRM antes de avançar."
            )
        else:
            flow = {"name": details["flow_name"]}
            form_data = {"lead_name": details["lead_name"]}
            render_contract_preview(flow, form_data)
        st.markdown("</div>", unsafe_allow_html=True)


def render_settings_view() -> None:
    settings = st.session_state.office_settings
    render_shell_page_header("Configuracoes do Escritorio", f"{AGENT_NAME} aplicada ao escritorio com honorarios e materiais de assinatura.")

    st.markdown("<div class='pre-two-column'>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Seus dados</h3>", unsafe_allow_html=True)
        responsavel_nome = st.text_input("Nome completo", value=settings.get("responsavel_nome", ""), key="settings_responsavel_nome")
        responsavel_email = st.text_input("Email", value=settings.get("responsavel_email", ""), key="settings_responsavel_email")
        responsavel_whatsapp = st.text_input("WhatsApp", value=settings.get("responsavel_whatsapp", ""), key="settings_responsavel_whatsapp")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='pre-card' style='margin-top:1rem;'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Dados do escritorio</h3>", unsafe_allow_html=True)
        office_name = st.text_input("Nome do Escritorio", value=settings.get("office_name", ""), key="settings_office_name")
        oab = st.text_input("OAB", value=settings.get("oab", ""), key="settings_oab")
        tutorial_video_url = st.text_input(
            "Video tutorial de assinatura",
            value=settings.get("tutorial_video_url", ""),
            key="settings_tutorial_video_url",
            placeholder="https://storage.exemplo.com/tutorial-assinatura.mp4",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Honorarios por beneficio (%)</h3>", unsafe_allow_html=True)
        fee_percentages = dict(settings.get("fee_percentages", {}))
        fee_cols = st.columns(2, gap="medium")
        fee_keys = list(fee_percentages.keys())
        for index, key in enumerate(fee_keys):
            with fee_cols[index % 2]:
                fee_percentages[key] = st.number_input(
                    key,
                    min_value=0,
                    max_value=100,
                    value=int(fee_percentages.get(key, 30)),
                    key=f"fee_{key}",
                )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='pre-card' style='margin-top:1rem;'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Resumo operacional</h3>", unsafe_allow_html=True)
        st.markdown(
            (
                f"<p><strong>Escritorio:</strong> {office_name or 'Nao configurado'}</p>"
                f"<p><strong>Responsavel:</strong> {responsavel_nome or 'Nao configurado'}</p>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Salvar Configuracoes", key="save_settings", use_container_width=False):
        updated_settings = {
            "responsavel_nome": responsavel_nome.strip(),
            "responsavel_email": responsavel_email.strip(),
            "responsavel_whatsapp": responsavel_whatsapp.strip(),
            "plano": settings.get("plano", "Essencial"),
            "office_name": office_name.strip(),
            "oab": oab.strip(),
            "tutorial_video_url": tutorial_video_url.strip(),
            "fee_percentages": fee_percentages,
        }
        save_office_settings(updated_settings)
        st.session_state.office_settings = load_office_settings()
        st.success("Configuracoes salvas com sucesso.")


def build_fee_contract_preview(flow_name: str, lead_name: str) -> str:
    office_settings = st.session_state.get("office_settings", load_office_settings())
    return build_contract_preview(flow_name, lead_name, office_settings)


def render_contract_preview(flow: dict[str, Any], form_data: dict[str, Any]) -> None:
    contract_text = build_fee_contract_preview(flow["name"], form_data["lead_name"])
    render_panel_header(
        "Honorarios",
        "Contrato padrao de honorarios advocaticios",
        "Minuta inicial sugerida para leads aprovados no filtro.",
    )
    st.code(contract_text.strip(), language="text")


def clamp_benefit_value(value: float) -> float:
    return clamp_maternity_benefit_value(value)


def render_salario_maternidade_calculator() -> None:
    render_panel_header("Calculo", "Calculadora de Salario-Maternidade", "Estimativa inicial com base nas regras parametrizadas para 2026.")

    category = st.selectbox(
        "Categoria da segurada",
        ["CLT", "MEI", "Autonoma / Facultativa", "Desempregada"],
        key="sm_category",
    )

    monthly_value = SALARIO_MINIMO_2026
    note = ""

    if category == "CLT":
        remuneration_type = st.radio(
            "Tipo de remuneracao",
            ["Salario fixo", "Remuneracao variavel"],
            key="sm_clt_type",
            horizontal=True,
        )
        if remuneration_type == "Salario fixo":
            salary = st.number_input(
                "Ultimo salario de contribuicao",
                min_value=0.0,
                step=100.0,
                value=SALARIO_MINIMO_2026,
                key="sm_clt_fixed_salary",
            )
            monthly_value = clamp_benefit_value(salary)
            note = "Para CLT com salario fixo, a estimativa usa o ultimo salario de contribuicao."
        else:
            salaries = []
            cols = st.columns(3)
            for index in range(6):
                with cols[index % 3]:
                    salaries.append(
                        st.number_input(
                            f"Salario {index + 1}",
                            min_value=0.0,
                            step=100.0,
                            value=SALARIO_MINIMO_2026,
                            key=f"sm_clt_var_{index}",
                        )
                    )
            monthly_value = clamp_benefit_value(sum(salaries) / 6 if salaries else SALARIO_MINIMO_2026)
            note = "Para CLT com remuneracao variavel, a estimativa usa a media dos 6 ultimos salarios."

    elif category == "MEI":
        mei_mode = st.radio(
            "Tipo de contribuicao",
            ["MEI padrao", "MEI com complementacao de 20%"],
            key="sm_mei_mode",
            horizontal=True,
        )
        if mei_mode == "MEI padrao":
            monthly_value = SALARIO_MINIMO_2026
            note = "Para MEI padrao, a estimativa considera o salario minimo de 2026."
        else:
            contribution_count = st.slider(
                "Quantidade de contribuicoes consideradas",
                min_value=1,
                max_value=12,
                value=12,
                key="sm_mei_count",
            )
            values = []
            cols = st.columns(3)
            for index in range(contribution_count):
                with cols[index % 3]:
                    values.append(
                        st.number_input(
                            f"Contribuicao {index + 1}",
                            min_value=0.0,
                            step=100.0,
                            value=SALARIO_MINIMO_2026,
                            key=f"sm_mei_comp_{index}",
                        )
                    )
            monthly_value = clamp_benefit_value(sum(values) / len(values))
            note = "Para MEI com complementacao, a estimativa segue a media das contribuicoes informadas."

    elif category == "Autonoma / Facultativa":
        contribution_count = st.slider(
            "Quantidade de contribuicoes consideradas",
            min_value=1,
            max_value=12,
            value=12,
            key="sm_aut_count",
        )
        values = []
        cols = st.columns(3)
        for index in range(contribution_count):
            with cols[index % 3]:
                values.append(
                    st.number_input(
                        f"Contribuicao {index + 1}",
                        min_value=0.0,
                        step=100.0,
                        value=SALARIO_MINIMO_2026,
                        key=f"sm_aut_{index}",
                    )
                )
        monthly_value = clamp_benefit_value(sum(values) / len(values))
        note = (
            "Para autonoma ou facultativa, a estimativa usa a media das contribuicoes informadas, "
            "respeitando minimo e teto."
        )

    elif category == "Desempregada":
        contribution_count = st.slider(
            "Quantidade de contribuicoes consideradas",
            min_value=1,
            max_value=12,
            value=12,
            key="sm_des_count",
        )
        values = []
        cols = st.columns(3)
        for index in range(contribution_count):
            with cols[index % 3]:
                values.append(
                    st.number_input(
                        f"Contribuicao {index + 1}",
                        min_value=0.0,
                        step=100.0,
                        value=SALARIO_MINIMO_2026,
                        key=f"sm_des_{index}",
                    )
                )
        monthly_value = clamp_benefit_value(sum(values) / len(values))
        note = "Para desempregada, a estimativa usa a media das contribuicoes disponiveis."

    total_benefit = monthly_value * 4
    st.session_state.sm_estimate = {
        "category": category,
        "monthly_value": monthly_value,
        "total_value": total_benefit,
    }
    st.metric("Valor mensal estimado", format_currency(monthly_value))
    st.metric("Total estimado em 120 dias", format_currency(total_benefit))
    st.info(note)
    st.caption(
        f"Referencia 2026: minimo {format_currency(SALARIO_MINIMO_2026)} | "
        f"teto {format_currency(TETO_INSS_2026)}"
    )


def render_question_panel(flow: dict[str, Any], form_data: dict[str, Any]) -> None:
    triage_state = st.session_state.triage_state
    node = get_current_node(triage_state, flow)

    if node is None:
        render_result_panel(flow, form_data)
        return

    render_panel_header("Fluxo", "Triagem guiada", "Conducao sequencial da analise inicial do lead.")
    st.caption(f"{flow['name']} | {node['code']} | Pergunta {len(triage_state.history) + 1}")
    st.markdown(f"### {node['title']}")
    st.write(node.get("help", ""))

    option_cols = st.columns(len(node["options"]))
    for col, option in zip(option_cols, node["options"]):
        with col:
            st.markdown(" ")
            if st.button(
                option["label"],
                key=f"{node['id']}_{option['label']}",
                use_container_width=True,
                help=option["description"],
                type="primary",
            ):
                new_state, _ = answer_current_question(triage_state, flow, option["label"])
                st.session_state.triage_state = new_state
                st.session_state.saved_result_id = None
                st.rerun()
            st.caption(option["description"])

    controls = st.columns([1, 1, 4])
    with controls[0]:
        if st.button("Voltar", disabled=not triage_state.history, use_container_width=True, type="secondary"):
            st.session_state.triage_state = step_back(triage_state, flow)
            st.session_state.saved_result_id = None
            st.rerun()
    with controls[1]:
        if st.button("Reiniciar fluxo", use_container_width=True, type="secondary"):
            reset_triage(flow["id"])
            st.rerun()


def render_result_panel(flow: dict[str, Any], form_data: dict[str, Any]) -> None:
    triage_state = st.session_state.triage_state
    result = get_result(triage_state, flow)
    if result is None:
        st.info("Selecione um fluxo e inicie a triagem.")
        return

    label, background, color = STATUS_STYLE[result["status"]]
    render_panel_header("Encerramento", "Resultado final", "Classificacao final da triagem e proximo encaminhamento sugerido.")
    st.markdown(
        (
            f"<div class='status-chip' style='background:{background}; color:{color};'>{label}</div>"
            f"<div class='surface-card'><h3>{result['title']}</h3>"
            f"<p><strong>Resumo:</strong> {result['summary']}</p>"
            f"<p><strong>Proximo passo:</strong> {result['next_step']}</p>"
            f"<p><strong>Lead:</strong> {form_data['lead_name'] or 'Nao informado'}"
            f" | <strong>Telefone:</strong> {form_data['lead_phone'] or 'Nao informado'}</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    sm_estimate = st.session_state.sm_estimate if flow["id"] == "salarioMaternidade" else None
    if sm_estimate:
        st.markdown(
            (
                "<div class='surface-card'>"
                "<h4>Estimativa registrada</h4>"
                f"<p><strong>Categoria:</strong> {sm_estimate['category']}</p>"
                f"<p><strong>Valor mensal estimado:</strong> {format_currency(sm_estimate['monthly_value'])}</p>"
                f"<p><strong>Total estimado em 120 dias:</strong> {format_currency(sm_estimate['total_value'])}</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    if result["status"] == "aprovado":
        st.info("A minuta ficará disponível no CRM após a checagem de conflito ser liberada.")

    col1, col2 = st.columns([1.3, 1])
    with col1:
        if st.button("Salvar atendimento", use_container_width=True):
            if not all([form_data["lead_name"], form_data["lead_phone"], form_data["lead_email"], form_data["lead_source"]]):
                st.error("Informe nome, telefone, e-mail e origem do lead antes de salvar.")
                return
            if not form_data["privacy_notice_acknowledged"]:
                st.error("Registre a ciência do aviso de privacidade antes de salvar o atendimento.")
                return
            if flow["id"] == "aposentadoria":
                retirement_profile = form_data.get("triage_profile", {})
                if not retirement_profile.get("birth_date") or not retirement_profile.get("objective"):
                    st.error(
                        "Na aposentadoria, informe a data de nascimento e o objetivo previdenciário antes de salvar."
                    )
                    return
            saved_id = save_attendance(
                lead_name=form_data["lead_name"] or "Lead sem nome",
                lead_phone=form_data["lead_phone"],
                lead_email=form_data["lead_email"],
                lead_source=form_data["lead_source"],
                flow_id=flow["id"],
                flow_name=flow["name"],
                status=result["status"],
                result_title=result["title"],
                summary=result["summary"],
                next_step=result["next_step"],
                notes=form_data["lead_notes"],
                history=triage_state.history,
                benefit_category=sm_estimate["category"] if sm_estimate else None,
                estimated_monthly_value=sm_estimate["monthly_value"] if sm_estimate else None,
                estimated_total_value=sm_estimate["total_value"] if sm_estimate else None,
                privacy_notice_acknowledged=form_data["privacy_notice_acknowledged"],
                privacy_legal_basis=form_data["privacy_legal_basis"],
                triage_profile=form_data.get("triage_profile", {}),
            )
            st.session_state.saved_result_id = saved_id
            st.session_state.selected_attendance_id = saved_id
            st.session_state.selected_document_attendance_id = saved_id
            if result["status"] == "aprovado":
                automation_result = receive_and_process_event(
                    event_type="lead.qualified",
                    source="triagem_crm",
                    attendance_id=saved_id,
                    external_reference=f"triagem-{saved_id}",
                    payload={
                        "summary": result["summary"],
                        "assigned_to": "Equipe de triagem",
                    },
                )
                if automation_result.status == "concluido":
                    st.session_state.last_automation_notice = (
                        f"Automação concluída: tarefa #{automation_result.task_id} criada no CRM."
                    )
                elif automation_result.status == "falhou":
                    st.session_state.last_automation_notice = (
                        "O atendimento foi salvo, mas a automação ficou registrada com falha para reprocessamento."
                    )
            st.rerun()
    with col2:
        if st.button("Nova triagem", use_container_width=True):
            reset_triage(flow["id"])
            st.rerun()

    if st.session_state.saved_result_id:
        st.success(f"Atendimento salvo com sucesso. Registro #{st.session_state.saved_result_id}.")
        if st.session_state.last_automation_notice:
            st.info(st.session_state.last_automation_notice)
            st.session_state.last_automation_notice = ""
        if result["status"] in {"aprovado", "revisao"}:
            render_document_journey_preview(
                attendance_id=int(st.session_state.saved_result_id),
                flow=flow,
            )
    elif result["status"] in {"aprovado", "revisao"}:
        st.info(
            "Salve o atendimento para abrir o checklist documental estruturado da Fase 2."
        )


def render_document_journey_preview(attendance_id: int, flow: dict[str, Any]) -> None:
    strategy = get_flow_document_strategy(flow["id"])
    documents = list_attendance_documents(attendance_id)
    required_total, validated_total = get_document_progress(documents)
    score = build_document_case_score(documents)

    render_panel_header(
        "Fase 2",
        "Analise documental estruturada",
        "Checklist por beneficio para transformar triagem aprovada em dossie operacional.",
    )
    st.markdown(
        (
            "<div class='surface-card'>"
            f"<p><strong>Foco da fase:</strong> {strategy['analysis_focus']}</p>"
            f"<p><strong>Obrigatorios validados:</strong> {validated_total}/{required_total}</p>"
            f"<p><strong>Documentos no checklist:</strong> {len(documents)} itens "
            f"({strategy['optional_total']} opcionais)</p>"
            f"<p><strong>Score documental inicial:</strong> {score['score']}/100 | {score['label']}</p>"
            "<p><strong>Operacao:</strong> use a aba <em>Analise documental</em> para upload, "
            "classificacao, leitura tecnica e notas por documento.</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    preview_rows = documents[:5]
    if preview_rows:
        for row in preview_rows:
            st.markdown(
                (
                    "<div class='history-item'>"
                    f"<strong>{row['document_name']}</strong><br>"
                    f"{render_document_status_chip(row['status'])}"
                    f"<span class='muted'> {'Obrigatorio' if int(row['required']) == 1 else 'Opcional'}</span>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def render_document_pipeline() -> None:
    render_panel_header(
        "Documentos",
        "Dossie documental",
        "Fase 2 da operacao: checklist, upload local, OCR e validacao criteriosa por beneficio.",
    )

    summary = get_document_pipeline_summary()
    document_metrics = [
        {"label": "Documentos mapeados", "value": int(summary["total_documents"]), "tone": "soft-neutral"},
        {"label": "Obrigatorios", "value": int(summary["required_documents"]), "tone": "soft-blue"},
        {"label": "Extraidos", "value": int(summary["processed_documents"]), "tone": "soft-green"},
        {"label": "Pendentes", "value": int(summary["pending_documents"]), "tone": "soft-orange"},
    ]
    metric_markup = "".join(
        (
            f"<div class='pre-metric-card {metric['tone']}'>"
            f"<h3>{metric['value']}</h3>"
            f"<p>{metric['label']}</p>"
            "</div>"
        )
        for metric in document_metrics
    )
    st.markdown(f"<div class='pre-metric-grid'>{metric_markup}</div>", unsafe_allow_html=True)

    ocr_capabilities = get_ocr_capabilities()
    if ocr_capabilities["neural_ready"]:
        fallback_label = (
            "fallback Tesseract ativo"
            if ocr_capabilities["tesseract_ready"]
            else "fallback Tesseract opcional"
        )
        st.success(
            "OCR neural local ativo · PyMuPDF + RapidOCR/ONNX · "
            f"{fallback_label} · nenhum documento é enviado para a nuvem."
        )
    else:
        st.error(
            "OCR neural incompleto. Reinstale as dependências de requirements.txt antes de processar documentos."
        )
    with st.expander("Diagnóstico do motor documental", expanded=False):
        package_summary = " · ".join(
            f"{name} {package_version}"
            for name, package_version in ocr_capabilities["packages"].items()
        )
        st.caption(package_summary)
        st.caption(
            f"PDF escaneado: {ocr_capabilities['pdf_ocr_dpi']} DPI · "
            f"limite de {ocr_capabilities['max_ocr_pages']} páginas OCR por arquivo · "
            "processamento local com revisão humana obrigatória."
        )

    status_choice = st.selectbox(
        "Fila documental",
        ["Todos", "aprovado", "revisao"],
        format_func=lambda value: {
            "Todos": "Todos os atendimentos",
            "aprovado": "Apenas qualificados",
            "revisao": "Apenas em revisao",
        }[value],
        key="document_pipeline_filter",
    )

    queue_rows = list_document_pipeline_attendances(status_filter=status_choice, limit=100)
    queue_ids = [int(row["id"]) for row in queue_rows]
    if queue_ids and st.session_state.selected_document_attendance_id not in queue_ids:
        st.session_state.selected_document_attendance_id = queue_ids[0]
    left, right = st.columns([0.72, 1.58], gap="medium")

    with left:
        with st.container(border=True):
            st.markdown("<h3 class='pre-section-title'>Fila de dossiês</h3>", unsafe_allow_html=True)
            st.caption("Escolha um caso para leitura técnica e fechamento documental.")
            if not queue_rows:
                st.info("Ainda não há atendimentos prontos para a fase documental.")
            else:
                selected_queue_id = st.selectbox(
                    "Caso documental",
                    options=queue_ids,
                    format_func=lambda attendance_id: next(
                        (
                            f"#{row['id']} | {row['lead_name']} | {row['flow_name']}"
                            for row in queue_rows
                            if int(row["id"]) == int(attendance_id)
                        ),
                        f"Caso #{attendance_id}",
                    ),
                    key="selected_document_attendance_id",
                    label_visibility="collapsed",
                )
                selected_row = next(
                    row for row in queue_rows if int(row["id"]) == int(selected_queue_id)
                )
                progress = (
                    f"{int(selected_row['validated_total'] or 0)}/{int(selected_row['required_total'] or 0)} obrigatórios"
                    if int(selected_row["required_total"] or 0) > 0
                    else "Checklist aguardando inicialização"
                )
                triage_status = (
                    "Em revisão" if selected_row["triage_bucket"] == "revisao" else "Qualificado"
                )
                st.markdown(
                    (
                        "<div class='pre-lead-card selected'>"
                        f"<h5>#{selected_row['id']} - {selected_row['lead_name']}</h5>"
                        f"<p>{selected_row['flow_name']}</p>"
                        f"<p>{progress}</p>"
                        f"<p>{triage_status} | Ilegíveis: {int(selected_row['illegible_total'] or 0)} | Inconsistentes: {int(selected_row['inconsistent_total'] or 0)}</p>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

    with right:
        if not st.session_state.selected_document_attendance_id:
            st.info("Selecione um atendimento para operar o checklist documental.")
            return

        details = get_attendance_details(int(st.session_state.selected_document_attendance_id))
        if details is None:
            st.warning("Atendimento documental nao encontrado.")
            return

        strategy = get_flow_document_strategy(details["flow_id"])
        documents = list_attendance_documents(int(details["id"]))
        doc_map = {
            item["code"]: item
            for item in strategy["documents"]
        }
        required_total, validated_total = get_document_progress(documents)
        score = build_document_case_score(documents)
        normalized_status = normalize_triage_status(str(details["status"]))
        status_label, status_background, status_color = STATUS_STYLE.get(
            normalized_status,
            ("Status", "#f4f4f4", "#555555"),
        )
        illegible_total = len([document for document in documents if document["status"] == "ilegivel"])
        inconsistent_total = len([document for document in documents if document["status"] == "inconsistente"])
        focus_gap_text = ", ".join(score["critical_gaps"][:3]) if score["critical_gaps"] else "Nenhuma pendencia critica nos obrigatorios."

        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown(
            (
                "<div class='pre-focus-hero'>"
                f"<div class='eyebrow'>{details['flow_name']}</div>"
                f"<h3>#{details['id']} | {details['lead_name']}</h3>"
                f"<p>{status_label} | Dossie em consolidacao documental</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-focus-grid'>"
                f"<div class='pre-focus-stat'><strong>{validated_total}/{required_total}</strong><span>Obrigatorios validados</span></div>"
                f"<div class='pre-focus-stat'><strong>{score['score']}/100</strong><span>Score do dossie</span></div>"
                f"<div class='pre-focus-stat'><strong>{score['processed']}</strong><span>Itens com leitura extraida</span></div>"
                f"<div class='pre-focus-stat'><strong>{illegible_total + inconsistent_total}</strong><span>Alertas criticos de consistencia</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='status-chip' style='background:{status_background}; color:{status_color};'>{status_label}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-detail-list'>"
                f"<div class='pre-detail-row'><strong>Foco documental</strong><span>{strategy['analysis_focus']}</span></div>"
                f"<div class='pre-detail-row'><strong>Risco atual</strong><span>{focus_gap_text}</span></div>"
                f"<div class='pre-detail-row'><strong>Proximo passo juridico</strong><span>{details['next_step']}</span></div>"
                f"<div class='pre-detail-row'><strong>Notas da triagem</strong><span>{details['notes'] or 'Sem observacoes adicionais registradas.'}</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='pre-card' style='margin-top:1rem;'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Checklist do caso</h3>", unsafe_allow_html=True)
        if not documents:
            st.info("Esse atendimento ainda nao possui checklist documental.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        for row in documents:
            doc_rule = doc_map.get(row["document_code"], {})
            uploaded_files = json.loads(row["uploaded_files_json"] or "[]")
            critical_fields = json.loads(row["critical_fields_json"] or "[]")
            extracted_data = json.loads(row["extracted_data_json"] or "{}")
            required_label = "Obrigatorio" if int(row["required"]) == 1 else "Opcional"
            expander_label = (
                f"{required_label} | {row['document_name']} | {format_document_status(row['status'])}"
            )
            with st.expander(expander_label):
                st.markdown(render_document_status_chip(row["status"]), unsafe_allow_html=True)
                st.write(doc_rule.get("analysis_focus", "Sem foco tecnico adicional configurado."))
                if critical_fields:
                    st.caption(f"Campos criticos: {', '.join(critical_fields)}")

                if uploaded_files:
                    st.caption("Arquivos ja vinculados:")
                    for file_path in uploaded_files:
                        st.markdown(f"- `{file_path}`")
                else:
                    st.caption("Nenhum arquivo salvo ainda para este item.")

                extraction_cols = st.columns(3)
                extraction_cols[0].markdown(
                    render_extraction_status_chip(row["extraction_status"] or "nao_processado"),
                    unsafe_allow_html=True,
                )
                extraction_cols[1].metric(
                    "Confianca",
                    f"{int((row['extraction_confidence'] or 0) * 100)}%",
                )
                extraction_cols[2].metric(
                    "Fonte",
                    row["source_type"] or "Nao identificada",
                )

                if row["technical_notes"]:
                    st.caption(f"Leitura tecnica: {row['technical_notes']}")
                if row["extraction_status"] in {"erro", "dependencia_ausente", "sem_texto"}:
                    st.error(
                        "A leitura automática não produziu texto confiável. Confira o arquivo e o diagnóstico técnico."
                    )
                elif row["raw_text"] and float(row["extraction_confidence"] or 0) < 0.70:
                    st.warning(
                        "Baixa confiança: não valide este documento sem comparação visual com o original."
                    )

                if extracted_data:
                    st.markdown("**Campos detectados**")
                    for field_name, field_value in extracted_data.items():
                        st.markdown(
                            f"- `{field_name}`: {field_value or 'Nao identificado'}"
                        )

                if row["raw_text"]:
                    st.text_area(
                        "Texto extraido",
                        value=row["raw_text"][:5000],
                        height=180,
                        disabled=True,
                        key=f"raw_text_preview_{row['id']}",
                    )

                new_status = st.selectbox(
                    "Status documental",
                    list(DOCUMENT_STATUS_STYLE.keys()),
                    index=list(DOCUMENT_STATUS_STYLE.keys()).index(row["status"]),
                    format_func=format_document_status,
                    key=f"document_status_{row['id']}",
                )
                notes_value = st.text_area(
                    "Notas internas",
                    value=row["notes"] or "",
                    height=90,
                    key=f"document_notes_{row['id']}",
                )
                uploaded_batch = st.file_uploader(
                    "Anexar PDF ou imagem",
                    type=["pdf", "png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"],
                    accept_multiple_files=True,
                    key=f"document_upload_{row['id']}",
                )

                button_cols = st.columns(2)
                with button_cols[0]:
                    if st.button(
                        "Salvar documento",
                        key=f"save_document_{row['id']}",
                        use_container_width=True,
                    ):
                        stored_files = persist_document_uploads(
                            attendance_id=int(details["id"]),
                            document_code=str(row["document_code"]),
                            current_files=uploaded_files,
                            uploaded_batch=uploaded_batch,
                        )
                        update_attendance_document(
                            document_id=int(row["id"]),
                            status=new_status,
                            notes=notes_value.strip(),
                            uploaded_files=stored_files,
                        )
                        st.success("Documento atualizado com sucesso.")
                        st.rerun()

                with button_cols[1]:
                    if st.button(
                        "Executar leitura tecnica",
                        key=f"process_document_{row['id']}",
                        use_container_width=True,
                    ):
                        stored_files = persist_document_uploads(
                            attendance_id=int(details["id"]),
                            document_code=str(row["document_code"]),
                            current_files=uploaded_files,
                            uploaded_batch=uploaded_batch,
                        )
                        with st.spinner(
                            "Lendo texto nativo e aplicando OCR neural somente nas páginas necessárias..."
                        ):
                            analysis = analyze_document_bundle(
                                document_code=str(row["document_code"]),
                                uploaded_files=stored_files,
                                critical_fields=critical_fields,
                            )
                        auto_status = new_status
                        if stored_files and auto_status == "pendente":
                            auto_status = "em_validacao"
                        update_attendance_document(
                            document_id=int(row["id"]),
                            status=auto_status,
                            notes=notes_value.strip(),
                            uploaded_files=stored_files,
                            raw_text=analysis["raw_text"],
                            extracted_data=analysis["extracted_data"],
                            source_type=analysis["source_type"],
                            extraction_status=analysis["extraction_status"],
                            extraction_confidence=float(analysis["extraction_confidence"]),
                            technical_notes=analysis["technical_notes"],
                        )
                        st.success("Leitura tecnica executada.")
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_attendance_consultation() -> None:
    render_panel_header(
        "Consulta",
        "Consulta analitica da carteira",
        "Leitura consolidada dos registros salvos com filtros, performance por fluxo e visao aprofundada do caso.",
    )

    dashboard = get_dashboard_summary()
    qualified_total = next((row["total"] for row in dashboard["by_status"] if row["status"] == "aprovado"), 0)
    revision_total = next((row["total"] for row in dashboard["by_status"] if row["status"] == "revisao"), 0)
    disqualified_total = next((row["total"] for row in dashboard["by_status"] if row["status"] == "desqualificado"), 0)
    source_df = build_source_breakdown_dataframe(dashboard)
    activity_df = build_recent_activity_dataframe(dashboard)

    consultation_metrics = [
        {"label": "Total de atendimentos", "value": int(dashboard["total"]), "tone": "soft-neutral"},
        {"label": "Qualificados", "value": int(qualified_total), "tone": "soft-green"},
        {"label": "Em revisao", "value": int(revision_total), "tone": "soft-blue"},
        {"label": "Desqualificados", "value": int(disqualified_total), "tone": "soft-orange"},
    ]
    metric_markup = "".join(
        (
            f"<div class='pre-metric-card {metric['tone']}'>"
            f"<h3>{metric['value']}</h3>"
            f"<p>{metric['label']}</p>"
            "</div>"
        )
        for metric in consultation_metrics
    )
    st.markdown(f"<div class='pre-metric-grid'>{metric_markup}</div>", unsafe_allow_html=True)

    chart_left, chart_right = st.columns(2, gap="large")
    with chart_left:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Atendimentos por fluxo</h3>", unsafe_allow_html=True)
        st.caption("Volume e distribuicao atual das teses previdenciarias monitoradas.")
        if dashboard["by_flow"]:
            flow_chart_data = [
                {"Fluxo": row["flow_name"], "Total": int(row["total"])}
                for row in dashboard["by_flow"]
            ]
            st.bar_chart(flow_chart_data, x="Fluxo", y="Total", horizontal=True)
        else:
            st.info("Sem dados suficientes para o grafico por fluxo.")
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_right:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Conversao e evolucao</h3>", unsafe_allow_html=True)
        st.caption("Leitura simultanea do historico recente e da qualidade da carteira por fluxo.")
        if not source_df.empty:
            st.bar_chart(
                source_df,
                x="Fonte",
                y=["Qualificados", "Em revisao", "Desqualificados"],
                horizontal=True,
            )
        elif activity_df.empty:
            st.info("Ainda nao ha dados suficientes para a conversao por fluxo.")

        if not activity_df.empty:
            st.line_chart(activity_df, x="Dia", y="Casos")
        else:
            st.info("Sem dados suficientes para a evolucao diaria.")
        st.markdown("</div>", unsafe_allow_html=True)

    filter_col1, filter_col2, filter_col3 = st.columns([1.6, 1, 1])
    with filter_col1:
        lead_query = st.text_input(
            "Buscar por nome ou telefone",
            key="consult_lead_query",
            placeholder="Ex.: Maria ou 1199999",
        ).strip()
    with filter_col2:
        flow_name = st.selectbox(
            "Fluxo",
            ["Todos", *[flow["name"] for flow in FLOW_DEFINITIONS.values()]],
            key="consult_flow_name",
        )
    with filter_col3:
        status_label_map = {"Todos": "Todos", "Qualificado": "aprovado", "Em revisao": "revisao", "Desqualificado": "desqualificado"}
        status_label = st.selectbox("Status", list(status_label_map.keys()), key="consult_status")

    rows = search_attendances(
        lead_query=lead_query,
        flow_name=flow_name,
        status=status_label_map[status_label],
        limit=100,
    )

    left, right = st.columns([1.1, 1.4], gap="large")
    with left:
        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Carteira filtrada</h3>", unsafe_allow_html=True)
        st.caption("Use os filtros acima para montar uma mesa cirurgica dos registros salvos.")
        if not rows:
            st.info("Nenhum atendimento encontrado com esses filtros.")
        else:
            for row in rows:
                label, background, color = STATUS_STYLE.get(row["status"], ("Status", "#f4f4f4", "#555555"))
                selected_class = (
                    " selected"
                    if int(st.session_state.selected_attendance_id or 0) == int(row["id"])
                    else ""
                )
                st.markdown(
                    (
                        f"<div class='pre-lead-card{selected_class}'>"
                        f"<h5>#{row['id']} - {row['lead_name']}</h5>"
                        f"<p>{row['flow_name']} | {row['created_at']}</p>"
                        f"<p><span class='status-chip' style='background:{background}; color:{color};'>{label}</span></p>"
                        f"<p>{row['result_title']}</p>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
                if st.button(f"Ler caso #{row['id']}", key=f"open_attendance_{row['id']}", use_container_width=True):
                    st.session_state.selected_attendance_id = int(row["id"])
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        if not st.session_state.selected_attendance_id and rows:
            st.session_state.selected_attendance_id = int(rows[0]["id"])

        if not st.session_state.selected_attendance_id:
            st.info("Selecione um atendimento para ver os detalhes.")
            return

        details = get_attendance_details(int(st.session_state.selected_attendance_id))
        if details is None:
            st.warning("Atendimento nao encontrado.")
            return

        label, background, color = STATUS_STYLE.get(details["status"], ("Status", "#f4f4f4", "#555555"))
        documents = list_attendance_documents(int(details["id"]))
        required_total, validated_total = get_document_progress(documents)
        score = build_document_case_score(documents)
        focus_benefit = details["benefit_category"] or details["flow_name"]

        st.markdown("<div class='pre-card'>", unsafe_allow_html=True)
        st.markdown(
            (
                "<div class='pre-focus-hero'>"
                f"<div class='eyebrow'>{details['flow_name']}</div>"
                f"<h3>#{details['id']} | {details['lead_name']}</h3>"
                f"<p>{details['result_title']} | {label}</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-focus-grid'>"
                f"<div class='pre-focus-stat'><strong>{focus_benefit}</strong><span>Beneficio dominante</span></div>"
                f"<div class='pre-focus-stat'><strong>{details['lead_phone'] or '-'}</strong><span>Contato principal</span></div>"
                f"<div class='pre-focus-stat'><strong>{validated_total}/{required_total}</strong><span>Obrigatorios validados</span></div>"
                f"<div class='pre-focus-stat'><strong>{score['score']}/100</strong><span>Score documental</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='status-chip' style='background:{background}; color:{color};'>{label}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='pre-detail-list'>"
                f"<div class='pre-detail-row'><strong>Resumo executivo</strong><span>{details['summary']}</span></div>"
                f"<div class='pre-detail-row'><strong>Proximo passo</strong><span>{details['next_step']}</span></div>"
                f"<div class='pre-detail-row'><strong>Observacoes</strong><span>{details['notes'] or 'Sem observacoes adicionais.'}</span></div>"
                f"<div class='pre-detail-row'><strong>Data do registro</strong><span>{details['created_at']}</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        if details["benefit_category"] or details["estimated_monthly_value"] or details["estimated_total_value"]:
            monthly = details["estimated_monthly_value"]
            total = details["estimated_total_value"]
            st.markdown(
                (
                    "<div class='pre-meta-list' style='margin-top:1rem;'>"
                    f"<div class='pre-meta-item'><strong>Categoria especifica</strong><span>{details['benefit_category'] or 'Nao informada'}</span></div>"
                    f"<div class='pre-meta-item'><strong>Valor mensal estimado</strong><span>{format_currency(monthly) if monthly else 'Nao informado'}</span></div>"
                    f"<div class='pre-meta-item'><strong>Total estimado</strong><span>{format_currency(total) if total else 'Nao informado'}</span></div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        history = load_history(details["history_json"])
        st.markdown("<div class='pre-card' style='margin-top:1rem;'>", unsafe_allow_html=True)
        st.markdown("<h3 class='pre-section-title'>Historico de respostas</h3>", unsafe_allow_html=True)
        if not history:
            st.info("Sem historico de respostas registrado.")
        else:
            for index, item in enumerate(history, start=1):
                st.markdown(
                    (
                        '<div class="history-item">'
                        f"<strong>{index}. {item['node_code']}</strong><br>"
                        f"{item['question']}<br>"
                        f"<span class='muted'>Resposta: {item['answer']}</span>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)


def render_calculations_view() -> None:
    render_shell_page_header(
        "Cálculos previdenciários",
        "Triagem técnica com regras versionadas e revisão humana obrigatória.",
    )
    st.warning(
        "Esta tela não concede benefício nem calcula RMI. Confirme os dados no CNIS e revise juridicamente antes de orientar o cliente."
    )
    with st.expander("Referências locais e calculadora de intervalo"):
        reference_left, reference_right = st.columns(2)
        with reference_left:
            interval_start = st.date_input("Início do intervalo", value=date.today(), key="interval_start")
            interval_end = st.date_input("Fim do intervalo", value=date.today(), key="interval_end")
            inclusive = st.checkbox("Contar os dois extremos", key="interval_inclusive")
            try:
                st.metric("Dias no intervalo", calculate_day_interval(interval_start, interval_end, inclusive))
            except ValueError as error:
                st.error(str(error))
        with reference_right:
            reference_file = st.file_uploader("Importar referência JSON", type=["json"], key="reference_dataset_file")
            if reference_file and st.button("Validar e salvar referência", key="save_reference_dataset"):
                try:
                    payload = json.loads(reference_file.getvalue().decode("utf-8"))
                    dataset = ReferenceDataset(
                        kind=str(payload["kind"]), version=str(payload["version"]),
                        source_url=str(payload["source_url"]),
                        effective_date=date.fromisoformat(str(payload["effective_date"])),
                        data=dict(payload["data"]),
                    )
                    ReferenceDataRepository().save(dataset)
                    st.success(f"Referência {dataset.kind} {dataset.version} salva localmente.")
                except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                    st.error(f"Referência inválida: {error}")
    attendances = list_recent_attendances(limit=200)
    if not attendances:
        st.info("Registre um atendimento antes de iniciar uma triagem de cálculo.")
        return

    selected_id = st.selectbox(
        "Atendimento vinculado",
        options=[int(row["id"]) for row in attendances],
        format_func=lambda attendance_id: next(
            f"#{row['id']} — {row['lead_name']} ({row['flow_name']})"
            for row in attendances if int(row["id"]) == attendance_id
        ),
    )
    with st.expander("Importar CNIS com prévia", expanded=False):
        cnis_upload = st.file_uploader(
            "Extrato CNIS em PDF ou imagem", type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"], key="cnis_import_upload"
        )
        if cnis_upload and st.button("Ler CNIS e gerar prévia", key="read_cnis_import"):
            saved_path = save_uploaded_document(int(selected_id), "CNIS_IMPORTACAO", cnis_upload)
            with st.spinner("Extraindo texto localmente..."):
                preview = build_cnis_preview([saved_path])
            preview["import_id"] = CnisImportRepository().create(int(selected_id), saved_path, preview)
            st.session_state["cnis_import_preview"] = preview
        preview = st.session_state.get("cnis_import_preview")
        if preview:
            st.caption(f"Status: {preview['extraction_status']} · confiança: {preview['confidence']:.0%}")
            st.json(preview["fields"])
            st.caption(preview["technical_notes"])
            if preview["text_excerpt"]:
                st.text_area("Texto extraído para conferência", preview["text_excerpt"], height=160, disabled=True, key="cnis_import_text")
            if preview.get("import_id") and st.button("Confirmar prévia revisada", key="confirm_cnis_import"):
                CnisImportRepository().confirm(int(preview["import_id"]))
                st.success("Prévia CNIS marcada como revisada.")
        cnis_history = CnisImportRepository().list_for_attendance(int(selected_id))
        if cnis_history:
            st.caption(f"{len(cnis_history)} importação(ões) CNIS registrada(s) para este atendimento.")
    cnis_history = CnisImportRepository().list_for_attendance(int(selected_id))
    confirmed_imports = [item for item in cnis_history if item["confirmed_at"]]
    cnis_import_id = st.selectbox(
        "CNIS revisado usado como evidência (opcional)",
        options=[None] + [item["id"] for item in confirmed_imports],
        format_func=lambda import_id: "Sem CNIS vinculado" if import_id is None else next(
            f"Importação #{item['id']} · {item['created_at']} · confiança {item['confidence']:.0%}"
            for item in confirmed_imports if item["id"] == import_id
        ),
        key="calc_rgps_cnis_import_id",
    )
    st.markdown("### Planejamento RGPS — regras selecionadas de 2026")
    first, second, third = st.columns(3)
    with first:
        birth_date = st.date_input("Data de nascimento", value=date(1965, 1, 1), key="calc_rgps_birth_date")
        sex_label = st.radio("Sexo para a regra", ["Mulher", "Homem"], horizontal=True, key="calc_rgps_sex")
    with second:
        contribution_years = st.number_input("Anos completos de contribuição", min_value=0, max_value=60, value=15, key="calc_rgps_years")
        contribution_months = st.number_input("Meses adicionais", min_value=0, max_value=11, value=0, key="calc_rgps_months")
    with third:
        carencia_months = st.number_input("Carência reconhecida (meses)", min_value=0, max_value=720, value=180, key="calc_rgps_carencia")
        affiliation_date = st.date_input("Data da primeira filiação ao RGPS", value=date(2010, 1, 1), key="calc_rgps_affiliation")

    if st.button("Executar triagem e registrar", icon=":material/fact_check:", type="primary"):
        data = RgpsPlanningInput(
            birth_date=birth_date,
            sex="F" if sex_label == "Mulher" else "M",
            contribution_months=int(contribution_years) * 12 + int(contribution_months),
            carencia_months=int(carencia_months),
            affiliation_date=affiliation_date,
        )
        try:
            result = screen_rgps_planning(data)
            serialized = serialize_planning_result(result)
            repository = CalculationRepository()
            calculation_id = repository.create(
                attendance_id=int(selected_id), calculation_type="planejamento_rgps",
                title="Triagem de planejamento RGPS (2026)",
                inputs={
                    "birth_date": birth_date.isoformat(), "sex": data.sex,
                    "contribution_months": data.contribution_months,
                    "carencia_months": data.carencia_months,
                    "affiliation_date": affiliation_date.isoformat(),
                    "cnis_import_id": cnis_import_id,
                },
                ruleset_version=RULESET_VERSION,
            )
            repository.save_result(calculation_id, serialized)
            st.session_state["last_rgps_planning_result"] = serialized
            st.success("Triagem registrada como aguardando revisão humana.")
        except ValueError as error:
            st.error(str(error))

    result_data = st.session_state.get("last_rgps_planning_result")
    if result_data:
        st.markdown("### Resultado da triagem")
        for screening in result_data["screenings"]:
            if screening["eligible"]:
                st.success(f"{screening['title']}: requisitos objetivos informados atendidos.")
            else:
                st.info(f"{screening['title']}: " + " ".join(screening["pending_requirements"]))
        for notice in result_data["notices"]:
            st.caption(notice)

    records = CalculationRepository().list_for_attendance(int(selected_id))
    if records:
        st.markdown("### Histórico do atendimento")
        st.dataframe(
            [
                {
                    "Data": record.created_at,
                    "Módulo": record.title,
                    "Regras": record.ruleset_version,
                    "Status": record.status.replace("_", " ").title(),
                }
                for record in records
            ],
            use_container_width=True,
            hide_index=True,
        )
        for record in records:
            with st.expander(f"#{record.id} · {record.title} · {record.status.replace('_', ' ').title()}"):
                evidence_import_id = record.inputs.get("cnis_import_id")
                evidence_label = "Nenhum CNIS vinculado"
                if evidence_import_id:
                    matching_import = next((item for item in cnis_history if item["id"] == evidence_import_id), None)
                    evidence_label = (
                        f"CNIS #{evidence_import_id} · {'revisado' if matching_import and matching_import['confirmed_at'] else 'não confirmado'}"
                    )
                metadata_left, metadata_right = st.columns(2)
                with metadata_left:
                    st.caption("Evidência documental")
                    st.write(evidence_label)
                    st.caption("Entradas registradas")
                    st.json(record.inputs)
                with metadata_right:
                    st.caption("Versão da regra")
                    st.write(record.ruleset_version)
                    st.caption("Revisão humana")
                    if record.reviewed_at:
                        st.write(f"Concluída em {record.reviewed_at}")
                        st.write(record.review_notes)
                    else:
                        st.write("Pendente")
                if record.result:
                    st.caption("Resultado preservado")
                    st.json(record.result)
        awaiting_review = [record for record in records if record.status == "aguardando_revisao"]
        if awaiting_review:
            review_id = st.selectbox(
                "Cálculo a revisar",
                options=[record.id for record in awaiting_review],
                format_func=lambda calculation_id: next(
                    f"#{record.id} · {record.title} · {record.created_at}"
                    for record in awaiting_review if record.id == calculation_id
                ),
                key="calculation_review_id",
            )
            review_notes = st.text_area(
                "Observação da revisão",
                placeholder="Ex.: CNIS conferido, pendência de período rural mantida para análise jurídica.",
                key="calculation_review_notes",
                height=90,
            )
            if st.button("Marcar cálculo como revisado", icon=":material/verified:", key="mark_calculation_reviewed"):
                try:
                    CalculationRepository().mark_reviewed(int(review_id), review_notes)
                    st.success("Cálculo marcado como revisado.")
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


def render_current_view() -> None:
    current_view = st.session_state.current_view
    if current_view == "dashboard":
        render_dashboard_view()
    elif current_view == "crm":
        render_crm_view()
    elif current_view == "calculos":
        render_calculations_view()
    elif current_view == "leads":
        render_leads_view()
    elif current_view == "contratos":
        render_contracts_view()
    elif current_view == "configuracoes":
        render_settings_view()
    else:
        render_dashboard_view()


def main() -> None:
    init_database()
    inject_styles()
    inject_lawfirm_admin_theme()
    ensure_session_defaults()
    if not st.session_state.is_authenticated:
        render_auth_screen()
        return
    render_admin_topbar()
    render_current_view()


if __name__ == "__main__":
    main()
