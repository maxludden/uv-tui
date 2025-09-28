"""Textual screens for the uv-tui application."""

from typing import Any, Optional, cast

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import Reactive, reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    TabbedContent,
    TabPane,
)

from .dialogs import AddDependencyDialog, ErrorDialog
from .models import Project


class ProjectDetailScreen(Screen):
    """The screen for managing a single project."""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle dark mode"),
        ("a", "activate", "Activate project"),
        ("q", "app.pop_screen", "Back to project list"),
    ]

    project: Reactive[Optional[Project]] = reactive(None)

    class LogLine(Message):
        """A message carrying a single log line for the Logs tab."""

        def __init__(self, line: str) -> None:
            self.line = line
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        if self.project:
            with TabbedContent(initial="dependencies"):
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
        else:
            yield Label("No project selected.")
        yield Footer()

    async def on_mount(self) -> None:
        """When the screen mounts, set the application title for the current project
        and refresh the dependencies table."""
        if self.project:
            # Header widget doesn't expose a public 'title' attribute; set the app title instead,
            # which the Header will display.
            try:
                self.app.title = f"Project: {self.project.name}"
            except AttributeError:
                pass
            await self.update_dependencies_table()

    async def update_dependencies_table(self) -> None:
        """Refresh the dependencies DataTable for the current project.

        Retrieves the dependency list from the application's uv_executor and repopulates
        the table shown in the Dependencies tab.
        """
        if not self.project:
            return

        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("Package", "Version")

        executor = cast(Any, self.app).uv_executor
        dependencies = await executor.list_dependencies(self.project.path)
        self.project.dependencies = dependencies or []
        for dep in self.project.dependencies:
            table.add_row(dep.name, dep.version)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events for project actions (add/remove dependencies,
        sync environment, and run commands)."""
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
                    # Construct a Coordinate instance compatible with DataTable.get_cell_at.
                    # Prefer the DataTable's own Coordinate type if available.
                    coord_type = getattr(table, "Coordinate", None) or getattr(
                        type(table), "Coordinate", None
                    )
                    if coord_type:
                        coord = coord_type(table.cursor_row, 0)
                    else:
                        # Fallback: try to use the table's cursor_coordinate and set its column,
                        # or fall back to a plain tuple at runtime (the DataTable accepts this).
                        cursor_coord = getattr(table, "cursor_coordinate", None)
                        if cursor_coord is not None:
                            # Use the _replace method if present; allow the outer exception handler
                            # to catch AttributeError/TypeError if calling _replace fails.
                            replace = getattr(cursor_coord, "_replace", None)
                            if replace is not None:
                                coord = replace(column=0)  # type: ignore[attr-defined]
                            else:
                                coord = cursor_coord
                        else:
                            coord = (table.cursor_row, 0)  # runtime fallback
                    package_to_remove = table.get_cell_at(cast(Any, coord))
                except (IndexError, KeyError, TypeError, AttributeError):
                    # Be explicit about the exceptions we expect when accessing a cell.
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
        """Append a received log line to the Logs widget."""
        try:
            self.query_one(Log).write_line(message.line)
        except (LookupError, AttributeError):
            # Log widget not found or doesn't provide write_line; ignore silently.
            pass


__all__ = ["ProjectDetailScreen"]
