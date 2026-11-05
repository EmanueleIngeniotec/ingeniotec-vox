"""Voci e nomi delle persone in una call (solo pipeline call).

1. **Voci** (`diarize`): ogni segmento di Whisper è diviso in pezzi di ~3 s; di ogni pezzo
   si calcola l'impronta della voce (embedding sherpa-onnx, modello libero, offline, CPU)
   e i pezzi si raggruppano per somiglianza (clustering agglomerativo). Ogni segmento di
   Whisper riceve la voce che copre più tempo al suo interno. Le voci sono V1, V2, …
   in ordine di tempo parlato.
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

from .transcribe import SAMPLE_RATE, decode_audio

MODEL_DIRNAME = "diarizzazione"
EMBEDDING_MODEL = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"

UNIT_SECONDS = 3.0      # lunghezza indicativa di un pezzo di parlato
MIN_UNIT = 1.0          # pezzi più corti si allargano attorno al centro
THRESHOLD = 0.60        # somiglianza (coseno) minima per unire due gruppi
MIN_VOICE = 8.0         # secondi: sotto, una voce si unisce alla più simile …
MERGE_SMALL = 0.35      # … se la somiglianza è almeno questa, altrimenti resta a sé

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
            threads: int | None = None, progress=None):
    """Assegna una voce a ogni segmento di Whisper. `audio`: video o audio della call.

    Restituisce (risultato, impronte): il risultato va nel checkpoint `voci.json`,
    le impronte dei pezzi (matrice numpy) servono ad abbinare i nomi.
    """
    import numpy as np

    samples = decode_audio(audio)
    units = _units(segments)
    if not units:
        return ({"modello": EMBEDDING_MODEL, "soglia": threshold, "voci": [], "segmenti": [],
                 "pezzi": []}, np.zeros((0, 1), np.float32))
    emb = _embeddings(samples, units, threads or min(16, os.cpu_count() or 4), progress)
    weights = np.array([u1 - u0 for _, u0, u1 in units])
    labels = _cluster(emb, weights, threshold)

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
                     "a": segments[idx[-1]]["end"] if idx else None})
    return ({"modello": EMBEDDING_MODEL, "soglia": threshold, "voci": voci, "segmenti": seg_out,
             "pezzi": pezzi}, emb)


def resolve_names(diar: dict, emb, evid: dict, answer: dict, n_seg: int) -> dict:
    """Nome di ogni voce e di ogni segmento, dai campioni etichettati da Claude.

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
        if names:
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
    by_voice: dict[str, list[dict]] = {v["id"]: [] for v in diar["voci"] if v["secondi"] >= MIN_VOICE}
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
