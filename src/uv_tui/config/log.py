"""Rich logger setup and usage."""

from __future__ import annotations

import atexit
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import deque

import loguru
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TaskID
)
from rich.style import Style
from rich.text import Text
from rich.traceback import install as tr_install
from rich_gradient import Color, Gradient

__all__ = [
    "get_console",
    "get_logger",
    "get_progress",
    "find_cwd",
    "CWD",
    "LOGS_DIR",
    "RUN_FILE",
    "FORMAT",
    "trace_sink",
]


def get_progress(console: Optional[Console] = None) -> Progress:
    """Initialize and return a Rich progress bar."""
    if console is None:
        console = Console()
    progress = Progress(
        SpinnerColumn(spinner_name="earth"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        MofNCompleteColumn(),
    )
    progress.start()
    return progress


def get_console(
    console: Optional[Console] = None, record: bool = False, show_locals: bool = False
) -> Console:
    """Initialize and return a Rich console.

    Args:
        console (Optional[Console]): An optional existing Rich console.
        record (bool): Whether to record console output.
        show_locals (bool): Whether to show local variables in tracebacks.

    Returns:
        Console: A configured Rich console.
    """
    if console is None:
        console = Console()
    console.record = record
    # Install the Rich traceback handler with the desired settings.
    tr_install(show_locals=show_locals)
    return console


def find_cwd(
    start_dir: Path = Path(__file__).parent.parent, verbose: bool = False
) -> Path:
    """Find the current working directory by walking upward until a 'pyproject.toml' is found.

    Args:
        start_dir (Path): The starting directory.
        verbose (bool): If True, prints the found directory in a styled panel.

    Returns:
        Path: The current working directory.
    """
    cwd: Path = start_dir
    while not (cwd / "pyproject.toml").exists():
        cwd = cwd.parent
        if cwd == Path.home():
            break
    if verbose:
        console = get_console()
        console.line(2)
        panel_title = Gradient(
            "Current Working Directory",
            colors=[
                Color("#ff005f"),
                Color("#ff00af"),
                Color("#ff00ff"),
            ],
            style="bold",
        ).as_text()
        console.print(
            Panel(
                f"[i #5f00ff]{cwd.resolve()}",
                title=panel_title,
            )
        )
        console.line(2)
    return cwd


# Constants and paths
CWD: Path = find_cwd()
LOGS_DIR: Path = CWD / "logs"
RUN_FILE: Path = LOGS_DIR / "run.txt"
FORMAT: str = (
    "{time:hh:mm:ss.SSS} | {file.name: ^12} | Line {line} | {level} ➤ {message}"
)


def trace_sink() -> Dict[str, Any]:
    """Return the configuration for the trace sink."""
    return {
        "sink": str((LOGS_DIR / "trace.log").resolve()),
        "format": FORMAT,
        "level": "TRACE",
        "backtrace": True,
        "diagnose": True,
        "colorize": False,
        "mode": "w",
    }


def setup() -> int:
    """Setup the logger by creating necessary directories and files.

    Only triggered if the run file is not found in `read_run_from_file`.

    Returns:
        int: The run count (read from the run file).
    """
    console = get_console()
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir(parents=True)
        console.print(f"Created Logs Directory: {LOGS_DIR}")
    if not RUN_FILE.exists():
        with open(RUN_FILE, "w", encoding="utf-8") as f:
            f.write("0")
            console.print("Created Run File, set to 0")
    with open(RUN_FILE, "r", encoding="utf-8") as f:
        run = int(f.read())
    return run


def read_run_from_file() -> int:
    """Read the run count from the run file.

    Returns:
        int: The run count.
    """
    console = get_console()
    if not RUN_FILE.exists():
        console.print("[b #FF9900]Run File Not Found[/b #FF9900][b #ffffff] \
–[/b #ffffff] [i #FFFF00]Creating...[/i #FFFF00]")
        setup()
    with open(RUN_FILE, "r", encoding="utf-8") as f:
        run = int(f.read())
    return run


def get_logger() -> loguru.Logger:
    """Initialize and return a configured Loguru logger."""
    run = read_run_from_file()
    log = loguru.logger.bind(sink="")
    log.remove()
    log.configure(
        handlers=[
            {
                "sink": RichSink(),
                "format": "{message}",
                "level": "DEBUG",
                "backtrace": True,
                "diagnose": True,
                "colorize": False,
            },
            {
                "sink": str(LOGS_DIR / "trace.log"),
                "format": FORMAT,
                "level": "TRACE",
                "backtrace": True,
                "diagnose": True,
                "colorize": False,
                "mode": "a",  # Use append mode instead of write mode
                "retention": "30 minutes",
            },
        ],
        extra={"run": run, "rich": ""},
    )
    return log



def write_run_to_file(run: int, verbose: bool = False) -> None:
    """Write the run count to the run file.

    Args:
        run (int): The run count to write.
        verbose (bool): If True, logs a trace message.
    """
    if verbose:
        log = get_logger()
        log.trace("Writing run count...")
    with open(RUN_FILE, "w", encoding="utf-8") as f:
        f.write(str(run))


def increment_run_and_write_to_file() -> int:
    """Increment the run count, write it to the file, and return the new count."""
    log = get_logger()
    log.trace("Incrementing run count...")
    run = read_run_from_file()
    run += 1
    write_run_to_file(run)
    return run


class RichSink:
    """A custom Loguru sink that uses Rich to print styled log messages.

    Args:
        console (Optional[Console]): An optional Rich console.
        run (Optional[int]): The current run number. If None, it is read from the run file.
    """

    LEVEL_STYLES: Dict[str, Style] = {
        "TRACE": Style(italic=True),
        "DEBUG": Style(color="#aaaaaa"),
        "INFO": Style(color="#00afff"),
        "SUCCESS": Style(bold=True, color="#00ff00"),
        "WARNING": Style(italic=True, color="#ffaf00"),
        "ERROR": Style(bold=True, color="#ff5000"),
        "CRITICAL": Style(bold=True, color="#ff0000"),
    }

    GRADIENTS: Dict[str, List[Color]] = {
        "TRACE": [Color("#888888"), Color("#aaaaaa"), Color("#cccccc")],
        "DEBUG": [Color("#338888"), Color("#55aaaa"), Color("#77cccc")],
        "INFO": [Color("#008fff"), Color("#00afff"), Color("#00cfff")],
        "SUCCESS": [Color("#00aa00"), Color("#00ff00"), Color("#afff00")],
        "WARNING": [Color("#ffaa00"), Color("#ffcc00"), Color("#ffff00")],
        "ERROR": [Color("#ff0000"), Color("#ff5500"), Color("#ff7700")],
        "CRITICAL": [Color("#ff0000"), Color("#ff005f"), Color("#ff00af")],
    }

    def __init__(
        self,
        console: Optional[Console] = None,
        run: Optional[int] = None,
        progress: Optional[Progress] = None,
        tasks: List[TaskID] = [],
    ) -> None:
        if run is None:
            try:
                run = read_run_from_file()
            except FileNotFoundError:
                run = setup()
        self.run = run
        if progress is not None:
            self.progress = progress or get_progress()
            self.tasks = tasks
            self.console = self.progress.console
        else:
            self.console = console or get_console()

    def __call__(self, message: loguru.Message) -> None:
        record = message.record
        panel = self.__class__._build_panel(record, self.run, highlight_style="#666666")
        self.console.print(panel)

    @classmethod
    def rich_sink(cls, message: loguru.Message) -> None:
        """A Loguru sink that uses Rich to print styled log messages (class method version)."""
        record = message.record
        run = read_run_from_file()
        panel = cls._build_panel(record, run, highlight_style="#999999")
        console = get_console(record=True)
        console.print(panel)
        record["extra"]["rich"] = console.export_text()

    @classmethod
    def _build_panel(
        cls, record: loguru.Record, run: int, highlight_style: str
    ) -> Panel:
        """Helper method to build a Rich Panel for a log record.

        Args:
            record (loguru.Record): The log record.
            run (int): The current run count.
            highlight_style (str): The color to use when highlighting separator words.

        Returns:
            Panel: A Rich Panel containing the formatted log message.
        """
        level_name = record["level"].name
        colors = cls.GRADIENTS.get(level_name, [])
        style = cls.LEVEL_STYLES.get(level_name, Style())

        # Title with gradient and highlighted separators.
        title: Text = Gradient(
            f" {level_name} | {record['file'].name} | Line {record['line']} ",
            colors=colors,
        ).as_text()
        title.highlight_words("|", style=f"italic {highlight_style}")
        title.stylize(Style(reverse=True))

        # Subtitle with run count and formatted time.
        subtitle: Text = Text.assemble(
            Text(f"Run {run}"),
            Text(" | "),
            Text(record["time"].strftime("%H:%M:%S.%f")[:-3]),
            Text(record["time"].strftime(" %p")),
        )
        subtitle.highlight_words(":", style="dim #aaaaaa")

        # Message text with gradient.
        message_text: Text = Gradient(record["message"], colors, style="bold")

        return Panel(
            message_text,
            title=title,
            title_align="left",
            subtitle=subtitle,
            subtitle_align="right",
            border_style=style + Style(bold=True),
            padding=(1, 2),
        )


def on_exit() -> None:
    """At exit, increment the run count, add a header to the run’s log,
    and trim the trace log to the last three runs."""
    log = get_logger()
    run = increment_run_and_write_to_file()
    log.info(f"Run {run} Completed")  # This line marks the run's end.

    # Use a regex pattern that captures the run number.
    run_pattern = re.compile(r"Run (\d+) Completed")
    segments: deque[str] = deque(maxlen=3)
    current_segment: list[str] = []
    trace_log_path = LOGS_DIR / "trace.log"

    # Process the log file line by line to build segments.
    with open(trace_log_path, "r", encoding="utf-8") as f:
        for line in f:
            current_segment.append(line)
            if run_pattern.search(line):
                segments.append("".join(current_segment))
                current_segment = []

    # If there's remaining content, add it to the last segment.
    if current_segment:
        if segments:
            segments[-1] += "".join(current_segment)
        else:
            segments.append("".join(current_segment))

    # For each segment, insert a header if not already present.
    updated_segments = []
    for segment in segments:
        # Check if the first non-empty line already is a header.
        stripped = segment.lstrip()
        if not stripped.startswith("===="):
            # Attempt to extract the run number from the segment.
            m = run_pattern.search(segment)
            run_number = m.group(1) if m else "Unknown"
            header = f"\n===== Run {run_number} Log =====\n"
            segment = header + segment
        updated_segments.append(segment)

    trimmed_log = "\n".join(updated_segments)
    log.debug(f"Trimmed trace log to the last {len(updated_segments)} run(s).")

    # Overwrite the trace log with the trimmed (and header-enhanced) content.
    trace_log_path.write_text(trimmed_log, encoding="utf-8")


atexit.register(on_exit)

if __name__ == "__main__":
    log: loguru.Logger = get_logger()

    log.info("Started")
    log.trace("Trace")
    log.debug("Debug")
    log.info("Info")
    log.success("Success")
    log.warning("Warning")
    log.error("Error")
    log.critical("Critical")

    sys.exit(0)
