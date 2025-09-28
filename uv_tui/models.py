"""Data models used by the uv-tui application."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class CommandResult:
    """Represents the result of a subprocess command."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0


@dataclass
class Dependency:
    """Represents a single Python dependency."""

    name: str
    version: str


@dataclass
class Project:
    """Represents a managed Python project."""

    name: str
    path: Path
    description: str = ""
    verision: str = "0.1.0"
    status: str = "Unknown"
    python_version: str = "N/A"
    dependencies: List[Dependency] = field(default_factory=list)

    def __post_init__(self):
        self.path = self.path.expanduser().resolve()

__all__ = ["CommandResult", "Dependency", "Project"]
