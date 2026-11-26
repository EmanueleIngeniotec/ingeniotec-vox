"""Voci e nomi delle persone in una call (solo pipeline call).

1. **Voci** (`diarize`): ogni segmento di Whisper è diviso in pezzi di ~3 s; di ogni pezzo
   si calcola l'impronta della voce (embedding sherpa-onnx, modello libero, offline, CPU)
   e i pezzi si raggruppano per somiglianza (clustering agglomerativo). Ogni segmento di
   Whisper riceve la voce che copre più tempo al suo interno. Le voci sono V1, V2, …
   in ordine di tempo parlato.
   **Chi registra**: il suo riquadro in Teams non viene evidenziato in modo riconoscibile
   (riquadro piccolo con le iniziali), quindi dal video non si può riconoscere. Se la
   registrazione ha una seconda traccia audio con il solo microfono (OBS: traccia 1 = tutto,
   traccia 2 = microfono), i pezzi in cui l'energia viene soprattutto dal microfono sono
   di persone nella stanza di chi registra (`microfono: true`) e si raggruppano a parte.
   Le voci del microfono non hanno campioni video (quando parlano, Teams evidenzia il riquadro
   di chi registra, che non si riconosce); i frammenti brevi vanno alla voce grande del
   microfono più simile. Tra queste voci, chi registra (`chi_registra: true`) è la più
   forte nel microfono (è la più vicina) e, se c'è un'impronta salvata dalle call precedenti
   (`impronte.json` in `%LOCALAPPDATA%\\Ingeniotec Vox`), la più simile a quella. Se i due
   indizi non bastano o non concordano, la scelta è segnata come incerta.
2. **Riquadro evidenziato** (`scan_highlights`, `evidence`): sui fotogrammi chiave del video
   si cerca il bordo con cui Teams evidenzia chi parla; per ogni voce si raccolgono
   i riquadri evidenziati mentre parla solo lei e si compone un foglio per Claude,
   che legge il nome nel riquadro o riconosce il volto nella griglia con i nomi.

Modelli in `models/diarizzazione/` (accanto all'eseguibile o nella cartella corrente),
oppure nella cartella indicata da `VOX_DIARIZE_DIR`.
"""

import os
import sys
from pathlib import Path

from .transcribe import SAMPLE_RATE, audio_tracks, decode_audio

MODEL_DIRNAME = "diarizzazione"
EMBEDDING_MODEL = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"

UNIT_SECONDS = 3.0      # lunghezza indicativa di un pezzo di parlato
MIN_UNIT = 1.0          # pezzi più corti si allargano attorno al centro
THRESHOLD = 0.60        # somiglianza (coseno) minima per unire due gruppi
MIN_VOICE = 8.0         # secondi: sotto, una voce si unisce alla più simile …
MERGE_SMALL = 0.35      # … se la somiglianza è almeno questa, altrimenti resta a sé
MIC_SHARE = 0.5         # quota dell'energia di un pezzo che viene dal microfono: da qui parla chi registra
MIC_MAX = 0.9           # se il microfono domina quasi tutto il parlato, la traccia 2 non è il solo microfono
LOUD_GAP = 4.0          # dB: di tanto chi registra deve superare gli altri nel microfono per essere certo
PRINT_MIN = 0.40        # somiglianza minima con l'impronta salvata di chi registra …
PRINT_MARGIN = 0.10     # … e vantaggio sulla seconda voce per contare
PRINT_FILE = "impronte.json"
PRINT_KEEP = 10         # l'impronta salvata è la media delle ultime ~10 call

# colori del bordo di chi parla (RGB) e tolleranza per canale
HIGHLIGHT_COLORS = [(127, 132, 245)]   # Microsoft Teams (nuovo Teams, tema scuro e chiaro)
COLOR_TOL = 30
LAG = 0.8               # s: Teams evidenzia il riquadro con un po' di ritardo
SAMPLES_PER_VOICE = 8
PURE = 0.75             # quota dei campioni con lo stesso nome per dare il nome a tutta la voce


