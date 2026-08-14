"""Workspace de cálculos previdenciários, isolado do shell Streamlit."""

from __future__ import annotations

import json
from datetime import date
from typing import Callable

import streamlit as st

from database import list_recent_attendances
from document_storage import save_uploaded_document
from repositories.calculation_repository import CalculationRepository
from repositories.cnis_import_repository import CnisImportRepository
from repositories.reference_data_repository import ReferenceDataRepository
from services.cnis_import_service import build_cnis_preview
from services.date_calculation_service import calculate_day_interval
from services.reference_data_service import ReferenceDataset
from services.rgps_planning_service import (
    RULESET_VERSION,
    RgpsPlanningInput,
    screen_rgps_planning,
    serialize_planning_result,
)
from services.technical_logging import log_technical_event
from runtime_paths import DATA_DIR


def render_calculations_view(render_page_header: Callable[[str, str], None]) -> None:
    """Renderiza cálculos com persistência auditável e revisão humana."""
    render_page_header(
        "Cálculos previdenciários",
        "Triagem técnica com regras versionadas e revisão humana obrigatória.",
    )
    st.warning(
        "Esta tela não concede benefício nem calcula RMI. Confirme os dados no CNIS e revise juridicamente antes de orientar o cliente."
    )
    attendances = list_recent_attendances(limit=200)
    if not attendances:
        st.info("Para importar um CNIS, primeiro registre ou selecione o atendimento do cliente.")
        if st.button("Ir para Atendimentos", icon=":material/person_add:", type="primary"):
            st.session_state.current_view = "leads"
            st.rerun()
        return

    with st.expander("Referências técnicas (JSON — opcional) e calculadora de intervalo"):
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
            reference_file = st.file_uploader(
                "Importar referência técnica (.json; não é documento CNIS)",
                type=["json"],
                key="reference_dataset_file",
            )
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
    selected_id = st.selectbox(
        "Atendimento vinculado", options=[int(row["id"]) for row in attendances],
        format_func=lambda attendance_id: next(
            f"#{row['id']} — {row['lead_name']} ({row['flow_name']})"
            for row in attendances if int(row["id"]) == attendance_id
        ),
    )
    with st.expander("1. Importar CNIS do cliente (PDF ou imagem)", expanded=True):
        cnis_upload = st.file_uploader(
            "CNIS do cliente — arraste o documento aqui ou clique em Procurar arquivos",
            type=["pdf", "png", "jpg", "jpeg", "tif", "tiff"],
            key="cnis_import_upload",
        )
        st.caption("Formatos aceitos: PDF, PNG, JPG e TIFF. Se arrastar não funcionar no navegador, clique em Procurar arquivos.")
        if cnis_upload and st.button("Ler CNIS e gerar prévia", key="read_cnis_import"):
            try:
                saved_path = save_uploaded_document(int(selected_id), "CNIS_IMPORTACAO", cnis_upload)
                with st.spinner("Extraindo texto localmente..."):
                    preview = build_cnis_preview([saved_path])
                preview["import_id"] = CnisImportRepository().create(int(selected_id), saved_path, preview)
                st.session_state["cnis_import_preview"] = preview
            except ValueError as error:
                log_technical_event(
                    DATA_DIR,
                    event="cnis.upload_rejected",
                    level="warning",
                    component="calculations",
                    correlation_id=f"attendance-{selected_id}",
                    context={"reason": str(error)},
                )
                st.error(f"CNIS não importado: {error}")
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
        "CNIS revisado usado como evidência (opcional)", options=[None] + [item["id"] for item in confirmed_imports],
        format_func=lambda import_id: "Sem CNIS vinculado" if import_id is None else next(
            f"Importação #{item['id']} · {item['created_at']} · confiança {item['confidence']:.0%}"
            for item in confirmed_imports if item["id"] == import_id
        ), key="calc_rgps_cnis_import_id",
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
        data = RgpsPlanningInput(birth_date=birth_date, sex="F" if sex_label == "Mulher" else "M", contribution_months=int(contribution_years) * 12 + int(contribution_months), carencia_months=int(carencia_months), affiliation_date=affiliation_date)
        try:
            result = screen_rgps_planning(data)
            serialized = serialize_planning_result(result)
            repository = CalculationRepository()
            calculation_id = repository.create(
                attendance_id=int(selected_id), calculation_type="planejamento_rgps", title="Triagem de planejamento RGPS (2026)",
                inputs={"birth_date": birth_date.isoformat(), "sex": data.sex, "contribution_months": data.contribution_months, "carencia_months": data.carencia_months, "affiliation_date": affiliation_date.isoformat(), "cnis_import_id": cnis_import_id},
                ruleset_version=RULESET_VERSION,
                created_by=str(st.session_state.get("auth_login_email") or "sistema local"),
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
    if not records:
        return
    st.markdown("### Histórico do atendimento")
    st.dataframe([{"Data": record.created_at, "Módulo": record.title, "Regras": record.ruleset_version, "Status": record.status.replace("_", " ").title()} for record in records], use_container_width=True, hide_index=True)
    for record in records:
        with st.expander(f"#{record.id} · {record.title} · {record.status.replace('_', ' ').title()}"):
            evidence_import_id = record.inputs.get("cnis_import_id")
            evidence_label = "Nenhum CNIS vinculado"
            if evidence_import_id:
                matching_import = next((item for item in cnis_history if item["id"] == evidence_import_id), None)
                evidence_label = f"CNIS #{evidence_import_id} · {'revisado' if matching_import and matching_import['confirmed_at'] else 'não confirmado'}"
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
        review_id = st.selectbox("Cálculo a revisar", options=[record.id for record in awaiting_review], format_func=lambda calculation_id: next(f"#{record.id} · {record.title} · {record.created_at}" for record in awaiting_review if record.id == calculation_id), key="calculation_review_id")
        review_notes = st.text_area("Observação da revisão", placeholder="Ex.: CNIS conferido, pendência de período rural mantida para análise jurídica.", key="calculation_review_notes", height=90)
        if st.button("Marcar cálculo como revisado", icon=":material/verified:", key="mark_calculation_reviewed"):
            try:
                CalculationRepository().mark_reviewed(
                    int(review_id), review_notes,
                    reviewed_by=str(st.session_state.get("auth_login_email") or "sistema local"),
                )
                st.success("Cálculo marcado como revisado.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
