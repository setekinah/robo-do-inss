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
PDF_OCR_DPI = _env_int("OCR_PDF_DPI", 170, 120, 300)
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
        with Image.open(file_path) as opened:
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


def build_cnis_report(raw_text: str, extracted_data: dict[str, str]) -> dict[str, Any]:
    """Build a CNIS report only from text evidence; it never decides entitlement."""
    vinculos = extract_cnis_vinculos(raw_text)
    competencias = extract_competency_list(raw_text)
    indicadores = [indicator for vinculo in vinculos for indicator in vinculo["indicadores"]]
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
        carencia = f"{len(competencias)} competencia(s) identificada(s)"
        carencia_note = "Contagem documental preliminar; nao equivale a carencia homologada pelo INSS."
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
        "signals": ["cnis", "extrato previdenciario", "nit", "remuneracoes", "vinculos"],
    },
    "RG": {
        "label": "Documento de Identidade - RG",
        "modules": ["cadastro", "qualificacao"],
        "signals": ["doc. identidade", "doc identidade", "org. emissor", "orgao emissor", "ssp", "registro geral"],
    },
    "CNH": {
        "label": "Carteira Nacional de Habilitacao - CNH",
        "modules": ["cadastro", "qualificacao"],
        "signals": ["carteira nacional de habilitacao", "detran", "registro nacional", "cnh"],
    },
    "CTPS": {
        "label": "Carteira de Trabalho - CTPS",
        "modules": ["cadastro", "vinculos", "qualificacao"],
        "signals": ["carteira de trabalho", "ctps", "contrato de trabalho", "admissao"],
    },
    "PPP": {
        "label": "Perfil Profissiografico Previdenciario - PPP/LTCAT",
        "modules": ["aposentadoria_especial", "qualificacao"],
        "signals": ["perfil profissiografico", "ppp", "ltcat", "agente nocivo"],
    },
    "LAUDO_MEDICO": {
        "label": "Laudo Medico",
        "modules": ["auxilio_doenca", "invalidez", "auxilio_acidente"],
        "signals": ["laudo medico", "relatorio medico", "cid", "crm"],
    },
    "CADUNICO": {
        "label": "CadUnico",
        "modules": ["bpc_loas", "qualificacao"],
        "signals": ["cadunico", "cadunico", "nis", "renda familiar", "grupo familiar"],
    },
    "CARTA_CONCESSAO": {
        "label": "Carta de Concessao",
        "modules": ["revisao_beneficio", "qualificacao"],
        "signals": ["carta de concessao", "numero do beneficio", "memoria de calculo", "rmi"],
    },
}


def classify_document(file_name: str, raw_text: str) -> dict[str, Any]:
    """Classify locally by OCR text before choosing a field schema or legal module."""
    normalized = f"{file_name}\n{raw_text}".casefold()
    ranked: list[tuple[int, str, list[str]]] = []
    for code, definition in DOCUMENT_DEFINITIONS.items():
        evidence = [signal for signal in definition["signals"] if signal.casefold() in normalized]
        if evidence:
            ranked.append((len(evidence), code, evidence))
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
        "confidence": round(min(0.95, 0.45 + score * 0.16), 2),
        "evidence": evidence,
        "modules": definition["modules"],
    }


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
        ]
    elif document_code == "CNH":
        specific = [("numero_cnh", "Numero da CNH", extract_cnh_number(raw_text))]
    elif document_code == "CNIS":
        specific = [
            ("nit", "NIT/PIS", first_valid_nit(raw_text)),
            ("competencias", "Competencias", extract_competencies(raw_text)),
            ("indicadores", "Indicadores INSS", summarize_keywords(raw_text, "indicadores")),
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
        r"(?:rg|registro geral)\s*[:\-]?\s*(\d{5,12})",
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
    match = re.search(r"(?:registro|cnh)\s*[:\-]?\s*(\d{9,12})", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def extract_cnis_vinculos(raw_text: str) -> list[dict[str, Any]]:
    """Extract employer blocks only when the OCR supplied labelled evidence."""
    labels = re.compile(
        r"(?im)^(?:empregador|empresa|raz[aã]o\s+social|nome\s+do\s+empregador)\s*[:\-]\s*(?P<name>[^\n\r]+)"
    )
    matches = list(labels.finditer(raw_text))
    indicator_pattern = re.compile(r"\b(?:PEXT|PREM|IREC|PADM|AEXT|ACNIS|IDINV|PEND)\b", re.IGNORECASE)
    result: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else min(len(raw_text), match.end() + 1400)
        block = raw_text[match.start():end]
        employer = normalize_whitespace(match.group("name")).strip(" .;|")[:180]
        start = search_labeled_date(block, ["admissão", "admissao", "início", "inicio", "data início", "data inicio"])
        finish = search_labeled_date(block, ["rescisão", "rescisao", "término", "termino", "fim", "data fim", "data saída", "data saida"])
        cnpj = first_valid_identifier(block, "cnpj")
        indicators = list(dict.fromkeys(item.upper() for item in indicator_pattern.findall(block)))
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
    return result


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
            "nome do requerente", "nome completo", "nome",
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
    forbidden = {"DOC", "DOCUMENTO", "IDENTIDADE", "ORGAO", "EMISSOR", "UF", "DATA", "NASCIMENTO"}
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