def models_dir() -> Path:
    if os.environ.get("VOX_DIARIZE_DIR"):
        dirs = [Path(os.environ["VOX_DIARIZE_DIR"])]
    else:
        bases = [Path(sys.executable).parent] if getattr(sys, "frozen", False) else []
        bases += [Path.cwd(), Path(__file__).resolve().parents[2]]
        dirs = [b / "models" / MODEL_DIRNAME for b in bases]
    for d in dirs:
        if (d / EMBEDDING_MODEL).is_file():
            return d
    raise FileNotFoundError(
        f"Modello delle voci non trovato: serve models\\{MODEL_DIRNAME}\\{EMBEDDING_MODEL}")


def available() -> bool:
    try:
        import sherpa_onnx  # noqa: F401
        models_dir()
        return True
    except (ImportError, FileNotFoundError):
        return False


# ---------------------------------------------------------------- voci

def _units(segments: list[dict]) -> list[tuple[int, float, float]]:
    units = []
    for i, s in enumerate(segments):
        length = s["end"] - s["start"]
        n = max(1, round(length / UNIT_SECONDS))
        for k in range(n):
            units.append((i, s["start"] + k * length / n, s["start"] + (k + 1) * length / n))
    return units


def _embeddings(samples, units, threads: int, progress=None):
    import numpy as np
    import sherpa_onnx as so

    cfg = so.SpeakerEmbeddingExtractorConfig(model=str(models_dir() / EMBEDDING_MODEL),
                                             num_threads=threads)
    ex = so.SpeakerEmbeddingExtractor(cfg)
    out = []
    for n, (_, u0, u1) in enumerate(units):
        if u1 - u0 < MIN_UNIT:
            c = (u0 + u1) / 2
            u0, u1 = c - MIN_UNIT / 2, c + MIN_UNIT / 2
        x = samples[max(0, int(u0 * SAMPLE_RATE)):int(u1 * SAMPLE_RATE)]
        st = ex.create_stream()
        st.accept_waveform(SAMPLE_RATE, x)
        st.input_finished()
        out.append(ex.compute(st))
        if progress and n % 200 == 0:
            progress(n / len(units))
    e = np.array(out, dtype=np.float32)
    return e / np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-9)


def _frame_energy(x, hop: int):
    import numpy as np

    n = len(x) // hop
    return (x[:n * hop].astype(np.float64).reshape(n, hop) ** 2).sum(axis=1)


def _unit_energy(x, units, hop: int = 160):
    """Energia e numero di campioni di `x` dentro ogni pezzo."""
    import numpy as np

    cum = np.concatenate([[0.0], np.cumsum(_frame_energy(x, hop))])
    n = len(cum) - 1
    e, length = [], []
    for _, u0, u1 in units:
        a = min(max(0, int(u0 * SAMPLE_RATE / hop)), n)
        b = min(max(a, int(u1 * SAMPLE_RATE / hop)), n)
        e.append(cum[b] - cum[a])
        length.append((b - a) * hop)
    return np.array(e), np.array(length)


def mic_shares(mix, mic, units, hop: int = 160):
    """Per ogni pezzo, quota dell'energia della traccia completa (`mix`) che viene dalla
    traccia del solo microfono (`mic`): ~1 se parla chi è nella stanza, ~0 se parlano gli altri."""
    import numpy as np

    e_mix, _ = _unit_energy(mix, units, hop)
    e_mic, _ = _unit_energy(mic, units, hop)
    return np.where(e_mix > 1e-9, np.minimum(e_mic / np.maximum(e_mix, 1e-9), 2.0), 0.0)


def mic_levels(mic, units, hop: int = 160):
    """Livello (dBFS) di ogni pezzo nella traccia del microfono."""
    import numpy as np

    e, length = _unit_energy(mic, units, hop)
    return 10 * np.log10(e / np.maximum(length, 1) + 1e-12)


