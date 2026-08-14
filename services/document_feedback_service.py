"""Mensagens operacionais consistentes para o fluxo documental."""

from __future__ import annotations


def build_document_feedback(extraction_status: str, confidence: float = 0.0) -> dict[str, str]:
    """Traduz o status técnico em orientação segura, sem validar juridicamente."""
    if extraction_status == "extraido" and confidence >= 0.70:
        return {"level": "success", "title": "Leitura concluída", "message": "Confira os campos extraídos e valide o documento após comparar com o original."}
    if extraction_status == "parcial" or confidence < 0.70 and extraction_status == "extraido":
        return {"level": "warning", "title": "Leitura parcial", "message": "Confira o original, corrija campos ausentes se necessário e mantenha o documento em revisão."}
    if extraction_status == "dependencia_ausente":
        return {"level": "warning", "title": "Leitura automática indisponível", "message": "Use o Diagnóstico do ambiente para instalar a dependência indicada ou registre o documento para revisão manual."}
    if extraction_status in {"erro", "sem_texto"}:
        return {"level": "error", "title": "Não foi possível extrair texto", "message": "Confira se o arquivo está íntegro e legível. Você pode substituir o arquivo ou seguir com revisão manual."}
    return {"level": "info", "title": "Aguardando leitura", "message": "Anexe um documento válido e execute a leitura técnica quando estiver pronto."}
