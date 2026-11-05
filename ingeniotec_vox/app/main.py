"""Avvio della GUI: `python -m ingeniotec_vox.app.main` (nel pacchetto: Vox.exe)."""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def data_dir() -> Path:
    """Dati e log del programma, mai nella cartella di installazione (ARCHITETTURA.md)."""
    d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Ingeniotec Vox"
    d.mkdir(parents=True, exist_ok=True)
    return d


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .window import MainWindow, apply_style

    def excepthook(etype, value, tb):
        text = "".join(traceback.format_exception(etype, value, tb))
        log = data_dir() / "vox_gui.log"
        with log.open("a", encoding="utf-8") as f:
            f.write(f"\n{datetime.now():%Y-%m-%d %H:%M:%S}\n{text}")
        QMessageBox.critical(None, "Ingeniotec Vox",
                             f"Errore imprevisto nella finestra:\n{value}\n\nDettagli in {log}")

    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    app.setApplicationName("Ingeniotec Vox")
    app.setOrganizationName("Ingeniotec")
    apply_style(app)
    try:  # icona propria nella barra delle applicazioni, non quella di Python
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Ingeniotec.Vox")
    except Exception:
        pass
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
