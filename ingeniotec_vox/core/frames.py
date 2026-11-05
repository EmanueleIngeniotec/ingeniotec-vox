"""Fotogrammi candidati dal video e fogli di anteprima per Claude.

Si decodificano solo i fotogrammi chiave (veloce anche su video di ore) e si
tiene quello che differisce abbastanza dall'ultimo tenuto: un cambio di
schermata condivisa, una slide nuova, il passaggio alla griglia dei volti.
"""

from pathlib import Path

SMALL = (96, 54)        # confronto su miniatura in scala di grigi
PIXEL_DELTA = 24        # differenza minima di un pixel per contarlo come cambiato
CHANGED_SHARE = 0.08    # quota di pixel cambiati per un nuovo candidato
MIN_GAP = 20.0          # secondi minimi tra due candidati
MAX_CANDIDATES = 144    # oltre, si tengono i cambi più marcati
FULL_WIDTH = 1920

SHEET_COLS, SHEET_ROWS = 4, 3
THUMB = (480, 270)


def hms(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}"


def candidates(video: Path, out_dir: Path, progress=None,
               max_candidates: int = MAX_CANDIDATES) -> list[dict]:
    """Salva i fotogrammi candidati in `out_dir` e ne restituisce l'elenco."""
    import av
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    found, last, last_t = [], None, -MIN_GAP
    with av.open(str(video)) as c:
        st = c.streams.video[0]
        st.codec_context.skip_frame = "NONKEY"
        duration = (c.duration or 0) / 1e6
        for fr in c.decode(st):
            if fr.time is None:
                continue
            small = fr.reformat(width=SMALL[0], height=SMALL[1], format="gray").to_ndarray()
            small = small.astype(np.int16)
            score = 1.0 if last is None else float((abs(small - last) > PIXEL_DELTA).mean())
            if score >= CHANGED_SHARE and fr.time - last_t >= MIN_GAP:
                found.append({"t": round(fr.time, 1), "score": round(score, 3),
                              "image": fr.to_image()})
                last, last_t = small, fr.time
            if progress and duration:
                progress(min(fr.time / duration, 1.0))

    if len(found) > max_candidates:
        keep = sorted(found, key=lambda f: f["score"], reverse=True)[:max_candidates]
        found = sorted(keep, key=lambda f: f["t"])

    result = []
    for n, f in enumerate(found, 1):
        img = f.pop("image")
        if img.width > FULL_WIDTH:
            img = img.resize((FULL_WIDTH, round(img.height * FULL_WIDTH / img.width)))
        name = f"f{n:03d}_{hms(f['t']).replace(':', '-')}.jpg"
        img.save(out_dir / name, quality=85)
        result.append({"id": f"f{n:03d}", "t": f["t"], "min": hms(f["t"]),
                       "file": name, "score": f["score"]})
    return result


def contact_sheets(frames: list[dict], frames_dir: Path, out_dir: Path) -> list[dict]:
    """Fogli di anteprima 4×3 con id e minuto su ogni miniatura."""
    from PIL import Image, ImageDraw, ImageFont

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("arialbd.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    per = SHEET_COLS * SHEET_ROWS
    sheets = []
    for k in range(0, len(frames), per):
        group = frames[k:k + per]
        sheet = Image.new("RGB", (SHEET_COLS * THUMB[0], SHEET_ROWS * THUMB[1]), "white")
        draw = ImageDraw.Draw(sheet)
        for i, f in enumerate(group):
            with Image.open(frames_dir / f["file"]) as im:
                thumb = im.convert("RGB").resize(THUMB)
            x, y = (i % SHEET_COLS) * THUMB[0], (i // SHEET_COLS) * THUMB[1]
            sheet.paste(thumb, (x, y))
            draw.rectangle([x, y, x + THUMB[0] - 1, y + THUMB[1] - 1], outline="white", width=2)
            label = f"{f['id']} · {f['min']}"
            draw.rectangle([x, y, x + 210, y + 32], fill="yellow")
            draw.text((x + 6, y + 4), label, fill="black", font=font)
        name = f"foglio_{k // per + 1:02d}.jpg"
        sheet.save(out_dir / name, quality=80)
        sheets.append({"file": name, "ids": [f["id"] for f in group]})
    return sheets


def crop(src: Path, dst: Path, box: list[float] | None, width: int = 1600) -> Path:
    """Ritaglia `src` con `box` = [x0, y0, x1, y1] in frazioni dell'immagine."""
    from PIL import Image

    with Image.open(src) as im:
        if box:
            x0, y0, x1, y1 = (max(0.0, min(1.0, v)) for v in box)
            if x1 - x0 > 0.05 and y1 - y0 > 0.05:
                im = im.crop((round(x0 * im.width), round(y0 * im.height),
                              round(x1 * im.width), round(y1 * im.height)))
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)))
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(dst, quality=90)
    return dst