def _centroid(emb, weights):
    import numpy as np

    c = (emb * weights[:, None]).sum(axis=0)
    return c / max(float(np.linalg.norm(c)), 1e-9)


def pick_recorder(stats: dict, saved=None) -> tuple:
    """Chi registra tra le voci del microfono. `stats`: {etichetta: {"db", "centro"}},
    `saved`: impronta salvata di chi registra (o None). Restituisce (etichetta, incerta, motivo)."""
    labs = list(stats)
    db = {lab: stats[lab]["db"] for lab in labs}
    sims = {lab: float(stats[lab]["centro"] @ saved) for lab in labs} if saved is not None else {}
    if len(labs) == 1:
        lab = labs[0]
        if sims and sims[lab] < PRINT_MIN:
            return lab, True, (f"una sola voce nel microfono, poco simile all'impronta salvata "
                               f"di chi registra ({sims[lab]:.2f})")
        return lab, False, "una sola voce nel microfono" + (f" (impronta {sims[lab]:.2f})" if sims else "")
    loud = sorted(labs, key=db.get, reverse=True)
    gap = db[loud[0]] - db[loud[1]]
    loud_ok = gap >= LOUD_GAP
    why_loud = f"la più forte nel microfono (+{gap:.1f} dB)"
    if not sims:
        return loud[0], not loud_ok, why_loud + ("" if loud_ok else ", poco più delle altre")
    near = sorted(labs, key=sims.get, reverse=True)
    margin = sims[near[0]] - sims[near[1]]
    print_ok = sims[near[0]] >= PRINT_MIN and margin >= PRINT_MARGIN
    why_print = f"la più simile all'impronta salvata ({sims[near[0]]:.2f}, +{margin:.2f})"
    if near[0] == loud[0]:
        return loud[0], not (loud_ok or print_ok), f"{why_loud} e {why_print}"
    if print_ok and not loud_ok:
        return near[0], False, why_print + f"; volume poco diverso (+{gap:.1f} dB)"
    if loud_ok and not print_ok:
        return loud[0], False, why_loud + "; impronta salvata poco indicativa"
    return loud[0], True, f"{why_loud}, ma l'impronta salvata indica un'altra voce"


def voice_print(diar: dict, emb, vid: str):
    """Impronta media (normalizzata) dei pezzi di una voce."""
    import numpy as np

    idx = [k for k, p in enumerate(diar["pezzi"]) if p[2] == vid]
    if not idx or not len(emb):
        return None
    w = np.array([diar["pezzi"][k][1] - diar["pezzi"][k][0] for k in idx])
    return _centroid(emb[idx], w)


def _prints_file() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Ingeniotec Vox" / PRINT_FILE


