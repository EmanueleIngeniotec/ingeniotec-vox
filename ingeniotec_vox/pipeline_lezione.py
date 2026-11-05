"""Pipeline "dispense di una lezione": video → dispensa + scheda di ripasso (.docx e PDF).

Fasi, ognuna con checkpoint in `<out>/<nome>/_lavoro/`:
trascrizione → fotogrammi → struttura → capitoli (in parallelo, con le schermate)
→ fonti (verifica con ricerca web, a lotti) → scheda → documenti → PDF con controllo
dell'impaginazione → aggiornamento della guida all'esame (facoltativo).

Profili: `lesson_exam` (corso con esame) e `lesson_generic` (senza esame, prova
pratica né guida); le differenze stanno nei prompt e nell'opzione `esame` del profilo.
"""

import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .core import claude, frames, transcribe
from .core.jobs import Job
from .docs import call_report, guida as guide_doc, lezione, pdf
from .docs.lezione import hm, to_secs
from .pipeline_call import (ask, call_meta, guarded, now, reset_from as _reset, retire_old,
                            transcript_text)
from .profiles import Profile

STEPS = {
    "trascrizione": ["trascrizione.json"],
    "fotogrammi": ["fotogrammi.json", "fogli.json", "fotogrammi", "fogli"],
    "struttura": ["struttura.json"],
    "capitoli": ["capitoli"],
    "fonti": ["fonti", "link.json"],
    "scheda": ["scheda.json"],
    "guida": ["guida.json"],
}
PROFILES = {"esame": "lesson_exam", "generico": "lesson_generic"}
MAX_FRAMES = 240            # lezioni di 3–4 ore con schermo condiviso
MARGIN = 30                 # secondi di trascrizione e fotogrammi oltre i limiti del capitolo
CLAIMS_PER_CALL = 6         # affermazioni verificate in una richiesta con ricerca web
CLAIMS_WARNING = 60         # nessun limite alle verifiche, ma oltre questo numero un avviso nel log
# Dimensioni della dispensa L9 fatta a mano (33 pagine): senza limiti espliciti Claude ne scrive
# il triplo. I totali si ripartiscono sui capitoli in base a durata e peso per l'esame.
TOTAL_WORDS = 8000
TOTAL_SHOTS = 24
TOTAL_QUESTIONS = 30
WEIGHTS = {"basso": 0.5, "medio": 0.8, "alto": 1.0, "altissimo": 1.3}


def budgets(chapters: list[dict], duration: float, max_shots: int) -> list[dict]:
    """Limiti per capitolo (parole, schermate, domande, sottotitoli); le verifiche
    non hanno limite: una per ogni affermazione da controllare."""
    starts = [to_secs(c["inizio"]) for c in chapters] + [duration]
    w = [max(starts[i + 1] - starts[i], 60) * WEIGHTS.get(c["peso"].split(":")[0].strip().lower(), 1.0)
         for i, c in enumerate(chapters)]
    out = []
    for x in w:
        share = x / sum(w)
        words = min(max(round(TOTAL_WORDS * share / 10) * 10, 150), 800)
        out.append({"parole": words,
                    "max_schermate": min(max_shots, max(1, round(TOTAL_SHOTS * share))),
                    "autoverifica": min(3, max(1, round(TOTAL_QUESTIONS * share))),
                    "sottotitoli": "nessuno" if words < 350 else ("due" if words < 600 else "tre")})
    return out


def parallel(fn, n: int, workers: int) -> list:
    """`fn(0..n-1)` in parallelo; al primo limite d'uso di Claude le richieste non ancora
    partite non si lanciano (fallirebbero tutte) e l'errore risale."""
    hit = []

    def guarded(i):
        if hit:
            raise hit[0]
        try:
            return fn(i)
        except claude.ClaudeLimitError as exc:
            hit.append(exc)
            raise

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(guarded, range(n)))


def reset_from(job: Job, step: str) -> None:
    _reset(job, step, STEPS)


def compact_transcript(segments: list[dict], seconds: float = 30) -> str:
    """Paragrafi di circa `seconds` con il minuto di inizio: la lezione intera sta in una richiesta."""
    lines, cur = [], []
    for s in segments:
        if cur and s["start"] - cur[0]["start"] >= seconds:
            lines.append(cur); cur = []
        cur.append(s)
    if cur:
        lines.append(cur)
    return "\n".join(f"[{frames.hms(g[0]['start'])}] " + " ".join(s["text"] for s in g) for g in lines)


