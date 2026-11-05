"""Genera l'icona di Vox: quadrato arrotondato nel verde del marchio Ingeniotec con una «V»
bianca a tratto spesso e arrotondato. Disegnata a 1024 px e ridotta, così resta
leggibile anche a 16 px (il marchio a fascia non lo era).

Scrive assets/vox.ico (16–256 px) e assets/vox.png (256 px, per la finestra).
"""

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TEAL = (67, 129, 141, 255)       # colore della fascia di logo_wordmark.png
WHITE = (255, 255, 255, 255)
S = 1024


def draw(size: int, detail: bool) -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=S * 0.22, fill=TEAL)
    # V: due aste spesse
    w = S * (0.16 if detail else 0.19)
    top, bottom = S * 0.24, S * 0.78
    left, right, mid = S * 0.22, S * 0.78, S * 0.5
    d.line([(left, top), (mid, bottom)], fill=WHITE, width=int(w))
    d.line([(right, top), (mid, bottom)], fill=WHITE, width=int(w))
    d.ellipse((mid - w / 2, bottom - w / 2, mid + w / 2, bottom + w / 2), fill=WHITE)
    for x in (left, right):
        d.ellipse((x - w / 2, top - w / 2, x + w / 2, top + w / 2), fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
frames = [draw(n, detail=n >= 48) for n in sizes]
frames[-1].save(ASSETS / "vox.ico", sizes=[(n, n) for n in sizes], append_images=frames[:-1])
frames[-1].save(ASSETS / "vox.png")
print(f"Creati {ASSETS / 'vox.ico'} e {ASSETS / 'vox.png'}")
