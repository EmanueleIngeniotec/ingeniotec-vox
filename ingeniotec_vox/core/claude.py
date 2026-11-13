"""Unico punto di contatto con Claude Code CLI in modalità headless (`claude -p`).

Il prompt passa da stdin (niente limiti di lunghezza della riga di comando);
con `schema` l'output è JSON validato da Claude Code (`structured_output`).

Limiti del piano: Claude Code comunica a ogni richiesta quanto è stato usato del limite
di 5 ore e di quello settimanale (`rate_limit_event`). Arrivati a `THRESHOLD` Vox non
manda altre richieste, così non si consumano i crediti a pagamento («uso extra»)
dell'account, a meno che l'utente lo consenta (`allow_credits`).
"""

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .env_check import CREATE_NO_WINDOW, claude_exe


class ClaudeError(RuntimeError):
    pass


class ClaudeLimitError(ClaudeError):
    """Limite d'uso del piano raggiunto o quasi: inutile riprovare subito.
    `credits`: l'account ha i crediti a pagamento, con cui si può continuare."""

    def __init__(self, msg: str, credits: bool = False):
        super().__init__(msg)
        self.credits = credits


@dataclass
class ClaudeResult:
    text: str
    data: dict | None
    cost_usd: float | None
    duration_ms: int | None
    raw: dict


# Fissati qui, non presi dalle impostazioni di Claude Code del PC: stessi risultati per tutti.
# "opus" = ultimo Opus disponibile.
MODEL = "opus"
EFFORT = "medium"


THRESHOLD = 0.90            # quota del limite oltre la quale non partono altre richieste
allow_credits = False       # True: si continua oltre il limite con i crediti a pagamento (--crediti)
WINDOWS = {"five_hour": "delle 5 ore"}      # gli altri (seven_day, seven_day_opus, …) sono settimanali
_lock = threading.Lock()


def _state_file() -> Path:
    """Ultimo stato dei limiti: vale anche per il lavoro successivo e per «Riprendi»."""
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Ingeniotec Vox" / "limiti.json"


def _load_state() -> dict:
    try:
        return json.loads(_state_file().read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _when(ts: float) -> str:
    d = datetime.fromtimestamp(ts)
    if d.date() == datetime.now().date():
        return f"alle {d:%H:%M}"
    return f"il {d:%d/%m} alle {d:%H:%M}"


def _note_limits(info: dict) -> None:
    """Registra lo stato dei limiti letto da un `rate_limit_event`."""
    windows = dict(info.get("unifiedWindows") or {})
    kind = info.get("rateLimitType")
    if kind and kind not in windows:
        windows[kind] = {k: info.get(k) for k in ("utilization", "resetsAt", "status")}
    with _lock:
        state = _load_state()
        # senza crediti (uso extra non attivo) non c'è nulla da proteggere; nel dubbio, sì
        state["crediti"] = info.get("overageStatus") != "rejected"
        state["in_crediti"] = bool(info.get("isUsingOverage"))
        state["letto"] = time.time()
        fin = state.setdefault("finestre", {})
        for name, w in windows.items():
            used = w.get("utilization")
            if used is None and w.get("status") == "rejected":
                used = 1.0
            if used is not None and w.get("resetsAt"):
                fin[name] = {"uso": float(used), "azzera": float(w["resetsAt"])}
        try:
            _state_file().parent.mkdir(parents=True, exist_ok=True)
            _state_file().write_text(json.dumps(state), "utf-8")
        except OSError:
            pass


def limit_reached() -> ClaudeLimitError | None:
    """L'errore da sollevare se un limite è a `THRESHOLD` o oltre e non è ancora azzerato."""
    with _lock:
        state = _load_state()
    now = time.time()
    credits = state.get("crediti", True)
    limit = THRESHOLD if credits else 1.0     # senza crediti si usa il piano fino in fondo
    full = [(w["azzera"], name, w["uso"]) for name, w in state.get("finestre", {}).items()
            if w["uso"] >= limit and w["azzera"] > now]
    if not full:
        # in crediti senza sapere fino a quando: lo stato vale per poco
        if state.get("in_crediti") and now - state.get("letto", 0) < 300:
            return ClaudeLimitError("Il limite d'uso di Claude è esaurito e l'account sta consumando "
                                    "crediti a pagamento: Vox si è fermato.", credits=True)
        return None
    reset, name, used = max(full)     # si riparte quando si azzera l'ultimo
    label = WINDOWS.get(name, "settimanale")
    if used >= 1:
        msg = f"Limite d'uso {label} di Claude raggiunto: si azzera {_when(reset)}."
    else:
        msg = (f"Uso di Claude al {int(used * 100)}% del limite {label} (si azzera {_when(reset)}): "
               "Vox si è fermato prima di consumare crediti a pagamento.")
    return ClaudeLimitError(msg + " Le fasi già concluse non verranno rifatte.",
                            credits=credits)


def run(prompt: str, *, schema: dict | None = None, system_prompt: str | None = None,
        tools: list[str] | None = None, add_dirs: list[Path] | None = None,
        cwd: Path | None = None, model: str = MODEL, effort: str = EFFORT,
        timeout: int = 600) -> ClaudeResult:
    exe = claude_exe()
    if not exe:
        raise ClaudeError("Claude Code non è installato.")
    if not allow_credits:
        exc = limit_reached()
        if exc:
            raise exc
    # stream-json: oltre al risultato arrivano gli eventi sui limiti del piano
    args = [exe, "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
            "--tools", ",".join(tools or [])]
    if tools:
        args += ["--allowedTools", ",".join(tools)]
    if schema:
        args += ["--json-schema", json.dumps(schema)]
    if system_prompt:
        args += ["--append-system-prompt", system_prompt]
    for d in add_dirs or []:
        args += ["--add-dir", str(d)]
    if model:
        args += ["--model", model]
    if effort:
        args += ["--effort", effort]

    try:
        proc = subprocess.run(args, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              cwd=cwd, creationflags=CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise ClaudeError(f"Claude non ha risposto entro {timeout} s.") from exc

    raw = None
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "rate_limit_event":
            _note_limits(ev.get("rate_limit_info") or {})
        elif ev.get("type") == "result":
            raw = ev
    if raw is None:
        raise ClaudeError(f"Risposta non valida da Claude Code (codice {proc.returncode}): "
                          f"{(proc.stderr or proc.stdout).strip()[:500]}")
    if raw.get("is_error"):
        msg = str(raw.get("result") or raw.get("subtype"))
        # es. "You've hit your 5-hour limit · resets 8:30pm (Europe/Rome)"
        if raw.get("api_error") == "usage_limit_reached" or re.search(
                r"usage limit|limit reached|hit your [\w-]*\s*limit|rate limit|session limit|weekly limit",
                msg, re.I):
            exc = limit_reached()
            if exc:
                exc.credits = False     # rifiutata anche con i crediti: non resta che aspettare
                raise exc
            raise ClaudeLimitError("Limite d'uso di Claude raggiunto. Riprendere il lavoro più tardi: "
                                   f"le fasi già concluse non verranno rifatte. ({msg})")
        raise ClaudeError(f"Errore da Claude: {msg}")
    return ClaudeResult(
        text=raw.get("result", ""),
        data=raw.get("structured_output"),
        cost_usd=raw.get("total_cost_usd"),
        duration_ms=raw.get("duration_ms"),
        raw=raw,
    )
