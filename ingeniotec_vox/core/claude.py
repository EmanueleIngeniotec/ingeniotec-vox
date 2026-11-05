"""Unico punto di contatto con Claude Code CLI in modalità headless (`claude -p`).

Il prompt passa da stdin (niente limiti di lunghezza della riga di comando);
con `schema` l'output è JSON validato da Claude Code (`structured_output`).
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .env_check import CREATE_NO_WINDOW, claude_exe


class ClaudeError(RuntimeError):
    pass


class ClaudeLimitError(ClaudeError):
    """Limite d'uso del piano raggiunto: inutile riprovare subito."""


@dataclass
class ClaudeResult:
    text: str
    data: dict | None
    cost_usd: float | None
    duration_ms: int | None
    raw: dict


def run(prompt: str, *, schema: dict | None = None, system_prompt: str | None = None,
        tools: list[str] | None = None, add_dirs: list[Path] | None = None,
        cwd: Path | None = None, model: str | None = None, timeout: int = 600) -> ClaudeResult:
    exe = claude_exe()
    if not exe:
        raise ClaudeError("Claude Code non è installato.")
    args = [exe, "-p", "--output-format", "json", "--no-session-persistence",
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

    try:
        proc = subprocess.run(args, input=prompt, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              cwd=cwd, creationflags=CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise ClaudeError(f"Claude non ha risposto entro {timeout} s.") from exc

    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeError(f"Risposta non valida da Claude Code (codice {proc.returncode}): "
                          f"{(proc.stderr or proc.stdout).strip()[:500]}") from exc
    if raw.get("is_error"):
        msg = str(raw.get("result") or raw.get("subtype"))
        # es. "You've hit your session limit · resets 7pm (Europe/Rome)"
        if re.search(r"usage limit|limit reached|hit your \w*\s*limit|rate limit|session limit|weekly limit",
                     msg, re.I):
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
