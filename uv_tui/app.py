"""Core Textual application for uv-tui.

This module wires together the Textual application that powers uv-tui. It
defines the :class:`~uv_tui.app.UvTuiApp` class responsible for scanning project
directories, responding to user interactions, and orchestrating long-running
tasks such as dependency management or environment synchronisation.
"""

import asyncio
import os
import shutil
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    import tomli as tomllib  # type: ignore[no-redef]
from datetime import datetime
from pathlib import Path
from typing import List, Optional, cast

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.reactive import Reactive, reactive
from textual.widgets import Footer, Header, ListView, Log

from .config import PROJECTS_ROOT
from .dialogs import DeleteProjectDialog, ErrorDialog, NewProjectDialog
from .models import Project
from .uv_executor import UVCommandExecutor
from .widgets import ProjectDetailView, ProjectListItem


class UvTuiApp(App):
    """Textual application that presents and manages uv projects.

    The app renders a list of discovered projects, surfaces detailed
    information for the active selection, and exposes actions for modifying the
    selected project. It also coordinates asynchronous workers that invoke the
    ``uv`` command-line tool.
    """

    CSS_PATH = "/Users/maxludden/dev/py/uv-tui/uv-tui.css"
    TITLE = "uv-tui"
    SUB_TITLE = "Project Manager for astral/uv"
    BINDINGS = [
        ("n", "new_project", "New Project"),
        ("a", "activate", "Activate Project"),
        ("q", "quit", "Quit"),
    ]

    projects: Reactive[List[Project]] = reactive([])
    uv_executor = UVCommandExecutor()

    def compose(self) -> ComposeResult:
        """Create the static layout for the application.

        Returns:
            ComposeResult: A generator of root widgets (header, list/detail
            view, and footer) that Textual mounts into the DOM.
        """
        self.theme = "textual-dark"
        yield Header(show_clock=True, time_format="%I:%M %p")
        with Horizontal(id="main-content"):
            yield ListView(id="project-list")
            yield ProjectDetailView()
        yield Footer()

    async def on_mount(self) -> None:
        """Complete asynchronous initialisation once the app is mounted.

        Returns:
            None
        """
        await self.scan_projects()

    async def scan_projects(self) -> None:
        """Discover uv projects beneath :data:`uv_tui.config.PROJECTS_ROOT`.

        Iterates the configured project root, gathers metadata for directories
        that contain a ``pyproject.toml`` file, and stores the resulting
        :class:`~uv_tui.models.Project` instances in the reactive ``projects``
        list.

        Returns:
            None
        """
        found_projects: List[Project] = []
        if not PROJECTS_ROOT.exists():
            PROJECTS_ROOT.mkdir(parents=True)

        for item in PROJECTS_ROOT.iterdir():
            if item.is_dir() and (item / "pyproject.toml").exists():
                status = "Venv OK" if (item / ".venv").exists() else "Venv Missing"

                pyproject_path = item / "pyproject.toml"
                python_version = "N/A"
                description = ""
                version = "0.1.0"
                primary_dependencies: List[str] = []
                last_modified_dt: Optional[datetime] = None
                try:
                    with open(pyproject_path, "rb") as f:
                        config = tomllib.load(f)
                        project_cfg = config.get("project", {})
                        python_version = project_cfg.get("requires-python", "N/A")
                        description = project_cfg.get("description") or ""
                        version = str(project_cfg.get("version", "0.1.0"))
                        raw_deps = project_cfg.get("dependencies") or []
                        if isinstance(raw_deps, list):
                            for entry in raw_deps:
                                if isinstance(entry, str):
                                    primary_dependencies.append(entry)
                                else:
                                    primary_dependencies.append(str(entry))
                except (tomllib.TOMLDecodeError, FileNotFoundError):
                    status = "Invalid pyproject.toml"
                else:
                    try:
                        mtime = pyproject_path.stat().st_mtime
                    except OSError:
                        last_modified_dt = None
                    else:
                        last_modified_dt = datetime.fromtimestamp(mtime).astimezone()

                found_projects.append(
                    Project(
                        name=item.name,
                        path=item,
                        status=status,
                        python_version=python_version,
                        description=description,
                        version=version,
                        primary_dependencies=primary_dependencies,
                        last_modified=last_modified_dt,
                    )
                )
        self.projects = sorted(found_projects, key=lambda p: p.name)

    def watch_projects(self, *args) -> None:
        """React to changes in the ``projects`` reactive attribute.

        Args:
            *args: Either ``(new_projects,)`` or ``(old_projects, new_projects)``
                depending on the Textual version. The final positional argument
                is treated as the latest list of
                :class:`~uv_tui.models.Project` instances.

        Returns:
            None
        """
        # Determine new_projects from args
        new_projects = None
        if len(args) == 1:
            new_projects = args[0]
        elif len(args) == 2:
            new_projects = args[1]
        else:
            # Unexpected call signature; do nothing
            return

        if new_projects is None:
            return

        lv = self.query_one(ListView)
        lv.clear()
        detail_view = self.query_one(ProjectDetailView)
        for project in new_projects:
            lv.append(ProjectListItem(project))

        if new_projects:
            first_project = new_projects[0]
            self._select_project_in_list(first_project)
            detail_view.show_project(first_project)
        else:
            self._select_project_in_list(None)
            detail_view.show_project(None)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selection changes within the project list.

        Args:
            event (ListView.Selected): Textual event describing the selected
                list item.

        Returns:
            None
        """
        project_item = event.item
        if isinstance(project_item, ProjectListItem):
            detail_view = self.query_one(ProjectDetailView)
            self._select_project_in_list(project_item.project)
            detail_view.show_project(project_item.project)

    def action_new_project(self) -> None:
        """Open the dialog that collects data for a new project.

        Returns:
            None
        """

        def callback(data: Optional[dict]) -> None:
            # push_screen may invoke the callback with None when the dialog is dismissed
            if data:
                self.create_project_worker(
                    data["name"],
                    data.get("description", ""),
                    data.get("libraries", []),
                )

        self.push_screen(NewProjectDialog(), callback)
    def action_delete_project(self) -> None:
        """Prompt for confirmation before deleting the highlighted project.

        Returns:
            None
        """
        lv = self.query_one(ListView)
        if lv.index is not None and isinstance(lv.children[lv.index], ProjectListItem):
            project = cast(ProjectListItem, lv.children[lv.index]).project

            def callback(confirmed: Optional[bool]) -> None:
                # push_screen may call the callback with None when dismissed
                if confirmed:
                    self.delete_project_worker(project)

            self.push_screen(DeleteProjectDialog(project.name), callback)
        else:
            self.push_screen(ErrorDialog("No project selected to delete."))

    def action_archive_project(self) -> None:
        """Archive the highlighted project into a zip file.

        Returns:
            None
        """
        lv = self.query_one(ListView)
        if lv.index is not None and isinstance(lv.children[lv.index], ProjectListItem):
            project = cast(ProjectListItem, lv.children[lv.index]).project
            self.archive_project_worker(project)
        else:
            self.push_screen(ErrorDialog("No project selected to archive."))

    async def _log_to_detail_view(self, line: str) -> None:
        """Forward worker output to the active detail view.

        Args:
            line (str): Rich-formatted text to append to the log widget.

        Returns:
            None
        """
        try:
            detail_view = self.query_one(ProjectDetailView)
        except LookupError:
            return
        detail_view.post_message(ProjectDetailView.LogLine(line))

    def _select_project_in_list(self, project: Optional[Project]) -> None:
        """Ensure the ListView selection matches the provided project.

        Args:
            project (Optional[Project]): Project to select. ``None`` clears the
                current selection.

        Returns:
            None
        """

        try:
            lv = self.query_one(ListView)
        except LookupError:
            return

        if project is None:
            try:
                lv.index = None  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                pass
            try:
                lv.highlighted_child = None  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                pass
            return

        for idx, child in enumerate(lv.children):
            if (
                isinstance(child, ProjectListItem)
                and child.project.path == project.path
            ):
                try:
                    if getattr(lv, "index", None) != idx:
                        lv.index = idx  # type: ignore[attr-defined]
                except (AttributeError, TypeError):
                    pass
                try:
                    if getattr(lv, "highlighted_child", None) is not child:
                        lv.highlighted_child = child  # type: ignore[attr-defined]
                except (AttributeError, TypeError):
                    pass
                try:
                    scroll_to_index = getattr(lv, "scroll_to_index", None)
                    if callable(scroll_to_index):
                        scroll_to_index(idx)
                except Exception:
                    pass
                break

    async def _update_project_metadata(
        self, project_path: Path, description: str
    ) -> None:
        """Write the provided description to the project's pyproject file."""

        if not description.strip():
            return

        pyproject_path = project_path / "pyproject.toml"
        try:
            content = pyproject_path.read_text(encoding="utf-8")
        except OSError as exc:
            self.log(f"Failed to read pyproject.toml: {exc}")
            return

        lines = content.splitlines()
        updated_lines: List[str] = []
        in_project = False
        description_written = False
        escaped_description = description.replace("\"", "\\\"")

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("["):
                if in_project and not description_written:
                    updated_lines.append(f'description = "{escaped_description}"')
                    description_written = True
                in_project = stripped == "[project]"
                updated_lines.append(line)
                continue

            if in_project and stripped.startswith("description"):
                updated_lines.append(f'description = "{escaped_description}"')
                description_written = True
            else:
                updated_lines.append(line)

        if in_project and not description_written:
            updated_lines.append(f'description = "{escaped_description}"')

        new_content = "\n".join(updated_lines) + "\n"
        try:
            pyproject_path.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            self.log(f"Failed to update pyproject.toml: {exc}")

    async def _install_initial_libraries(
        self, project_path: Path, libraries: List[str]
    ) -> None:
        """Install the requested libraries into the new project environment."""

        for library in libraries:
            await self._log_to_detail_view(f"Adding dependency: {library}")
            result = await self.uv_executor.add(
                project_path, library, False, self._log_to_detail_view
            )
            if result.success:
                await self._log_to_detail_view(
                    f"[bold green]{library} installed successfully[/bold green]"
                )
            else:
                await self._log_to_detail_view(
                    f"[bold red]Failed to install {library}: {result.return_code}[/bold red]"
                )

    @work(exclusive=True, group="uv_commands")
    async def create_project_worker(
        self, name: str, description: str, libraries: List[str]
    ) -> None:
        """Create a new uv project and refresh discovery state.

        Args:
            name (str): Directory / package name to pass to ``uv init``.
            description (str): Optional project description to write into the
                generated ``pyproject.toml``.
            libraries (List[str]): Additional libraries to install once the
                project scaffold is created.

        Returns:
            None
        """
        project_path = PROJECTS_ROOT / name
        if project_path.exists():
            self.push_screen(ErrorDialog(f"Project directory '{name}' already exists."))
            return

        self.log(f"Creating project {name}...")
        result = await self.uv_executor.init(
            project_path, name, self._log_to_detail_view
        )
        if result.success:
            await self._update_project_metadata(project_path, description)
            if libraries:
                await self._install_initial_libraries(project_path, libraries)
            await self.scan_projects()
            self.log(f"Project '{name}' created successfully.")
        else:
            self.push_screen(ErrorDialog(f"Failed to create project: {result.stderr}"))

    @work(exclusive=True, group="uv_commands")
    async def add_dependency_worker(
        self, project: Project, package: str, is_dev: bool
    ) -> None:
        """Install a dependency into the project using ``uv add``.

        Args:
            project (Project): Target project definition.
            package (str): Requirement specifier understood by uv.
            is_dev (bool): ``True`` when the dependency should be added to the
                development group.

        Returns:
            None
        """
        detail_view = self.query_one(ProjectDetailView)
        try:
            self._select_project_in_list(project)
            detail_view.show_project(project)
            detail_view.query_one(Log).clear()
        except (LookupError, RuntimeError, AttributeError):
            # If the detail view or Log widget is not available, continue gracefully.
            pass

        result = await self.uv_executor.add(
            project.path, package, is_dev, self._log_to_detail_view
        )
        if result.success:
            await detail_view.update_dependencies_table()
            await self._log_to_detail_view(
                "[bold green]Dependency added successfully.[/bold green]"
            )
        else:
            await self._log_to_detail_view(
                f"[bold red]Error adding dependency: {result.return_code}[/bold red]"
            )
    async def remove_dependency_worker(self, project: Project, package: str) -> None:
        """Remove a dependency from the project via ``uv remove``.

        Args:
            project (Project): Project whose environment should be modified.
            package (str): Package name to remove.

        Returns:
            None
        """
        detail_view = self.query_one(ProjectDetailView)
        try:
            self._select_project_in_list(project)
            detail_view.show_project(project)
            detail_view.query_one(Log).clear()
        except (LookupError, RuntimeError, AttributeError):
            # Non-fatal: log widget may not be available; continue gracefully.
            pass

        result = await self.uv_executor.remove(
            project.path, package, self._log_to_detail_view
        )
        if result.success:
            await detail_view.update_dependencies_table()
            await self._log_to_detail_view(
                "[bold green]Dependency removed successfully.[/bold green]"
            )
        else:
            await self._log_to_detail_view(
                f"[bold red]Error removing dependency: {result.return_code}[/bold red]"
            )

    async def sync_worker(self, project: Project) -> None:
        """Synchronise the project's environment with its dependency graph.

        Args:
            project (Project): Project to synchronise.

        Returns:
            None
        """
        detail_view = self.query_one(ProjectDetailView)
        try:
            self._select_project_in_list(project)
            detail_view.show_project(project)
            detail_view.query_one(Log).clear()
        except (LookupError, RuntimeError, AttributeError):
            # Safe to ignore when detail view/log isn't ready.
            pass

        result = await self.uv_executor.sync(project.path, self._log_to_detail_view)
        if result.success:
            await detail_view.update_dependencies_table()
            await self._log_to_detail_view(
                "[bold green]Environment synced successfully.[/bold green]"
            )
        else:
            await self._log_to_detail_view(
                f"[bold red]Error syncing environment: {result.return_code}[/bold red]"
            )

    async def run_command_worker(self, project: Project, command: str) -> None:
        """Execute an arbitrary command inside the project's uv environment.

        Args:
            project (Project): Project providing the execution context.
            command (str): Shell-style command string to pass to ``uv run``.

        Returns:
            None
        """
        detail_view = self.query_one(ProjectDetailView)
        try:
            self._select_project_in_list(project)
            detail_view.show_project(project)
            detail_view.query_one(Log).clear()
        except (LookupError, RuntimeError, AttributeError):
            # Ignore errors related to missing widgets.
            pass

        result = await self.uv_executor.run(
            project.path, command, self._log_to_detail_view
        )
        if result.success:
            await self._log_to_detail_view(
                "[bold green]Command finished successfully.[/bold green]"
            )
        else:
            await self._log_to_detail_view(
                f"[bold red]Command failed with exit code: {result.return_code}[/bold red]"
            )

    @work(exclusive=True, group="uv_commands")
    async def activate_and_open_worker(self, project: Project) -> None:
        """Prepare the project's environment and open it in VS Code.

        Args:
            project (Project): Project to activate and open in an editor.

        Returns:
            None
        """
        detail_view = self.query_one(ProjectDetailView)
        try:
            detail_view.show_project(project)
            detail_view.query_one(Log).clear()
        except (LookupError, RuntimeError, AttributeError):
            pass

        venv_path = project.path / ".venv"
        if not venv_path.exists():
            await self._log_to_detail_view(
                "[yellow]Virtual environment missing. Running uv sync...[/yellow]"
            )
            result = await self.uv_executor.sync(project.path, self._log_to_detail_view)
            if not result.success:
                await self._log_to_detail_view(
                    "[bold red]Failed to prepare virtual environment.[/bold red]"
                )
                return
        else:
            await self._log_to_detail_view("Virtual environment already present.")

        activate_script = (
            venv_path / "Scripts" / "activate"
            if os.name == "nt"
            else venv_path / "bin" / "activate"
        )
        if activate_script.exists():
            await self._log_to_detail_view(
                f"To activate manually run: source {activate_script}" if os.name != "nt" else f"To activate manually run: {activate_script}"
            )
        else:
            await self._log_to_detail_view(
                "[yellow]Activation script not found; ensure uv sync completed successfully.[/yellow]"
            )

        code_command = ["code"]
        if os.environ.get("TERM_PROGRAM", "").lower() == "vscode":
            code_command.append("--reuse-window")
        code_command.append(str(project.path))

        await self._log_to_detail_view(
            "Launching VS Code with the project folder..."
        )
        try:
            process = await asyncio.create_subprocess_exec(*code_command)
        except FileNotFoundError:
            await self._log_to_detail_view(
                "[bold red]VS Code command 'code' not found in PATH.[/bold red]"
            )
            return

        return_code = await process.wait()
        if return_code == 0:
            await self._log_to_detail_view(
                "[bold green]Project opened in VS Code.[/bold green]"
            )
        else:
            await self._log_to_detail_view(
                f"[bold red]Opening VS Code failed with exit code {return_code}.[/bold red]"
            )

    @work(exclusive=True, group="filesystem")
    async def delete_project_worker(self, project: Project) -> None:
        """Delete an on-disk project directory and refresh discovery state.

        Args:
            project (Project): Project whose directory should be removed.

        Returns:
            None
        """
        self.log(f"Deleting project {project.name}...")
        try:
            shutil.rmtree(project.path)
            await self.scan_projects()
            self.log(f"Project '{project.name}' deleted.")
        except (OSError, shutil.Error) as exc:
            # Catch filesystem-related errors only (e.g., permission issues, missing files).
            self.push_screen(ErrorDialog(f"Failed to delete project: {exc}"))

    @work(exclusive=True, group="filesystem")
    async def archive_project_worker(self, project: Project) -> None:
        """Zip a project directory and relocate it beneath ``_archived``.

        Args:
            project (Project): Project to archive.

        Returns:
            None
        """
        self.log(f"Archiving project {project.name}...")
        archive_dir = PROJECTS_ROOT / "_archived"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / project.name
        try:
            shutil.make_archive(str(archive_path), "zip", project.path)
            shutil.rmtree(project.path)
            await self.scan_projects()
            self.log(f"Project '{project.name}' archived to {archive_path}.zip")
        except (OSError, shutil.Error) as exc:
            # Catch filesystem/archive related errors only.
            self.push_screen(ErrorDialog(f"Failed to archive project: {exc}"))


__all__ = ["UvTuiApp"]
