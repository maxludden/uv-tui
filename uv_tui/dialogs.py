"""Modal dialog definitions."""
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static


class ErrorDialog(ModalScreen):
    """A simple modal for displaying error messages."""

    def __init__(self, message: str) -> None:
        """Initialize the error dialog with a message."""
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        """Compose the widgets for the error dialog."""
        with Vertical(id="dialog", classes="error-dialog"):
            yield Label("Error")
            yield Static(self.message)
            yield Button("OK", variant="primary")

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        """Handle button presses in the error dialog by closing the modal."""
        self.app.pop_screen()


class NewProjectDialog(ModalScreen[dict]):
    """A modal dialog for creating a new project."""

    def compose(self) -> ComposeResult:
        """Compose the widgets required to create a new project."""
        with Vertical(id="dialog"):
            yield Label("Create New Project")
            yield Input(placeholder="Project Name", id="name")
            yield Horizontal(
                Button("Create", variant="primary", id="create"),
                Button("Cancel", id="cancel"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Create/Cancel button presses and validate the project name."""
        if event.button.id == "create":
            name = self.query_one("#name", Input).value
            if name:
                self.dismiss({"name": name})
            else:
                self.app.push_screen(ErrorDialog("Project name cannot be empty."))
        else:
            self.dismiss({})


class AddDependencyDialog(ModalScreen[dict]):
    """A modal dialog for adding a new dependency."""

    def compose(self) -> ComposeResult:
        """Compose widgets for adding a dependency."""
        with Vertical(id="dialog"):
            yield Label("Add Dependency")
            yield Input(placeholder="e.g., requests or 'requests>=2.0'", id="package")
            yield Checkbox("Development dependency (--dev)", id="is_dev")
            yield Horizontal(
                Button("Add", variant="primary", id="add"),
                Button("Cancel", id="cancel"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Add/Cancel presses and validate the package field."""
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
    """A high-friction confirmation dialog for project deletion."""

    def __init__(self, project_name: str) -> None:
        """Initialize the delete confirmation dialog with the project name."""
        super().__init__()
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        """Compose widgets that ask the user to confirm project deletion."""
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
        """Enable the Delete button only when the confirmation input matches the project name."""
        is_match = event.value == self.project_name
        try:
            self.query_one("#delete", Button).disabled = not is_match
        except LookupError:
            # query_one raises LookupError when the selector does not match any widget;
            # ignore that case as it simply means the delete button isn't present yet.
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Delete/Cancel presses and dismiss the dialog with a boolean result."""
        if event.button.id == "delete":
            self.dismiss(True)
        else:
            self.dismiss(False)


__all__ = [
    "ErrorDialog",
    "NewProjectDialog",
    "AddDependencyDialog",
    "DeleteProjectDialog",
]
