import sys
import os
from pathlib import Path

from src.gui.main_window import MainWindow


def _configure_qt_runtime() -> None:
    """
    Ensure Qt runtime DLL path is visible when running from PyInstaller bundle.
    """
    if not getattr(sys, "frozen", False):
        return

    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        candidates.append(base / "PyQt6" / "Qt6" / "bin")
        candidates.append(base / "PyQt6" / "Qt" / "bin")
        candidates.append(base / "PyQt6" / "Qt6" / "plugins")
    exe_base = Path(sys.executable).resolve().parent
    candidates.append(exe_base / "_internal" / "PyQt6" / "Qt6" / "bin")
    candidates.append(exe_base / "_internal" / "PyQt6" / "Qt" / "bin")
    candidates.append(exe_base / "_internal" / "PyQt6" / "Qt6" / "plugins")

    for path in candidates:
        if not path.exists():
            continue
        if "plugins" in path.parts:
            os.environ["QT_PLUGIN_PATH"] = str(path)
            continue
        os.environ["PATH"] = str(path) + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(str(path))
        except (AttributeError, OSError):
            pass


def main() -> int:
    _configure_qt_runtime()
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
