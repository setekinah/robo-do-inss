"""Regras documentais da fase de analise criteriosa por beneficio."""

from __future__ import annotations

from typing import Any


COMMON_DOCUMENTS = [
    {
        "code": "identidade",
        "name": "Documento de identidade com foto",
        "category": "comum",
        "required": True,
        "analysis_focus": "Confirmar identidade civil, nome completo e data de nascimento do requerente.",
        "critical_fields": ["nome", "data_nascimento", "orgao_emissor"],
    },
    {
        "code": "cpf",
        "name": "CPF",
        "category": "comum",
        "required": True,
        "analysis_focus": "Validar o CPF que sera usado em cruzamentos com CNIS, CTPS e consultas oficiais.",
        "critical_fields": ["cpf"],
    },
    {
        "code": "comprovante_residencia",
        "name": "Comprovante de residencia atualizado",
        "category": "comum",
        "required": True,
        "analysis_focus": "Confirmar endereco e atualidade do comprovante para instruir atendimento e eventual processo.",
        "critical_fields": ["endereco", "data_emissao"],
    },
    {
        "code": "cnis",
        "name": "CNIS",
        "category": "comum",
        "required": True,
        "analysis_focus": "Mapear vinculos, remuneracoes, indicadores e consistencia do historico previdenciario.",
        "critical_fields": ["nit", "vinculos", "competencias", "indicadores"],
    },
    {
        "code": "ctps",
        "name": "CTPS fisica digitalizada ou CTPS Digital",
        "category": "comum",
        "required": True,
        "analysis_focus": "Conferir datas de admissao, desligamento, funcao e coerencia com o CNIS.",
        "critical_fields": ["empresa", "funcao", "data_admissao", "data_saida"],
    },
]


