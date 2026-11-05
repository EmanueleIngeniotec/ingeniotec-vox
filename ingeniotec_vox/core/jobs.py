"""Cartella di lavoro di un'elaborazione, con checkpoint su disco.

Ogni fase scrive il proprio risultato in `_lavoro/`; se il lavoro si interrompe,
rilanciandolo le fasi già concluse vengono lette dal disco invece di essere rifatte.

Con la variabile d'ambiente `VOX_EVENTI=1` (impostata dalla GUI) il lavoro scrive su
stdout anche righe `§VOX {json}` con la fase in corso e l'avanzamento, così chi lo
lancia come processo separato può mostrare il progresso senza interpretare il log.
"""

import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

EVENT_PREFIX = "§VOX "
RECORD = "lavoro.json"      # parametri ed esito del lavoro, letti dalla GUI per riprenderlo


def emit(**event) -> None:
    if os.environ.get("VOX_EVENTI") == "1":
        print(EVENT_PREFIX + json.dumps(event, ensure_ascii=False), flush=True)


class Job:
    def __init__(self, out_dir: Path, echo=print, steps: dict | None = None):
        self.out = Path(out_dir)
        self.work = self.out / "_lavoro"
        self.work.mkdir(parents=True, exist_ok=True)
        self._echo = echo
        self._log = self.work / "vox.log"
        self._lock = threading.Lock()
        # file di checkpoint → fase (per gli eventi): prima parte del percorso
        self._phase_of = {item: key for key, items in (steps or {}).items() for item in items}
        self._phase = None

    def log(self, msg: str) -> None:
        line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
        with self._lock:
            with self._log.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._echo(msg)
            sys.stdout.flush()

    def phase(self, key: str) -> None:
        """Inizio di una fase (per la barra di avanzamento della GUI)."""
        if key != self._phase:
            self._phase = key
            emit(fase=key)

    def progress(self, fraction: float) -> None:
        emit(fase=self._phase, avanzamento=round(fraction, 3))

    def record(self, **fields) -> None:
        """Aggiorna `lavoro.json` (parametri, esito, file prodotti)."""
        with self._lock:
            data = self.load(RECORD) if self.has(RECORD) else {}
            data.update(fields)
            self.save(RECORD, data)

    def path(self, name: str) -> Path:
        return self.work / name

    def has(self, name: str) -> bool:
        return self.path(name).is_file()

    def load(self, name: str):
        return json.loads(self.path(name).read_text("utf-8"))

    def save(self, name: str, data) -> Path:
        """Scrittura atomica: un file a metà non viene mai scambiato per un checkpoint."""
        p = self.path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        os.replace(tmp, p)
        return p

    def step(self, name: str, label: str, fn):
        """Esegue `fn()` e ne salva il risultato in `name`, oppure lo rilegge se c'è già."""
        key = self._phase_of.get(name.split("/")[0])
        if key:
            self.phase(key)
        if self.has(name):
            self.log(f"{label}: già fatto, riuso {name}")
            return self.load(name)
        self.log(f"{label} …")
        t0 = time.perf_counter()
        data = fn()
        self.save(name, data)
        self.log(f"{label}: fatto in {time.perf_counter() - t0:.0f} s")
        return data