def check_link(url: str, timeout: int = 20) -> bool:
    """Il link esiste? Molti siti ufficiali rifiutano i client automatici (401/403/405/429):
    in quel caso la pagina c'è e il link si tiene; 404, 410, errori del server e DNS no."""
    if not url.lower().startswith(("http://", "https://")):
        return False
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 400
    except urllib.error.HTTPError as exc:
        return exc.code in (401, 403, 405, 429)
    except Exception:
        return False


def run(video: Path, out_root: Path, *, corso: str = "", numero: int | None = None,
        profilo: str = "esame", guida: Path | None = None, nome: str | None = None,
        docente: str | None = None, max_shots: int = 3, workers: int = 3,
        model: str | None = None, redo: str | None = None, echo=print) -> list[Path]:
    """`guida`: la guida all'esame del corso da aggiornare (solo profilo con esame e numero)."""
    video = Path(video).resolve()
    prof = Profile(PROFILES[profilo])
    exam = prof.option("esame", True)
    if guida and not (exam and numero):
        raise ValueError("La guida all'esame si aggiorna solo con il profilo «esame» e il numero della lezione.")
    meta = {**call_meta(video), "corso": corso, "numero": numero}
    job = Job(Path(out_root) / (nome or (f"L{numero}_{meta['iso']}" if numero else f"Lezione_{meta['iso']}")),
              echo=echo, steps=STEPS)
    if redo:
        reset_from(job, redo)
    job.record(tipo="lezione", video=str(video), esito="in corso", aggiornato=now(),
               opzioni={"profilo": profilo, "corso": corso, "numero": numero, "docente": docente,
                        "guida": str(Path(guida).resolve()) if guida else None,
                        "max_schermate": max_shots})
    return guarded(job, lambda: _run(job, video, prof, exam, meta, corso, numero, guida, docente,
                                     max_shots, workers, model))


