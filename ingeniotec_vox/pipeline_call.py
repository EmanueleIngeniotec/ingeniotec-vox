"""Pipeline "report di call": video → report snello + allegato (.docx e PDF).

Fasi, ognuna con checkpoint in `<out>/<nome>/_lavoro/`:
trascrizione → fotogrammi → partecipanti → voci → nomi → blocchi (map)
→ report (reduce) → schermate → documenti → PDF.

Le fasi voci e nomi (Fase 4) si saltano se manca sherpa-onnx o il modello delle voci:
in quel caso gli interventi si attribuiscono dal solo contenuto, come prima.
"""

import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from .core import claude, diarize, frames, transcribe
from .core.jobs import Job
from .docs import call_report, pdf
from .profiles import Profile

CORREZIONI = "correzioni_nomi.json"   # nomi corretti a mano dalla GUI (voce → nome)

# file di checkpoint di ogni fase, in ordine: `rifai` cancella dalla fase indicata in poi
STEPS = {
    "trascrizione": ["trascrizione.json"],
    "fotogrammi": ["fotogrammi.json", "fogli.json", "fotogrammi", "fogli"],
    "partecipanti": ["partecipanti.json"],
    "voci": ["voci.json", "voci_impronte.npy", CORREZIONI],
    "nomi": ["riquadri.json", "evidenze.json", "voci_fogli", "nomi.json"],
    "blocchi": ["blocchi"],
    "report": ["report.json"],
    "schermate": ["schermate.json", "schermate"],
}


def call_meta(video: Path) -> dict:
    """Data e ora dal nome del file (OBS: `2026-10-23 14-35-18`), altrimenti dalla data di modifica."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[-.](\d{2})", video.stem)
    if m:
        dt = datetime(*map(int, m.groups()))
    else:
        dt = datetime.fromtimestamp(video.stat().st_mtime)
    return {"data": f"{dt:%d/%m/%Y}", "ora": f"{dt:%H:%M}", "iso": f"{dt:%Y-%m-%d}",
            "video": video.name}


def default_name(video: Path) -> str:
    meta = call_meta(video)
    return f"Call_{meta['iso']}_{meta['ora'].replace(':', '')}"


def reset_from(job: Job, step: str, steps: dict = STEPS) -> None:
    names = list(steps)
    for s in names[names.index(step):]:
        for item in steps[s]:
            p = job.path(item)
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
    job.log(f"Checkpoint cancellati dalla fase '{step}' in poi")


def split_blocks(segments: list[dict], seconds: float) -> list[list[dict]]:
    """Blocchi di circa `seconds`, tagliati tra un segmento e l'altro."""
    blocks, cur, start = [], [], 0.0
    for s in segments:
        if cur and s["start"] - start >= seconds:
            blocks.append(cur)
            cur, start = [], s["start"]
        cur.append(s)
    if cur:
        blocks.append(cur)
    return blocks


def transcript_text(segments: list[dict]) -> str:
    """Una riga per segmento; con le voci separate, anche chi parla («?» se non identificato)."""
    def who(s):
        return f"{s['persona'] or '?'}: " if "persona" in s else ""
    return "\n".join(f"[{frames.hms(s['start'])}] {who(s)}{s['text']}" for s in segments)


ATTRIBUZIONE_VOCI = (
    "Ogni riga della trascrizione indica chi parla («Nome: …»), riconosciuto dalla voce e dal "
    "riquadro evidenziato nel video; «?» indica una voce non identificata. Attribuisci i contributi "
    "con questi nomi; scostati solo se la conversazione li contraddice in modo evidente (es. una "
    "persona viene chiamata per nome e risponde un'altra). I contributi di «?» includili solo se "
    "dal contenuto è chiaro chi parla.")
ATTRIBUZIONE_TESTO = "Se non è chiaro chi parla, non includere il contributo."


def voice_list(diar: dict, evid: dict, segments: list[dict]) -> str:
    """Descrizione delle voci per il prompt `nomi`: tempo, foglio dei campioni, frasi d'esempio."""
    lines = []
    for v in diar["voci"]:
        if v["secondi"] < diarize.MIN_VOICE:
            continue
        ev = evid.get(v["id"], {})
        sheet = (f"foglio `voci_fogli/{ev['foglio']}` con {len(ev['campioni'])} campioni"
                 if ev.get("foglio") else "nessun campione con riquadro evidenziato")
        own = [s for s, d in zip(segments, diar["segmenti"]) if d["voce"] == v["id"]]
        longest = sorted(own, key=lambda s: s["end"] - s["start"], reverse=True)[:4]
        frasi = "; ".join(f"«{s['text'][:160]}» ({frames.hms(s['start'])})"
                          for s in sorted(longest, key=lambda s: s["start"]))
        lines.append(f"- {v['id']}: {v['secondi'] / 60:.1f} min di parlato, {sheet}. Frasi: {frasi}")
    return "\n".join(lines) or "(nessuna voce)"


