"""Backups locais verificáveis do diretório operacional.

Os arquivos permanecem no computador do escritório. A restauração só aceita
arquivos criados por este serviço e bloqueia caminhos inseguros no ZIP.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path


BACKUP_FORMAT = "robo-inss-backup-v1"
MANIFEST_NAME = "manifest.json"
BACKUPS_DIR_NAME = "backups"


def _archive_name(now: datetime | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"robo-inss-backup-{timestamp}.zip"


def _is_safe_member(name: str) -> bool:
    path = Path(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and not name.startswith("/")


def create_backup(data_dir: Path, now: datetime | None = None) -> Path:
    """Cria ZIP com todos os dados operacionais, exceto backups anteriores."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = data_dir / BACKUPS_DIR_NAME
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / _archive_name(now)
    manifest = {"format": BACKUP_FORMAT, "created_at": (now or datetime.now()).isoformat(timespec="seconds")}
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, __import__("json").dumps(manifest, ensure_ascii=False))
        for source in sorted(data_dir.rglob("*")):
            if not source.is_file() or backup_dir in source.parents:
                continue
            archive.write(source, source.relative_to(data_dir).as_posix())
    return backup_path


def validate_backup(content: bytes) -> list[str]:
    """Valida estrutura e devolve os arquivos que serão restaurados."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            if MANIFEST_NAME not in names or any(not _is_safe_member(name) for name in names):
                raise ValueError("Arquivo de backup inválido ou inseguro.")
            import json
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
            if manifest.get("format") != BACKUP_FORMAT:
                raise ValueError("Este arquivo não é um backup compatível do Robo do INSS.")
            return [name for name in names if name != MANIFEST_NAME and not name.endswith("/")]
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"Backup inválido: {error}") from error


def restore_backup(data_dir: Path, content: bytes) -> list[Path]:
    """Restaura arquivos validados; uma cópia preventiva é criada antes da alteração."""
    files = validate_backup(content)
    data_dir = Path(data_dir)
    create_backup(data_dir)
    restored: list[Path] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in files:
            target = data_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("wb") as destination:
                destination.write(source.read())
            restored.append(target)
    return restored
