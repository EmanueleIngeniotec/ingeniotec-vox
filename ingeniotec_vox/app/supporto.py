"""Segnalazione dei problemi (issue su GitHub già compilata) e controllo delle nuove versioni."""

import json
import platform
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .. import REPO_URL, __version__

API_LATEST = REPO_URL.replace("https://github.com/", "https://api.github.com/repos/") + "/releases/latest"
MAX_URL = 7000          # GitHub rifiuta indirizzi troppo lunghi: il log si accorcia per starci
LOG_LINES = 40


ERROR_LINE = re.compile(r"Traceback|Error|Exception|errore|Errore|non riuscit|fallit|^\s*File \"")


def _tail(path: Path | None, n: int, errors_only: bool = False) -> str:
    """Ultime n righe del log. Con errors_only solo le righe d'errore (traceback compresi):
    le issue sono pubbliche e il resto del log del lavoro contiene nomi e titoli."""
    if not path or not path.is_file():
        return ""
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if errors_only:
        lines = [ln for ln in lines if ERROR_LINE.search(ln.split("  ", 1)[-1])]
    return "\n".join(lines[-n:])


def anonymize(text: str) -> str:
    """Toglie il nome dell'utente Windows dai percorsi."""
    return re.sub(r"(?i)([a-z]:(\\{1,2}|/)users(\\{1,2}|/))[^\\/\s'\"]+", r"\1<utente>", text)


def issue_url(job_log: Path | None, gui_log: Path | None, context: str = "") -> str:
    title = f"[{__version__}] "
    def body(n: int) -> str:
        parts = [
            "**Cosa stavi facendo e cosa è successo?**\n\n(scrivi qui)\n",
            f"**Versione:** {__version__} · Windows {platform.release()} ({platform.version()}) · "
            f"Python {sys.version.split()[0]}",
        ]
        if context:
            parts.append(f"**Situazione:** {context}")
        job = _tail(job_log, n, errors_only=True)
        if job:
            parts.append(f"**Errori nel log del lavoro:**\n```\n{anonymize(job)}\n```")
        gui = _tail(gui_log, n // 2)
        if gui:
            parts.append(f"**Errori della finestra:**\n```\n{anonymize(gui)}\n```")
        parts.append("_Prima di inviare controlla che il log non contenga dati riservati._")
        return "\n\n".join(parts)
    n = LOG_LINES
    while True:
        url = f"{REPO_URL}/issues/new?" + urllib.parse.urlencode({"title": title, "body": body(n)})
        if len(url) <= MAX_URL or n <= 2:
            return url
        n //= 2


def _version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def latest_release(timeout: float = 5.0) -> dict | None:
    """Ultima release pubblicata su GitHub se più nuova di questa, altrimenti None (anche se
    non ci sono release). Senza rete solleva un'eccezione: chi chiama decide se tacere."""
    req = urllib.request.Request(API_LATEST, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": "Ingeniotec-Vox"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:      # nessuna release pubblicata
            return None
        raise
    tag = data.get("tag_name", "")
    if _version_tuple(tag) > _version_tuple(__version__):
        return {"versione": tag.lstrip("vV"), "url": data.get("html_url") or f"{REPO_URL}/releases"}
    return None
