"""Asynchronous wrapper around uv CLI commands.

The :class:`~uv_tui.uv_executor.UVCommandExecutor` encapsulates invocations of
the ``uv`` CLI, providing coroutine-friendly helpers that stream process output
back to the UI layer.
"""
import asyncio
from asyncio.subprocess import Process
from pathlib import Path
from typing import Awaitable, Callable, List

from .models import CommandResult, Dependency


class UVCommandExecutor:
    """Service object responsible for running uv commands asynchronously."""

    async def _stream_process(
        self,
        process: Process,
        log_callback: Callable[[str], Awaitable[None]],
    ) -> CommandResult:
        """Stream process output and await completion.

        Args:
            process (Process): Asyncio subprocess handle referencing the uv
                command.
            log_callback (Callable[[str], Awaitable[None]]): Coroutine used to
                surface log lines to the UI.

        Returns:
            CommandResult: Aggregated result containing stdout, stderr, and the
            return code.
        """
        stdout_buf = []
        stderr_buf = []

        async def read_stream(stream, stream_name: str) -> None:
            if stream:
                async for line in stream:
                    decoded_line = line.decode("utf-8", errors="ignore").rstrip()
                    if stream_name == "stdout":
                        stdout_buf.append(decoded_line)
                    else:
                        stderr_buf.append(decoded_line)
                    await log_callback(f"[{stream_name}] {decoded_line}")

        await asyncio.gather(
            read_stream(process.stdout, "stdout"), read_stream(process.stderr, "stderr")
        )

        await process.wait()

        return CommandResult(
            success=(process.returncode == 0),
            stdout="\n".join(stdout_buf),
            stderr="\n".join(stderr_buf),
            return_code=process.returncode or 0,
        )

    async def init(
        self, path: Path, name: str, log_callback: Callable[[str], Awaitable[None]]
    ) -> CommandResult:
        """Run ``uv init`` within ``path`` to scaffold a new project.

        Args:
            path (Path): Target directory for the new project.
            name (str): Package name to pass to ``uv init``.
            log_callback (Callable[[str], Awaitable[None]]): Coroutine for
                streaming log lines.

        Returns:
            CommandResult: Outcome of the ``uv init`` invocation.
        """
        await log_callback(f"Initializing project '{name}' at {path}...")
        path.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            "uv",
            "init",
            "--name",
            name,
            cwd=path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await self._stream_process(process, log_callback)

    async def add(
        self,
        project_path: Path,
        package: str,
        is_dev: bool,
        log_callback: Callable[[str], Awaitable[None]],
    ) -> CommandResult:
        """Run ``uv add`` to install a dependency into the project.

        Args:
            project_path (Path): Directory containing the ``pyproject`` file.
            package (str): Requirement string to install.
            is_dev (bool): ``True`` to add the dependency to the dev group.
            log_callback (Callable[[str], Awaitable[None]]): Coroutine for
                streaming log lines.

        Returns:
            CommandResult: Result of the ``uv add`` execution.
        """
        args = ["uv", "add", package]
        if is_dev:
            args.append("--dev")
        await log_callback(f"Running: {' '.join(args)} in {project_path}")
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await self._stream_process(process, log_callback)

    async def activate(
        self, project_path: Path, log_callback: Callable[[str], Awaitable[None]]
    ) -> CommandResult:
        """Run ``uv activate`` for the provided project directory.

        Args:
            project_path (Path): Directory whose environment should be
                activated.
            log_callback (Callable[[str], Awaitable[None]]): Coroutine for
                streaming log lines.

        Returns:
            CommandResult: Result of the activation attempt.
        """
        await log_callback(f"Running: uv activate in {project_path}")
        process = await asyncio.create_subprocess_exec(
            "source",
            ".venv/bin/activate",
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await self._stream_process(process, log_callback)

    async def remove(
        self,
        project_path: Path,
        package: str,
        log_callback: Callable[[str], Awaitable[None]],
    ) -> CommandResult:
        """Run ``uv remove`` to uninstall a dependency from the project.

        Args:
            project_path (Path): Directory representing the project root.
            package (str): Package name to remove.
            log_callback (Callable[[str], Awaitable[None]]): Coroutine for
                streaming log lines.

        Returns:
            CommandResult: Result of the ``uv remove`` invocation.
        """
        await log_callback(f"Running: uv remove {package} in {project_path}")
        process = await asyncio.create_subprocess_exec(
            "uv",
            "remove",
            package,
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await self._stream_process(process, log_callback)

    async def sync(
        self, project_path: Path, log_callback: Callable[[str], Awaitable[None]]
    ) -> CommandResult:
        """Synchronise the project's environment using ``uv sync``.

        Args:
            project_path (Path): Directory containing the project.
            log_callback (Callable[[str], Awaitable[None]]): Coroutine for
                streaming log lines.

        Returns:
            CommandResult: Result of the synchronisation command.
        """
        await log_callback(f"Running: uv sync in {project_path}")
        process = await asyncio.create_subprocess_exec(
            "uv",
            "sync",
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await self._stream_process(process, log_callback)

    async def run(
        self,
        project_path: Path,
        command: str,
        log_callback: Callable[[str], Awaitable[None]],
    ) -> CommandResult:
        """Run an arbitrary command under ``uv run``.

        Args:
            project_path (Path): Directory whose environment should be used.
            command (str): Shell-style command string to execute.
            log_callback (Callable[[str], Awaitable[None]]): Coroutine for
                streaming log lines.

        Returns:
            CommandResult: Result of the command execution.
        """
        await log_callback(f"Running: uv run {command} in {project_path}")
        command_parts = command.split()
        process = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            *command_parts,
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await self._stream_process(process, log_callback)

    async def list_dependencies(self, project_path: Path) -> List[Dependency]:
        """List installed dependencies by invoking ``uv pip list``.

        Args:
            project_path (Path): Directory representing the project whose
                dependencies should be enumerated.

        Returns:
            List[Dependency]: Sequence of discovered dependencies, or an empty
            list if the virtual environment is missing.
        """
        if not (project_path / ".venv").exists():
            return []

        process = await asyncio.create_subprocess_exec(
            "uv",
            "pip",
            "list",
            cwd=project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()

        text = stdout.decode("utf-8", errors="ignore")
        dependencies: List[Dependency] = []

        lines = [ln for ln in text.splitlines() if ln.strip() != ""]
        start_idx = 0
        if len(lines) >= 1 and lines[0].lower().startswith("package"):
            start_idx = 1
            if len(lines) > 1 and set(lines[1].strip()) <= set("- "):
                start_idx = 2

        for line in lines[start_idx:]:
            parts = line.split()
            if len(parts) >= 2:
                dependencies.append(Dependency(name=parts[0], version=parts[1]))

        return dependencies


__all__ = ["UVCommandExecutor"]
