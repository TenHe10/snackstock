from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent


class BarcodeScannerBuffer:
    def __init__(self):
        self._buffer: list[str] = []

    def feed(self, event: QKeyEvent) -> str | None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            code = "".join(self._buffer).strip()
            self._buffer.clear()
            return code if code else None

        text = event.text()
        if text and text.isprintable():
            self._buffer.append(text)
        return None