def load_print(name: str):
    """Impronta salvata della voce di `name` (chi registra), o None."""
    import json

    import numpy as np

    try:
        data = json.loads(_prints_file().read_text("utf-8"))
        p = data[name.strip().casefold()]
        if p.get("modello") == EMBEDDING_MODEL:
            return np.array(p["impronta"], np.float32)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def save_print(name: str, vec) -> int:
    """Aggiorna l'impronta di `name` con quella di questa call (media mobile).
    Restituisce il numero di call su cui è calcolata."""
    import json

    import numpy as np

    f = _prints_file()
    try:
        data = json.loads(f.read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    key = name.strip().casefold()
    old = data.get(key, {})
    n = old.get("chiamate", 0) if old.get("modello") == EMBEDDING_MODEL else 0
    vec = np.asarray(vec, np.float64)
    if n:
        k = min(n, PRINT_KEEP - 1)
        vec = np.asarray(old["impronta"], np.float64) * k + vec
        vec /= max(float(np.linalg.norm(vec)), 1e-9)
    data[key] = {"nome": name.strip(), "modello": EMBEDDING_MODEL, "chiamate": n + 1,
                 "impronta": [round(float(x), 6) for x in vec]}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    return n + 1


def _cluster(emb, weights, threshold: float):
    """Agglomerativo: unisce sempre i due gruppi con i centroidi più simili."""
    import numpy as np

    n = len(emb)
    cen, w = emb.copy(), weights.astype(np.float64).copy()
    members = [[k] for k in range(n)]
    alive = np.ones(n, bool)
    sim = cen @ cen.T
    np.fill_diagonal(sim, -9)
    while alive.sum() > 1:
        i, j = np.unravel_index(np.argmax(sim), sim.shape)
        if sim[i, j] < threshold:
            break
        c = cen[i] * w[i] + cen[j] * w[j]
        cen[i] = c / np.linalg.norm(c)
        w[i] += w[j]
        members[i] += members[j]
        alive[j] = False
        sim[j, :] = sim[:, j] = -9
        row = cen @ cen[i]
        row[~alive] = -9
        row[i] = -9
        sim[i, :] = sim[:, i] = row
    groups = [(members[k], cen[k], w[k]) for k in np.where(alive)[0]]
    # voci con pochissimo parlato: si uniscono alla voce grande più simile, se abbastanza simile
    big = [g for g in groups if g[2] >= MIN_VOICE]
    if big:
        for g in [g for g in groups if g[2] < MIN_VOICE]:
            s = [float(g[1] @ b[1]) for b in big]
            k = int(np.argmax(s))
            if s[k] >= MERGE_SMALL:
                big[k][0].extend(g[0])
                groups.remove(g)
    labels = np.zeros(n, int)
    for gi, (m, _, _) in enumerate(groups):
        labels[m] = gi
    return labels


def _by_segment(pezzi: list, n_seg: int, key: int = 2) -> list[dict]:
    """Per ogni segmento di Whisper, l'etichetta (voce o nome) che copre più tempo."""
    votes: list[dict] = [{} for _ in range(n_seg)]
    for p in pezzi:
        lab = p[key]
        votes[p[3]][lab] = votes[p[3]].get(lab, 0.0) + (p[1] - p[0])
    out = []
    for v in votes:
        best = max(v, key=v.get) if v else ""
        out.append({"etichetta": best, "quota": round(v[best] / sum(v.values()), 2) if v else 0.0})
    return out


def diarize(audio: Path, segments: list[dict], threshold: float = THRESHOLD,
            threads: int | None = None, progress=None, saved_print=None):
    """Assegna una voce a ogni segmento di Whisper. `audio`: video o audio della call.
    `saved_print`: impronta salvata di chi registra, aiuta a sceglierlo tra le voci del microfono.

    Restituisce (risultato, impronte): il risultato va nel checkpoint `voci.json`,
    le impronte dei pezzi (matrice numpy) servono ad abbinare i nomi.
    """
    import numpy as np

    samples = decode_audio(audio)
    units = _units(segments)
    tracks = audio_tracks(audio)
    mic_info = {"tracce": tracks, "usata": False}
    if not units:
        return ({"modello": EMBEDDING_MODEL, "soglia": threshold, "microfono": mic_info, "voci": [],
                 "segmenti": [], "pezzi": []}, np.zeros((0, 1), np.float32))
    emb = _embeddings(samples, units, threads or min(16, os.cpu_count() or 4), progress)
    weights = np.array([u1 - u0 for _, u0, u1 in units])

    # persone nella stanza di chi registra: pezzi in cui parla soprattutto il microfono (traccia 2)
    is_mic = np.zeros(len(units), bool)
    if tracks >= 2:
        mic = decode_audio(audio, track=1)
        share = mic_shares(samples, mic, units)
        level = mic_levels(mic, units)
        is_mic = share >= MIC_SHARE
        q = float(weights[is_mic].sum() / weights.sum())
        mic_info["quota"] = round(q, 3)
        if q > MIC_MAX:
            mic_info["motivo"] = ("la traccia 2 non è il solo microfono (contiene quasi tutto il "
                                  "parlato): ignorata")
            is_mic[:] = False
        else:
            mic_info["usata"] = True

    labels = np.zeros(len(units), int)
    rest = np.where(~is_mic)[0]
    if len(rest):
        labels[rest] = _cluster(emb[rest], weights[rest], threshold)
    mic_labs: set = set()
    rec_lab = None
    mic_idx = np.where(is_mic)[0]
    if len(mic_idx):
        base = int(labels[rest].max()) + 1 if len(rest) else 0
        sub = _cluster(emb[mic_idx], weights[mic_idx], threshold)
        # frammenti (un «sì», una risata): impronta e livello poco affidabili, nella stanza ci sono
        # poche persone → vanno alla voce grande del microfono più simile
        talk_sub = {g: float(weights[mic_idx][sub == g].sum()) for g in set(sub.tolist())}
        big_sub = [g for g, s in talk_sub.items() if s >= MIN_VOICE]
        if big_sub:
            cen = {g: _centroid(emb[mic_idx][sub == g], weights[mic_idx][sub == g]) for g in big_sub}
            for g in [g for g in talk_sub if g not in big_sub]:
                c = _centroid(emb[mic_idx][sub == g], weights[mic_idx][sub == g])
                sub[sub == g] = max(big_sub, key=lambda b: float(cen[b] @ c))
        else:
            sub[:] = 0          # poco parlato nel microfono: non si distinguono le persone
        labels[mic_idx] = base + sub
        mic_labs = set(labels[mic_idx].tolist())
        stats = {}
        for lab in mic_labs:
            m = mic_idx[labels[mic_idx] == lab]
            stats[lab] = {"db": float(np.median(level[m])), "centro": _centroid(emb[m], weights[m])}
        rec_lab, incerta, motivo = pick_recorder(stats, saved_print)
        mic_info.update(incerta=incerta, scelta=motivo, impronta_salvata=saved_print is not None)

    # voci in ordine di tempo parlato
    talk: dict = {}
    for lab, wt in zip(labels, weights):
        talk[lab] = talk.get(lab, 0.0) + float(wt)
    order = sorted(talk, key=talk.get, reverse=True)
    name = {lab: f"V{k + 1}" for k, lab in enumerate(order)}
    pezzi = [[round(u0, 2), round(u1, 2), name[lab], i] for (i, u0, u1), lab in zip(units, labels)]
    seg_out = [{"voce": s["etichetta"], "quota": s["quota"]}
               for s in _by_segment(pezzi, len(segments))]

    voci = []
    for lab in order:
        idx = [i for i, s in enumerate(seg_out) if s["voce"] == name[lab]]
        voci.append({"id": name[lab], "secondi": round(talk[lab], 1), "segmenti": len(idx),
                     "da": segments[idx[0]]["start"] if idx else None,
                     "a": segments[idx[-1]]["end"] if idx else None,
                     **({"microfono": True, "livello_db": round(stats[lab]["db"], 1)}
                        if lab in mic_labs else {}),
                     **({"chi_registra": True} if lab == rec_lab else {})})
    if rec_lab is not None:
        mic_info["chi_registra"] = name[rec_lab]
    return ({"modello": EMBEDDING_MODEL, "soglia": threshold, "microfono": mic_info, "voci": voci,
             "segmenti": seg_out, "pezzi": pezzi}, emb)


def resolve_names(diar: dict, emb, evid: dict, answer: dict, n_seg: int, recorder: str = "") -> dict:
    """Nome di ogni voce e di ogni segmento, dai campioni etichettati da Claude.

    - voce di chi registra (dal microfono): `recorder`, se indicato, altrimenti il nome
      proposto da Claude se la certezza non è bassa; le altre voci del microfono (persone
      nella stessa stanza) seguono le regole delle altre voci;
    - voce con un nome in almeno `PURE` dei campioni: tutta la voce prende quel nome;
    - voce mista (due persone con voci simili unite): ogni suo pezzo va alla persona,
      tra quelle viste nei suoi campioni, con l'impronta media più simile (impronte medie
      calcolate sui campioni di tutte le voci);
    - voce senza campioni utili: il nome proposto da Claude, se la certezza non è bassa.
    """
    import numpy as np

    by_id = {v["voce"]: v for v in answer.get("voci", [])}
    pezzi = diar["pezzi"]

    def piece_at(t: float) -> int | None:
        for k, p in enumerate(pezzi):
            if p[0] <= t - LAG / 2 <= p[1]:
                return k
        return None

    # campioni etichettati: (voce, nome, indice del pezzo)
    labelled = []
    for v, ev in evid.items():
        names = {c["n"]: c["nome"].strip() for c in by_id.get(v, {}).get("campioni", [])}
        for n, s in enumerate(ev["campioni"], 1):
            nome = names.get(n, "")
            k = piece_at(s["t"])
            s["nome"] = nome
            if nome and k is not None:
                labelled.append((v, nome, k))

    centroids = {}
    if len(emb):
        for nome in {x[1] for x in labelled}:
            c = emb[[k for _, n, k in labelled if n == nome]].mean(axis=0)
            centroids[nome] = c / max(float(np.linalg.norm(c)), 1e-9)

    voci = {}
    piece_name = [""] * len(pezzi)
    for v in diar["voci"]:
        vid = v["id"]
        names = [n for vv, n, _ in labelled if vv == vid]
        cl = by_id.get(vid, {})
        info = {"secondi": v["secondi"], "campioni": len(evid.get(vid, {}).get("campioni", [])),
                "etichettati": len(names), "motivo": cl.get("motivo", "")}
        idx = [k for k, p in enumerate(pezzi) if p[2] == vid]
        if v.get("microfono"):
            info["stanza"] = True
        if v.get("chi_registra"):
            guess = cl.get("nome") if cl.get("certezza") in ("alta", "media") else ""
            info.update(nome=recorder.strip() or guess or "", modo="microfono",
                        incerta=bool(diar.get("microfono", {}).get("incerta")))
            for k in idx:
                piece_name[k] = info["nome"]
        elif names:
            top = max(set(names), key=names.count)
            share = names.count(top) / len(names)
            info["accordo"] = round(share, 2)
            if share >= PURE or len(names) == 1 or not centroids:
                info.update(nome=top, modo="voce")
                for k in idx:
                    piece_name[k] = top
            else:
                seen = sorted(set(names))
                info.update(nome=" / ".join(seen), modo="mista")
                mat = np.stack([centroids[n] for n in seen])
                for k in idx:
                    piece_name[k] = seen[int(np.argmax(mat @ emb[k]))]
        elif cl.get("nome") and cl.get("certezza") in ("alta", "media"):
            info.update(nome=cl["nome"], modo="conversazione")
            for k in idx:
                piece_name[k] = cl["nome"]
        else:
            info.update(nome="", modo="non identificata")
        voci[vid] = info

    named = [p + [piece_name[k]] for k, p in enumerate(pezzi)]
    seg = [s["etichetta"] for s in _by_segment(named, n_seg, key=4)]
    total = sum(p[1] - p[0] for p in pezzi) or 1.0
    covered = sum(p[1] - p[0] for k, p in enumerate(pezzi) if piece_name[k])
    talk: dict = {}
    for k, p in enumerate(pezzi):
        if piece_name[k]:
            talk[piece_name[k]] = talk.get(piece_name[k], 0.0) + p[1] - p[0]
    return {"voci": voci, "segmenti": seg, "copertura": round(covered / total, 3),
            "persone": {n: round(s) for n, s in sorted(talk.items(), key=lambda x: -x[1])}}


# ---------------------------------------------------------------- riquadro evidenziato

def _groups(idx) -> list[tuple[int, int]]:
    out = []
    for x in idx:
        if out and x - out[-1][1] <= 3:
            out[-1] = (out[-1][0], int(x))
        else:
            out.append((int(x), int(x)))
    return out


def highlight_boxes(rgb) -> list[list[int]]:
    """Rettangoli [x0, y0, x1, y1] con il bordo del colore di chi parla."""
    import numpy as np

    px = rgb.astype(np.int16)
    mask = np.zeros(rgb.shape[:2], bool)
    for col in HIGHLIGHT_COLORS:
        mask |= np.abs(px - np.array(col)).max(axis=2) <= COLOR_TOL
    cols = _groups(np.where(mask.sum(0) >= 40)[0])
    rows = _groups(np.where(mask.sum(1) >= 40)[0])
    found = []
    for i, (l0, l1) in enumerate(cols):
        for r0, r1 in cols[i + 1:]:
            x0, x1 = l0, r1
            if not 80 <= x1 - x0 <= 1300:
                continue
            for a, (t0, t1) in enumerate(rows):
                for b0, b1 in rows[a + 1:]:
                    y0, y1 = t0, b1
                    if not 50 <= y1 - y0 <= 900:
                        continue
                    top = mask[t0:t1 + 1, x0:x1].any(0).mean()
                    bot = mask[b0:b1 + 1, x0:x1].any(0).mean()
                    lef = mask[y0:y1, l0:l1 + 1].any(1).mean()
                    rig = mask[y0:y1, r0:r1 + 1].any(1).mean()
                    inner = mask[y0 + 6:y1 - 6, x0 + 6:x1 - 6].mean()
                    if min(top, bot, lef, rig) > 0.8 and inner < 0.05:
                        found.append([x0, y0, x1, y1])
    # due riquadri vicini evidenziati formano anche rettangoli che li contengono: si tolgono
    return [b for b in found if not any(o != b and o[0] >= b[0] and o[1] >= b[1]
                                        and o[2] <= b[2] and o[3] <= b[3] for o in found)]


def scan_highlights(video: Path, progress=None) -> list[dict]:
    """Riquadri evidenziati su tutti i fotogrammi chiave (veloce: ~1 min per 80 min di 1080p)."""
    import av

    out = []
    with av.open(str(video)) as c:
        st = c.streams.video[0]
        st.codec_context.skip_frame = "NONKEY"
        duration = (c.duration or 0) / 1e6
        for fr in c.decode(st):
            if fr.time is None:
                continue
            out.append({"t": round(fr.time, 2), "riquadri": highlight_boxes(fr.to_ndarray(format="rgb24"))})
            if progress and duration:
                progress(min(fr.time / duration, 1.0))
    return out


def voice_at(diar: dict, t: float, lag: float = LAG) -> str | None:
    """Voce che parla da sola in tutto l'intervallo [t - lag, t]."""
    found = set()
    covered = 0.0
    for u0, u1, v, *_ in diar["pezzi"]:
        if u1 < t - lag or u0 > t:
            continue
        found.add(v)
        covered += min(u1, t) - max(u0, t - lag)
    return found.pop() if len(found) == 1 and covered >= lag * 0.9 else None


def _spread(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(k * step + step / 2)] for k in range(n)]


