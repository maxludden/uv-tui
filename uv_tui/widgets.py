"""Custom widgets used by the uv-tui application.

This module defines bespoke Textual widgets that extend the framework's
built-in components. They render project lists, project metadata, and provide a
rich detail view for interacting with the uv-backed environment.
"""

import asyncio
from typing import Any, Optional, Tuple, cast
from packaging.requirements import Requirement, InvalidRequirement
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
    TabbedContent,
    TabPane,
)

from .dialogs import AddDependencyDialog, ErrorDialog
from .models import Project


def _split_dependency_spec(spec: str) -> Tuple[str, str, str]:
    """Split a dependency requirement into name, operator, and version strings.

    Args:
        spec (str): Requirement string pulled from ``pyproject.toml``.

    Returns:
        Tuple[str, str, str]: Name, comparison operator, and version token. When
        the specifier is absent the operator and version will be empty strings.
    """

    spec = spec.strip()
    if not spec:
        return ("Unknown", "", "")

    try:
        requirement = Requirement(spec)
        specifiers_iter = iter(requirement.specifier)
        first_spec = next(specifiers_iter, None)
        if first_spec is not None:
            return (
                requirement.name,
                first_spec.operator,
                first_spec.version or "",
            )
        return (requirement.name, "", "")
    except InvalidRequirement:  # pragma: no cover - fall back to heuristic parsing.
        pass

    operators = ["===", "==", "!=", "<=", ">=", "~=", "<", ">"]
    for operator in operators:
        if operator in spec:
            name, version = spec.split(operator, 1)
            return (name.strip(), operator, version.strip())

    return (spec, "", "")


def _ensure_overview_columns(table: DataTable) -> None:
    """Ensure the overview dependency table has the expected columns."""

    column_count = getattr(table, "column_count", None)
    if column_count is None:
        columns = getattr(table, "columns", None)
        column_count = len(columns) if columns is not None else 0
    if column_count == 0:
        table.add_columns("Dependency", "Operator", "Version")


class ProjectListItem(ListItem):
    """List item that displays a project's high-level metadata."""

    def __init__(self, project: Project) -> None:
        """Store the project to be rendered inside the list item.

        Args:
            project (Project): Project instance that this list item represents.

        Returns:
            None
        """

        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        """Render the child widgets that make up the list row.

        Returns:
            ComposeResult: Labels describing the project name and recorded
            version.
        """

        version = self.project.version or "0.1.0"
        yield Horizontal(
            Label(f"[b]{self.project.name}[/b]", classes="project-name"),
            Label(f"  [dim]v[/dim]{version}", classes="project-version", markup=True),
        )


