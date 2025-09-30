"""uv-tui package initialisation utilities.

Importing :mod:`uv_tui` exposes the :class:`~uv_tui.app.UvTuiApp` class that
launches the Textual interface for managing uv projects.
"""

from .__main__ import main
from .app import UvTuiApp

__all__ = ["UvTuiApp", "main"]
