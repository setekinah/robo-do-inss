"""Centraliza os caminhos dos dados operacionais e migra dados portáteis legados."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterable, Mapping
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_DATA_FOLDER = "Robo do INSS"


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def resolve_data_dir(
    environ: Mapping[str, str] | None = None,
    base_dir: Path | None = None,
) -> Path:
    """Resolve um único diretório gravável para banco, configurações e documentos.

    ``ROBO_INSS_DATA_DIR`` é útil para instalações portáteis e testes. Sem ele,
    o Windows usa LocalAppData; se indisponível, mantém o modo portátil em
    ``data/`` no diretório da aplicação.
    """
    environment = os.environ if environ is None else environ
    project_dir = BASE_DIR if base_dir is None else Path(base_dir)
    configured = environment.get("ROBO_INSS_DATA_DIR")
    local_app_data = environment.get("LOCALAPPDATA")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    if local_app_data:
        candidates.append(Path(local_app_data) / APP_DATA_FOLDER / "data")
    candidates.append(project_dir / "data")

    for candidate in candidates:
        if _is_writable(candidate):
            return candidate
    # A última tentativa preserva o contrato da função mesmo em ambientes
    # extremamente restritos; a escrita posterior apresentará o erro real.
    return project_dir / "data"


def migrate_legacy_data(target_dir: Path, legacy_dirs: Iterable[Path] | None = None) -> list[Path]:
    """Copia dados legados ausentes sem substituir a instalação atual.

    A origem é preservada e arquivos já existentes no destino nunca são
    alterados. O retorno lista apenas os arquivos efetivamente migrados.
    """
    target_dir = Path(target_dir)
    source_dirs = list(legacy_dirs) if legacy_dirs is not None else [BASE_DIR / "data"]
    migrated: list[Path] = []
    for source_dir in source_dirs:
        source_dir = Path(source_dir)
        if not source_dir.exists() or source_dir.resolve() == target_dir.resolve():
            continue
        for source in source_dir.rglob("*"):
            if not source.is_file():
                continue
            relative_path = source.relative_to(source_dir)
            destination = target_dir / relative_path
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            migrated.append(destination)
    return migrated


DATA_DIR = resolve_data_dir()
migrate_legacy_data(DATA_DIR)
