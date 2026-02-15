import os
import sys
from pathlib import Path


def _add_dll_path(path: Path) -> None:
    if not path.exists():
        return
    os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(str(path))
    except (AttributeError, OSError):
        pass


def _configure_pyqt6_runtime() -> None:
    if not getattr(sys, "frozen", False):
        return

    exe_dir = Path(sys.executable).resolve().parent
    base = Path(getattr(sys, "_MEIPASS", exe_dir))
    candidates = [
        base / "PyQt6" / "Qt6",
        base / "PyQt6" / "Qt",
        exe_dir / "_internal" / "PyQt6" / "Qt6",
        exe_dir / "_internal" / "PyQt6" / "Qt",
    ]

    for qt_root in candidates:
        bin_dir = qt_root / "bin"
        plugins_dir = qt_root / "plugins"
        platform_dir = plugins_dir / "platforms"

        _add_dll_path(bin_dir)
        if plugins_dir.exists():
            os.environ.setdefault("QT_PLUGIN_PATH", str(plugins_dir))
        if platform_dir.exists():
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(platform_dir))


_configure_pyqt6_runtime()
