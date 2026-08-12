"""Compatibilidade para integrações que ainda importam ``runtime_paths``."""

from data_paths import BASE_DIR, DATA_DIR, migrate_legacy_data, resolve_data_dir

__all__ = ["BASE_DIR", "DATA_DIR", "migrate_legacy_data", "resolve_data_dir"]
