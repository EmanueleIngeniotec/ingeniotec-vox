"""Trascrizione locale con faster-whisper su GPU."""

import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from . import cuda_dll

MODEL_NAME = "large-v3"
MODEL_DIRNAME = "faster-whisper-large-v3"
SAMPLE_RATE = 16000


@dataclass
class Segment:
    start: float
    end: float
    text: str


def resolve_model(explicit: str | None = None) -> str:
    """Percorso del modello: argomento > VOX_MODEL_DIR > cartella `models` accanto
    all'eseguibile > nome Hugging Face (cache locale o download)."""
    if explicit:
        return explicit
    if os.environ.get("VOX_MODEL_DIR"):
        return os.environ["VOX_MODEL_DIR"]
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    local = base / "models" / MODEL_DIRNAME
    if (local / "model.bin").is_file():
        return str(local)
    return MODEL_NAME


def decode_audio(path: Path, max_seconds: float | None = None) -> "np.ndarray":
    """Prima traccia audio del file → mono float32 a 16 kHz.

    Sostituisce `faster_whisper.audio.decode_audio`, che con PyAV 19 non funziona
    (parametro `metadata_errors` rimosso).
    """
    import av
    import numpy as np

    limit = int(max_seconds * SAMPLE_RATE) if max_seconds else None
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks, total = [], 0

    def packets_frames(container, stream):
        # un pacchetto corrotto (tipico: ultimo pacchetto di una registrazione interrotta)
        # si salta invece di fermare tutta la decodifica
        for packet in container.demux(stream):
            try:
                yield from packet.decode()
            except av.error.InvalidDataError:
                continue

    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        for frame in packets_frames(container, stream):
            for out in resampler.resample(frame):
                arr = out.to_ndarray().reshape(-1)
                chunks.append(arr)
                total += arr.size
            if limit and total >= limit:
                break
        else:
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().reshape(-1))
    samples = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
    return (samples[:limit] if limit else samples).astype(np.float32) / 32768.0


def transcribe(audio: Path, model: str | None = None, max_seconds: float | None = None,
               language: str | None = None, progress=None) -> dict:
    """Trascrive `audio` (qualsiasi formato leggibile da PyAV, anche video).

    `max_seconds` limita l'elaborazione all'inizio del file (test rapidi).
    `progress(frazione)` viene chiamata a ogni segmento riconosciuto.
    """
    cuda_dll.register()
    from faster_whisper import WhisperModel

    samples = decode_audio(audio, max_seconds=max_seconds)
    duration = len(samples) / SAMPLE_RATE

    wm = WhisperModel(resolve_model(model), device="cuda", compute_type="float16")
    segments, info = wm.transcribe(samples, language=language, vad_filter=True, beam_size=5)
    result = []
    for s in segments:
        result.append(Segment(round(s.start, 2), round(s.end, 2), s.text.strip()))
        if progress and duration:
            progress(min(s.end / duration, 1.0))
    return {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration": round(duration, 2),
        "segments": [asdict(s) for s in result],
    }
