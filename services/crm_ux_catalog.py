"""Inventário do comportamento atual do CRM para desenho de UI/UX."""

from __future__ import annotations

CRM_UX_CATALOG = (
    ("Funil", "Etapas, busca, filtros, seleção de caso e priorização.", "novo contato → conflito → triagem → reunião → proposta → documentos → caso ativo → encerrado/perdido"),
    ("Caso em foco", "Resumo, benefício, score documental, próximo passo, perfil e contato.", "selecionar caso, abrir workspace e encaminhar contratos"),
    ("Governança", "Checagem de conflito, aviso de privacidade e base legal.", "bloquear avanço contratual quando há pendência"),
    ("Documentos", "Checklist por fluxo, upload, OCR local, confiança e notas técnicas.", "receber, validar, dispensar e revisar documento"),
    ("Tarefas e atividades", "Fila priorizada, responsáveis, prazos e linha do tempo.", "criar, concluir, revisar e registrar atividade"),
    ("Automações", "Eventos recebidos, tarefas derivadas, revisão humana e auditoria.", "processar, revisar e repetir evento com segurança"),
    ("Contratos", "Elegibilidade, dossiê, honorário potencial e minuta.", "bloquear/liberar e abrir contrato"),
    ("Indicadores", "Funil, conversão, carteira, documentos e performance.", "filtrar leitura operacional e acompanhar gargalos"),
    ("Cálculos", "Triagem RGPS, importação CNIS, referências locais e histórico.", "registrar resultado versionado e exigir revisão humana"),
)
