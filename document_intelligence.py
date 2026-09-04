"""Pipeline local de inteligência documental com OCR em camadas e revisão humana."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import unicodedata
from datetime import datetime
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
from typing import Any


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


MAX_FILE_BYTES = _env_int("OCR_MAX_FILE_MB", 50, 1, 250) * 1024 * 1024
MAX_OCR_PAGES = _env_int("OCR_MAX_PAGES", 12, 1, 100)
MAX_PDF_PAGES = _env_int("OCR_MAX_PDF_PAGES", 50, 1, 500)
MAX_IMAGE_PIXELS = _env_int("OCR_MAX_IMAGE_PIXELS", 30_000_000, 1_000_000, 100_000_000)
PDF_OCR_DPI = _env_int("OCR_PDF_DPI", 170, 120, 300)
MIN_NATIVE_PAGE_CHARS = _env_int("OCR_MIN_NATIVE_CHARS", 32, 12, 500)
OCR_RETRY_CONFIDENCE = 0.78
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
OCR_ROTATION_RETRY_CONFIDENCE = 0.72


def analyze_document_bundle(
    *,
    document_code: str,
    uploaded_files: list[str],
    critical_fields: list[str],
) -> dict[str, Any]:
    """Extract text and critical fields without releasing documents to external services."""
    if not uploaded_files:
        return {
            "raw_text": "",
            "extracted_data": {},
            "source_type": "sem_arquivo",
            "extraction_status": "nao_processado",
            "extraction_confidence": 0.0,
            "technical_notes": "Nenhum arquivo foi anexado para leitura técnica.",
            "document_code": document_code,
        }

    extracted_chunks: list[str] = []
    source_types: list[str] = []
    technical_notes: list[str] = []
    confidence_samples: list[tuple[float, int]] = []
    dependency_missing = False
    hard_failure = False

    for stored_path in uploaded_files:
        extraction = extract_text_from_file(Path(stored_path))
        source_types.append(str(extraction["source_type"]))
        text = str(extraction["text"] or "").strip()
        if text:
            extracted_chunks.append(text)
            confidence_samples.append(
                (float(extraction.get("source_confidence") or 0.0), max(1, len(text)))
            )
        if extraction.get("technical_note"):
            technical_notes.append(str(extraction["technical_note"]))
        dependency_missing = dependency_missing or bool(extraction.get("dependency_missing"))
        hard_failure = hard_failure or bool(extraction.get("hard_failure"))

    raw_text = normalize_whitespace("\n\n".join(extracted_chunks))
    extracted_data = extract_structured_fields(raw_text, critical_fields)
    field_hits = sum(1 for value in extracted_data.values() if value)
    total_fields = len(critical_fields)
    source_confidence = weighted_confidence(confidence_samples)
    confidence = estimate_confidence(
        raw_text=raw_text,
        field_hits=field_hits,
        total_fields=total_fields,
        source_confidence=source_confidence,
    )

    if raw_text:
        extraction_status = (
            "parcial"
            if confidence < 0.58 or (total_fields > 0 and field_hits < total_fields)
            else "extraido"
        )
    elif dependency_missing:
        extraction_status = "dependencia_ausente"
    elif hard_failure:
        extraction_status = "erro"
    else:
        extraction_status = "sem_texto"

    if raw_text and confidence < 0.70:
        technical_notes.append(
            "Confiança abaixo de 70%; confira o original e os campos antes de validar o documento."
        )
    if raw_text and total_fields and field_hits < total_fields:
        missing_fields = [field for field, value in extracted_data.items() if not value]
        technical_notes.append(
            f"Revisão humana pendente para: {', '.join(missing_fields)}."
        )

    return {
        "raw_text": raw_text,
        "extracted_data": extracted_data,
        "source_type": consolidate_source_types(source_types),
        "extraction_status": extraction_status,
        "extraction_confidence": confidence,
        "technical_notes": " | ".join(note for note in technical_notes if note)
        or "Processamento concluído.",
        "document_code": document_code,
    }


def extract_text_from_file(file_path: Path) -> dict[str, Any]:
    """Validate a local file and reuse extraction while its content metadata is unchanged."""
    try:
        resolved_path = file_path.resolve(strict=True)
        stat = resolved_path.stat()
    except OSError as exc:
        return extraction_failure(
            source_type="arquivo_inacessivel",
            note=f"Arquivo indisponível para leitura: {file_path.name} ({exc}).",
            hard_failure=True,
        )
    if stat.st_size <= 0:
        return extraction_failure(
            source_type="arquivo_vazio",
            note=f"O arquivo {resolved_path.name} está vazio.",
            hard_failure=True,
        )
    if stat.st_size > MAX_FILE_BYTES:
        return extraction_failure(
            source_type="arquivo_excede_limite",
            note=(
                f"O arquivo {resolved_path.name} excede o limite local de "
                f"{MAX_FILE_BYTES // (1024 * 1024)} MB para OCR."
            ),
            hard_failure=True,
        )
    cached = _extract_text_cached(str(resolved_path), stat.st_mtime_ns, stat.st_size)
    return dict(cached)


@lru_cache(maxsize=128)
def _extract_text_cached(file_path: str, _mtime_ns: int, _size: int) -> dict[str, Any]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return extract_text_from_image(path)
    return extraction_failure(
        source_type=f"nao_suportado:{suffix or 'sem_extensao'}",
        note=f"Formato ainda não suportado automaticamente: {path.name}.",
    )


def extract_text_from_pdf(file_path: Path) -> dict[str, Any]:
    """Read native PDF text and OCR only the pages that actually need it."""
    try:
        import pymupdf  # type: ignore
    except ImportError:
        return extract_text_from_pdf_with_pypdf(file_path)

    document = None
    try:
        document = pymupdf.open(file_path)
        if document.needs_pass:
            return extraction_failure(
                source_type="pdf_protegido",
                note=f"O PDF {file_path.name} exige senha e não pôde ser analisado.",
                hard_failure=True,
            )
        if len(document) > MAX_PDF_PAGES:
            return extraction_failure(
                source_type="pdf_excede_paginas",
                note=(
                    f"O PDF {file_path.name} possui {len(document)} páginas; o limite seguro "
                    f"para análise local é {MAX_PDF_PAGES}."
                ),
                hard_failure=True,
            )

        chunks: list[str] = []
        confidence_samples: list[tuple[float, int]] = []
        native_pages = 0
        ocr_pages = 0
        ocr_attempts = 0
        missing_ocr_pages = 0
        failed_ocr_pages = 0
        notes: list[str] = []

        for page_index, page in enumerate(document):
            native_text = normalize_whitespace(page.get_text("text", sort=True))
            dominant_image = page_dominant_image_coverage(page)
            needs_ocr = not is_native_text_usable(native_text) or (
                dominant_image >= 0.65 and len(native_text) < 800
            ) or needs_identity_visual_recovery(file_path, native_text, dominant_image)
            if not needs_ocr:
                chunks.append(f"[Página {page_index + 1}]\n{native_text}")
                native_pages += 1
                confidence_samples.append((0.98, max(1, len(native_text))))
                continue

            if ocr_attempts >= MAX_OCR_PAGES:
                missing_ocr_pages += 1
                continue

            ocr_attempts += 1
            pixmap = page.get_pixmap(dpi=PDF_OCR_DPI, alpha=False, colorspace=pymupdf.csRGB)
            with _open_image_bytes(pixmap.tobytes("png")) as image:
                ocr_result = run_ocr_image(image, source_label=f"página {page_index + 1}")
            if ocr_result["text"]:
                page_text = str(ocr_result["text"])
                chunks.append(f"[Página {page_index + 1} · OCR]\n{page_text}")
                ocr_pages += 1
                confidence_samples.append(
                    (float(ocr_result["confidence"]), max(1, len(page_text)))
                )
            elif ocr_result["dependency_missing"]:
                missing_ocr_pages += 1
            else:
                failed_ocr_pages += 1
            if ocr_result.get("technical_note"):
                notes.append(str(ocr_result["technical_note"]))

        if missing_ocr_pages and native_pages + ocr_pages < len(document):
            notes.append(
                f"{missing_ocr_pages} página(s) sem texto não foram processadas; "
                f"o limite é {MAX_OCR_PAGES} páginas OCR ou o motor está indisponível."
            )
        if failed_ocr_pages:
            notes.append(f"OCR sem texto útil em {failed_ocr_pages} página(s).")

        text = normalize_whitespace("\n\n".join(chunks))
        # Alguns CNIS nativos expõem texto pelo PyMuPDF em ordem geométrica, o
        # que embaralha linhas da tabela e pode esconder Nome/Data de nascimento.
        # Comparamos uma segunda extração local e preservamos a que mantém mais
        # campos rotulados. Isso não envia o documento para nenhum serviço externo.
        if native_pages == len(document) and not ocr_pages:
            pypdf_extraction = extract_text_from_pdf_with_pypdf(file_path)
            pypdf_text = str(pypdf_extraction.get("text") or "")
            if pypdf_text and native_pdf_semantic_score(pypdf_text) > native_pdf_semantic_score(text):
                pypdf_extraction["technical_note"] = (
                    f"{file_path.name}: pypdf selecionado por preservar melhor a estrutura "
                    "semântica do PDF nativo (campos cadastrais/tabelas)."
                )
                return pypdf_extraction
        if native_pages and ocr_pages:
            source_type = "pdf_hibrido_ocr_neural"
        elif ocr_pages:
            source_type = "pdf_ocr_neural"
        elif native_pages:
            source_type = "pdf_nativo_pymupdf"
        else:
            source_type = "pdf_escaneado_sem_texto"

        summary_note = (
            f"{file_path.name}: {native_pages} página(s) com texto nativo e "
            f"{ocr_pages} página(s) processada(s) por OCR neural local."
        )
        return {
            "text": text,
            "source_type": source_type,
            "source_confidence": weighted_confidence(confidence_samples),
            "technical_note": " | ".join([summary_note, *notes]),
            "dependency_missing": bool(missing_ocr_pages and not text),
            "hard_failure": bool(failed_ocr_pages and not text),
        }
    except Exception as exc:
        fallback = extract_text_from_pdf_with_pypdf(file_path)
        if fallback["text"]:
            fallback["technical_note"] = (
                f"PyMuPDF falhou ({type(exc).__name__}); "
                f"leitura nativa recuperada com pypdf. {fallback['technical_note']}"
            )
            return fallback
        return extraction_failure(
            source_type="pdf_erro",
            note=f"Falha ao ler {file_path.name}: {type(exc).__name__}: {exc}",
            hard_failure=True,
        )
    finally:
        if document is not None:
            document.close()


def extract_text_from_pdf_with_pypdf(file_path: Path) -> dict[str, Any]:
    """Compatibility fallback for native PDFs when PyMuPDF is unavailable."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return extraction_failure(
            source_type="pdf_sem_leitor",
            note=(
                "Leitura de PDF indisponível. Instale PyMuPDF e pypdf para habilitar "
                "texto nativo e OCR de páginas escaneadas."
            ),
            dependency_missing=True,
        )
    try:
        reader = PdfReader(str(file_path))
        if len(reader.pages) > MAX_PDF_PAGES:
            return extraction_failure(
                source_type="pdf_excede_paginas",
                note=(
                    f"O PDF {file_path.name} possui mais de {MAX_PDF_PAGES} páginas e não "
                    "foi processado automaticamente."
                ),
                hard_failure=True,
            )
        chunks = [
            f"[Página {index + 1}]\n{normalize_whitespace(page.extract_text() or '')}"
            for index, page in enumerate(reader.pages)
        ]
        text = normalize_whitespace("\n\n".join(chunk for chunk in chunks if chunk))
        if text:
            return {
                "text": text,
                "source_type": "pdf_nativo_pypdf",
                "source_confidence": 0.94,
                "technical_note": f"Texto nativo recuperado de {file_path.name} com pypdf.",
                "dependency_missing": False,
                "hard_failure": False,
            }
        return extraction_failure(
            source_type="pdf_escaneado_sem_renderizador",
            note=(
                f"O PDF {file_path.name} não expôs texto nativo e requer PyMuPDF "
                "para rasterização antes do OCR."
            ),
            dependency_missing=True,
        )
    except Exception as exc:
        return extraction_failure(
            source_type="pdf_erro",
            note=f"Falha no leitor alternativo de {file_path.name}: {type(exc).__name__}: {exc}",
            hard_failure=True,
        )