def voices_and_names(job: Job, prof: Profile, video: Path, tr: dict, part: dict, context: str,
                     names: str, frame_list: str) -> float | None:
    """Fasi voci e nomi. Scrive `persona` in ogni segmento di `tr`; restituisce la quota del
    parlato attribuita (None se le voci non si possono separare su questo PC)."""
    if not diarize.available():
        job.log("Voci non separate: manca sherpa-onnx o il modello in models\\diarizzazione "
                "(attribuzione dal solo contenuto)")
        return None
    import numpy as np

    def do_voci():
        last = {"f": 0.0}

        def prog(f):
            job.progress(f)
            if f - last["f"] >= 0.25:
                last["f"] = f
                job.log(f"  impronte delle voci {f:.0%}")
        res, emb = diarize.diarize(video, tr["segments"], progress=prog)
        np.save(job.path("voci_impronte.npy"), emb)
        return res

    voci = job.step("voci.json", "Separazione delle voci", do_voci)
    big = [v for v in voci["voci"] if v["secondi"] >= diarize.MIN_VOICE]
    job.log(f"  {len(big)} voci: " + ", ".join(f"{v['id']} {v['secondi'] / 60:.1f} min" for v in big))
    riq = job.step("riquadri.json", "Riquadri evidenziati nel video",
                   lambda: diarize.scan_highlights(video))
    evid = job.step("evidenze.json", "Campioni delle voci",
                    lambda: diarize.evidence(video, voci, riq, job.path("voci_fogli")))

    def do_nomi():
        answer = ask(job, prof, "nomi", "nomi", {
            "contesto": context, "partecipanti": names, "video": part["descrizione_video"],
            "voci": voice_list(voci, evid, tr["segments"]), "fotogrammi": frame_list},
            tools=["Read"])
        p = job.path("voci_impronte.npy")
        emb = np.load(p) if p.is_file() else np.zeros((0, 1), np.float32)
        res = diarize.resolve_names(voci, emb, evid, answer, len(tr["segments"]))
        return {**res, "risposta": answer}

    nomi = job.step("nomi.json", "Nomi delle voci", do_nomi)
    for vid, info in nomi["voci"].items():
        if info["secondi"] >= diarize.MIN_VOICE:
            acc = f", campioni concordi {info['accordo']:.0%}" if "accordo" in info else ""
            job.log(f"  {vid}: {info['nome'] or 'non identificata'} ({info['modo']}{acc})")
    job.log(f"  parlato attribuito: {nomi['copertura']:.0%} · "
            + ", ".join(f"{n} {s / 60:.1f} min" for n, s in nomi["persone"].items()))
    for s, nome in zip(tr["segments"], nomi["segmenti"]):
        s["persona"] = nome
    if job.has(CORREZIONI):
        return apply_corrections(job, tr["segments"], voci, job.load(CORREZIONI))
    return nomi["copertura"]


def apply_corrections(job: Job, segments: list[dict], voci: dict, corr: dict) -> float:
    """Nomi corretti a mano: `voci` {V1: nome} vale per tutti i segmenti della voce
    (anche se era mista); `persone` {vecchio: nuovo} rinomina ovunque. Nome vuoto = «?».
    Restituisce la nuova quota del parlato attribuita."""
    by_voice = corr.get("voci", {})
    rename = corr.get("persone", {})
    for s, d in zip(segments, voci["segmenti"]):
        if d["voce"] in by_voice:
            s["persona"] = by_voice[d["voce"]].strip()
        elif s["persona"] in rename:
            s["persona"] = rename[s["persona"]].strip()
    total = sum(s["end"] - s["start"] for s in segments) or 1.0
    covered = sum(s["end"] - s["start"] for s in segments if s["persona"])
    job.log(f"  nomi corretti a mano: {len(by_voice)} voci, {len(rename)} persone rinominate; "
            f"parlato attribuito {covered / total:.0%}")
    return round(covered / total, 3)


