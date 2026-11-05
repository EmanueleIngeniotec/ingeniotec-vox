"""Fase 0 – prova di fumo: controllo ambiente, trascrizione su GPU, chiamata a Claude.

Uso:
    vox_smoke --check
    vox_smoke AUDIO_O_VIDEO [--seconds 60] [--model PERCORSO] [--out CARTELLA]
"""

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__
from .core import claude, env_check, transcribe

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "titolo": {"type": "string"},
        "sintesi": {"type": "string"},
        "argomenti": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titolo", "sintesi", "argomenti"],
    "additionalProperties": False,
}


def _print_checks(checks: list[env_check.Check]) -> bool:
    for c in checks:
        mark = "OK " if c.ok else ("!! " if c.blocking else "?? ")
        print(f"  [{mark}] {c.name}: {c.message}")
    return all(c.ok or not c.blocking for c in checks)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="vox_smoke", description="Ingeniotec Vox – prova Fase 0")
    p.add_argument("audio", nargs="?", type=Path, help="file audio o video da trascrivere")
    p.add_argument("--check", action="store_true", help="solo controllo dell'ambiente")
    p.add_argument("--seconds", type=float, default=60, help="secondi iniziali da trascrivere")
    p.add_argument("--model", help="cartella del modello faster-whisper")
    p.add_argument("--out", type=Path, default=Path("_out"), help="cartella dei risultati")
    a = p.parse_args(argv)

    print(f"Ingeniotec Vox {__version__} – prova Fase 0")
    print("Controllo ambiente:")
    if not _print_checks(env_check.run_all(a.out.resolve())):
        print("Ambiente non pronto: correggere i punti segnati con !!")
        return 2
    if a.check:
        return 0
    if not a.audio or not a.audio.is_file():
        p.error("indicare un file audio o video esistente")

    a.out.mkdir(parents=True, exist_ok=True)

    print(f"Trascrizione dei primi {a.seconds:.0f} s di {a.audio.name} …")
    t0 = time.perf_counter()
    tr = transcribe.transcribe(a.audio, model=a.model, max_seconds=a.seconds)
    t_tr = time.perf_counter() - t0
    (a.out / "trascrizione.json").write_text(json.dumps(tr, ensure_ascii=False, indent=2), "utf-8")
    print(f"  {len(tr['segments'])} segmenti, lingua {tr['language']} "
          f"({tr['language_probability']:.0%}), {t_tr:.1f} s")

    text = "\n".join(f"[{s['start']:.0f}s] {s['text']}" for s in tr["segments"])
    if not text:
        print("  Nessun parlato riconosciuto: chiamata a Claude saltata.")
        return 1

    print("Chiamata a Claude Code (headless) …")
    t0 = time.perf_counter()
    res = claude.run(
        "Ecco la trascrizione di un breve estratto audio. Restituisci un titolo, "
        "una sintesi di 2-3 frasi in italiano e l'elenco degli argomenti.\n\n" + text,
        schema=SUMMARY_SCHEMA,
    )
    t_cl = time.perf_counter() - t0
    (a.out / "claude.json").write_text(json.dumps(res.raw, ensure_ascii=False, indent=2), "utf-8")
    data = res.data or {}
    print(f"  {t_cl:.1f} s – {data.get('titolo', '(senza titolo)')}")
    print(f"  {data.get('sintesi', res.text)}")
    print(f"Risultati in {a.out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
