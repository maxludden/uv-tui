# src/uv_tui/config/__init__.py
#
# this module load the logger and the console for the app.

from __future__ import annotations

from uv_tui.config.log import get_console, get_logger, get_progress
from rich_gradient import Gradient, Color, GradientRule

__all__ = [
    "get_console",
    "get_logger",
    "get_progress",
    "Color",
    "Gradient",
    "GradientRule"
]
