"""Rende visibili le DLL CUDA (cuBLAS, cuDNN) dei pacchetti pip `nvidia-*`.

ctranslate2 carica cuBLAS/cuDNN con LoadLibrary: le cartelle `nvidia/*/bin`
devono essere sia in `os.add_dll_directory` sia nel PATH. Funziona sia da
sorgente sia dal pacchetto PyInstaller (dove stanno sotto `sys._MEIPASS`).
"""

import os
import sys
from pathlib import Path

_done = False


def _candidate_roots() -> list[Path]:
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(Path(sys._MEIPASS))
    roots += [Path(p) for p in sys.path if p and Path(p).is_dir()]
    return roots


def register() -> list[str]:
    """Aggiunge le cartelle DLL trovate; restituisce l'elenco (per il log)."""
    global _done
    found = []
    for root in _candidate_roots():
        nvidia = root / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in sorted(nvidia.glob("*/bin")):
            found.append(str(bin_dir))
        if found:
            break
    if not _done:
        for d in found:
            os.add_dll_directory(d)
        os.environ["PATH"] = os.pathsep.join(found + [os.environ.get("PATH", "")])
        _done = True
    return found
