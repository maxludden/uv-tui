"""Modal dialog definitions.

These dialogs provide consistent UI affordances for error reporting,
project creation, dependency management, and destructive confirmations.
"""
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static


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


class NewProjectDialog(ModalScreen[dict]):
    """Modal dialog that collects details required to create a new project."""

    def compose(self) -> ComposeResult:
        """Compose the widgets required to create a new project.

        Returns:
            ComposeResult: Controls for entering a name and confirming/cancelling.
        """
        with Vertical(id="dialog"):
            yield Label("Create New Project")
            yield Input(placeholder="Project Name", id="name")
            yield Horizontal(
                Button("Create", variant="primary", id="create"),
                Button("Cancel", id="cancel"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle Create/Cancel button presses and validate the project name.

        Args:
            event (Button.Pressed): Event emitted by the pressed button.

        Returns:
            None
        """
        if event.button.id == "create":
            name = self.query_one("#name", Input).value
            if name:
                self.dismiss({"name": name})
            else:
                self.app.push_screen(ErrorDialog("Project name cannot be empty."))
        else:
            self.dismiss({})


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


__all__ = [
    "ErrorDialog",
    "NewProjectDialog",
    "AddDependencyDialog",
    "DeleteProjectDialog",
]
