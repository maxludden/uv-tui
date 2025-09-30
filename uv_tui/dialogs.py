"""Modal dialog definitions.

These dialogs provide consistent UI affordances for error reporting,
project creation, dependency management, and destructive confirmations.
"""
from typing import Dict, List, Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, SelectionList, Static, Checkbox


class ErrorDialog(ModalScreen):
    """Modal window that displays a single error message to the user."""

    def __init__(self, message: str) -> None:
        """Store the error message that should be rendered.

        Args:
            message (str): Human-readable error text to display.

        Returns:
            None
        """
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        """Compose the widgets for the error dialog.

        Returns:
            ComposeResult: Controls that make up the modal's content.
        """
        with Vertical(id="dialog", classes="error-dialog"):
            yield Label("Error")
            yield Static(self.message)
            yield Button("OK", variant="primary")

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        """Close the dialog when the acknowledgement button is pressed.

        Args:
            _event (Button.Pressed): Event emitted by the ``OK`` button.

        Returns:
            None
        """
        self.app.pop_screen()


class NewProjectDialog(ModalScreen[Dict[str, object]]):
    """Modal dialog that collects details required to create a new project."""

    LIBRARY_CHOICES: List[str] = [
        "rich",
        "rich-color-ext",
        "rich-gradient",
        "loguru",
        "openai",
        "dotenv",
        "pydantic",
        "beanie",
        "asyncio",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.selected_libraries: List[str] = []
        self._libraries_ready = False

    def compose(self) -> ComposeResult:
        """Compose the widgets required to create a new project.

        Returns:
            ComposeResult: Controls for entering metadata and launching the
            library selection dialog.
        """
        with Vertical(id="dialog"):
            yield Label("Create New Project")
            yield Input(placeholder="Project Name", id="name")
            yield Input(placeholder="Project Description", id="description")
            yield Static("No libraries selected.", id="library-summary")
            yield Horizontal(
                Button("Select Libraries", id="primary-action", variant="primary"),
                Button("Cancel", id="cancel"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Create/Cancel button presses and validate the project metadata.

        Args:
            event (Button.Pressed): Event emitted by the pressed button.

        Returns:
            None
        """
        if event.button.id == "primary-action":
            if self._libraries_ready:
                self._finalize_creation()
                return

            dialog = LibrarySelectionDialog(
                self.LIBRARY_CHOICES,
                list(self.selected_libraries),
            )

            def _callback(selection: Optional[List[str]]) -> None:
                if selection is not None:
                    self.selected_libraries = selection
                    summary = (
                        ", ".join(selection)
                        if selection
                        else "No libraries selected."
                    )
                    self.query_one("#library-summary", Static).update(summary)
                    self._libraries_ready = True
                    self.query_one("#primary-action", Button).label = "Create Project"

            self.app.push_screen(dialog, callback=_callback)
        elif event.button.id == "cancel":
            self.dismiss({})
        else:
            self.dismiss({})

    def _finalize_creation(self) -> None:
        """Validate the inputs and dismiss with project data."""

        name_input = self.query_one("#name", Input)
        desc_input = self.query_one("#description", Input)
        name = name_input.value.strip()
        description = desc_input.value.strip()

        if not name:
            self.app.push_screen(ErrorDialog("Project name cannot be empty."))
            return

        self.dismiss(
            {
                "name": name,
                "description": description,
                "libraries": list(self.selected_libraries),
            }
        )



class AddDependencyDialog(ModalScreen[dict]):
    """Modal dialog that captures information for a new dependency."""

    def compose(self) -> ComposeResult:
        """Compose widgets for adding a dependency.

        Returns:
            ComposeResult: Controls used to input dependency metadata.
        """
        with Vertical(id="dialog"):
            yield Label("Add Dependency")
            yield Input(placeholder="e.g., requests or 'requests>=2.0'", id="package")
            yield Checkbox("Development dependency (--dev)", id="is_dev")
            yield Horizontal(
                Button("Add", variant="primary", id="add"),
                Button("Cancel", id="cancel"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Add/Cancel presses and validate the package field.

        Args:
            event (Button.Pressed): Event emitted by the pressed button.

        Returns:
            None
        """
        if event.button.id == "add":
            package = self.query_one("#package", Input).value
            if package:
                self.dismiss({
                    "package": package,
                    "is_dev": self.query_one("#is_dev", Checkbox).value,
                })
            else:
                self.app.push_screen(ErrorDialog("Package name cannot be empty."))
        else:
            self.dismiss({})


class DeleteProjectDialog(ModalScreen[bool]):
    """High-friction confirmation dialog used when deleting a project."""

    def __init__(self, project_name: str) -> None:
        """Persist the project name used for confirmation checks.

        Args:
            project_name (str): Name of the project being deleted.

        Returns:
            None
        """
        super().__init__()
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        """Compose widgets that ask the user to confirm project deletion.

        Returns:
            ComposeResult: Controls for the irreversible confirmation flow.
        """
        with Vertical(id="dialog"):
            yield Label(f"Delete Project '{self.project_name}'?")
            yield Static(
                "This action is irreversible. It will permanently delete the \
project directory and its virtual environment."
            )
            yield Label(f"Type the project name to confirm: [b]{self.project_name}[/b]")
            yield Input(placeholder=self.project_name, id="confirm_name")
            yield Horizontal(
                Button("Delete", variant="error", id="delete", disabled=True),
                Button("Cancel", id="cancel"),
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Enable the Delete button only when the confirmation input matches.

        Args:
            event (Input.Changed): Event describing the new input value.

        Returns:
            None
        """
        is_match = event.value == self.project_name
        try:
            self.query_one("#delete", Button).disabled = not is_match
        except LookupError:
            # query_one raises LookupError when the selector does not match any widget;
            # ignore that case as it simply means the delete button isn't present yet.
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Delete/Cancel presses and dismiss with a boolean result.

        Args:
            event (Button.Pressed): Event emitted by the pressed button.

        Returns:
            None
        """
        if event.button.id == "delete":
            self.dismiss(True)
        else:
            self.dismiss(False)


class LibrarySelectionDialog(ModalScreen[List[str]]):
    """Modal dialog for selecting optional libraries to install."""

    def __init__(self, libraries: List[str], preselected: List[str]) -> None:
        super().__init__()
        self._libraries = libraries
        self._preselected = set(preselected)

    def compose(self) -> ComposeResult:
        """Build the selection list interface."""
        with Vertical(id="dialog"):
            yield Label("Choose Libraries to Install")
            selection = SelectionList[str](id="library-selection")
            for library in self._libraries:
                selection.add_option((library, library))
            yield selection
            yield Horizontal(
                Button("Done", variant="primary", id="confirm-selection"),
                Button("Cancel", id="cancel-selection"),
            )

    def on_mount(self) -> None:
        """Apply the initial preselected state."""
        selection = self.query_one("#library-selection", SelectionList)
        for value in self._preselected:
            try:
                selection.select(value)
            except KeyError:
                continue

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle confirmation or cancellation of library selection."""
        if event.button.id == "confirm-selection":
            selection = self.query_one("#library-selection", SelectionList)
            self.dismiss(list(selection.selected))
        elif event.button.id == "cancel-selection":
            self.dismiss(None)


__all__ = [
    "ErrorDialog",
    "NewProjectDialog",
    "AddDependencyDialog",
    "DeleteProjectDialog",
    "LibrarySelectionDialog",
]
