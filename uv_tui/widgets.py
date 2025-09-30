"""Custom widgets used by the uv-tui application."""

import asyncio
from typing import Any, Optional, cast

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    ListItem,
    Log,
    Static,
    TabPane,
    TabbedContent,
)

from .dialogs import AddDependencyDialog, ErrorDialog
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


class ProjectDetailView(Vertical):
    """Panel that displays details for the currently selected project."""

    DEFAULT_CSS = "#project-tabs { height: 1fr; }"

    class LogLine(Message):
        """Message carrying a single log line for the Logs tab."""

        def __init__(self, line: str) -> None:
            self.line = line
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="project-detail")
        self.project: Optional[Project] = None
        self._placeholder: Optional[Static] = None
        self._content: Optional[Vertical] = None
        self._title: Optional[Static] = None
        self._description: Optional[Static] = None
        self._meta: Optional[Static] = None
        self._tabs: Optional[TabbedContent] = None

    def compose(self) -> ComposeResult:
        yield Static(
            "Select a project from the list to view details.",
            id="detail-placeholder",
        )
        with Vertical(id="detail-content"):
            yield Static("", id="project-title")
            yield Static("", id="project-description", markup=False)
            yield Static("", id="project-meta")
            with TabbedContent(initial="dependencies", id="project-tabs"):
                with TabPane("Dependencies", id="dependencies"):
                    yield DataTable()
                    with Horizontal(classes="button-bar"):
                        yield Button("Add Dependency", id="add-dep")
                        yield Button("Remove Selected", id="remove-dep")
                        yield Button("Sync Environment", id="sync-env")
                with TabPane("Logs", id="logs"):
                    yield Log(highlight=True)
                with TabPane("Commands", id="commands"):
                    yield Label(
                        "Run a command in the project environment (e.g., ruff check.)"
                    )
                    yield Input(placeholder="<command>", id="run-command-input")
                    yield Button("Run", id="run-command-button")

    def on_mount(self) -> None:
        """Cache widget references and ensure initial visibility state."""
        self._placeholder = self.query_one("#detail-placeholder", Static)
        self._content = self.query_one("#detail-content", Vertical)
        self._title = self.query_one("#project-title", Static)
        self._description = self.query_one("#project-description", Static)
        self._meta = self.query_one("#project-meta", Static)
        self._tabs = self.query_one("#project-tabs", TabbedContent)
        if self._tabs:
            self._tabs.display = False
        self._update_visibility()

    def show_project(self, project: Optional[Project]) -> None:
        """Display the given project in the detail panel."""
        self.project = project
        self._update_visibility()
        if project:
            self._clear_tables()
            try:
                self.app.title = f"Project: {project.name}"
            except AttributeError:
                pass
            self._update_header(project)
            asyncio.create_task(self.update_dependencies_table())
        else:
            try:
                self.app.title = "uv-tui"
            except AttributeError:
                pass
            self._clear_tables()
            self._reset_header()

    def _update_visibility(self) -> None:
        if not self._placeholder or not self._tabs or not self._content:
            return
        is_project_selected = self.project is not None
        self._placeholder.display = not is_project_selected
        self._content.display = is_project_selected
        self._tabs.display = is_project_selected

    def _update_header(self, project: Project) -> None:
        if self._title:
            self._title.update(f"[b]{project.name}[/b]")
        if self._description:
            description = str(project.description or "").strip()
            if not description:
                description = "No description provided."
            self._description.update(description)
        if self._meta:
            if project.last_modified:
                formatted = project.last_modified.strftime("%b %d, %Y %I:%M %p %Z")
                meta_text = f"Last edited: {formatted}"
            else:
                meta_text = "Last edited: Unknown"
            self._meta.update(meta_text)

    def _reset_header(self) -> None:
        if self._title:
            self._title.update("")
        if self._description:
            self._description.update("")
        if self._meta:
            self._meta.update("")

    def _clear_tables(self) -> None:
        try:
            self.query_one(DataTable).clear(columns=True)
        except (LookupError, AttributeError):
            pass
        try:
            self.query_one(Log).clear()
        except (LookupError, AttributeError):
            pass

    async def update_dependencies_table(self) -> None:
        """Refresh the dependency table to reflect the current project."""
        current_project = self.project
        if not current_project:
            return

        try:
            table = self.query_one(DataTable)
        except LookupError:
            return

        table.clear(columns=True)
        table.add_columns("Package", "Version")

        executor = cast(Any, self.app).uv_executor
        dependencies = await executor.list_dependencies(current_project.path)

        if self.project is not current_project:
            return

        current_project.dependencies = dependencies or []
        for dep in current_project.dependencies:
            table.add_row(dep.name, dep.version)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button actions within the detail panel."""
        if not self.project:
            return

        if event.button.id == "add-dep":

            def callback(data: Any) -> None:
                if data:
                    cast(Any, self.app).add_dependency_worker(
                        self.project, data["package"], data["is_dev"]
                    )

            self.app.push_screen(AddDependencyDialog(), callback=callback)

        elif event.button.id == "remove-dep":
            table = self.query_one(DataTable)
            if table.cursor_row is not None and table.cursor_row >= 0:
                try:
                    coord_type = getattr(table, "Coordinate", None) or getattr(
                        type(table), "Coordinate", None
                    )
                    if coord_type:
                        coord = coord_type(table.cursor_row, 0)
                    else:
                        cursor_coord = getattr(table, "cursor_coordinate", None)
                        if cursor_coord is not None:
                            replace = getattr(cursor_coord, "_replace", None)
                            if replace is not None:
                                coord = replace(column=0)  # type: ignore[attr-defined]
                            else:
                                coord = cursor_coord
                        else:
                            coord = (table.cursor_row, 0)
                    package_to_remove = table.get_cell_at(cast(Any, coord))
                except (IndexError, KeyError, TypeError, AttributeError):
                    package_to_remove = None
                if package_to_remove:
                    cast(Any, self.app).remove_dependency_worker(
                        self.project, package_to_remove
                    )
                else:
                    self.app.push_screen(ErrorDialog("No dependency selected."))
            else:
                self.app.push_screen(ErrorDialog("No dependency selected."))

        elif event.button.id == "sync-env":
            cast(Any, self.app).sync_worker(self.project)

        elif event.button.id == "run-command-button":
            command = self.query_one("#run-command-input", Input).value
            if command:
                cast(Any, self.app).run_command_worker(self.project, command)
            else:
                self.app.push_screen(ErrorDialog("Command cannot be empty."))

    def on_log_line(self, message: LogLine) -> None:
        """Append a log line to the Logs tab."""
        try:
            self.query_one(Log).write_line(message.line)
        except (LookupError, AttributeError):
            pass


__all__ = ["ProjectListItem", "ProjectDetailView"]
