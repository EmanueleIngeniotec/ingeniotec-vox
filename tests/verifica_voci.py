"""Verifica a campione dell'attribuzione degli interventi (Fase 4).

Sceglie a caso segmenti della trascrizione con un nome assegnato (anche lontani dai campioni
usati per dare i nomi), prende il fotogramma a metà del segmento e compone fogli con il nome
assegnato, il fotogramma ridotto e il riquadro evidenziato ingrandito. Chi controlla guarda i
fogli e annota se la persona evidenziata è quella assegnata.

    .venv\\Scripts\\python tests\\verifica_voci.py <video> <cartella _lavoro> [--n 40] [--seed 1]

Fogli in `<_lavoro>/verifica/verifica_NN.jpg`, elenco in `verifica.json`.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingeniotec_vox.core import diarize  # noqa: E402
from ingeniotec_vox.core.frames import hms  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("video", type=Path)
    p.add_argument("lavoro", type=Path)
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=1)
    a = p.parse_args()

    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    tr = json.loads((a.lavoro / "trascrizione.json").read_text("utf-8"))
    nomi = json.loads((a.lavoro / "nomi.json").read_text("utf-8"))
    used = {round(c["t"], 1) for v in json.loads((a.lavoro / "evidenze.json").read_text("utf-8")).values()
            for c in v["campioni"]}
    segs = [(s, n) for s, n in zip(tr["segments"], nomi["segmenti"])
            if n and s["end"] - s["start"] >= 3.0]
    rnd = random.Random(a.seed)
    # campione stratificato: ogni persona almeno qualche segmento, il resto in proporzione
    by = {}
    for s, n in segs:
        by.setdefault(n, []).append(s)
    pick = []
    for n, lst in by.items():
        pick += [(s, n) for s in rnd.sample(lst, min(len(lst), 3))]
    rest = [x for x in segs if x not in pick]
    pick += rnd.sample(rest, max(0, min(len(rest), a.n - len(pick))))
    pick.sort(key=lambda x: x[0]["start"])

    times = [round(min(s["start"] + 2.0, (s["start"] + s["end"]) / 2), 2) for s, _ in pick]
    frames = diarize._grab(a.video, times)
    out = a.lavoro / "verifica"
    out.mkdir(exist_ok=True)
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    W, H, per = 480, 270, 8
    rows = []
    for k, ((s, n), t) in enumerate(zip(pick, times), 1):
        im = frames.get(t)
        boxes = diarize.highlight_boxes(np.asarray(im.convert("RGB"))) if im else []
        rows.append({"k": k, "t": t, "min": hms(t), "assegnato": n, "riquadri": len(boxes),
                     "vicino_a_campione": any(abs(t - u) < 10 for u in used), "testo": s["text"][:80],
                     "_img": im, "_box": boxes[0] if len(boxes) == 1 else None})
    for g in range(0, len(rows), per):
        group = rows[g:g + per]
        sheet = Image.new("RGB", (2 * (W + 240), (per // 2) * (H + 30)), "white")
        d = ImageDraw.Draw(sheet)
        for i, r in enumerate(group):
            x, y = (i % 2) * (W + 240), (i // 2) * (H + 30)
            d.text((x + 4, y + 4), f"#{r['k']} {r['min']}  assegnato: {r['assegnato']}", fill="black", font=font)
            if r["_img"] is None:
                continue
            im = r["_img"].convert("RGB")
            small = im.resize((W, H))
            if r["_box"]:
                x0, y0, x1, y1 = r["_box"]
                sx, sy = W / im.width, H / im.height
                ImageDraw.Draw(small).rectangle([x0 * sx - 3, y0 * sy - 3, x1 * sx + 3, y1 * sy + 3],
                                                outline="red", width=3)
                tile = im.crop((x0, y0, x1, y1))
                sc = min(236 / tile.width, H / tile.height)
                sheet.paste(tile.resize((round(tile.width * sc), round(tile.height * sc))), (x + W + 2, y + 28))
            sheet.paste(small, (x, y + 28))
        sheet.save(out / f"verifica_{g // per + 1:02d}.jpg", quality=85)
    (out / "verifica.json").write_text(json.dumps(
        [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows], ensure_ascii=False, indent=1),
        "utf-8")
    print(f"{len(rows)} segmenti, {sum(r['riquadri'] == 1 for r in rows)} con un solo riquadro evidenziato; "
          f"fogli in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
