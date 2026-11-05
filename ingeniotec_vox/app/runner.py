"""Esecuzione di un lavoro come processo separato (la riga di comando di Vox).

Il processo separato rende l'annullamento affidabile (si chiude l'intero albero:
Whisper, `claude -p`, Word) e tiene la finestra reattiva. Il progresso arriva dalle
righe `§VOX {json}` (vedi `core/jobs.py`) e dalle righe del log.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from ..core.env_check import CREATE_NO_WINDOW
from ..core.jobs import EVENT_PREFIX, RECORD

# fasi mostrate all'utente: chiave degli eventi → (etichetta, peso sul tempo totale)
PHASES = {
    "call": {
        "trascrizione": ("Trascrizione dell'audio", 22),
        "fotogrammi": ("Fotogrammi del video", 8),
        "partecipanti": ("Partecipanti", 5),
        "voci": ("Separazione delle voci", 5),
        "nomi": ("Nomi di chi parla", 8),
        "blocchi": ("Analisi della conversazione", 22),
        "report": ("Composizione del report", 10),
        "schermate": ("Scelta delle schermate", 8),
        "documenti": ("Documenti Word", 2),
        "pdf": ("PDF", 10),
    },
    "lezione": {
        "trascrizione": ("Trascrizione dell'audio", 10),
        "fotogrammi": ("Fotogrammi del video", 5),
        "struttura": ("Struttura della dispensa", 8),
        "capitoli": ("Scrittura dei capitoli", 38),
        "fonti": ("Verifica delle fonti", 24),
        "scheda": ("Scheda di ripasso", 4),
        "documenti": ("Documenti Word", 1),
        "pdf": ("PDF e controllo dell'impaginazione", 7),
        "guida": ("Aggiornamento della guida all'esame", 6),
    },
}
# righe del log delle fasi in parallelo: «Parte 2/5: fatto in 40 s», «Capitolo 3/21: già fatto …»
PART_DONE = re.compile(r"^(?:Parte|Capitolo|Fonti) (\d+)/(\d+): (?:fatto|già fatto)")

ERRORS = {
    "limite": "È stato raggiunto il limite d'uso di Claude. Il lavoro è salvato: riprendilo più tardi "
              "da «Lavori recenti» (le fasi già concluse non si rifanno).",
    "claude": "Claude non ha completato una richiesta. Controlla la connessione a internet e "
              "riprendi il lavoro da «Lavori recenti».",
    "word": "Microsoft Word non ha creato i PDF. Chiudi eventuali finestre di Word bloccate e "
            "riprendi il lavoro.",
    "ambiente": "Il PC non è pronto per l'elaborazione.",
    "altro": "Si è verificato un errore imprevisto. Il lavoro è salvato e si può riprendere; "
             "se l'errore si ripete, invia il file vox.log (pulsante «Apri log») a chi gestisce Vox.",
}


def app_dir() -> Path:
    """Cartella dei modelli e della CLI: accanto all'eseguibile, o la radice del repository."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def cli_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(app_dir() / "vox_cli.exe")]
    return [sys.executable, "-m", "ingeniotec_vox.cli"]


def job_args(record: dict, job_dir: Path, redo: str | None = None) -> list[str]:
    """Argomenti della CLI per (ri)lanciare il lavoro descritto da `lavoro.json`."""
    o = record.get("opzioni", {})
    out = ["--out", str(job_dir.parent), "--nome", job_dir.name]
    if record["tipo"] == "call":
        args = ["call", record["video"], *out]
        if o.get("trascrizione"):
            args.append("--trascrizione")
    else:
        args = ["lezione", record["video"], *out, "--profilo", o.get("profilo") or "esame"]
        if o.get("corso"):
            args += ["--corso", o["corso"]]
        if o.get("numero"):
            args += ["--numero", str(o["numero"])]
        if o.get("docente"):
            args += ["--docente", o["docente"]]
        if o.get("guida"):
            args += ["--guida", o["guida"]]
    if redo:
        args += ["--rifai", redo]
    return args


