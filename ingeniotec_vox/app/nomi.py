"""Correzione manuale dei nomi delle voci di una call (ripiego previsto in ARCHITETTURA.md).

Mostra ogni voce con minuti di parlato, nome dato da Vox, frasi d'esempio e foglio dei
campioni; il nome scelto vale per tutta la voce. Salva `_lavoro/correzioni_nomi.json`,
poi il report si rifà dalla fase «blocchi» (trascrizione, voci e schermate restano).
"""

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QGridLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..core.diarize import MIN_VOICE
from ..pipeline_call import CORREZIONI

KEEP = "(lascia com'è)"
NONE = "(nessuno – non identificata)"


def _load(work: Path, name: str):
    p = work / name
    return json.loads(p.read_text("utf-8")) if p.is_file() else None


def available(job_dir: Path) -> bool:
    work = job_dir / "_lavoro"
    return (work / "nomi.json").is_file() and (work / "voci.json").is_file()


class SheetViewer(QDialog):
    def __init__(self, image: Path, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        lab = QLabel()
        pix = QPixmap(str(image))
        if pix.width() > 1400:
            pix = pix.scaledToWidth(1400, Qt.SmoothTransformation)
        lab.setPixmap(pix)
        area = QScrollArea()
        area.setWidget(lab)
        lay = QVBoxLayout(self)
        lay.addWidget(area)
        self.resize(min(pix.width() + 40, 1450), min(pix.height() + 40, 900))


class NamesDialog(QDialog):
    def __init__(self, job_dir: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correggi i nomi di chi parla")
        self.work = job_dir / "_lavoro"
        nomi = _load(self.work, "nomi.json")
        voci = _load(self.work, "voci.json")
        evid = _load(self.work, "evidenze.json") or {}
        tr = _load(self.work, "trascrizione.json") or {"segments": []}
        part = _load(self.work, "partecipanti.json") or {"partecipanti": []}
        corr = (_load(self.work, CORREZIONI) or {}).get("voci", {})

        people = [p["nome"] for p in part["partecipanti"]]
        for n in nomi["persone"]:
            if n not in people:
                people.append(n)

        lay = QVBoxLayout(self)
        intro = QLabel(
            "Vox ha riconosciuto queste voci e ha dato loro un nome guardando chi era evidenziato "
            "nel video. Se un nome è sbagliato, sceglilo dall'elenco o scrivilo; poi il report si "
            "rifà con i nomi corretti (qualche minuto, la trascrizione non si ripete).")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        for c, h in enumerate(["Voce", "Parlato", "Nome dato da Vox", "Esempi di frasi", "", "Nome corretto"]):
            lab = QLabel(f"<b>{h}</b>")
            grid.addWidget(lab, 0, c)
        self.combos: dict[str, tuple[QComboBox, str]] = {}
        row = 1
        for v in voci["voci"]:
            if v["secondi"] < MIN_VOICE:
                continue
            vid = v["id"]
            info = nomi["voci"].get(vid, {})
            current = info.get("nome", "")
            mixed = info.get("modo") == "mista"
            own = [s for s, d in zip(tr["segments"], voci["segmenti"]) if d["voce"] == vid]
            longest = sorted(own, key=lambda s: s["end"] - s["start"], reverse=True)[:2]
            phrases = "<br>".join(f"«{s['text'][:110]}{'…' if len(s['text']) > 110 else ''}»"
                                  for s in longest)
            grid.addWidget(QLabel(vid), row, 0)
            grid.addWidget(QLabel(f"{v['secondi'] / 60:.1f} min"), row, 1)
            shown = current or "non identificata"
            if mixed:
                shown += "<br><i>(due persone con voce simile)</i>"
            grid.addWidget(QLabel(shown), row, 2)
            ph = QLabel(phrases)
            ph.setWordWrap(True)
            ph.setMinimumWidth(340)
            grid.addWidget(ph, row, 3)
            sheet = evid.get(vid, {}).get("foglio")
            if sheet and (self.work / "voci_fogli" / sheet).is_file():
                b = QPushButton("Vedi campioni")
                b.clicked.connect(lambda _=False, p=self.work / "voci_fogli" / sheet, t=vid:
                                  SheetViewer(p, f"Campioni della voce {t}", self).exec())
                grid.addWidget(b, row, 4)
            cb = QComboBox()
            cb.setEditable(True)
            cb.addItems([KEEP, *people, NONE])
            cb.setMinimumWidth(220)
            if vid in corr:
                cb.setCurrentText(corr[vid] or NONE)
            grid.addWidget(cb, row, 5)
            self.combos[vid] = (cb, current)
            row += 1
        grid.setRowStretch(row, 1)
        grid.setColumnStretch(3, 1)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(grid_w)
        lay.addWidget(area)

        buttons = QDialogButtonBox()
        self.ok = buttons.addButton("Salva e rifai il report", QDialogButtonBox.AcceptRole)
        buttons.addButton("Annulla", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.resize(1150, min(160 + 90 * row, 800))

    def corrections(self) -> dict:
        out = {}
        for vid, (cb, current) in self.combos.items():
            text = cb.currentText().strip()
            if not text or text == KEEP:
                continue
            name = "" if text == NONE else text
            if name != current:
                out[vid] = name
        return out

    def _save(self) -> None:
        data = {"voci": self.corrections()}
        (self.work / CORREZIONI).write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        self.accept()