class ProjectDetailView(Vertical):
    """Panel that surfaces the currently selected project's details and actions."""

    DEFAULT_CSS = "#project-tabs { height: 1fr; }"

    class LogLine(Message):
        """Message type used to stream log output into the detail view."""

        def __init__(self, line: str) -> None:
            """Capture the rendered log line text.

            Args:
                line (str): Rich-formatted log message.

            Returns:
                None
            """

            self.line = line
            super().__init__()

    def __init__(self) -> None:
        """Initialise child references used for efficient updates.

        Returns:
            None
        """

        super().__init__(id="project-detail")
        self.project: Optional[Project] = None
        self._placeholder: Optional[Static] = None
        self._content: Optional[Vertical] = None
        self._title: Optional[Static] = None
        self._description: Optional[Static] = None
        self._meta: Optional[Static] = None
        self._tabs: Optional[TabbedContent] = None
        self._overview_version: Optional[Static] = None
        self._overview_python: Optional[Static] = None
        self._overview_dependencies: Optional[DataTable] = None
        self._dependencies_table: Optional[DataTable] = None

    def compose(self) -> ComposeResult:
        """Create the container layout for the detail view.

        Returns:
            ComposeResult: The placeholder and tabbed content widgets that make
            up the detail pane.
        """

        yield Static(
            "Select a project from the list to view details.",
            id="detail-placeholder",
        )
        with Vertical(id="detail-content"):
            yield Static("", id="project-title", classes="project-title")
            yield Static(
                "",
                id="project-description",
                classes="project-description",
                markup=True,
            )
            yield Static("", id="project-meta", classes="project-meta")
            with TabbedContent(initial="overview", id="project-tabs"):
                with TabPane("Overview", id="overview"):
                    with Vertical(id="overview-content"):
                        yield Static("", id="overview-version")
                        yield Static("", id="overview-python")
                        yield DataTable(id="overview-dependencies")
                        with Horizontal(id="overview-actions"):
                            yield Button("Open in VS Code", id="open-vscode")
                            yield Button(
                                "Delete Project",
                                id="request-delete",
                                variant="error",
                            )
                with TabPane("Dependencies", id="dependencies"):
                    yield DataTable(id="project-dependencies")
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
        """Cache widget references and ensure initial visibility state.

        Returns:
            None
        """
        self._placeholder = self.query_one("#detail-placeholder", Static)
        self._content = self.query_one("#detail-content", Vertical)
        self._title = self.query_one("#project-title", Static)
        self._description = self.query_one("#project-description", Static)
        self._meta = self.query_one("#project-meta", Static)
        self._tabs = self.query_one("#project-tabs", TabbedContent)
        self._overview_version = self.query_one("#overview-version", Static)
        self._overview_python = self.query_one("#overview-python", Static)
        self._overview_dependencies = self.query_one(
            "#overview-dependencies", DataTable
        )
        self._dependencies_table = self.query_one("#project-dependencies", DataTable)
        if self._overview_dependencies:
            _ensure_overview_columns(self._overview_dependencies)
        if self._tabs:
            self._tabs.display = False
        self._update_visibility()
        if self.project:
            self._update_overview(self.project)
            asyncio.create_task(self.update_dependencies_table())

    def show_project(self, project: Optional[Project]) -> None:
        """Display the supplied project within the detail panel.

        Args:
            project (Optional[Project]): Project that should be surfaced. ``None``
                hides the detail view until a selection is made.

        Returns:
            None
        """
        self.project = project
        self._update_visibility()
        if project:
            self._clear_tables()
            try:
                self.app.title = f"Project: {project.name}"
            except AttributeError:
                pass
            self._update_header(project)
            self._update_overview(project)
            asyncio.create_task(self.update_dependencies_table())
        else:
            try:
                self.app.title = "uv-tui"
            except AttributeError:
                pass
            self._clear_tables()
            self._reset_header()
            self._reset_overview()

    def _update_visibility(self) -> None:
        """Toggle UI elements based on whether a project is selected.

        Returns:
            None
        """

        if not self._placeholder or not self._tabs or not self._content:
            return
        is_project_selected = self.project is not None
        self._placeholder.display = not is_project_selected
        self._content.display = is_project_selected
        self._tabs.display = is_project_selected

    def _update_header(self, project: Project) -> None:
        """Update the textual header for the currently selected project.

        Args:
            project (Project): Active project whose name, description, and last
                modified timestamp should be displayed.

        Returns:
            None
        """

        if self._title:
            self._title.update(f"[b]{project.name}[/b]")
        if self._description:
            description = str(project.description or "").strip()
            if not description:
                description = "No description provided."
            self._description.update(f"[i]{description}[/i]")
        if self._meta:
            if project.last_modified:
                formatted = project.last_modified.strftime("%b %d, %Y %I:%M %p %Z")
                meta_text = f"Last edited: {formatted}"
            else:
                meta_text = "Last edited: Unknown"
            self._meta.update(meta_text)

    def _update_overview(self, project: Project) -> None:
        """Populate the Overview tab with high-level project metadata.

        Args:
            project (Project): Project providing version, Python requirement,
                and declared dependencies.

        Returns:
            None
        """

        if self._overview_version:
            self._overview_version.update(f"Version: {project.version}")
        if self._overview_python:
            python_text = project.python_version or "Unknown"
            self._overview_python.update(f"Python Requirement: {python_text}")
        if self._overview_dependencies:
            table = self._overview_dependencies
            table.clear(columns=True)
            _ensure_overview_columns(table)
            if project.primary_dependencies:
                for dependency in project.primary_dependencies:
                    name, operator, version = _split_dependency_spec(dependency)
                    table.add_row(name, operator, version)
            else:
                table.add_row("No dependencies declared.", "", "")

    def _reset_header(self) -> None:
        """Clear the header widgets when no project is selected.

        Returns:
            None
        """

        if self._title:
            self._title.update("")
        if self._description:
            self._description.update("")
        if self._meta:
            self._meta.update("")

    def _reset_overview(self) -> None:
        """Clear the Overview panel when no project is selected.

        Returns:
            None
        """

        if self._overview_version:
            self._overview_version.update("")
        if self._overview_python:
            self._overview_python.update("")
        if self._overview_dependencies:
            self._overview_dependencies.clear(columns=True)
            _ensure_overview_columns(self._overview_dependencies)

    def _clear_tables(self) -> None:
        """Empty the dependency and log tables prior to refresh.

        Returns:
            None
        """

        if self._dependencies_table:
            self._dependencies_table.clear(columns=True)
        try:
            self.query_one(Log).clear()
        except (LookupError, AttributeError):
            pass

    async def update_dependencies_table(self) -> None:
        """Refresh the dependency table to reflect the current project.

        Returns:
            None
        """
        current_project = self.project
        if not current_project:
            return

        table = self._dependencies_table
        if table is None:
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
        """Respond to button presses emitted from the detail panel.

        Args:
            event (Button.Pressed): Textual event triggered by the pressed
                button.

        Returns:
            None
        """
        if not self.project:
            return

        if event.button.id == "open-vscode":
            cast(Any, self.app).activate_and_open_worker(self.project)

        elif event.button.id == "request-delete":
            cast(Any, self.app).action_delete_project()

        elif event.button.id == "add-dep":

            def callback(data: Any) -> None:
                if data:
                    cast(Any, self.app).add_dependency_worker(
                        self.project, data["package"], data["is_dev"]
                    )

            self.app.push_screen(AddDependencyDialog(), callback=callback)

        elif event.button.id == "remove-dep":
            table = self._dependencies_table
            if not table:
                self.app.push_screen(ErrorDialog("No dependency selected."))
                return
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
        """Append a log line to the Logs tab.

        Args:
            message (ProjectDetailView.LogLine): Message containing the log
                content to render.

        Returns:
            None
        """
        try:
            self.query_one(Log).write_line(message.line)
        except (LookupError, AttributeError):
            pass


__all__ = ["ProjectListItem", "ProjectDetailView"]
