# PyInstaller – prova Fase 0 (cartella, console). Build: build\build.ps1
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent
SITE = Path(sys.prefix) / "Lib" / "site-packages"

# DLL CUDA dei pacchetti nvidia-* nella stessa struttura nvidia/<pkg>/bin (vedi core/cuda_dll.py).
# ctranslate2 carica solo cuBLAS (cudnn64_9.dll arriva già con ctranslate2): cuDNN e NVRTC
# dei pacchetti nvidia-* non servono e pesano ~1,3 GB (verificato in Fase 0).
CUDA_KEEP = {"cublas64_12.dll", "cublasLt64_12.dll"}
cuda = [(str(dll), str(dll.parent.relative_to(SITE)))
        for dll in (SITE / "nvidia").glob("*/bin/*.dll") if dll.name in CUDA_KEEP]

a = Analysis(
    [str(ROOT / "build" / "smoke_entry.py")],
    pathex=[str(ROOT)],
    binaries=cuda + collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime"),
    datas=collect_data_files("faster_whisper"),  # modello VAD silero
    hiddenimports=["win32com.client"],
    excludes=["tkinter", "matplotlib", "torch"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="vox_smoke", console=True,
          icon=str(ROOT / "assets" / "vox.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="vox_smoke")
