# src.uv_tui.__init__.py

from __future__ import annotations



def install_missing_dependencies() -> None:
    import importlib
    import subprocess
    import sys

    requirements = {
        "loguru": "loguru",
        "rich": "rich",
        "rich_gradient": "rich-gradient",
        "textual": "textual",
    }
    missing_packages = []
    for module_name, package_name in requirements.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing_packages.append(package_name)

    if missing_packages:
        print('')
        print(f"The following packages are missing and will be installed: {'\n'.join([f'- {package}' for package in missing_packages])}")
        subprocess.check_call([sys.executable, "-m", "uv", "add", *missing_packages])

install_missing_dependencies()
