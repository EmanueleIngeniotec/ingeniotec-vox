"""Controllo dell'ambiente al primo avvio: GPU, Claude Code, Word, disco.

Ogni controllo restituisce un `Check` con esito e messaggio in italiano
pensato per un utente non tecnico.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import cuda_dll

MIN_FREE_GB = 10
CREATE_NO_WINDOW = 0x08000000


@dataclass
class Check:
    name: str
    ok: bool
    message: str
    blocking: bool = True


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=CREATE_NO_WINDOW,
    )


def check_gpu() -> Check:
    cuda_dll.register()
    try:
        import ctranslate2
        count = ctranslate2.get_cuda_device_count()
    except Exception as exc:  # DLL mancanti, driver assente
        return Check("GPU", False, f"Impossibile usare la GPU NVIDIA ({exc}). "
                     "Verificare che il driver NVIDIA sia installato e aggiornato.")
    if count == 0:
        return Check("GPU", False, "Nessuna GPU NVIDIA rilevata. "
                     "Il programma richiede una scheda NVIDIA con driver aggiornato.")
    name = ""
    if shutil.which("nvidia-smi"):
        r = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
        name = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
    return Check("GPU", True, f"GPU NVIDIA disponibile{': ' + name if name else ''}.")


def claude_exe() -> str | None:
    return shutil.which("claude")


def check_claude() -> Check:
    exe = claude_exe()
    if not exe:
        return Check("Claude Code", False,
                     "Claude Code non è installato. Chiedere all'IT di installarlo "
                     "(https://claude.com/claude-code) e poi riavviare il programma.")
    r = _run([exe, "--version"])
    version = r.stdout.strip().split()[0] if r.returncode == 0 and r.stdout.strip() else "?"
    r = _run([exe, "auth", "status"])
    try:
        status = json.loads(r.stdout)
    except json.JSONDecodeError:
        return Check("Claude Code", False,
                     f"Claude Code {version} installato ma non risponde correttamente. "
                     "Aprire un terminale ed eseguire 'claude' per verificarlo.")
    if not status.get("loggedIn"):
        return Check("Claude Code", False,
                     f"Claude Code {version} non è collegato a un account. Aprire un terminale, "
                     "eseguire 'claude auth login' e accedere con l'account aziendale.")
    who = status.get("email", "?")
    org = status.get("orgName") or "nessuna organizzazione"
    plan = status.get("subscriptionType", "?")
    return Check("Claude Code", True,
                 f"Claude Code {version}, collegato come {who} ({org}, piano {plan}).")


def check_word() -> Check:
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID").Close()
    except OSError:
        return Check("Word", False, "Microsoft Word non risulta installato: serve per creare i PDF.")
    return Check("Word", True, "Microsoft Word installato.")


def check_disk(path: Path) -> Check:
    path = path if path.exists() else Path(path.anchor or ".")
    free_gb = shutil.disk_usage(path).free / 1024**3
    if free_gb < MIN_FREE_GB:
        return Check("Disco", False, f"Spazio libero insufficiente su {path.anchor}: "
                     f"{free_gb:.1f} GB (servono almeno {MIN_FREE_GB} GB).", blocking=False)
    return Check("Disco", True, f"Spazio libero su {path.anchor}: {free_gb:.0f} GB.")


def run_all(output_dir: Path) -> list[Check]:
    return [check_gpu(), check_claude(), check_word(), check_disk(output_dir)]
