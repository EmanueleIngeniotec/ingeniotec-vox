"""Riga di comando di Ingeniotec Vox (la GUI la lancia come processo separato).

    python -m ingeniotec_vox.cli call <video> [--out DIR] [--nome NOME] ...
    python -m ingeniotec_vox.cli lezione <video> --corso CORSO --numero N [--guida GUIDA.docx] ...
    python -m ingeniotec_vox.cli lezione <video> --profilo generico [--corso CORSO] [--numero N] ...
"""

import argparse
import sys
from pathlib import Path

from . import __version__, pipeline_call, pipeline_lezione
from .core import claude, env_check
from .core.jobs import emit
from .docs.pdf import PdfError

# codici di uscita, letti anche dalla GUI
OK, ERR_AMBIENTE, ERR_CLAUDE, ERR_LIMITE, ERR_WORD, ERR_ALTRO = 0, 2, 3, 4, 5, 6


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(prog="vox", description=f"Ingeniotec Vox {__version__}")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("call", help="report PDF di una call video")
    c.add_argument("video", type=Path, help="registrazione della call (mp4, mkv, …)")
    c.add_argument("--out", type=Path, default=Path("_out"), help="cartella dei risultati")
    c.add_argument("--nome", help="nome della cartella del lavoro (predefinito: Call_<data>_<ora>)")
    c.add_argument("--trascrizione", action="store_true", help="trascrizione in appendice all'allegato")
    c.add_argument("--max-schermate", type=int, default=12, help="schermate massime nell'allegato")
    c.add_argument("--blocco-min", type=float, default=20, help="minuti di trascrizione per richiesta")
    c.add_argument("--model", help="cartella del modello faster-whisper")
    c.add_argument("--rifai", choices=list(pipeline_call.STEPS),
                   help="rifà il lavoro da questa fase in poi (le precedenti restano)")
    l = sub.add_parser("lezione", help="dispensa e scheda di ripasso di una lezione")
    l.add_argument("video", type=Path, help="registrazione della lezione (mp4, mkv, …)")
    l.add_argument("--profilo", choices=list(pipeline_lezione.PROFILES), default="esame",
                   help="esame: corso con esame (predefinito); generico: senza esame né prova pratica")
    l.add_argument("--corso", default="", help="nome del corso (es. \"Certificazione BIM\"); obbligatorio con esame")
    l.add_argument("--numero", type=int, help="numero della lezione (titoli e nomi dei file); obbligatorio con esame")
    l.add_argument("--guida", type=Path,
                   help="guida all'esame (.docx) da aggiornare con la lezione; copia della versione "
                        "precedente in _versioni_precedenti accanto alla guida")
    l.add_argument("--docente", help="nome del docente, se non si vuole ricavarlo dalla lezione")
    l.add_argument("--out", type=Path, default=Path("_out"), help="cartella dei risultati")
    l.add_argument("--nome", help="nome della cartella del lavoro (predefinito: L<numero>_<data>)")
    l.add_argument("--max-schermate", type=int, default=3, help="schermate massime per capitolo")
    l.add_argument("--model", help="cartella del modello faster-whisper")
    l.add_argument("--rifai", choices=list(pipeline_lezione.STEPS),
                   help="rifà il lavoro da questa fase in poi (le precedenti restano)")
    a = p.parse_args(argv)

    if not a.video.is_file():
        p.error(f"file non trovato: {a.video}")
    if a.cmd == "lezione":
        if a.profilo == "esame" and (not a.corso or not a.numero):
            p.error("con il profilo esame servono --corso e --numero")
        if a.guida and (a.profilo != "esame" or not a.guida.is_file()):
            p.error("--guida: serve il profilo esame e un file .docx esistente")
    checks = env_check.run_all(a.out.resolve())
    bad = [ch for ch in checks if not ch.ok and ch.blocking]
    for ch in bad:
        print(f"[!!] {ch.name}: {ch.message}")
    if bad:
        emit(errore="ambiente", messaggio=" ".join(ch.message for ch in bad))
        return ERR_AMBIENTE

    try:
        if a.cmd == "lezione":
            files = pipeline_lezione.run(a.video, a.out, corso=a.corso, numero=a.numero, nome=a.nome,
                                         profilo=a.profilo, guida=a.guida,
                                         docente=a.docente, max_shots=a.max_schermate,
                                         model=a.model, redo=a.rifai)
        else:
            files = pipeline_call.run(a.video, a.out, a.nome, with_transcript=a.trascrizione,
                                      max_shots=a.max_schermate, block_minutes=a.blocco_min,
                                      model=a.model, redo=a.rifai)
    except claude.ClaudeLimitError as exc:
        return _fail(ERR_LIMITE, "limite", str(exc))
    except claude.ClaudeError as exc:
        return _fail(ERR_CLAUDE, "claude", f"{exc}")
    except PdfError as exc:
        return _fail(ERR_WORD, "word", f"{exc} Chiudere eventuali finestre di Word bloccate e riprendere.")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return _fail(ERR_ALTRO, "altro", f"Errore imprevisto ({type(exc).__name__}: {exc}).")
    for f in files:
        print(f"  {f}")
    emit(fine=[str(Path(f).resolve()) for f in files])
    return OK


def _fail(code: int, kind: str, msg: str) -> int:
    print(f"Interrotto: {msg}")
    print("Rilanciando lo stesso comando il lavoro riprende dalla fase interrotta.")
    emit(errore=kind, messaggio=msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