def _grab(video: Path, times: list[float]) -> dict:
    """Fotogrammi (PIL) ai tempi indicati, cercando dal fotogramma chiave precedente."""
    import av

    res = {}
    with av.open(str(video)) as c:
        st = c.streams.video[0]
        for t in sorted(times):
            c.seek(int(t / st.time_base), stream=st, backward=True)
            for fr in c.decode(st):
                if fr.time is not None and fr.time >= t:
                    res[t] = fr.to_image()
                    break
    return res


def evidence(video: Path, diar: dict, scan: list[dict], out_dir: Path,
             per_voice: int = SAMPLES_PER_VOICE) -> dict:
    """Per ogni voce, fotogrammi in cui parla solo lei e riquadro evidenziato, in un foglio."""
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    by_voice: dict[str, list[dict]] = {v["id"]: [] for v in diar["voci"]
                                       if v["secondi"] >= MIN_VOICE and not v.get("microfono")}
    for s in scan:
        if len(s["riquadri"]) != 1:
            continue
        v = voice_at(diar, s["t"])
        if v in by_voice:
            by_voice[v].append({"t": s["t"], "riquadro": s["riquadri"][0]})

    # voci con pochi fotogrammi chiave utili: si cercano fotogrammi dentro i loro pezzi più lunghi
    extra_t: dict[float, str] = {}
    for v, found in by_voice.items():
        if len(found) >= per_voice // 2:
            continue
        pieces = sorted((p for p in diar["pezzi"] if p[2] == v and p[1] - p[0] >= 1.5),
                        key=lambda p: p[1] - p[0], reverse=True)
        for p in pieces[:per_voice]:
            t = round(min(p[0] + LAG + 0.7, p[1]), 2)
            if voice_at(diar, t):
                extra_t[t] = v
    if extra_t:
        for t, img in _grab(video, list(extra_t)).items():
            boxes = highlight_boxes(np.asarray(img.convert("RGB")))
            if len(boxes) == 1:
                by_voice[extra_t[t]].append({"t": t, "riquadro": boxes[0]})

    chosen = {v: _spread(sorted(f, key=lambda s: s["t"]), per_voice) for v, f in by_voice.items()}
    need = sorted({s["t"] for f in chosen.values() for s in f})
    images = _keyframes(video, need)
    missing = [t for t in need if t not in images]
    images.update(_grab(video, missing))

    result = {}
    for v, samples in chosen.items():
        samples = [s for s in samples if s["t"] in images]
        sheet = out_dir / f"voce_{v}.jpg"
        if samples:
            _voice_sheet(v, samples, images, sheet)
        result[v] = {"campioni": samples, "foglio": sheet.name if samples else None}
    return result


