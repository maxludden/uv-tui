from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple
from toml import load as toml_load, TomlDecodeError
from json import load, dump

from pydantic import BaseModel, Field
from rich.console import Console
from loguru import Logger

from uv_tui.config.log import get_console, get_logger, get_progress

console: Console = get_console()
log: Logger = get_logger()

class Project(BaseModel):
    """A uv managaged python project."""
    name: str = Field(..., title="Name", description="The name of the project.")
    version: str = Field(
        ...,
        title="Version",
        description="The version of the project.",
        pattern=r"^\d+\.\d+\.\d+$")


def get_projects_dir() -> Path:
    with open("static/json/packages.json", "r") as f:
        packages_dict: Dict[str, Any] = load(f)
        return Path(packages_dict["projects_dir"])

def get_pyproject(project_dir: Path) -> Dict[str, Any]:
    """Get the metadata of a project.

    Args:
        project_dir (Path): The directory of the project.

    Returns:
        Dict[str, Any]: The metadata of the project.
    """
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory {project_dir} does not exist.")

    # python
    pyproject_toml_path: Path = project_dir / "pyproject.toml"
    if not pyproject_toml_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found in {project_dir}")
    with open(pyproject_toml_path, "r") as infile:
        try:
            pyproject_toml: Dict[str, Any] = toml_load(infile)
            return pyproject_toml
        except TomlDecodeError as tde:
            raise
        except Exception as e:
            raise ValueError(f"Error reading pyproject.toml: {e}")
