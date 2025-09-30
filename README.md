# uv-tui

uv-tui is a Textual-powered terminal interface for exploring and managing
Python projects that are driven by Astral's `uv` package manager. It discovers
projects within a workspace, surfaces metadata from `pyproject.toml`, and lets
you perform common dependency and environment tasks without leaving your
terminal.

## Features
- Auto-discovers projects containing `pyproject.toml` inside a configurable root
- Presents project metadata including versions, declared dependencies, and last
  modified timestamps
- Creates new projects via `uv init` with optional starter dependencies
- Adds, removes, and synchronises dependencies through `uv add`, `uv remove`,
  and `uv sync`
- Runs arbitrary `uv run` commands while streaming output in a dedicated log
- Provides keyboard shortcuts (`n`, `a`, `q`) and dialogs for high-friction
  actions like deletion and archiving

## Requirements
- Python 3.10 or newer (3.11+ recommended for the standard library `tomllib`)
- [uv](https://github.com/astral-sh/uv) CLI available on your `PATH`
- A terminal capable of rendering rich text (most modern terminals work well)

## Installation

Install the application in editable mode while you develop:

```bash
uv pip install -e .
```

This exposes the `uv-tui` console script declared in `pyproject.toml` and
installs runtime dependencies such as Textual, Rich, and the conditional
`tomli` backport for Python 3.10.

If you prefer `pip`, the equivalent command is:

```bash
python -m pip install -e .
```

## Usage

Launch the interface from the command line:

```bash
uv-tui
```

You can also run it directly as a module while developing:

```bash
python -m uv_tui
```

On start-up the app scans the configured projects directory, displays the list
of discovered projects, and shows details for the active selection. Use the
Tabs in the detail view to inspect declared dependencies, `uv`-reported
packages, log output, and the command runner.

### Keyboard shortcuts
- `n` &mdash; open the New Project dialog
- `a` &mdash; prepare the virtual environment and open the project in VS Code
- `q` &mdash; exit the application

Contextual buttons within the detail view let you add or remove dependencies,
run `uv sync`, delete or archive a project, and execute ad-hoc commands.

## Project discovery

Projects are looked up under `~/dev/py` by default (see
`uv_tui/config.py`). Each folder containing a `pyproject.toml` is treated as a
project. To change the discovery root, edit `PROJECTS_ROOT` or expose an
override in your environment before launching the app.

### Configuration file

A top-level `config.toml` is bundled with the repository. The loader in
`uv_tui/config.py` looks for a `[paths]` table and, if present, uses the
`projects_root` value as the default workspace. For example:

```toml
[paths]
projects_root = "~/dev/py"
```

Set the `UV_PROJECTS_ROOT` environment variable to override both the baked-in
default and any value from `config.toml`:

```bash
UV_PROJECTS_ROOT=~/client-work uv-tui
```

If the override can’t be resolved (e.g., path does not exist yet) the
application still proceeds and attempts to create the directory when scanning
for projects.

## Development

Suggested local workflow:

1. Create a virtual environment (with `uv tool install` or `python -m venv`).
2. Install dependencies in editable mode: `uv pip install -e .[dev]` once a dev
   extra is defined, or install the packages listed in `pyproject.toml`.
3. Run `uv-tui` or `python -m uv_tui` to iterate on UI changes.
4. Use `uv pip compile` or `uv lock` to refresh dependency pins as needed.

Linting and tests are not yet wired up; add them as the project evolves. The
`uv_tui/uv_executor.py` module is a good starting point if you intend to extend
command execution or add new worker flows.

## Troubleshooting

- **`uv` command not found** &mdash; verify `uv` is installed and adjust `PATH` or
  install via `pipx install uv`.
- **`tomllib` import error on Python 3.10** &mdash; ensure installation pulled in
  the `tomli` backport (automatically added for Python < 3.11).
- **Terminal rendering issues** &mdash; confirm `$TERM` reports a modern emulator
  and that True Color support is enabled when using the bundled theme.

Happy hacking!
