"""Application configuration helpers and constants.

This module centralises configuration loading so uv-tui can determine runtime
paths from defaults, ``config.toml``, or environment overrides. The
``PROJECTS_ROOT`` path drives project discovery.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_PROJECTS_ROOT = Path.home() / "dev" / "py"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"


def _load_config_toml(path: Path) -> Dict[str, Any]:
    """Load configuration values from ``config.toml`` if present."""

    if not path.exists():
        return {}
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _resolve_projects_root() -> Path:
    """Resolve the projects root from defaults, config file, and env overrides."""

    config = _load_config_toml(CONFIG_PATH)
    file_value = (
        config.get("paths", {}).get("projects_root")
        if isinstance(config, dict)
        else None
    )
    env_value = os.environ.get("UV_PROJECTS_ROOT")

    for candidate in (env_value, file_value, DEFAULT_PROJECTS_ROOT):
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        try:
            return path.resolve()
        except OSError:
            return path

    return DEFAULT_PROJECTS_ROOT


PROJECTS_ROOT = _resolve_projects_root()

__all__ = ["PROJECTS_ROOT", "DEFAULT_PROJECTS_ROOT", "CONFIG_PATH"]
