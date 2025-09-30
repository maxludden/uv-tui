"""Core Textual application for uv-tui."""

import shutil
import tomllib
from datetime import datetime
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
    """A Textual TUI for managing uv projects."""

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
        yield Header(show_clock=True, time_format="%I:%M %p")
        with Horizontal(id="main-content"):
            yield ListView(id="project-list")
            yield ProjectDetailView()
        yield Footer()

    async def on_mount(self) -> None:
        """Called when the app is first mounted."""
        await self.scan_projects()

    async def scan_projects(self) -> None:
        """Scans the PROJECTS_ROOT directory for uv projects."""
        found_projects: List[Project] = []
        if not PROJECTS_ROOT.exists():
            PROJECTS_ROOT.mkdir(parents=True)

        for item in PROJECTS_ROOT.iterdir():
            if item.is_dir() and (item / "pyproject.toml").exists():
                status = "Venv OK" if (item / ".venv").exists() else "Venv Missing"

                pyproject_path = item / "pyproject.toml"
                python_version = "N/A"
                description = ""
                last_modified_dt: Optional[datetime] = None
                try:
                    with open(pyproject_path, "rb") as f:
                        config = tomllib.load(f)
                        project_cfg = config.get("project", {})
                        python_version = project_cfg.get("requires-python", "N/A")
                        description = project_cfg.get("description") or ""
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
                        last_modified=last_modified_dt,
                    )
                )
        self.projects = sorted(found_projects, key=lambda p: p.name)

    def watch_projects(self, *args) -> None:
        """Reactive method to update the project list view.
        Accepts either (new_projects,) or (old_projects, new_projects) to be
        compatible with different Textual versions.
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
            try:
                lv.index = 0  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                pass
            detail_view.show_project(new_projects[0])
        else:
            detail_view.show_project(None)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle project selection."""
        project_item = event.item
        if isinstance(project_item, ProjectListItem):
            detail_view = self.query_one(ProjectDetailView)
            detail_view.show_project(project_item.project)

    def action_new_project(self) -> None:
        """Action to open the new project dialog."""

        def callback(data: Optional[dict]) -> None:
            # push_screen may invoke the callback with None when the dialog is dismissed
            if data:
                self.create_project_worker(data["name"])

        self.push_screen(NewProjectDialog(), callback)
    def action_delete_project(self) -> None:
        """Action to delete the currently highlighted project."""
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
        """Action to archive the currently highlighted project."""
        lv = self.query_one(ListView)
        if lv.index is not None and isinstance(lv.children[lv.index], ProjectListItem):
            project = cast(ProjectListItem, lv.children[lv.index]).project
            self.archive_project_worker(project)
        else:
            self.push_screen(ErrorDialog("No project selected to archive."))

    async def _log_to_detail_view(self, line: str) -> None:
        """Stream log output into the detail view when available."""
        try:
            detail_view = self.query_one(ProjectDetailView)
        except LookupError:
            return
        detail_view.post_message(ProjectDetailView.LogLine(line))

    @work(exclusive=True, group="uv_commands")
    async def create_project_worker(self, name: str) -> None:
        """Create a new uv project asynchronously and refresh the project list on success."""
        project_path = PROJECTS_ROOT / name
        if project_path.exists():
            self.push_screen(ErrorDialog(f"Project directory '{name}' already exists."))
            return

        self.log(f"Creating project {name}...")
        result = await self.uv_executor.init(
            project_path, name, self._log_to_detail_view
        )
        if result.success:
            await self.scan_projects()
            self.log(f"Project '{name}' created successfully.")
        else:
            self.push_screen(ErrorDialog(f"Failed to create project: {result.stderr}"))

    @work(exclusive=True, group="uv_commands")
    async def add_dependency_worker(
        self, project: Project, package: str, is_dev: bool
    ) -> None:
        """Add a dependency to the given project asynchronously and stream logs."""
        detail_view = self.query_one(ProjectDetailView)
        try:
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
        """Remove a dependency from the project asynchronously and stream logs."""
        detail_view = self.query_one(ProjectDetailView)
        try:
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
        """Synchronize the project's environment asynchronously and stream logs."""
        detail_view = self.query_one(ProjectDetailView)
        try:
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
        """Run a command in the project's environment and stream its output."""
        detail_view = self.query_one(ProjectDetailView)
        try:
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

    @work(exclusive=True, group="filesystem")
    async def delete_project_worker(self, project: Project) -> None:
        """Delete the given project directory and refresh the project list.

        This runs asynchronously and is executed in the filesystem work group
        to avoid blocking the UI.
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
        """Archive the given project directory into a zip under PROJECTS_ROOT/_archived \
and refresh the project list.

        The archive will be created as a zip file named after the project and the
        original project directory will be removed on success.
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