def ask(job: Job, prof: Profile, step: str, label: str, values: dict,
        tools: list[str] | None = None, timeout: int = 1200) -> dict:
    prompt = prof.prompt(step, **values)
    for attempt in (1, 2):
        try:
            res = claude.run(prompt, schema=prof.schema(step), system_prompt=prof.system(),
                             tools=tools, add_dirs=[job.work] if tools else None,
                             cwd=job.work, timeout=timeout)
            if res.data is None:
                raise claude.ClaudeError("Claude non ha restituito il risultato strutturato.")
            job.log(f"  {label}: risposta di Claude in {(res.duration_ms or 0) / 1000:.0f} s")
            return res.data
        except claude.ClaudeLimitError:
            raise
        except claude.ClaudeError as exc:
            if attempt == 2:
                raise
            job.log(f"  {label}: {exc} – nuovo tentativo")


def run(video: Path, out_root: Path, nome: str | None = None, *, with_transcript: bool = False,
        max_shots: int = 12, block_minutes: float = 20, workers: int = 3,
        model: str | None = None, redo: str | None = None, echo=print) -> list[Path]:
    video = Path(video).resolve()
    job = Job(Path(out_root) / (nome or default_name(video)), echo=echo, steps=STEPS)
    if redo:
        reset_from(job, redo)
    job.record(tipo="call", video=str(video), esito="in corso", aggiornato=now(),
               opzioni={"trascrizione": with_transcript, "max_schermate": max_shots,
                        "blocco_min": block_minutes})
    return guarded(job, lambda: _run(job, video, with_transcript, max_shots, block_minutes,
                                     workers, model))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def guarded(job: Job, fn) -> list[Path]:
    """Esegue il lavoro e ne scrive l'esito in `lavoro.json` (completato, interrotto, errore)."""
    try:
        files = fn()
    except claude.ClaudeLimitError as exc:
        job.record(esito="limite", messaggio=str(exc), aggiornato=now())
        raise
    except KeyboardInterrupt:
        job.record(esito="interrotto", messaggio="Annullato dall'utente.", aggiornato=now())
        raise
    except BaseException as exc:
        job.log(f"ERRORE: {type(exc).__name__}: {exc}")
        job.record(esito="errore", messaggio=f"{exc}", aggiornato=now())
        raise
    job.record(esito="completato", messaggio="", aggiornato=now(),
               file=[str(Path(f).resolve()) for f in files])
    return files


def retire_old(job: Job, new: list[Path]) -> None:
    """Documenti di un giro precedente con un altro nome (Claude ha cambiato il titolo):
    spostati in `_lavoro/versioni_precedenti` perché non restino accanto ai nuovi."""
    from .core.jobs import RECORD
    old = job.load(RECORD).get("file", []) if job.has(RECORD) else []
    keep = {Path(n).resolve() for p in new for n in (p, Path(p).with_suffix(".pdf"))}
    for f in map(Path, old):
        if f.is_file() and f.resolve() not in keep and f.resolve().parent == job.out.resolve():
            dst = job.path("versioni_precedenti") / f.name
            dst.parent.mkdir(exist_ok=True)
            f.replace(dst)
            job.log(f"  {f.name}: nome cambiato, versione precedente in _lavoro/versioni_precedenti")


