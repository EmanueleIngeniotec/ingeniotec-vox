# PyInstaller – Vox (Fase 5): una cartella con due eseguibili che condividono le librerie.
#   Vox.exe      interfaccia grafica (senza console)
#   vox_cli.exe  riga di comando; la GUI la lancia come processo separato per ogni lavoro
# Build: build\build.ps1
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
SITE = Path(sys.prefix) / "Lib" / "site-packages"

# DLL CUDA: solo cuBLAS (vedi FASE0.md e core/cuda_dll.py)
CUDA_KEEP = {"cublas64_12.dll", "cublasLt64_12.dll"}
cuda = [(str(dll), str(dll.parent.relative_to(SITE)))
        for dll in (SITE / "nvidia").glob("*/bin/*.dll") if dll.name in CUDA_KEEP]

binaries = (cuda + collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")
            + collect_dynamic_libs("sherpa_onnx"))
datas = (collect_data_files("faster_whisper") + collect_data_files("docx") + collect_data_files("pymupdf")
         + [(str(ROOT / "ingeniotec_vox" / "profiles"), "ingeniotec_vox/profiles"),
            (str(ROOT / "assets"), "assets")])
common = dict(pathex=[str(ROOT)], binaries=binaries, datas=datas,
              hiddenimports=["win32com.client", "pythoncom", "sherpa_onnx", "psutil"],
              excludes=["tkinter", "matplotlib", "torch", "PySide6.QtWebEngineCore",
                        "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml"])

gui = Analysis([str(ROOT / "build" / "vox_gui_entry.py")], **common)
cli = Analysis([str(ROOT / "build" / "vox_cli_entry.py")], **common)

ICON = str(ROOT / "assets" / "vox.ico")
gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name="Vox", console=False, icon=ICON)
cli_exe = EXE(PYZ(cli.pure), cli.scripts, [], exclude_binaries=True, name="vox_cli", console=True, icon=ICON)
coll = COLLECT(gui_exe, cli_exe, gui.binaries, gui.datas, cli.binaries, cli.datas, name="Vox")