def extract_text_from_image(file_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError:
        return extraction_failure(
            source_type="imagem_sem_pillow",
            note="Leitura de imagem indisponível. Instale Pillow para preparar as imagens.",
            dependency_missing=True,
        )
    try:
        with Image.open(file_path) as opened:
            width, height = opened.size
            if width * height > MAX_IMAGE_PIXELS:
                return extraction_failure(
                    source_type="imagem_excede_pixels",
                    note=(
                        f"A imagem {file_path.name} excede o limite de "
                        f"{MAX_IMAGE_PIXELS:,} pixels para OCR local."
                    ),
                    hard_failure=True,
                )
            image = ImageOps.exif_transpose(opened).convert("RGB")
            result = run_ocr_image(image, source_label=file_path.name)
        return {
            "text": result["text"],
            "source_type": result["source_type"],
            "source_confidence": result["confidence"],
            "technical_note": result["technical_note"],
            "dependency_missing": result["dependency_missing"],
            "hard_failure": result["hard_failure"],
        }
    except Exception as exc:
        return extraction_failure(
            source_type="imagem_erro",
            note=f"Falha no OCR de {file_path.name}: {type(exc).__name__}: {exc}",
            hard_failure=True,
        )


def run_ocr_image(image: Any, *, source_label: str = "imagem") -> dict[str, Any]:
    """Run local OCR with preparation, orientation recovery and a conservative fallback.

    Phone photographs and scanned attachments frequently arrive sideways.  OCR engines
    can return a misleadingly high score for a few characters in that situation, so a
    weak first pass is retried in the four cardinal orientations before we ask the
    operator to review it.
    """
    candidates: list[dict[str, Any]] = []
    notes: list[str] = []
    engines_available = False
    engine_failed = False

    prepared = preprocess_document_image(image, aggressive=False)
    try:
        neural = ocr_with_rapidocr(prepared)
        engines_available = True
        neural["variant"] = "normalizada"
        candidates.append(neural)
        if neural["confidence"] < OCR_RETRY_CONFIDENCE or text_quality(neural["text"]) < 0.68:
            enhanced = preprocess_document_image(image, aggressive=True)
            retried = ocr_with_rapidocr(enhanced)
            retried["variant"] = "contraste adaptativo"
            candidates.append(retried)

        best_before_rotation = choose_best_ocr_candidate(candidates)
        if (
            best_before_rotation is None
            or (
                best_before_rotation["confidence"] < OCR_ROTATION_RETRY_CONFIDENCE
                and text_quality(best_before_rotation["text"]) < 0.62
            )
        ):
            from PIL import Image  # type: ignore

            for angle in (90, 180, 270):
                rotated = preprocess_document_image(image.rotate(angle, expand=True), aggressive=True)
                oriented = ocr_with_rapidocr(rotated)
                oriented["variant"] = f"orientacao {angle} graus + contraste adaptativo"
                candidates.append(oriented)
    except ImportError:
        notes.append("RapidOCR/ONNX Runtime não está instalado.")
    except Exception as exc:
        engine_failed = True
        notes.append(f"RapidOCR falhou: {type(exc).__name__}: {exc}.")

    best_neural = choose_best_ocr_candidate(candidates)
    if best_neural is None or best_neural["confidence"] < 0.70:
        try:
            tesseract = ocr_with_tesseract(preprocess_document_image(image, aggressive=True))
            engines_available = True
            tesseract["variant"] = "fallback Tesseract"
            candidates.append(tesseract)
        except ImportError:
            notes.append("Fallback Tesseract não instalado.")
        except FileNotFoundError:
            notes.append("Executável Tesseract não encontrado para o fallback.")
        except Exception as exc:
            engine_failed = True
            notes.append(f"Fallback Tesseract falhou: {type(exc).__name__}: {exc}.")

    best = choose_best_ocr_candidate(candidates)
    if best is None or not best["text"]:
        return {
            "text": "",
            "confidence": 0.0,
            "source_type": "imagem_sem_ocr" if not engines_available else "imagem_ocr_sem_texto",
            "technical_note": " ".join(notes) or f"Nenhum texto reconhecido em {source_label}.",
            "dependency_missing": not engines_available,
            "hard_failure": engine_failed and engines_available,
        }

    engine_label = "RapidOCR + ONNX" if best["engine"] == "rapidocr" else "Tesseract"
    review_note = (
        " Revisão humana recomendada por baixa confiança."
        if best["confidence"] < 0.75
        else ""
    )
    return {
        "text": normalize_whitespace(str(best["text"])),
        "confidence": round(float(best["confidence"]), 3),
        "source_type": (
            "imagem_ocr_neural" if best["engine"] == "rapidocr" else "imagem_ocr_tesseract"
        ),
        "technical_note": (
            f"{source_label}: OCR local com {engine_label}, variante {best['variant']}, "
            f"{best['line_count']} linha(s), confiança {best['confidence']:.0%}."
            f"{review_note} {' '.join(notes)}"
        ).strip(),
        "dependency_missing": False,
        "hard_failure": False,
    }


@lru_cache(maxsize=1)
def get_rapidocr_engine() -> Any:
    from rapidocr import RapidOCR  # type: ignore

    return RapidOCR()


def ocr_with_rapidocr(image: Any) -> dict[str, Any]:
    engine = get_rapidocr_engine()
    output = engine(image_to_png_bytes(image))
    texts = [str(item).strip() for item in (getattr(output, "txts", None) or [])]
    scores = [float(item) for item in (getattr(output, "scores", None) or [])]
    valid_pairs = [
        (text, scores[index] if index < len(scores) else 0.0)
        for index, text in enumerate(texts)
        if text
    ]
    text = "\n".join(item[0] for item in valid_pairs)
    confidence = (
        sum(item[1] * max(1, len(item[0])) for item in valid_pairs)
        / sum(max(1, len(item[0])) for item in valid_pairs)
        if valid_pairs
        else 0.0
    )
    return {
        "engine": "rapidocr",
        "text": text,
        "confidence": max(0.0, min(1.0, confidence)),
        "line_count": len(valid_pairs),
    }


def ocr_with_tesseract(image: Any) -> dict[str, Any]:
    try:
        import pytesseract  # type: ignore
        from pytesseract import Output  # type: ignore
    except ImportError as exc:
        raise ImportError("pytesseract ausente") from exc

    executable = find_tesseract_executable()
    if executable is None:
        raise FileNotFoundError("tesseract.exe ausente")
    pytesseract.pytesseract.tesseract_cmd = str(executable)
    available_languages = set(pytesseract.get_languages(config=""))
    if {"por", "eng"}.issubset(available_languages):
        language = "por+eng"
    elif "por" in available_languages:
        language = "por"
    elif "eng" in available_languages:
        language = "eng"
    else:
        language = next(iter(available_languages), "eng")
    data = pytesseract.image_to_data(
        image,
        lang=language,
        config="--oem 3 --psm 6",
        output_type=Output.DICT,
    )
    valid_pairs: list[tuple[str, float]] = []
    for text, confidence in zip(data.get("text", []), data.get("conf", [])):
        clean_text = str(text).strip()
        try:
            clean_confidence = float(confidence) / 100
        except (TypeError, ValueError):
            clean_confidence = 0.0
        if clean_text and clean_confidence >= 0:
            valid_pairs.append((clean_text, clean_confidence))
    text = " ".join(item[0] for item in valid_pairs)
    weighted = (
        sum(item[1] * max(1, len(item[0])) for item in valid_pairs)
        / sum(max(1, len(item[0])) for item in valid_pairs)
        if valid_pairs
        else 0.0
    )
    return {
        "engine": "tesseract",
        "text": text,
        "confidence": max(0.0, min(1.0, weighted)),
        "line_count": len(valid_pairs),
    }


def preprocess_document_image(image: Any, *, aggressive: bool) -> Any:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps  # type: ignore

    prepared = ImageOps.exif_transpose(image).convert("RGB")
    longest = max(prepared.size)
    if longest < 1800:
        scale = 1800 / max(1, longest)
        prepared = prepared.resize(
            (max(1, int(prepared.width * scale)), max(1, int(prepared.height * scale))),
            Image.Resampling.LANCZOS,
        )
    elif longest > 3400:
        scale = 3400 / longest
        prepared = prepared.resize(
            (max(1, int(prepared.width * scale)), max(1, int(prepared.height * scale))),
            Image.Resampling.LANCZOS,
        )

    if aggressive:
        gray = ImageOps.autocontrast(ImageOps.grayscale(prepared), cutoff=1)
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore

            pixels = np.asarray(gray)
            enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(pixels)
            prepared = Image.fromarray(enhanced).convert("RGB")
        except ImportError:
            prepared = ImageEnhance.Contrast(gray).enhance(1.45).convert("RGB")
        prepared = prepared.filter(ImageFilter.MedianFilter(size=3))
        prepared = prepared.filter(ImageFilter.UnsharpMask(radius=1.5, percent=160, threshold=3))
    else:
        prepared = ImageOps.autocontrast(prepared, cutoff=1)
    return ImageOps.expand(prepared, border=16, fill="white")


def choose_best_ocr_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [candidate for candidate in candidates if str(candidate.get("text") or "").strip()]
    if not valid:
        return None
    return max(
        valid,
        key=lambda candidate: (
            float(candidate.get("confidence") or 0.0) * 0.78
            + text_quality(str(candidate.get("text") or "")) * 0.22,
            len(str(candidate.get("text") or "")),
        ),
    )


def _open_image_bytes(content: bytes) -> Any:
    from PIL import Image  # type: ignore

    return Image.open(BytesIO(content))


def image_to_png_bytes(image: Any) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


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
        if str(base):
            candidates.extend(
                [
                    base / "Tesseract-OCR" / "tesseract.exe",
                    base / "Tesseract" / "tesseract.exe",
                    base / "UB Mannheim" / "Tesseract-OCR" / "tesseract.exe",
                ]
            )
    return next((candidate for candidate in candidates if candidate.exists()), None)


def get_ocr_capabilities() -> dict[str, Any]:
    """Expose a lightweight health snapshot without loading neural models."""
    packages = {
        "PyMuPDF": "pymupdf",
        "pypdf": "pypdf",
        "Pillow": "Pillow",
        "RapidOCR": "rapidocr",
        "ONNX Runtime": "onnxruntime",
    }
    detected: dict[str, str] = {}
    for label, package_name in packages.items():
        try:
            detected[label] = version(package_name)
        except PackageNotFoundError:
            detected[label] = "ausente"
    neural_ready = all(
        importlib.util.find_spec(module_name) is not None
        for module_name in ("pymupdf", "PIL", "rapidocr", "onnxruntime")
    )
    tesseract_path = find_tesseract_executable()
    pytesseract_ready = importlib.util.find_spec("pytesseract") is not None
    return {
        "neural_ready": neural_ready,
        "pdf_ready": importlib.util.find_spec("pymupdf") is not None,
        "tesseract_ready": tesseract_path is not None and pytesseract_ready,
        "tesseract_path": str(tesseract_path) if tesseract_path else "",
        "packages": detected,
        "max_ocr_pages": MAX_OCR_PAGES,
        "pdf_ocr_dpi": PDF_OCR_DPI,
        "privacy_mode": "local",
    }


def extraction_failure(
    *,
    source_type: str,
    note: str,
    dependency_missing: bool = False,
    hard_failure: bool = False,
) -> dict[str, Any]:
    return {
        "text": "",
        "source_type": source_type,
        "source_confidence": 0.0,
        "technical_note": note,
        "dependency_missing": dependency_missing,
        "hard_failure": hard_failure,
    }


def consolidate_source_types(source_types: list[str]) -> str:
    unique = list(dict.fromkeys(item for item in source_types if item))
    return ", ".join(unique) if unique else "indefinido"


def normalize_whitespace(text: str) -> str:
    compact = re.sub(r"[ \t]+", " ", text or "")
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact.strip()


def text_quality(text: str) -> float:
    clean = str(text or "").strip()
    if not clean:
        return 0.0
    printable_ratio = sum(character.isprintable() for character in clean) / len(clean)
    alnum_ratio = sum(character.isalnum() for character in clean) / len(clean)
    word_count = len(re.findall(r"\b\w{2,}\b", clean, flags=re.UNICODE))
    word_signal = min(1.0, word_count / 30)
    length_signal = min(1.0, len(clean) / 500)
    return round(
        max(0.0, min(1.0, printable_ratio * 0.30 + alnum_ratio * 0.25 + word_signal * 0.25 + length_signal * 0.20)),
        3,
    )


def is_native_text_usable(text: str) -> bool:
    return len(text.strip()) >= MIN_NATIVE_PAGE_CHARS and text_quality(text) >= 0.50


def needs_identity_visual_recovery(file_path: Path, native_text: str, image_coverage: float) -> bool:
    """Detect digitally-signed identity PDFs whose personal data is raster-only.

    CNH/RG/CPF PDFs often expose only the certificate/validation notice as
    selectable text. A valid native layer is not enough if it contains none of
    the identity fields needed by the document schema.
    """
    name_hint = normalize_document_text(file_path.name)
    identity_hint = any(token in name_hint.split() for token in ("cnh", "rg", "cpf", "identidade", "habilitacao"))
    if not identity_hint or image_coverage < 0.05:
        return False
    has_identity_data = any((
        extract_person_name(native_text),
        first_valid_identifier(native_text, "cpf"),
        extract_rg(native_text),
        extract_cnh_number(native_text),
    ))
    return not has_identity_data


def page_dominant_image_coverage(page: Any) -> float:
    """Estimate whether a PDF page is effectively a scan with a weak text overlay."""
    try:
        page_area = float(page.rect.width * page.rect.height)
        if page_area <= 0:
            return 0.0
        coverages: list[float] = []
        for image_info in page.get_images(full=True):
            for rectangle in page.get_image_rects(image_info[0]):
                coverages.append(float(rectangle.width * rectangle.height) / page_area)
        return min(1.0, max(coverages, default=0.0))
    except Exception:
        return 0.0


def weighted_confidence(samples: list[tuple[float, int]]) -> float:
    total_weight = sum(max(1, weight) for _score, weight in samples)
    if not total_weight:
        return 0.0
    return round(
        sum(max(0.0, min(1.0, score)) * max(1, weight) for score, weight in samples)
        / total_weight,
        3,
    )


def estimate_confidence(
    *,
    raw_text: str,
    field_hits: int,
    total_fields: int,
    source_confidence: float = 0.0,
    extraction_status: str | None = None,
) -> float:
    del extraction_status  # compatibilidade com chamadas anteriores
    if not raw_text:
        return 0.0
    field_signal = field_hits / total_fields if total_fields else 0.80
    quality_signal = text_quality(raw_text)
    engine_signal = source_confidence or min(0.90, 0.55 + quality_signal * 0.35)
    confidence = engine_signal * 0.58 + quality_signal * 0.24 + field_signal * 0.18
    return round(max(0.0, min(0.99, confidence)), 2)


def extract_structured_fields(raw_text: str, critical_fields: list[str]) -> dict[str, str]:
    if not raw_text.strip():
        return {field: "" for field in critical_fields}
    return {field: extract_field_value(field, raw_text) for field in critical_fields}


def build_cnis_report(raw_text: str, extracted_data: dict[str, str]) -> dict[str, Any]:
    """Build a CNIS report only from text evidence; it never decides entitlement."""
    vinculos = extract_cnis_vinculos(raw_text)
    competencias = extract_competency_list(raw_text)
    # Os indicadores podem ficar na seção de remunerações, fora do bloco do
    # vínculo. Por isso a fonte é o documento inteiro, e não só cada linha.
    indicadores = extract_cnis_indicators(raw_text)
    intervals = [
        (vinculo["inicio_data"], vinculo["fim_data"])
        for vinculo in vinculos
        if vinculo.get("inicio_data") and vinculo.get("fim_data")
    ]
    days = contribution_days(intervals)
    for vinculo in vinculos:
        vinculo.pop("inicio_data", None)
        vinculo.pop("fim_data", None)
    if days:
        years, remainder = divmod(days, 365)
        months, remaining_days = divmod(remainder, 30)
        total_time = f"{years} ano(s), {months} mes(es) e {remaining_days} dia(s)"
        time_note = "Estimativa baseada em periodos com inicio e fim identificados; requer conferencia tecnica."
    else:
        total_time = "Nao apurado automaticamente"
        time_note = "Nao ha periodos completos e confiaveis suficientes no texto extraido."
    if competencias:
        carencia = f"{len(competencias)} competencia(s) localizadas"
        carencia_note = "Contagem documental preliminar; não representa carência cumprida ou homologada pelo INSS."
    else:
        carencia = "Nao apurada automaticamente"
        carencia_note = "Nenhuma competencia valida foi estruturada para calculo."
    return {
        "segurado": {
            "nome": extracted_data.get("nome", "") or "Nao identificado no documento",
            "cpf": extracted_data.get("cpf", "") or "Nao identificado",
            "nit_pis": extracted_data.get("nit", "") or "Nao identificado",
            "data_nascimento": extracted_data.get("data_nascimento", "") or "Nao identificada",
        },
        "metricas": {
            "tempo_contribuicao_total": total_time,
            "tempo_contribuicao_dias": days or None,
            "tempo_nota": time_note,
            "carencia_cumprida": carencia,
            "carencia_nota": carencia_note,
            "rmi_estimada": "Nao calculada",
            "rmi_nota": "A RMI exige base contributiva validada e calculo tecnico.",
            "diagnostico_principal": "Sem diagnostico automatico",
            "diagnostico_subtitulo": "A leitura documental nao substitui analise previdenciaria.",
            "alertas_contagem": len(indicadores),
            "alertas_nota": (
                "Indicadores identificados: " + ", ".join(sorted(set(indicadores)))
                if indicadores else "Nenhum indicador INSS estruturado foi identificado no texto."
            ),
        },
        "vinculos": vinculos,
        "competencias_identificadas": competencias,
    }


DOCUMENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "CNIS": {
        "label": "CNIS - Extrato Previdenciario",
        "modules": ["vinculos", "carencia", "simulacao", "qualificacao"],
        "strong_signals": ["cnis", "extrato previdenciario", "remuneracoes", "vinculos previdenciarios"],
        "weak_signals": ["nit", "competencias", "indicador"],
        "required_fields": ["nome", "cpf", "nit"],
    },
    "RG": {
        "label": "Documento de Identidade - RG",
        "modules": ["cadastro", "qualificacao"],
        "strong_signals": ["doc identidade", "orgao emissor", "registro geral"],
        "weak_signals": ["ssp", "rg"],
        "required_fields": ["nome", "cpf", "rg"],
    },
    "CPF": {
        "label": "Comprovante de Inscrição no CPF",
        "modules": ["cadastro", "qualificacao"],
        "strong_signals": ["comprovante de situacao cadastral", "cadastro de pessoas fisicas"],
        "weak_signals": ["receita federal", "inscricao no cpf", "cpf"],
        "required_fields": ["nome", "cpf"],
    },
    "CNH": {
        "label": "Carteira Nacional de Habilitacao - CNH",
        "modules": ["cadastro", "qualificacao"],
        "strong_signals": ["carteira nacional de habilitacao", "permissao para dirigir"],
        "weak_signals": ["detran", "cnh", "numero de registro"],
        "required_fields": ["nome", "cpf", "numero_cnh", "validade"],
    },
    "CTPS": {
        "label": "Carteira de Trabalho - CTPS",
        "modules": ["cadastro", "vinculos", "qualificacao"],
        "strong_signals": ["carteira de trabalho", "ctps"],
        "weak_signals": ["contrato de trabalho", "admissao", "empregador"],
        "required_fields": ["nome", "empresa", "data_admissao"],
    },
    "CAT": {
        "label": "Comunicacao de Acidente de Trabalho - CAT",
        "modules": ["auxilio_acidente", "auxilio_doenca", "invalidez", "qualificacao"],
        "strong_signals": ["comunicacao de acidente de trabalho", "comunicaçao de acidente de trabalho"],
        "weak_signals": ["cat", "acidente de trabalho", "parte do corpo atingida"],
        "required_fields": ["nome", "data_acidente", "empresa"],
    },
    "PPP": {
        "label": "Perfil Profissiografico Previdenciario - PPP/LTCAT",
        "modules": ["aposentadoria_especial", "qualificacao"],
        "strong_signals": ["perfil profissiografico", "ltcat"],
        "weak_signals": ["ppp", "agente nocivo"],
        "required_fields": ["empresa", "funcao", "agente_nocivo"],
    },
    "LAUDO_MEDICO": {
        "label": "Laudo Medico",
        "modules": ["auxilio_doenca", "invalidez", "auxilio_acidente"],
        "strong_signals": ["laudo medico", "relatorio medico"],
        "weak_signals": ["cid", "crm"],
        "required_fields": ["nome", "cid"],
    },
    "ATESTADO_MEDICO": {
        "label": "Atestado Medico",
        "modules": ["auxilio_doenca", "invalidez", "auxilio_acidente"],
        "strong_signals": ["atestado medico", "atesto para os devidos fins"],
        "weak_signals": ["afastamento", "cid", "crm"],
        "required_fields": ["nome", "cid", "crm_medico"],
    },
    "CADUNICO": {
        "label": "CadUnico",
        "modules": ["bpc_loas", "qualificacao"],
        "strong_signals": ["cadunico", "folha resumo cadastro unico"],
        "weak_signals": ["nis", "renda familiar", "grupo familiar"],
        "required_fields": ["nome", "nis"],
    },
    "CARTA_CONCESSAO": {
        "label": "Carta de Concessao",
        "modules": ["revisao_beneficio", "qualificacao"],
        "strong_signals": ["carta de concessao", "memoria de calculo"],
        "weak_signals": ["numero do beneficio", "rmi", "nb"],
        "required_fields": ["nome", "numero_beneficio"],
    },
    "CERTIDAO_NASCIMENTO": {
        "label": "Certidao de Nascimento",
        "modules": ["salario_maternidade", "qualificacao"],
        "strong_signals": ["certidao de nascimento", "certifico que"],
        "weak_signals": ["nascido", "livro", "termo"],
        "required_fields": ["nome_crianca", "data_nascimento"],
    },
    "CERTIDAO_OBITO": {
        "label": "Certidao de Obito",
        "modules": ["pensao_morte", "qualificacao"],
        "strong_signals": ["certidao de obito", "certidao de falecimento"],
        "weak_signals": ["falecido", "obito", "declarante"],
        "required_fields": ["nome_falecido", "data_obito"],
    },
    "CTC": {
        "label": "Certidao de Tempo de Contribuicao - CTC",
        "modules": ["aposentadoria", "planejamento_previdenciario", "simulacao"],
        "strong_signals": ["certidao de tempo de contribuicao", "contagem reciproca"],
        "weak_signals": ["ctc", "tempo de contribuicao", "regime proprio"],
        "required_fields": ["nome", "tempo_contribuicao"],
    },
    "GPS": {
        "label": "Guia da Previdencia Social - GPS",
        "modules": ["aposentadoria", "planejamento_previdenciario", "qualificacao"],
        "strong_signals": ["guia da previdencia social", "identificador gps"],
        "weak_signals": ["gps", "codigo de pagamento", "competencia"],
        "required_fields": ["competencia", "valor"],
    },
    "CERTIDAO_RECOLHIMENTO": {
        "label": "Certidao Carceraria / Recolhimento Prisional",
        "modules": ["auxilio_reclusao", "qualificacao"],
        "strong_signals": ["certidao carceraria", "recolhimento prisional", "unidade prisional"],
        "weak_signals": ["regime", "detento", "recluso"],
        "required_fields": ["nome", "data_recolhimento", "regime"],
    },
}


