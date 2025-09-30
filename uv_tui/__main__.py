"""Executable entry point for the uv-tui Textual application."""

import shutil

from .app import UvTuiApp


def main() -> None:
    """Run the uv-tui Textual application after ensuring `uv` is installed."""
    if not shutil.which("uv"):
        print("Error: `uv` command not found.")
        print("Please install uv from Astral: https://github.com/astral-sh/uv")
        return

    app = UvTuiApp()
    app.run()


if __name__ == "__main__":
    main()
