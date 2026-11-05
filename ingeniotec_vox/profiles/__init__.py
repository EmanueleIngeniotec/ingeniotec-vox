"""Profili di elaborazione: prompt e schemi JSON come dati, non codice.

Ogni profilo è una cartella con `<passo>.md` (prompt per Claude, con segnaposto
`{nome}`) e `<passo>.schema.json` (schema dell'output strutturato). Un
`profilo.json` facoltativo contiene le opzioni del profilo e `eredita`: i file
che mancano si prendono dal profilo indicato.
"""

import json
import sys
from pathlib import Path


def _root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "ingeniotec_vox" / "profiles"
    return Path(__file__).parent


class Profile:
    def __init__(self, name: str):
        self.name = name
        self.dir = _root() / name
        if not self.dir.is_dir():
            raise FileNotFoundError(f"Profilo '{name}' non trovato in {self.dir}")
        cfg = self.dir / "profilo.json"
        self.options = json.loads(cfg.read_text("utf-8")) if cfg.is_file() else {}
        self.parent = Profile(self.options["eredita"]) if self.options.get("eredita") else None

    def option(self, key: str, default=None):
        if key in self.options:
            return self.options[key]
        return self.parent.option(key, default) if self.parent else default

    def _read(self, filename: str) -> str:
        p = self.dir / filename
        if p.is_file():
            return p.read_text("utf-8")
        if self.parent:
            return self.parent._read(filename)
        raise FileNotFoundError(f"'{filename}' non trovato nel profilo '{self.name}'")

    def prompt(self, step: str, **values) -> str:
        text = self._read(f"{step}.md")
        for k, v in values.items():
            text = text.replace("{" + k + "}", str(v))
        return text

    def schema(self, step: str) -> dict:
        return json.loads(self._read(f"{step}.schema.json"))

    def system(self) -> str:
        return self._read("sistema.md")