def classify_document(file_name: str, raw_text: str) -> dict[str, Any]:
    """Classify locally by OCR text before choosing a field schema or legal module."""
    normalized_file_name = normalize_document_text(file_name)
    normalized_text = normalize_document_text(raw_text)
    # O modelo oficial do PPP (Anexo XVII) menciona "CAT registrada" como
    # um dos seus próprios campos. Isso não transforma um PPP em CAT.
    # Um nome de arquivo que declare PPP, combinado com o cabeçalho do perfil,
    # é evidência direta e recebe precedência sobre essas referências internas.
    is_ppp_profile = (
        "ppp" in normalized_file_name.split()
        and (
            "perfil profissiogr" in normalized_text
            or "anexo xvii" in normalized_text
        )
    )
    is_cnh_document = (
        "cnh" in normalized_file_name.split()
        and (
            "senatran" in normalized_text
            or "carteira nacional de habilita" in normalized_text
            or "permissao para dirigir" in normalized_text
        )
    )
    ranked: list[tuple[float, str, list[str]]] = []
    for code, definition in DOCUMENT_DEFINITIONS.items():
        strong = [signal for signal in definition["strong_signals"] if normalize_document_text(signal) in normalized_text]
        weak = [signal for signal in definition["weak_signals"] if normalize_document_text(signal) in normalized_text]
        file_hits = [signal for signal in [*definition["strong_signals"], *definition["weak_signals"]] if normalize_document_text(signal) in normalized_file_name]
        score = len(strong) * 2.2 + len(weak) * 0.65 + len(file_hits) * 1.1
        if code == "PPP" and is_ppp_profile:
            score += 8.0
            strong = [*strong, "perfil profissiografico/anexo xvii"]
        if code == "CNH" and is_cnh_document:
            score += 8.0
            strong = [*strong, "arquivo CNH/SENATRAN"]
        # Um sinal fraco isolado (por exemplo, NIT ou CRM) nao identifica o documento.
        if strong or len(weak) >= 2 or file_hits:
            ranked.append((score, code, [*strong, *weak, *[f"arquivo:{item}" for item in file_hits]]))
    if not ranked:
        return {
            "code": "NAO_CLASSIFICADO",
            "label": "Documento nao classificado",
            "confidence": 0.0,
            "evidence": [],
            "modules": ["triagem_manual"],
        }
    score, code, evidence = max(ranked, key=lambda candidate: candidate[0])
    definition = DOCUMENT_DEFINITIONS[code]
    return {
        "code": code,
        "label": definition["label"],
        "confidence": round(min(0.95, 0.35 + score * 0.14), 2),
        "evidence": evidence,
        "modules": definition["modules"],
    }


