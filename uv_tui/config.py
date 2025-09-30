"""Application configuration constants.

This module centralises simple configuration values that govern where uv-tui
searches for projects and other filesystem-related behaviours.
"""
from pathlib import Path

# As requested, the application will manage projects in this directory.
PROJECTS_ROOT = Path.home() / "dev" / "py"
