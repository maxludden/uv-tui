"""Data models used by the uv-tui application.

This module defines lightweight dataclasses that represent the outcome of uv
commands, dependency rows, and high-level project metadata. These data
structures are passed between the UI layer and the asynchronous executor
workers.
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class CommandResult:
    """Represents the result of a subprocess command.

    Attributes:
        success (bool): ``True`` when the command exited with status ``0``.
        stdout (str): Captured standard output.
        stderr (str): Captured standard error.
        return_code (int): Numeric exit status provided by the process.
    """

    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0


@dataclass
class Dependency:
    """Describes a single Python dependency installed in a project.

    Attributes:
        name (str): Distribution name reported by ``uv pip list``.
        version (str): Resolved version string associated with the dependency.
    """

    name: str
    version: str


@dataclass
class Project:
    """Represents a managed Python project discovered by uv-tui.

    Attributes:
        name (str): Folder / package name of the project.
        path (Path): Absolute filesystem path to the project root.
        description (str): ``pyproject.toml`` description, if provided.
        version (str): Project version string sourced from ``pyproject.toml``.
        status (str): Derived status message (e.g. virtual environment state).
        python_version (str): Required Python version specifier.
        dependencies (List[Dependency]): Cached dependencies returned by uv.
        last_modified (Optional[datetime]): Timestamp of the ``pyproject`` file.
        primary_dependencies (List[str]): Declared dependency strings from
            ``pyproject.toml``.
    """

    name: str
    path: Path
    description: str = ""
    version: str = "0.1.0"
    status: str = "Unknown"
    python_version: str = "N/A"
    dependencies: List[Dependency] = field(default_factory=list)
    last_modified: Optional[datetime] = None
    primary_dependencies: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalise the stored path to an absolute location.

        Returns:
            None
        """

        self.path = self.path.expanduser().resolve()

__all__ = ["CommandResult", "Dependency", "Project"]
