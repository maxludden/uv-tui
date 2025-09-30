"""CLI entry point for launching the uv-tui Textual application."""
import shutil

from uv_tui.app import UvTuiApp


def main() -> None:
    """Launch the Textual UI after validating the ``uv`` CLI is available.

    Returns:
        None
    """
    if not shutil.which("uv"):
        print("Error: `uv` command not found.")
        print("Please install uv from Astral: https://github.com/astral-sh/uv")
        return

    app = UvTuiApp()
    app.run()


if __name__ == "__main__":
    main()