def normalize_document_text(value: str) -> str:
    """Normaliza acentos, pontuacao e espacos para sinais resistentes ao OCR."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents.casefold()).strip()


def extract_document_fields(document_code: str, raw_text: str) -> list[dict[str, str]]:
    """Return a typed, reviewable field contract for the classified document."""
    common = [
        ("nome", "Nome completo", extract_person_name(raw_text)),
        ("cpf", "CPF", first_valid_identifier(raw_text, "cpf")),
        ("data_nascimento", "Data de nascimento", extract_date_with_reverse_label(raw_text, ["data nascimento", "nascimento"])),
    ]
    specific: list[tuple[str, str, str]] = []
    if document_code == "RG":
        specific = [
            ("rg", "RG", extract_rg(raw_text)),
            ("orgao_emissor", "Orgao emissor", extract_issuing_agency(raw_text)),
            ("data_expedicao", "Data de expedicao", extract_date_with_reverse_label(raw_text, ["data expedicao", "expedicao", "data emissao", "emissao"])),
        ]
    elif document_code == "CPF":
        specific = [
            ("situacao_cadastral", "Situacao cadastral", extract_cpf_status(raw_text)),
            ("data_inscricao", "Data de inscricao", extract_date_with_reverse_label(raw_text, ["data de inscricao", "inscricao"])),
        ]
    elif document_code == "CNH":
        specific = [
            ("numero_cnh", "Numero de registro da CNH", extract_cnh_number(raw_text)),
            ("categoria_cnh", "Categoria", extract_cnh_category(raw_text)),
            ("validade", "Validade", extract_cnh_validity(raw_text)),
            ("primeira_habilitacao", "Primeira habilitacao", extract_date_with_reverse_label(raw_text, ["primeira habilitacao", "1a habilitacao", "1ª habilitacao"])),
            ("orgao_emissor", "Orgao emissor", extract_issuing_agency(raw_text)),
        ]
    elif document_code == "CNIS":
        specific = [
            ("nit", "NIT/PIS", first_valid_nit(raw_text)),
            ("competencias", "Competencias", extract_competencies(raw_text)),
            ("indicadores", "Indicadores INSS", summarize_keywords(raw_text, "indicadores")),
        ]
    elif document_code == "CTPS":
        vinculos_ctps = extract_ctps_vinculos(raw_text)
        primeiro_vinculo = vinculos_ctps[0] if vinculos_ctps else {}
        specific = [
            ("empresa", "Empresa", primeiro_vinculo.get("empregador") or search_labeled_value(raw_text, ["empresa", "empregador", "razao social"])),
            ("data_admissao", "Data de admissao", primeiro_vinculo.get("data_inicio") or search_labeled_date(raw_text, ["admissao", "data admissao"])),
            ("data_saida", "Data de saida", primeiro_vinculo.get("data_fim") or search_labeled_date(raw_text, ["saida", "demissao", "rescisao"])),
            ("vinculos_identificados", "Vinculos identificados", str(len(vinculos_ctps)) if vinculos_ctps else ""),
        ]
    elif document_code == "CAT":
        specific = [
            ("empresa", "Empresa", search_labeled_value(raw_text, ["empresa", "empregador", "razao social"])),
            ("data_acidente", "Data do acidente", search_labeled_date(raw_text, ["data do acidente", "data acidente", "ocorrencia"])),
            ("cid", "CID", extract_cid(raw_text)),
            ("descricao_evento", "Descricao do acidente", search_labeled_value(raw_text, ["descricao do acidente", "descricao da ocorrencia", "descricao"])),
        ]
    elif document_code == "PPP":
        specific = [
            ("empresa", "Empresa", search_labeled_value(raw_text, ["empresa", "empregador", "razao social"])),
            ("funcao", "Funcao", search_labeled_value(raw_text, ["funcao", "cargo"])),
            ("agente_nocivo", "Agente nocivo", search_labeled_value(raw_text, ["agente nocivo", "agentes nocivos"])),
        ]
    elif document_code == "LAUDO_MEDICO":
        specific = [
            ("cid", "CID", extract_cid(raw_text)),
            ("crm_medico", "CRM do profissional", extract_crm(raw_text)),
        ]
    elif document_code == "ATESTADO_MEDICO":
        specific = [
            ("cid", "CID", extract_cid(raw_text)),
            ("crm_medico", "CRM do profissional", extract_crm(raw_text)),
            ("periodo_afastamento", "Periodo de afastamento", extract_field_value("periodo_afastamento", raw_text)),
        ]
    elif document_code == "CADUNICO":
        specific = [
            ("nis", "NIS", first_valid_nit(raw_text)),
            ("renda_familiar", "Renda familiar", extract_currency_after_label(raw_text, ["renda familiar", "renda per capita"])),
        ]
    elif document_code == "CARTA_CONCESSAO":
        specific = [
            ("numero_beneficio", "Numero do beneficio", extract_benefit_number(raw_text)),
            ("dib", "DIB", search_labeled_date(raw_text, ["dib", "data inicio beneficio"])),
            ("rmi", "RMI", extract_currency_after_label(raw_text, ["rmi", "renda mensal inicial"])),
        ]
    elif document_code == "CERTIDAO_NASCIMENTO":
        specific = [
            ("nome_crianca", "Nome da crianca", extract_person_name(raw_text, "nome_crianca")),
        ]
    elif document_code == "CERTIDAO_OBITO":
        specific = [
            ("nome_falecido", "Nome do falecido", extract_person_name(raw_text, "nome_falecido")),
            ("data_obito", "Data do obito", search_labeled_date(raw_text, ["data do obito", "data obito", "falecimento"])),
        ]
    elif document_code == "CTC":
        specific = [
            ("tempo_contribuicao", "Tempo de contribuicao", search_labeled_value(raw_text, ["tempo de contribuicao", "tempo liquido"])),
            ("orgao_emissor", "Orgao emissor", search_labeled_value(raw_text, ["orgao emissor", "entidade expedidora"])),
        ]
    elif document_code == "GPS":
        specific = [
            ("competencia", "Competencia", extract_competencies(raw_text)),
            ("valor", "Valor recolhido", extract_currency_after_label(raw_text, ["valor", "total", "valor do documento"])),
        ]
    elif document_code == "CERTIDAO_RECOLHIMENTO":
        specific = [
            ("data_recolhimento", "Data de recolhimento", search_labeled_date(raw_text, ["data de recolhimento", "recolhimento", "data de ingresso"])),
            ("regime", "Regime prisional", extract_field_value("regime", raw_text)),
        ]
    fields = common + specific
    return [
        {
            "key": key,
            "label": label,
            "value": value or "Nao identificado",
            "status": "extraido" if value else "pendente_revisao",
        }
        for key, label, value in fields
    ]


def assess_document_extraction(
    classification: dict[str, Any],
    fields: list[dict[str, str]],
    *,
    raw_text: str,
    source_confidence: float,
) -> dict[str, Any]:
    """Recalcula status usando os campos do tipo detectado, nao um schema de CNIS."""
    if not raw_text.strip():
        return {"status": "sem_texto", "confidence": 0.0, "missing_fields": []}
    code = str(classification.get("code") or "NAO_CLASSIFICADO")
    required = DOCUMENT_DEFINITIONS.get(code, {}).get("required_fields", ["nome", "cpf"])
    values = {field["key"]: field.get("value", "") for field in fields}
    missing = [key for key in required if not values.get(key) or values[key] == "Nao identificado"]
    coverage = (len(required) - len(missing)) / len(required) if required else 1.0
    confidence = round(max(0.0, min(0.99, source_confidence * 0.60 + coverage * 0.25 + float(classification.get("confidence") or 0.0) * 0.15)), 2)
    if code == "NAO_CLASSIFICADO":
        status = "parcial"
    elif not missing and confidence >= 0.62:
        status = "extraido"
    else:
        status = "parcial"
    return {"status": status, "confidence": confidence, "missing_fields": missing}


def extract_date_with_reverse_label(text: str, labels: list[str]) -> str:
    labelled = search_labeled_date(text, labels)
    if labelled:
        return labelled
    for label in labels:
        pattern = rf"(\d{{2}}/\d{{2}}/\d{{4}})\s*(?:{re.escape(label)})"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and is_valid_date(match.group(1)):
            return match.group(1)
    return ""


def extract_rg(text: str) -> str:
    patterns = [
        r"\b(\d{5,12})\s+(?:SSP|DETRAN|PC|IGP)[/\-]?[A-Z]{0,2}\b",
        r"(?:rg|registro geral|documento de identidade|numero do rg|n[úu]mero do rg)\s*[:\-]?\s*(\d{5,12})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def extract_issuing_agency(text: str) -> str:
    match = re.search(r"\b((?:SSP|DETRAN|PC|IGP)[/\-]?[A-Z]{0,2})\b", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def extract_cnh_number(text: str) -> str:
    match = re.search(
        r"(?:n[úu]mero\s+de\s+registro|registro\s+nacional|registro|cnh)\s*[:\-]?\s*(\d{9,12})",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)
    label = re.search(r"(?:\d+\s*)?n[º°o]?\s*registro\b", text, flags=re.IGNORECASE)
    if not label:
        return ""
    trailing = text[label.end():label.end() + 220]
    for candidate in re.findall(r"(?<!\d)\d{9,12}(?!\d)", trailing):
        if not validate_identifier_digits(candidate):
            return candidate
    return ""


def extract_cnh_category(text: str) -> str:
    match = re.search(r"(?:categoria|cat\.)\s*[:\-]?\s*([A-E](?:\s*[A-E])?)\b", text, flags=re.IGNORECASE)
    if match:
        return re.sub(r"\s+", "", match.group(1)).upper()
    label = re.search(r"(?:\d+\s*)?cat\.?\s*hab\b", text, flags=re.IGNORECASE)
    if label:
        candidate = re.search(r"\b([A-E])\b", text[label.end():label.end() + 280], flags=re.IGNORECASE)
        return candidate.group(1).upper() if candidate else ""
    return ""


def extract_cnh_validity(text: str) -> str:
    match = re.search(r"(?:validade|v[aá]lida\s+at[eé])\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", text, flags=re.IGNORECASE)
    if not match:
        # Campos da CNH visual são lidos por coluna: a data pode preceder o
        # rótulo "4b Validade" na sequência do OCR.
        match = re.search(r"(\d{2}/\d{2}/\d{4})\s*(?:\d+\s*[a-z]\s*)?validade\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    try:
        # Uma CNH pode ter validade superior ao horizonte usado para datas de
        # documentos previdenciários; por isso não reutilizamos is_valid_date.
        parsed = datetime.strptime(match.group(1), "%d/%m/%Y")
    except ValueError:
        return ""
    return match.group(1) if 1900 <= parsed.year <= datetime.now().year + 20 else ""


def extract_cpf_status(text: str) -> str:
    match = re.search(r"situa[cç][aã]o\s+cadastral\s*[:\-]\s*([A-Za-zÀ-ÿ ]{3,50})", text, flags=re.IGNORECASE)
    return normalize_whitespace(match.group(1)).strip(" .;|") if match else ""


def extract_cid(text: str) -> str:
    match = re.search(r"\bCID(?:[-\s]?[A-Z])?\s*[:\-]?\s*([A-Z]\d{2}(?:\.\d{1,2})?)\b", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def extract_crm(text: str) -> str:
    match = re.search(r"\bCRM(?:[-/]?[A-Z]{2})?\s*[:\-]?\s*(\d{3,8})\b", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def extract_currency_after_label(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(
            rf"{re.escape(label)}\s*[:\-]?\s*(R\$\s*[\d.]+,\d{{2}})",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def extract_benefit_number(text: str) -> str:
    labels = ["numero do beneficio", "número do benefício", "beneficio", "benefício", "nb"]
    for label in labels:
        match = re.search(
            rf"{re.escape(label)}\s*[:\-]?\s*(\d{{3}}[.\s]?\d{{3}}[.\s]?\d{{3}}[-\s]?\d)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
    return ""


CNIS_INDICATOR_PATTERN = re.compile(
    r"\b(?:"
    r"PEXT(?:-[A-Z0-9]+)?|PREM(?:-[A-Z0-9]+)?|"
    r"IREM(?:-(?:INDPEND|SEM-DIAS-INTERM))?|"
    r"IREC(?:-(?:INDPEND|MEI|LC123))?|"
    r"PADM(?:-[A-Z0-9]+)?|AEXT(?:-[A-Z0-9]+)?|ACNIS(?:-[A-Z0-9]+)?|"
    r"IDINV(?:-[A-Z0-9]+)?|PEND(?:-[A-Z0-9]+)?"
    r")\b",
    re.IGNORECASE,
)


def extract_cnis_indicators(raw_text: str) -> list[str]:
    """Return the indicator codes evidenced in a CNIS, preserving no guesswork."""
    # Em tabelas nativas, uma coluna numérica pode encostar no fim de
    # IREC-LC123. Preservamos o código conhecido, sem transformar o número
    # vizinho em um indicador fictício.
    normalized = re.sub(r"\b(IREC-LC123)\d{1,2}\b", r"\1", raw_text, flags=re.IGNORECASE)
    return list(dict.fromkeys(match.upper() for match in CNIS_INDICATOR_PATTERN.findall(normalized)))


def extract_cnis_vinculos(raw_text: str) -> list[dict[str, Any]]:
    """Extract employer blocks only when the OCR supplied labelled evidence."""
    labels = re.compile(
        r"(?im)^(?:empregador|empresa|raz[aã]o\s+social|nome\s+do\s+empregador)\s*[:\-]\s*(?P<name>[^\n\r]+)"
    )
    matches = list(labels.finditer(raw_text))
    result: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else min(len(raw_text), match.end() + 1400)
        block = raw_text[match.start():end]
        employer = normalize_whitespace(match.group("name")).strip(" .;|")[:180]
        start = search_labeled_date(block, ["admissão", "admissao", "início", "inicio", "data início", "data inicio"])
        finish = search_labeled_date(block, ["rescisão", "rescisao", "término", "termino", "fim", "data fim", "data saída", "data saida"])
        cnpj = first_valid_identifier(block, "cnpj")
        indicators = extract_cnis_indicators(block)
        if not employer or not (start or finish or cnpj or indicators):
            continue
        result.append({
            "seq": len(result) + 1,
            "empregador": employer,
            "cnpj": cnpj or "Nao identificado",
            "tipo_filiacao": search_labeled_value(block, ["categoria", "tipo filiação", "tipo filiacao"]) or "Nao identificado",
            "data_inicio": start or "Nao identificada",
            "data_fim": finish or "Nao identificada",
            "inicio_data": parse_brazilian_date(start),
            "fim_data": parse_brazilian_date(finish),
            "status": "atencao" if indicators else "regular",
            "indicadores": indicators,
        })
    # O CNIS oficial costuma trazer vínculos em tabela, sem os rótulos
    # "Empresa:" ou "Empregador:" que a primeira estratégia procura.
    # Trata apenas linhas com CNPJ e duas datas, evitando inferir vínculos por
    # competências ou valores de remuneração.
    table_pattern = re.compile(
        r"(?im)^\s*(?P<seq>\d+)\s+"
        r"(?P<cnpj>\d{2}[.\s]?\d{3}[.\s]?\d{3}[/-]?\d{4}[-\s]?\d{2})\s+"
        r"(?P<employer>.+?)\s+"
        r"(?P<category>Empregado|Contribuinte|Avulso|Dom[eé]stico|Segurado)"
    )
    table_matches = list(table_pattern.finditer(raw_text))
    existing_keys = {(item.get("cnpj"), item.get("data_inicio"), item.get("data_fim")) for item in result}
    for index, match in enumerate(table_matches):
        cnpj = match.group("cnpj").strip()
        # Each row ends before the next CNPJ row or its remuneration section.
        end = table_matches[index + 1].start() if index + 1 < len(table_matches) else len(raw_text)
        block = raw_text[match.start():end]
        end_markers = [
            marker for marker in (
                block.find("Competência"), block.find("Competencia"), block.find("Remunerações"),
                block.find("Remuneracoes"), block.find("Relações Previdenciárias"),
                block.find("Relacoes Previdenciarias"), block.find("[Página"),
            ) if marker >= 0
        ]
        if end_markers:
            block = block[:min(end_markers)]
        # Alguns extratos colam o NIT imediatamente após a data final
        # (ex.: 21/10/1980108.818...). Não exigimos fronteira à direita.
        dates = re.findall(r"(?<!\d)\d{2}/\d{2}/\d{4}", block)
        start = dates[0] if dates else ""
        finish = dates[1] if len(dates) > 1 else ""
        if not start:
            continue
        key = (cnpj, start, finish)
        if key in existing_keys:
            continue
        employer = normalize_whitespace(match.group("employer")).strip(" .;|")[:180]
        if not employer or not first_valid_identifier(cnpj, "cnpj"):
            continue
        indicators = extract_cnis_indicators(block)
        result.append({
            "seq": len(result) + 1,
            "empregador": employer,
            "cnpj": first_valid_identifier(cnpj, "cnpj"),
            "tipo_filiacao": normalize_whitespace(match.group("category")),
            "data_inicio": start,
            "data_fim": finish or "Nao identificada",
            "inicio_data": parse_brazilian_date(start),
            "fim_data": parse_brazilian_date(finish),
            "status": "atencao" if indicators or not finish else "regular",
            "indicadores": indicators,
        })
        existing_keys.add(key)

    # O CNIS também lista períodos sem CNPJ, por exemplo "Contribuinte
    # Individual". Eles são vínculos contributivos e não podem desaparecer do
    # relatório só porque não há empregador. A sequência e as duas datas são a
    # evidência mínima; remunerações, competências e páginas não casam com este
    # formato e continuam fora da extração.
    individual_pattern = re.compile(
        r"(?im)^\s*(?P<seq>\d+)\s+"
        r"(?P<category>Contribuinte\s+Individual|Segurado\s+Especial|Empregado\s+Dom[eé]stico)\s+"
        r"(?P<start>\d{2}/\d{2}/\d{4})\s+(?P<finish>\d{2}/\d{2}/\d{4})"
    )
    for match in individual_pattern.finditer(raw_text):
        start, finish = match.group("start"), match.group("finish")
        key = ("Nao identificado", start, finish)
        if key in existing_keys:
            continue
        block = raw_text[match.start():match.start() + 1200]
        result.append({
            "seq": len(result) + 1,
            "empregador": "Sem empregador — recolhimento próprio",
            "cnpj": "Nao identificado",
            "tipo_filiacao": normalize_whitespace(match.group("category")),
            "data_inicio": start,
            "data_fim": finish,
            "inicio_data": parse_brazilian_date(start),
            "fim_data": parse_brazilian_date(finish),
            "status": "atencao",
            "indicadores": extract_cnis_indicators(block),
        })
        existing_keys.add(key)
    result.sort(key=lambda item: item.get("inicio_data") or datetime.max)
    for sequence, item in enumerate(result, start=1):
        item["seq"] = sequence
    return result


def extract_ctps_vinculos(raw_text: str) -> list[dict[str, Any]]:
    """Extract official CTPS Digital contract blocks without guessing unlabeled data."""
    contract_pattern = re.compile(
        r"(?im)^\s*(?P<inicio>\d{2}/\d{2}/\d{4})\s*-\s*"
        r"(?P<fim>\d{2}/\d{2}/\d{4})\s*\n+\s*"
        r"(?P<empregador>[^\n\r]{3,180})\s*\n+\s*"
        r"CNPJ\s*:\s*(?P<cnpj>\d{2}[.\s]?\d{3}[.\s]?\d{3}[/-]?\d{4}[-\s]?\d{2})"
    )
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for match in contract_pattern.finditer(raw_text):
        inicio = match.group("inicio")
        fim = match.group("fim")
        cnpj = first_valid_identifier(match.group("cnpj"), "cnpj")
        empregador = normalize_whitespace(match.group("empregador")).strip(" .;|")[:180]
        if not (cnpj and empregador and is_valid_date(inicio) and is_valid_date(fim)):
            continue
        key = (cnpj, inicio, fim)
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "seq": len(result) + 1,
            "empregador": empregador,
            "cnpj": cnpj,
            "data_inicio": inicio,
            "data_fim": fim,
            "inicio_data": parse_brazilian_date(inicio),
            "fim_data": parse_brazilian_date(fim),
            "fonte": "CTPS Digital",
            "status": "regular",
        })
    return result


def native_pdf_semantic_score(text: str) -> float:
    """Score local for choosing the native PDF reader that preserves labels."""
    normalized = normalize_whitespace(text)
    signals = 0
    if extract_person_name(normalized):
        signals += 3
    if extract_field_value("data_nascimento", normalized):
        signals += 2
    if first_valid_identifier(normalized, "cpf"):
        signals += 1
    if first_valid_nit(normalized):
        signals += 1
    if re.search(r"\b\d{2}[.]\d{3}[.]\d{3}/\d{4}-\d{2}\b", normalized):
        signals += 2
    return signals * 10 + min(9, text_quality(normalized) * 10)


def extract_competency_list(text: str) -> list[str]:
    without_full_dates = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", " ", text)
    current_year = datetime.now().year
    return list(dict.fromkeys(
        match.group(0) for match in re.finditer(r"\b(?:0[1-9]|1[0-2])/\d{4}\b", without_full_dates)
        if 1900 <= int(match.group(0)[-4:]) <= current_year + 2
    ))


def parse_brazilian_date(value: str) -> datetime | None:
    return datetime.strptime(value, "%d/%m/%Y") if value and is_valid_date(value) else None


def contribution_days(intervals: list[tuple[datetime, datetime]]) -> int:
    """Sum complete periods without double-counting overlap; result is an estimate."""
    normalized = sorted((start.date(), end.date()) for start, end in intervals if end >= start)
    if not normalized:
        return 0
    merged = [list(normalized[0])]
    for start, end in normalized[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum((end - start).days + 1 for start, end in merged)


def extract_field_value(field_name: str, text: str) -> str:
    lowered = field_name.lower().strip()
    if lowered == "cpf":
        return first_valid_identifier(text, "cpf")
    if lowered == "cnpj":
        return first_valid_identifier(text, "cnpj")
    if lowered == "cid":
        match = re.search(r"\bCID[:\s-]*([A-Z]\d{2}(?:\.\d{1,2})?)\b", text, flags=re.IGNORECASE)
        return match.group(1).upper() if match else ""
    if lowered == "crm_medico":
        match = re.search(r"\bCRM(?:\s*[/|-]\s*[A-Z]{2})?[\s:-]*\d{4,10}\b", text, flags=re.IGNORECASE)
        return match.group(0).strip() if match else ""
    if lowered in {"nit", "nis", "pis", "pasep"}:
        return first_valid_nit(text)
    if lowered == "nb":
        match = re.search(r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d\b", text)
        return match.group(0).strip() if match else ""
    if lowered.startswith("data_") or lowered in {"dib", "der", "dip"}:
        labels = [lowered.replace("_", " ")]
        if lowered == "data_nascimento":
            labels.extend(["nascimento", "data de nasc.", "nascido em"])
        labeled = search_labeled_date(text, labels)
        return labeled or first_valid_date(text)
    if lowered in {"periodo_afastamento", "periodo", "periodos"}:
        dates = valid_dates_in_text(text)
        return " a ".join(dates[:2]) if dates else summarize_keywords(text, "periodos")
    if lowered in {"competencia", "competencias"}:
        return extract_competencies(text)
    if lowered in {"renda_total", "renda_per_capita", "valor"}:
        match = re.search(r"R\$\s*[\d.]+,\d{2}", text, flags=re.IGNORECASE)
        return match.group(0).strip() if match else ""
    if lowered == "regime":
        match = re.search(r"\b(fechado|semiaberto|aberto)\b", text, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""
    if lowered in {"nome", "nome_crianca", "nome_falecido"}:
        return extract_person_name(text, lowered)
    if lowered in {"empresa", "empregador"}:
        return search_labeled_value(text, ["empresa", "empregador", "razão social"])
    if lowered in {"nome", "nome_crianca", "nome_falecido"}:
        return search_labeled_value(
            text,
            ["nome do segurado", "nome da criança", "nome do falecido", "nome"],
        )
    if lowered in {
        "endereco",
        "descricao_evento",
        "descricao_sequela",
        "fundamento_decisao",
        "objetivo",
    }:
        return search_labeled_value(text, [lowered.replace("_", " ")])
    if lowered in {
        "vinculos",
        "salarios",
        "grupo_familiar",
        "documentos_disponiveis",
        "indicadores",
        "contribuicoes",
        "restricoes",
    }:
        return summarize_keywords(text, lowered)
    return search_labeled_value(text, [lowered.replace("_", " ")])


def first_valid_identifier(text: str, kind: str) -> str:
    if kind == "cpf":
        candidates = re.findall(r"(?<!\d)\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}(?!\d)", text)
        size = 11
    else:
        candidates = re.findall(r"(?<!\d)\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2}(?!\d)", text)
        size = 14
    for candidate in candidates:
        digits = re.sub(r"\D", "", candidate)
        if len(digits) == size and validate_identifier_digits(digits):
            return candidate.strip()
    return ""


def first_valid_nit(text: str) -> str:
    candidates = re.findall(
        r"(?<!\d)\d{3}[.\s-]?\d{5}[.\s-]?\d{2}[-\s]?\d(?!\d)|(?<!\d)\d{11}(?!\d)",
        text,
    )
    for candidate in candidates:
        digits = re.sub(r"\D", "", candidate)
        if validate_nit_digits(digits):
            return candidate.strip()
    return ""


def validate_nit_digits(digits: str) -> bool:
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    weights = (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    total = sum(int(value) * weight for value, weight in zip(digits[:10], weights))
    check_digit = 11 - (total % 11)
    if check_digit in {10, 11}:
        check_digit = 0
    return int(digits[-1]) == check_digit


def extract_competencies(text: str) -> str:
    # Datas civis completas, como nascimento e emissao, nao sao competencias.
    without_full_dates = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", " ", text)
    current_year = datetime.now().year
    competencies = [
        match.group(0)
        for match in re.finditer(r"\b(?:0[1-9]|1[0-2])/\d{4}\b", without_full_dates)
        if 1900 <= int(match.group(0)[-4:]) <= current_year + 2
    ]
    return " | ".join(dict.fromkeys(competencies[:6]))


def validate_identifier_digits(digits: str) -> bool:
    if len(set(digits)) == 1:
        return False
    if len(digits) == 11:
        first = sum(int(digits[index]) * (10 - index) for index in range(9))
        digit_one = (first * 10 % 11) % 10
        second = sum(int(digits[index]) * (11 - index) for index in range(10))
        digit_two = (second * 10 % 11) % 10
        return digits[-2:] == f"{digit_one}{digit_two}"
    if len(digits) == 14:
        weights_one = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        total_one = sum(int(value) * weight for value, weight in zip(digits[:12], weights_one))
        digit_one = 0 if total_one % 11 < 2 else 11 - total_one % 11
        weights_two = [6, *weights_one]
        total_two = sum(int(value) * weight for value, weight in zip(digits[:13], weights_two))
        digit_two = 0 if total_two % 11 < 2 else 11 - total_two % 11
        return digits[-2:] == f"{digit_one}{digit_two}"
    return False


def search_labeled_value(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:\-]\s*([^\n\r]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .;|")
            return value[:240]
    return ""


def extract_person_name(text: str, field_name: str = "nome") -> str:
    """Accept the common CNIS labels, including a value rendered on its own line."""
    labels = {
        "nome": [
            "nome do segurado", "nome do filiado", "nome do trabalhador",
            "nome do requerente", "nome completo", "nome civil", "nome e sobrenome", "nome",
        ],
        "nome_crianca": ["nome da crianca", "nome da criança"],
        "nome_falecido": ["nome do falecido", "instituidor"],
    }.get(field_name, [field_name.replace("_", " ")])
    excluded = {"NOME", "SEGURADO", "TRABALHADOR", "FILIADO", "REQUERENTE", "CPF", "NIT", "PIS"}
    for label in labels:
        pattern = rf"{re.escape(label)}\s*(?::|\-|\n)\s*([^\n\r]{{4,160}})"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidate = normalize_whitespace(match.group(1)).strip(" .;|")
            candidate = re.split(r"\b(?:CPF|NIT|PIS|NIS|DATA\s+DE\s+NASCIMENTO)\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip(" .;|")
            words = re.findall(r"[A-Za-zÀ-ÿ]+", candidate)
            if is_person_name(candidate, words, excluded):
                return candidate[:120]
        reverse_pattern = rf"(?im)^([A-ZÀ-Ý][A-ZÀ-Ý ]{{5,120}})\s*\n\s*{re.escape(label)}\s*$"
        reverse_match = re.search(reverse_pattern, text)
        if reverse_match:
            candidate = normalize_whitespace(reverse_match.group(1)).strip(" .;|")
            words = re.findall(r"[A-Za-zÀ-ÿ]+", candidate)
            if is_person_name(candidate, words, excluded):
                return candidate[:120]
    return ""


def is_person_name(candidate: str, words: list[str], excluded: set[str]) -> bool:
    # "Nascimento" é um sobrenome brasileiro válido; "Data de Nascimento"
    # continua bloqueado por conter "DATA".
    forbidden = {"DOC", "DOCUMENTO", "IDENTIDADE", "ORGAO", "EMISSOR", "UF", "DATA"}
    return (
        2 <= len(words) <= 8
        and not any(word.upper() in excluded or word.upper() in forbidden for word in words)
        and not re.search(r"[/:;]", candidate)
        and not re.search(r"\d", candidate)
    )


def search_labeled_date(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:\-]?\s*(\d{{2}}/\d{{2}}/\d{{4}})"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and is_valid_date(match.group(1)):
            return match.group(1)
    return ""


def valid_dates_in_text(text: str) -> list[str]:
    candidates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", text)
    return list(dict.fromkeys(candidate for candidate in candidates if is_valid_date(candidate)))


def first_valid_date(text: str) -> str:
    dates = valid_dates_in_text(text)
    return dates[0] if dates else ""


def is_valid_date(value: str) -> bool:
    try:
        parsed = datetime.strptime(value, "%d/%m/%Y")
    except ValueError:
        return False
    return 1900 <= parsed.year <= datetime.now().year + 2


def summarize_keywords(text: str, field_name: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keywords = {
        "vinculos": ["empresa", "empregador", "admissão", "admissao", "saída", "saida"],
        "periodos": ["período", "periodo", "competência", "competencia", "admissão", "saída"],
        "salarios": ["salário", "salario", "remuneração", "remuneracao", "r$"],
        "grupo_familiar": ["grupo familiar", "familiar", "dependente"],
        "documentos_disponiveis": ["documento", "anexo", "arquivo"],
        "indicadores": ["indicador", "PEXT", "PREM", "IREC", "PADM", "PEND"],
        "contribuicoes": ["contribuição", "contribuicao", "GPS", "recolhimento"],
        "restricoes": ["restrição", "restricao", "limitação", "limitacao", "incapacidade"],
    }.get(field_name, [field_name.replace("_", " ")])
    matched_lines = [
        line for line in lines if any(keyword.casefold() in line.casefold() for keyword in keywords)
    ]
    return " | ".join(matched_lines[:4])
