"""Custom widgets used by the uv-tui application."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Label, ListItem

from .models import Project


class ProjectListItem(ListItem):
    """A widget to display a project in the main list."""

    def __init__(self, project: Project) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        python = self.project.python_version.replace(">=", "")
        yield Horizontal(
            Label(f"[b]{self.project.name}[/b]", classes="project-name"),
            Label(f"  {python}", classes="project-python"),
        )


__all__ = ["ProjectListItem"]