def _run(job, video, prof, exam, meta, corso, numero, guida, docente, max_shots, workers, model):
    job.log(f"Dispense della lezione {numero or ''} da {video} (profilo {prof.name})".replace("  ", " "))
    base = {"corso": corso or "non indicato",
            "lezione": f"Lezione {numero} del {meta['data']}" if numero else f"Lezione del {meta['data']}"}

    # 1. trascrizione
    state = {"last": 0.0}

    def progress(f):
        job.progress(f)
        if f - state["last"] >= 0.05:
            state["last"] = f
            job.log(f"  trascrizione {f:.0%}")

    tr = job.step("trascrizione.json", "Trascrizione",
                  lambda: transcribe.transcribe(video, model=model, progress=progress))
    meta["durata"] = tr["duration"]
    meta["durata_testo"] = call_report.duration_text(tr["duration"])
    if not tr["segments"]:
        raise RuntimeError("Nella registrazione non è stato riconosciuto parlato.")

    # 2. fotogrammi candidati (i fogli servono solo per il controllo a occhio)
    fr = job.step("fotogrammi.json", "Fotogrammi candidati",
                  lambda: frames.candidates(video, job.path("fotogrammi"), max_candidates=MAX_FRAMES))
    job.step("fogli.json", "Fogli di anteprima",
             lambda: frames.contact_sheets(fr, job.path("fotogrammi"), job.path("fogli")))

    # 3. struttura: titolo, capitoli con peso, indice del video
    context = (f"«{video.name}», durata {meta['durata_testo']}"
               + (f"; docente: {docente}" if docente else ""))
    st = job.step("struttura.json", "Struttura della dispensa",
                  lambda: ask(job, prof, "struttura", "struttura", {
                      **base, "contesto": context, "max_indice": round(meta["durata"] / 160),
                      "trascrizione": compact_transcript(tr["segments"])}, timeout=1800))
    if docente:
        st["docente"] = docente
    chapters = st["capitoli"]
    job.log(f"  {st['titolo']}: {len(chapters)} capitoli, {len(st['indice'])} voci di indice")
    chapter_list = "\n".join(f"{n}. {c['titolo']} ({c['inizio']}–{c['fine']})"
                             for n, c in enumerate(chapters, 1))
    limits = budgets(chapters, meta["durata"], max_shots)

    # 4. capitoli, in parallelo; ognuno sceglie le proprie schermate
    def do_chapter(i: int) -> dict:
        c = chapters[i]
        t0 = to_secs(c["inizio"]) - MARGIN
        t1 = (to_secs(chapters[i + 1]["inizio"]) if i + 1 < len(chapters) else meta["durata"]) + MARGIN
        seg = [s for s in tr["segments"] if t0 <= s["start"] < t1]
        shots = [f"{f['id']} ({hm(f['t'])}, {f['file']})" for f in fr if t0 <= f["t"] < t1]
        return job.step(f"capitoli/capitolo_{i + 1:02d}.json", f"Capitolo {i + 1}/{len(chapters)}",
                        lambda: ask(job, prof, "capitolo", f"capitolo {i + 1}", {
                            **base, "titolo_lezione": st["titolo"], "docente": st["docente"] or "non noto",
                            "capitoli": chapter_list, "n": i + 1, "titolo": c["titolo"],
                            "inizio": hm(c["inizio"]), "fine": hm(c["fine"]), "peso": c["peso"],
                            "contenuto": c["contenuto"], **limits[i],
                            "fotogrammi": "; ".join(shots) or "nessuno",
                            "trascrizione": transcript_text(seg)},
                            tools=["Read"], timeout=1800))

    caps = parallel(do_chapter, len(chapters), workers)

    # 5. verifica delle fonti, a lotti con ricerca web
    claims = []
    for n, cap in enumerate(caps, 1):
        k = 0
        for e in cap["elementi"]:
            if e["tipo"] == "verifica" and e.get("testo"):
                k += 1
                e["chiave"] = f"c{n:02d}_{k}"
                claims.append((e["chiave"], chapters[n - 1]["titolo"], e["testo"]))
    if len(claims) > CLAIMS_WARNING:
        job.log(f"  ATTENZIONE: {len(claims)} affermazioni da verificare, più del solito: "
                "controllare che i capitoli non segnalino cose ovvie o già viste a video")

    # la stessa affermazione detta in più capitoli si verifica una volta sola (box alla prima)
    if len(claims) > 1:
        text = "\n".join(f"- `{key}`: {claim}" for key, _, claim in claims)
        dup = job.step("fonti/doppioni.json", "Doppioni tra le verifiche",
                       lambda: ask(job, prof, "doppioni", "doppioni", {
                           **base, "titolo_lezione": st["titolo"], "verifiche": text}))
        order = [key for key, _, _ in claims]
        drop = {d["chiave"] for d in dup["doppioni"]
                if d["chiave"] in order and d["come"] in order and order.index(d["come"]) < order.index(d["chiave"])}
        if drop:
            job.log(f"  {len(drop)} doppioni tolti: " + ", ".join(sorted(drop)))
            claims = [c for c in claims if c[0] not in drop]
            for cap in caps:
                cap["elementi"] = [e for e in cap["elementi"] if e.get("chiave") not in drop]
    lots = [claims[k:k + CLAIMS_PER_CALL] for k in range(0, len(claims), CLAIMS_PER_CALL)]
    job.log(f"Verifica delle fonti: {len(claims)} affermazioni in {len(lots)} richieste …")

    def do_lot(j: int) -> dict:
        text = "\n".join(f"- `{key}` (capitolo «{tit}»): {claim}" for key, tit, claim in lots[j])
        return job.step(f"fonti/lotto_{j + 1:02d}.json", f"Fonti {j + 1}/{len(lots)}",
                        lambda: ask(job, prof, "fonti", f"fonti {j + 1}", {
                            **base, "titolo_lezione": st["titolo"], "verifiche": text},
                            tools=["WebSearch", "WebFetch"], timeout=2400))

    results = [e for lot in parallel(do_lot, len(lots), min(workers, 2)) for e in lot["esiti"]]
    urls = sorted({f["url"] for e in results for f in e["fonti"]})
    links = job.load("link.json") if job.has("link.json") else {}
    todo = [u for u in urls if u not in links]
    if todo:
        job.log(f"Controllo dei link: {len(todo)} indirizzi …")
        with ThreadPoolExecutor(max_workers=8) as pool:
            links.update(zip(todo, pool.map(check_link, todo)))
        job.save("link.json", links)
    bad = [u for u in urls if not links[u]]
    if bad:
        job.log(f"  {len(bad)} link non raggiungibili, tolti: " + ", ".join(bad))
    # senza fonti valide il box resta, come «non verificabile» con il minuto del video
    found = {}
    for e in results:
        good = [f for f in e["fonti"] if links.get(f["url"])]
        if e["esito"] != "non_verificabile" and e["testo"].strip() and good:
            found[e["chiave"]] = {"testo": e["testo"], "fonti": good}
    boxes = {}
    for key, _, claim in claims:
        if key in found:
            boxes[key] = found[key]
            continue
        e = next(x for cap in caps for x in cap["elementi"] if x.get("chiave") == key)
        try:
            where = f" al min. {hm(e['min'])}"
        except (KeyError, ValueError):
            where = ""
        boxes[key] = {"testo": f"Non verificabile: {claim.rstrip('.')}. Nessuna fonte ufficiale trovata: "
                               f"controllare nella registrazione{where}.", "fonti": []}
    job.log(f"  box VERIFICA FONTI: {len(found)} verificati, {len(claims) - len(found)} non verificabili")

    # schermate ritagliate e box risolti negli elementi
    by_id = {f["id"]: f for f in fr}
    for n, cap in enumerate(caps, 1):
        for e in cap["elementi"]:
            if e["tipo"] == "verifica":
                e["box"] = boxes.get(e.get("chiave"))
            elif e["tipo"] == "schermata":
                f = by_id.get(e.get("id", ""))
                if not f:
                    job.log(f"  capitolo {n}: fotogramma {e.get('id')} sconosciuto, ignorato")
                    continue
                e["path"] = frames.crop(job.path("fotogrammi") / f["file"],
                                        job.path("schermate") / f"c{n:02d}_{f['id']}.jpg", e.get("ritaglio"))
                e["t"] = f["t"]

    # 6. scheda di ripasso
    def digest() -> str:
        out = []
        for c, cap in zip(chapters, caps):
            els = []
            for e in cap["elementi"]:
                if e["tipo"] == "schermata":
                    continue
                if e["tipo"] == "verifica":
                    if e.get("box"):
                        els.append({"tipo": "verifica fonti", "testo": e["box"]["testo"]})
                    continue
                els.append({k: v for k, v in e.items() if k not in ("chiave", "box", "path", "t")})
            out.append({"capitolo": c["titolo"], "peso": c["peso"], "elementi": els,
                        "saper_fare": cap.get("saper_fare", [])})
        return json.dumps(out, ensure_ascii=False)

    sc = job.step("scheda.json", "Scheda di ripasso",
                  lambda: ask(job, prof, "scheda", "scheda", {
                      **base, "titolo_lezione": st["titolo"], "dispensa": digest()}, timeout=1800))

    # 7. documenti e PDF
    title = re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*]+', " ", st["titolo"])).strip()[:90]
    prefix = f"L{numero} - " if numero else ""
    dispensa = job.out / f"{prefix}Dispensa - {title}.docx"
    scheda = job.out / f"{prefix}Scheda di ripasso.docx"
    job.phase("documenti")
    retire_old(job, [dispensa, scheda])
    job.log("Composizione dei documenti …")
    lezione.build_dispensa(st, caps, meta, dispensa, exam=exam)
    lezione.build_scheda(sc, st, meta, dispensa.stem, scheda, exam=exam)
    job.phase("pdf")
    job.log("Esportazione PDF con Word e controllo dell'impaginazione …")
    pdfs = pdf.export([dispensa, scheda], layout=True, log=job.log)
    for p in pdfs:
        pdf.contact_sheet(p, job.path(f"controllo_{p.stem}.png"))
        job.log(f"  {p.name}: {pdf.page_count(p)} pagine")
    files = [dispensa, scheda, *pdfs]

    # 8. guida all'esame: modifiche proposte da Claude, applicate alla copia «prima della L<n>»
    if guida:
        guida = Path(guida).resolve()
        src = guide_doc.source_for(guida, numero)
        ops = job.step("guida.json", "Aggiornamento della guida all'esame",
                       lambda: ask(job, prof, "guida", "guida", {
                           **base, "titolo_lezione": st["titolo"], "numero": numero,
                           "dispensa": dispensa.stem, "scheda": scheda.stem,
                           "guida": guide_doc.describe(src),
                           "dispensa_json": digest() + "\n\nScheda di ripasso:\n"
                                            + json.dumps(sc, ensure_ascii=False)},
                           timeout=1800))
        for o in ops["operazioni"]:
            job.log(f"  guida: {o['op']} {o['dove']} – {o['motivo']}")
        n = guide_doc.apply(src, ops["operazioni"], guida, log=job.log)
        job.log(f"  {guida.name}: {n} modifiche su {len(ops['operazioni'])}; "
                f"versione precedente in {guide_doc.backup_path(guida, numero)}")
        gpdf = pdf.export([guida], layout=True, log=job.log, pdf_dir=job.work)[0]
        pdf.contact_sheet(gpdf, job.path(f"controllo_{gpdf.stem}.png"))
        files.append(guida)
    job.log(f"Fatto. Documenti in {job.out}")
    return files
