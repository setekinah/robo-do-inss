"""Leitura tecnica local de documentos com fallback gracioso."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any


def analyze_document_bundle(
    *,
    document_code: str,
    uploaded_files: list[str],
    critical_fields: list[str],
) -> dict[str, Any]:
    if not uploaded_files:
        return {
            "raw_text": "",
            "extracted_data": {},
            "source_type": "sem_arquivo",
            "extraction_status": "nao_processado",
            "extraction_confidence": 0.0,
            "technical_notes": "Nenhum arquivo foi anexado para leitura tecnica.",
        }

    extracted_chunks: list[str] = []
    source_types: list[str] = []
    technical_notes: list[str] = []
    dependency_missing = False
    hard_failure = False

    for file_path in uploaded_files:
        extraction = extract_text_from_file(Path(file_path))
        source_types.append(extraction["source_type"])
        if extraction["text"]:
            extracted_chunks.append(extraction["text"])
        if extraction["technical_note"]:
            technical_notes.append(extraction["technical_note"])
        dependency_missing = dependency_missing or extraction["dependency_missing"]
        hard_failure = hard_failure or extraction["hard_failure"]

    raw_text = "\n\n".join(chunk for chunk in extracted_chunks if chunk).strip()
    extracted_data = extract_structured_fields(raw_text, critical_fields)
    field_hits = sum(1 for value in extracted_data.values() if value)
    total_fields = max(1, len(critical_fields))

    if raw_text:
        if field_hits == 0:
            extraction_status = "extraido"
        elif field_hits < total_fields:
            extraction_status = "parcial"
        else:
            extraction_status = "extraido"
    elif dependency_missing:
        extraction_status = "dependencia_ausente"
    elif hard_failure:
        extraction_status = "erro"
    else:
        extraction_status = "sem_texto"

    confidence = estimate_confidence(
        raw_text=raw_text,
        field_hits=field_hits,
        total_fields=total_fields,
        extraction_status=extraction_status,
    )

    return {
        "raw_text": raw_text,
        "extracted_data": extracted_data,
        "source_type": consolidate_source_types(source_types),
        "extraction_status": extraction_status,
        "extraction_confidence": confidence,
        "technical_notes": " | ".join(note for note in technical_notes if note) or "Processamento concluido.",
        "document_code": document_code,
    }


def extract_text_from_file(file_path: Path) -> dict[str, Any]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    if suffix in {".png", ".jpg", ".jpeg"}:
        return extract_text_from_image(file_path)
    return {
        "text": "",
        "source_type": f"nao_suportado:{suffix or 'sem_extensao'}",
        "technical_note": f"Formato ainda nao suportado automaticamente: {file_path.name}.",
        "dependency_missing": False,
        "hard_failure": False,
    }


def extract_text_from_pdf(file_path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return {
            "text": "",
            "source_type": "pdf_sem_leitor",
            "technical_note": (
                "Leitura direta de PDF indisponivel. Instale a dependencia opcional pypdf para extrair texto de PDFs nativos."
            ),
            "dependency_missing": True,
            "hard_failure": False,
        }

    try:
        reader = PdfReader(str(file_path))
        chunks = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n".join(chunk for chunk in chunks if chunk).strip()
        if text:
            return {
                "text": normalize_whitespace(text),
                "source_type": "pdf_nativo",
                "technical_note": f"Texto extraido diretamente de {file_path.name}.",
                "dependency_missing": False,
                "hard_failure": False,
            }
        return {
            "text": "",
            "source_type": "pdf_escaneado",
            "technical_note": (
                f"O PDF {file_path.name} nao expôs texto nativo. Pode ser escaneado e depender de OCR."
            ),
            "dependency_missing": False,
            "hard_failure": False,
        }
    except Exception as exc:
        return {
            "text": "",
            "source_type": "pdf_erro",
            "technical_note": f"Falha ao ler {file_path.name}: {exc}",
            "dependency_missing": False,
            "hard_failure": True,
        }


def extract_text_from_image(file_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError:
        return {
            "text": "",
            "source_type": "imagem_sem_pillow",
            "technical_note": (
                "Leitura de imagem indisponivel. Instale pillow e pytesseract para habilitar OCR local."
            ),
            "dependency_missing": True,
            "hard_failure": False,
        }

    try:
        import pytesseract  # type: ignore
    except ImportError:
        return {
            "text": "",
            "source_type": "imagem_sem_ocr",
            "technical_note": (
                "OCR local indisponivel. Instale pytesseract e configure o Tesseract OCR para imagens e fotos de WhatsApp."
            ),
            "dependency_missing": True,
            "hard_failure": False,
        }

    try:
        tesseract_executable = find_tesseract_executable()
        if tesseract_executable is None:
            return {
                "text": "",
                "source_type": "imagem_sem_tesseract",
                "technical_note": (
                    "OCR local instalado em Python, mas o executavel tesseract.exe nao foi encontrado no Windows. "
                    "Instale o Tesseract OCR ou informe o caminho em TESSERACT_CMD."
                ),
                "dependency_missing": True,
                "hard_failure": False,
            }

        pytesseract.pytesseract.tesseract_cmd = str(tesseract_executable)
        image = Image.open(file_path)
        normalized = ImageOps.grayscale(image)
        text = pytesseract.image_to_string(normalized, lang="por")
        return {
            "text": normalize_whitespace(text),
            "source_type": "imagem_ocr",
            "technical_note": (
                f"OCR executado localmente em {file_path.name} com {tesseract_executable.name}."
            ),
            "dependency_missing": False,
            "hard_failure": False,
        }
    except Exception as exc:
        return {
            "text": "",
            "source_type": "imagem_erro",
            "technical_note": f"Falha no OCR de {file_path.name}: {exc}",
            "dependency_missing": False,
            "hard_failure": True,
        }


def find_tesseract_executable() -> Path | None:
    env_path = os.environ.get("TESSERACT_CMD")
    candidates: list[Path] = []

    if env_path:
        candidates.append(Path(env_path))

    which_path = shutil.which("tesseract")
    if which_path:
        candidates.append(Path(which_path))

    program_files = [
        Path(os.environ.get("ProgramFiles", "")),
        Path(os.environ.get("ProgramFiles(x86)", "")),
        Path.home() / "AppData" / "Local" / "Programs",
    ]
    for base in program_files:
        if not str(base):
            continue
        candidates.extend(
            [
                base / "Tesseract-OCR" / "tesseract.exe",
                base / "Tesseract" / "tesseract.exe",
                base / "UB Mannheim" / "Tesseract-OCR" / "tesseract.exe",
            ]
        )

    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate

    return None


def consolidate_source_types(source_types: list[str]) -> str:
    unique = sorted({item for item in source_types if item})
    return ", ".join(unique) if unique else "indefinido"


def normalize_whitespace(text: str) -> str:
    compact = re.sub(r"[ \t]+", " ", text or "")
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact.strip()


def estimate_confidence(
    *,
    raw_text: str,
    field_hits: int,
    total_fields: int,
    extraction_status: str,
) -> float:
    if not raw_text:
        return 0.0
    base = 0.35
    volume_bonus = min(len(raw_text) / 4000, 0.25)
    field_bonus = (field_hits / total_fields) * 0.35
    status_bonus = 0.05 if extraction_status == "extraido" else 0.0
    return round(min(0.95, base + volume_bonus + field_bonus + status_bonus), 2)


def extract_structured_fields(raw_text: str, critical_fields: list[str]) -> dict[str, str]:
    if not raw_text.strip():
        return {field: "" for field in critical_fields}

    text = raw_text
    extracted: dict[str, str] = {}
    for field in critical_fields:
        extracted[field] = extract_field_value(field, text)
    return extracted


def extract_field_value(field_name: str, text: str) -> str:
    lowered = field_name.lower()

    patterns = {
        "cpf": r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
        "cid": r"\bCID[:\s-]*([A-Z]\d{1,2}(?:\.\d+)?)\b",
        "crm_medico": r"\bCRM(?:/[A-Z]{2})?[\s:-]*\d{4,10}\b",
        "cnpj": r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b",
        "nit": r"\b\d{11}\b",
        "nb": r"\b\d{3}\.?\d{3}\.?\d{3}-?\d\b",
        "data_nascimento": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_inicio": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_obito": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_prisao": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_acidente": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_fato_gerador": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_atualizacao": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_emissao": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_admissao": r"\b\d{2}/\d{2}/\d{4}\b",
        "data_saida": r"\b\d{2}/\d{2}/\d{4}\b",
        "periodo_afastamento": r"\b\d{2}/\d{2}/\d{4}\b",
        "competencia": r"\b\d{2}/\d{4}\b",
        "renda_total": r"R\$ ?[\d\.\,]+",
        "renda_per_capita": r"R\$ ?[\d\.\,]+",
    }

    if lowered in patterns:
        match = re.search(patterns[lowered], text, flags=re.IGNORECASE)
        if not match:
            return ""
        if match.groups():
            return match.group(1).strip()
        return match.group(0).strip()

    if lowered == "regime":
        match = re.search(r"\b(fechado|semiaberto|aberto)\b", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    if lowered in {"empresa", "empregador"}:
        labeled = search_labeled_value(text, ["empresa", "empregador"])
        return labeled

    if lowered in {"nome", "nome_crianca", "nome_falecido"}:
        labeled = search_labeled_value(text, ["nome", "nome do segurado", "nome da crianca", "falecido"])
        return labeled

    if lowered in {"endereco", "descricao_evento", "descricao_sequela", "fundamento_decisao", "objetivo"}:
        return search_labeled_value(text, [lowered.replace("_", " ")])

    if lowered in {"vinculos", "periodos", "salarios", "grupo_familiar", "documentos_disponiveis"}:
        return summarize_keywords(text, lowered)

    return search_labeled_value(text, [lowered.replace("_", " ")])


def search_labeled_value(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:\-]\s*(.+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).splitlines()[0].strip()
    return ""


def summarize_keywords(text: str, field_name: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keywords = {
        "vinculos": ["empresa", "empregador", "admissao", "saida"],
        "periodos": ["periodo", "competencia", "admissao", "saida"],
        "salarios": ["salario", "remuneracao", "r$"],
        "grupo_familiar": ["grupo familiar", "familiar", "dependente"],
        "documentos_disponiveis": ["documento", "anexo", "arquivo"],
    }.get(field_name, [field_name.replace("_", " ")])

    matched_lines = [
        line for line in lines if any(keyword.lower() in line.lower() for keyword in keywords)
    ]
    return " | ".join(matched_lines[:3])
