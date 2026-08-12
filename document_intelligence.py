"""Pipeline local de inteligência documental com OCR em camadas e revisão humana."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
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
MAX_PDF_PAGES = _env_int("OCR_MAX_PDF_PAGES", 100, 1, 500)
PDF_OCR_DPI = _env_int("OCR_PDF_DPI", 170, 120, 300)
MAX_IMAGE_PIXELS = _env_int("OCR_MAX_IMAGE_PIXELS", 40_000_000, 1_000_000, 100_000_000)
MIN_NATIVE_PAGE_CHARS = _env_int("OCR_MIN_NATIVE_CHARS", 32, 12, 500)
OCR_RETRY_CONFIDENCE = 0.78
SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


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
                source_type="pdf_excede_limite_paginas",
                note=(f"O PDF {file_path.name} possui mais de {MAX_PDF_PAGES} "
                      "páginas e não foi processado automaticamente."),
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
            )
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
                source_type="pdf_excede_limite_paginas",
                note=(f"O PDF {file_path.name} possui mais de {MAX_PDF_PAGES} "
                      "páginas e não foi processado automaticamente."),
                hard_failure=True,
            )
        chunks = [normalize_whitespace(page.extract_text() or "") for page in reader.pages]
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
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        with Image.open(file_path) as opened:
            if opened.width * opened.height > MAX_IMAGE_PIXELS:
                return extraction_failure(
                    source_type="imagem_excede_limite_pixels",
                    note=(f"A imagem {file_path.name} excede o limite de "
                          f"{MAX_IMAGE_PIXELS:,} pixels para OCR."),
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
    """Run neural OCR first, retry an enhanced variant, then try Tesseract if available."""
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
        "max_pdf_pages": MAX_PDF_PAGES,
        "max_image_pixels": MAX_IMAGE_PIXELS,
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