def _keyframes(video: Path, times: list[float]) -> dict:
    import av

    want = set(times)
    res = {}
    if not want:
        return res
    with av.open(str(video)) as c:
        st = c.streams.video[0]
        st.codec_context.skip_frame = "NONKEY"
        for fr in c.decode(st):
            if fr.time is not None and round(fr.time, 2) in want:
                res[round(fr.time, 2)] = fr.to_image()
                if len(res) == len(want):
                    break
    return res


def _voice_sheet(voice: str, samples: list[dict], images: dict, dst: Path) -> None:
    """Per ogni campione: fotogramma intero ridotto (riquadro in rosso) e riquadro ingrandito."""
    from PIL import Image, ImageDraw, ImageFont

    from .frames import hms

    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    W, H = 640, 360            # fotogramma ridotto
    cols = 2
    rows = (len(samples) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 2 * W, rows * H), "white")
    draw = ImageDraw.Draw(sheet)
    for k, s in enumerate(samples):
        im = images[s["t"]].convert("RGB")
        x, y = (k % cols) * 2 * W, (k // cols) * H
        sx, sy = W / im.width, H / im.height
        x0, y0, x1, y1 = s["riquadro"]
        small = im.resize((W, H))
        ImageDraw.Draw(small).rectangle([x0 * sx - 3, y0 * sy - 3, x1 * sx + 3, y1 * sy + 3],
                                        outline="red", width=4)
        sheet.paste(small, (x, y))
        tile = im.crop((max(0, x0 - 4), max(0, y0 - 4), min(im.width, x1 + 4), min(im.height, y1 + 4)))
        scale = min(W / tile.width, H / tile.height)
        tile = tile.resize((max(1, round(tile.width * scale)), max(1, round(tile.height * scale))))
        sheet.paste(tile, (x + W, y))
        draw.rectangle([x, y, x + 185, y + 28], fill="yellow")
        draw.text((x + 5, y + 3), f"{voice} #{k + 1} · {hms(s['t'])}", fill="black", font=font)
        draw.rectangle([x, y, x + 2 * W - 1, y + H - 1], outline="white", width=2)
    sheet.save(dst, quality=85)