FLOW_DOCUMENT_RULES: dict[str, dict[str, Any]] = {
    "auxilioAcidente": {
        "analysis_focus": (
            "Confirmar nexo causal, consolidacao da lesao e sequela permanente com impacto na atividade habitual."
        ),
        "specific_documents": [
            {
                "code": "cat",
                "name": "CAT ou prova equivalente do acidente",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Buscar data do acidente, contexto do evento e nexo com o trabalho.",
                "critical_fields": ["data_acidente", "descricao_evento", "empregador"],
            },
            {
                "code": "bo_acidente",
                "name": "Boletim de ocorrencia ou documento do evento",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Reforcar o contexto do acidente e a cronologia dos fatos.",
                "critical_fields": ["data_evento", "local_evento"],
            },
            {
                "code": "laudo_sequela",
                "name": "Laudo medico de evolucao da sequela",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Identificar reducao funcional consolidada e limitacao permanente.",
                "critical_fields": ["cid", "data_incapacidade", "crm_medico", "descricao_sequela"],
            },
        ],
    },
    "aposentadoria": {
        "analysis_focus": "Fechar tempo, carencia, estrategia de especie e eventuais periodos especiais ou PCD.",
        "specific_documents": [
            {
                "code": "pps_ltcats",
                "name": "PPP, LTCAT ou prova de atividade especial",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Verificar agentes nocivos, intensidade e periodos especiais aproveitaveis.",
                "critical_fields": ["empresa", "periodo", "agente_nocivo", "epi"],
            },
            {
                "code": "carnes_guias",
                "name": "Carnes, GPS ou comprovantes de contribuicao",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Suportar acertos de contribuicao, retroacoes ou vinculos nao refletidos.",
                "critical_fields": ["competencia", "valor", "tipo_contribuicao"],
            },
            {
                "code": "certidoes_tempo",
                "name": "Certidoes e documentos de tempo de servico",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Ajudar em averbacoes, tempo rural, servico publico ou tempo especial.",
                "critical_fields": ["periodo", "orgao_origem", "natureza_tempo"],
            },
            {
                "code": "provas_atividade_rural",
                "name": "Provas de atividade rural ou segurado especial",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Organizar início de prova material, períodos rurais e coerência com o CNIS.",
                "critical_fields": ["periodo", "atividade", "localidade", "titular_documento"],
            },
            {
                "code": "laudos_pcd",
                "name": "Laudos e provas para aposentadoria da pessoa com deficiência",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Reunir impedimento, funcionalidade e marco temporal para revisão técnica e perícia.",
                "critical_fields": ["cid", "data_inicio", "restricoes", "profissional_responsavel"],
            },
        ],
    },
    "bpcLoas": {
        "analysis_focus": "Validar hipossuficiencia, composicao familiar e, quando houver, impedimento de longo prazo.",
        "specific_documents": [
            {
                "code": "cadunico",
                "name": "Comprovante do CadUnico atualizado",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Conferir atualizacao do cadastro e composicao do grupo familiar.",
                "critical_fields": ["nis", "data_atualizacao", "grupo_familiar"],
            },
            {
                "code": "renda_familiar",
                "name": "Extratos de renda e despesas dos membros da casa",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Apurar renda per capita e despesas relevantes para a tese assistencial.",
                "critical_fields": ["renda_total", "grupo_familiar", "renda_per_capita"],
            },
            {
                "code": "laudo_bpc",
                "name": "Laudos medicos e sociais do BPC",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Para BPC por deficiencia, confirmar impedimento de longo prazo.",
                "critical_fields": ["cid", "tempo_impedimento", "restricao_funcional"],
            },
        ],
    },
    "salarioMaternidade": {
        "analysis_focus": "Confirmar fato gerador, categoria da segurada, qualidade de segurada e carencia aplicavel.",
        "specific_documents": [
            {
                "code": "certidao_nascimento",
                "name": "Certidao de nascimento, termo de guarda ou adocao",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Validar a data do fato gerador e o vinculo juridico com a crianca.",
                "critical_fields": ["data_fato_gerador", "nome_crianca", "tipo_evento"],
            },
            {
                "code": "prova_categoria",
                "name": "Provas da categoria da segurada",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Diferenciar CLT, MEI, contribuinte individual, segurada especial ou desempregada.",
                "critical_fields": ["categoria", "vinculo", "competencias"],
            },
        ],
    },
    "auxilioDoenca": {
        "analysis_focus": "Comprovar incapacidade temporaria, qualidade de segurado e carencia.",
        "specific_documents": [
            {
                "code": "atestados",
                "name": "Atestados medicos atuais",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Validar CID, periodo de afastamento e CRM do medico.",
                "critical_fields": ["cid", "periodo_afastamento", "crm_medico"],
            },
            {
                "code": "laudos_exames",
                "name": "Laudos, exames e relatorios medicos",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Mapear diagnostico, data de inicio e restricoes funcionais.",
                "critical_fields": ["cid", "data_inicio", "restricoes"],
            },
            {
                "code": "prontuario",
                "name": "Prontuario ou relatorio de internacao",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Reforcar cronologia clinica e gravidade do quadro.",
                "critical_fields": ["internacao", "evolucao", "data_atendimento"],
            },
        ],
    },
    "aposentadoriaInvalidez": {
        "analysis_focus": "Confirmar incapacidade permanente, carencia e base previdenciaria suficiente.",
        "specific_documents": [
            {
                "code": "laudo_permanente",
                "name": "Laudo medico com indicacao de incapacidade permanente",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Apontar definitividade do quadro, prognostico e limitacoes permanentes.",
                "critical_fields": ["cid", "prognostico", "incapacidade_permanente", "crm_medico"],
            },
            {
                "code": "historico_beneficios",
                "name": "Historico de auxilios anteriores e pericias",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Reforcar continuidade incapacitante e cronologia de afastamentos.",
                "critical_fields": ["nb", "periodos", "resultado_pericia"],
            },
        ],
    },
    "pensaoMorte": {
        "analysis_focus": "Confirmar obito, dependencia economica e qualidade de segurado do instituidor.",
        "specific_documents": [
            {
                "code": "certidao_obito",
                "name": "Certidao de obito",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Fixar data do obito e dados civis do instituidor.",
                "critical_fields": ["data_obito", "nome_falecido", "filiacao"],
            },
            {
                "code": "prova_dependencia",
                "name": "Provas de dependencia economica ou parentesco",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Comprovar casamento, uniao estavel, filiacao ou dependencia.",
                "critical_fields": ["tipo_dependencia", "documento_base", "periodo_relacao"],
            },
            {
                "code": "documentos_instituidor",
                "name": "Documentos previdenciarios do instituidor",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Confirmar qualidade de segurado ou direito adquirido na data do obito.",
                "critical_fields": ["qualidade_segurado", "vinculos", "data_obito"],
            },
        ],
    },
    "auxilioReclusao": {
        "analysis_focus": "Confirmar prisao em regime compativel, dependencia e requisitos do segurado preso.",
        "specific_documents": [
            {
                "code": "certidao_carcere",
                "name": "Certidao de carcere",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Validar regime prisional, data da prisao e unidade.",
                "critical_fields": ["regime", "data_prisao", "unidade_prisional"],
            },
            {
                "code": "dependencia_reclusao",
                "name": "Provas de dependencia dos requerentes",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Fechar legitimidade previdenciaria dos dependentes.",
                "critical_fields": ["tipo_dependencia", "documento_base"],
            },
        ],
    },
    "revisaoBeneficio": {
        "analysis_focus": "Identificar tese revisional, erro de calculo ou documento nao considerado pelo INSS.",
        "specific_documents": [
            {
                "code": "carta_concessao",
                "name": "Carta de concessao, comunicacao de decisao ou indeferimento",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Mapear especie, DIB, fundamento da decisao e ponto de revisao.",
                "critical_fields": ["especie", "dib", "fundamento_decisao"],
            },
            {
                "code": "processo_administrativo",
                "name": "Processo administrativo e memoria de calculo",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Comparar periodos, salarios e formula utilizada pelo INSS.",
                "critical_fields": ["memoria_calculo", "periodos_reconhecidos", "salarios"],
            },
        ],
    },
    "planejamentoPrevidenciario": {
        "analysis_focus": "Organizar base documental para simulacoes, estrategia e definicao de melhor beneficio.",
        "specific_documents": [
            {
                "code": "docs_planejamento",
                "name": "Documentos complementares para planejamento",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Consolidar periodos, contribuicoes, atividades especiais e objetivos do cliente.",
                "critical_fields": ["objetivo", "periodos", "contribuicoes"],
            },
            {
                "code": "provas_especiais_pp",
                "name": "Provas especiais, PCD ou tempo diferenciado",
                "category": "beneficio",
                "required": False,
                "analysis_focus": "Permitir simulacoes mais sofisticadas e estrategia de enquadramento.",
                "critical_fields": ["tipo_enquadramento", "periodo", "prova_base"],
            },
        ],
    },
    "outrosAssuntos": {
        "analysis_focus": "Receber um dossie minimo para permitir enquadramento humano do caso.",
        "specific_documents": [
            {
                "code": "resumo_livre",
                "name": "Resumo livre do caso e documentos disponiveis",
                "category": "beneficio",
                "required": True,
                "analysis_focus": "Capturar contexto suficiente para definir a proxima rota interna.",
                "critical_fields": ["tema", "documentos_disponiveis"],
            }
        ],
    },
}

# Mantém o checklist documental alinhado aos fluxos ativos.
FLOW_DOCUMENT_RULES.pop("outrosAssuntos", None)


def build_document_checklist(flow_id: str) -> list[dict[str, Any]]:
    flow_rule = FLOW_DOCUMENT_RULES.get(flow_id, {})
    specific_documents = flow_rule.get("specific_documents", [])
    return [*COMMON_DOCUMENTS, *specific_documents]


def get_flow_document_strategy(flow_id: str) -> dict[str, Any]:
    flow_rule = FLOW_DOCUMENT_RULES.get(flow_id, {})
    checklist = build_document_checklist(flow_id)
    return {
        "analysis_focus": flow_rule.get(
            "analysis_focus",
            "Consolidar os documentos essenciais e preparar o caso para analise juridica aprofundada.",
        ),
        "documents": checklist,
        "required_total": sum(1 for item in checklist if item["required"]),
        "optional_total": sum(1 for item in checklist if not item["required"]),
    }