def _run(job: Job, video: Path, with_transcript: bool, max_shots: int, block_minutes: float,
         workers: int, model: str | None) -> list[Path]:
    job.log(f"Report di call da {video}")
    meta = call_meta(video)
    prof = Profile("call_report")

    # 1. trascrizione
    state = {"last": 0.0}

    def progress(f):
        job.progress(f)
        if f - state["last"] >= 0.1:
            state["last"] = f
            job.log(f"  trascrizione {f:.0%}")

    tr = job.step("trascrizione.json", "Trascrizione",
                  lambda: transcribe.transcribe(video, model=model, progress=progress))
    meta["durata"] = tr["duration"]
    if not tr["segments"]:
        raise RuntimeError("Nella registrazione non è stato riconosciuto parlato.")

    # 2. fotogrammi candidati e fogli di anteprima
    fr = job.step("fotogrammi.json", "Fotogrammi candidati",
                  lambda: frames.candidates(video, job.path("fotogrammi")))
    job.step("fogli.json", "Fogli di anteprima",
             lambda: frames.contact_sheets(fr, job.path("fotogrammi"), job.path("fogli")))
    frame_list = ", ".join(f"{f['id']} ({f['min']})" for f in fr)

    # 3. partecipanti dai riquadri con i nomi
    part = job.step("partecipanti.json", "Partecipanti dai fotogrammi",
                    lambda: ask(job, prof, "partecipanti", "partecipanti",
                                {"fotogrammi": frame_list}, tools=["Read"]))
    meta["piattaforma"] = part["piattaforma"]
    names = ", ".join(p["nome"] for p in part["partecipanti"]) or "non rilevati"
    context = (f"registrazione «{video.name}» del {meta['data']} ore {meta['ora']}, durata "
               f"{call_report.duration_text(meta['durata'])}, {part['piattaforma'] or 'piattaforma non nota'}"
               + (f", finestra «{part['titolo_finestra']}»" if part["titolo_finestra"] else ""))

    # 4. voci e nomi (chi parla in ogni segmento)
    copertura = voices_and_names(job, prof, video, tr, part, context, names, frame_list)
    attribuzione = ATTRIBUZIONE_TESTO if copertura is None else ATTRIBUZIONE_VOCI

    # 5. estratto di ogni blocco (in parallelo, checkpoint per blocco)
    blocks = split_blocks(tr["segments"], block_minutes * 60)
    job.log(f"Analisi della trascrizione in {len(blocks)} parti …")

    def do_block(i: int) -> dict:
        seg = blocks[i]
        return job.step(f"blocchi/blocco_{i + 1:02d}.json", f"Parte {i + 1}/{len(blocks)}",
                        lambda: ask(job, prof, "blocco", f"parte {i + 1}", {
                            "contesto": context, "partecipanti": names,
                            "attribuzione": attribuzione, "n": i + 1, "tot": len(blocks),
                            "inizio": frames.hms(seg[0]["start"]), "fine": frames.hms(seg[-1]["end"]),
                            "trascrizione": transcript_text(seg)}))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        extracts = list(pool.map(do_block, range(len(blocks))))

    # 6. report finale
    blocchi_json = "\n\n".join(f"### Parte {i + 1}\n" + json.dumps(e, ensure_ascii=False)
                               for i, e in enumerate(extracts))
    rep = job.step("report.json", "Composizione del report",
                   lambda: ask(job, prof, "report", "report", {
                       "contesto": context, "partecipanti": names,
                       "video": part["descrizione_video"], "tot": len(blocks),
                       "blocchi": blocchi_json}))

    # 7. schermate
    arg_list = "\n".join(f"- {a['titolo']} ({a['inizio']}–{a['fine']})" for a in rep["argomenti"])
    sel = job.step("schermate.json", "Scelta delle schermate",
                   lambda: ask(job, prof, "schermate", "schermate", {
                       "contesto": context, "argomenti": arg_list,
                       "fotogrammi": frame_list, "max": max_shots}, tools=["Read"]))
    by_id = {f["id"]: f for f in fr}
    shots = []
    for s in sel["schermate"][:max_shots]:
        f = by_id.get(s["id"])
        if not f:
            job.log(f"  schermata {s['id']} sconosciuta: ignorata")
            continue
        dst = frames.crop(job.path("fotogrammi") / f["file"], job.path("schermate") / f"{f['id']}.jpg",
                          s["ritaglio"])
        shots.append({**s, "t": f["t"], "path": dst})

    # 8. documenti e PDF
    base = job.out / nome_file(rep["titolo"], meta)
    allegato = base.with_name(base.name + " - Allegato.docx")
    report = base.with_name(base.name + " - Report.docx")
    job.phase("documenti")
    retire_old(job, [report, allegato])
    job.log("Composizione dei documenti …")
    call_report.build_report(rep, meta, report, allegato.with_suffix(".pdf").name)
    call_report.build_allegato(rep, meta, shots, allegato, tr if with_transcript else None,
                               copertura=copertura)
    job.phase("pdf")
    job.log("Esportazione PDF con Word …")
    pdfs = pdf.export([report, allegato])
    for p in pdfs:
        n = pdf.page_count(p)
        pdf.contact_sheet(p, job.path(f"controllo_{p.stem}.png"))
        job.log(f"  {p.name}: {n} pagine")
    job.log(f"Fatto. Documenti in {job.out}")
    return [report, allegato, *pdfs]


def nome_file(titolo: str, meta: dict) -> str:
    clean = re.sub(r'[<>:"/\\|?*]+', " ", titolo)
    clean = re.sub(r"\s+", " ", clean).strip()[:80]
    return f"{meta['iso']} {clean}"