def read_record(job_dir: Path) -> dict | None:
    try:
        return json.loads((job_dir / "_lavoro" / RECORD).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def write_record(job_dir: Path, **fields) -> None:
    rec = read_record(job_dir)
    if rec is not None:
        rec.update(fields)
        (job_dir / "_lavoro" / RECORD).write_text(json.dumps(rec, ensure_ascii=False, indent=2), "utf-8")


def recent_jobs(out_root: Path) -> list[tuple[Path, dict]]:
    if not out_root.is_dir():
        return []
    found = []
    for d in out_root.iterdir():
        rec = read_record(d) if d.is_dir() else None
        if rec:
            found.append((d, rec))
    return sorted(found, key=lambda x: x[1].get("aggiornato", ""), reverse=True)


def kill_tree(pid: int) -> None:
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                   creationflags=CREATE_NO_WINDOW)


def kill_automation_word(since: float) -> None:
    """Word aperto da Vox via COM (non è un processo figlio): si chiude solo quello
    avviato con /Automation dopo l'inizio del lavoro, mai il Word dell'utente."""
    try:
        import psutil
    except ImportError:
        return
    for p in psutil.process_iter(["name", "cmdline", "create_time"]):
        try:
            if (p.info["name"] or "").upper() == "WINWORD.EXE" and p.info["create_time"] >= since \
                    and any("/automation" in (a or "").lower() for a in p.info["cmdline"] or []):
                p.kill()
        except (psutil.Error, TypeError):
            continue


class Runner(QObject):
    """Un lavoro in esecuzione. Segnali: righe di log, fase, avanzamento, fine."""
    line = Signal(str)
    phase = Signal(str)                 # chiave della fase iniziata
    phase_progress = Signal(float)      # 0–1 nella fase corrente
    finished = Signal(int, str, str)    # codice di uscita, tipo di errore, messaggio
    files = Signal(list)

    def __init__(self, args: list[str], parent=None):
        super().__init__(parent)
        self.args = args
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("VOX_EVENTI", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("PYTHONUNBUFFERED", "1")
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(app_dir()))
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._done)
        self.proc.errorOccurred.connect(self._error)
        self._buf = b""
        self._err = ("", "")
        self.current = None
        self.cancelled = False
        self.started_at = 0.0

    def start(self) -> None:
        cmd = cli_command() + self.args
        self.started_at = time.time()
        self.proc.start(cmd[0], cmd[1:])

    def running(self) -> bool:
        return self.proc.state() != QProcess.NotRunning

    def cancel(self) -> None:
        if not self.running():
            return
        self.cancelled = True
        kill_tree(int(self.proc.processId()))
        if self.current in ("pdf", "guida", "documenti"):
            kill_automation_word(self.started_at)

    def _read(self) -> None:
        self._buf += bytes(self.proc.readAllStandardOutput())
        *lines, self._buf = self._buf.split(b"\n")
        for raw in lines:
            text = raw.decode("utf-8", "replace").rstrip("\r")
            if text.startswith(EVENT_PREFIX):
                try:
                    self._event(json.loads(text[len(EVENT_PREFIX):]))
                except ValueError:
                    pass
                continue
            self.line.emit(text)
            m = PART_DONE.match(text.strip())
            if m and self.current in ("blocchi", "capitoli", "fonti"):
                self._parts = getattr(self, "_parts", {})
                key = (self.current, int(m.group(2)))
                self._parts.setdefault(key, set()).add(int(m.group(1)))
                self.phase_progress.emit(len(self._parts[key]) / int(m.group(2)))

    def _event(self, ev: dict) -> None:
        if "errore" in ev:
            self._err = (ev["errore"], ev.get("messaggio", ""))
        elif "fine" in ev:
            self.files.emit(ev["fine"])
        elif "avanzamento" in ev:
            self.phase_progress.emit(float(ev["avanzamento"]))
        elif ev.get("fase"):
            self.current = ev["fase"]
            self.phase.emit(ev["fase"])

    def _done(self, code: int, _status) -> None:
        if self._buf:
            self.line.emit(self._buf.decode("utf-8", "replace"))
            self._buf = b""
        if self.cancelled:
            self.finished.emit(-1, "annullato", "")
        else:
            kind, msg = self._err
            if code != 0 and not kind:
                kind = "altro"
            self.finished.emit(code, kind, msg)

    def _error(self, err) -> None:
        if err == QProcess.FailedToStart:
            self.finished.emit(-2, "altro", f"Impossibile avviare {cli_command()[0]}.")


def keep_awake(on: bool) -> None:
    """Il PC non va in sospensione durante un lavoro (lezioni di 3–4 ore)."""
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


def open_path(path: Path) -> None:
    os.startfile(str(path))  # noqa: S606 (Windows)
