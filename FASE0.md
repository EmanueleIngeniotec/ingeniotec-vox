# Ingeniotec Vox – Fase 0: setup e prova di fumo (2026-10-28)

Riferimenti: `REQUISITI.md`, `ARCHITETTURA.md` (piano a fasi, riga 0).

## Obiettivo
Dimostrare che la catena tecnica regge **dentro un .exe** prima di scrivere la pipeline:
GPU + faster-whisper + DLL CUDA impacchettate, Claude Code CLI in headless, controllo ambiente.

**Esito verificabile:** `vox_smoke.exe` trascrive 1 min di audio sulla GPU e chiama Claude ottenendo JSON strutturato.

## Piano
| # | Attività | Stato |
|---|---|---|
| 1 | Struttura repo (`ingeniotec_vox/core`, `build/`, `tests/`), `.gitignore`, versione | ✅ |
| 2 | Ambiente `.venv` Python 3.13 con dipendenze bloccate (`requirements.txt`) | ✅ |
| 3 | `core/env_check.py`: GPU, Claude Code (installato, versione, login), Word, disco; messaggi in italiano | ✅ |
| 4 | `core/cuda_dll.py`: caricamento DLL cuBLAS/cuDNN da sorgente e da pacchetto | ✅ |
| 5 | `core/transcribe.py`: decodifica audio con PyAV + faster-whisper large-v3 su CUDA | ✅ |
| 6 | `core/claude.py`: unico wrapper di `claude -p` (stdin, `--json-schema`, nessuno strumento, nessuna sessione salvata) | ✅ |
| 7 | `smoke.py`: comando di prova (`--check` o trascrizione + sintesi) | ✅ |
| 8 | Build PyInstaller a cartella + script `build\build.ps1` riproducibile + icona provvisoria | ✅ |
| 9 | Prova dell'exe con PATH minimo da un'altra cartella | ✅ |
| 10 | Riduzione DLL NVIDIA (solo cuBLAS) e prova offline con modello in `models\`, PATH minimo, cache vuota | ✅ |
| 11 | Prova su un secondo PC pulito | ➖ non prevista: si lavora solo su questo PC (2026-11-02) |
| 12 | Build da zero con `build.ps1` (rimette il modello in `models\`) e prova offline, PATH minimo | ✅ 2026-11-02 |

## Come si usa
Build (da PowerShell, nella cartella del progetto):
```
powershell -ExecutionPolicy Bypass -File build\build.ps1
```
Audio di prova (sintesi vocale italiana di Windows, ~1 min):
```
powershell -ExecutionPolicy Bypass -File tests\fixtures\make_sample.ps1
```
Esecuzione:
```
dist\vox_smoke\vox_smoke.exe --check
dist\vox_smoke\vox_smoke.exe tests\fixtures\sample_it.wav --seconds 60
```
Da sorgente: `.venv\Scripts\python -m ingeniotec_vox.smoke ...` (stessi argomenti).

`build.ps1` ricopia il modello dalla cache Hugging Face in `dist\vox_smoke\models\` (PyInstaller svuota la cartella a ogni build).

Modello Whisper, in ordine: `--model`, variabile `VOX_MODEL_DIR`, cartella `models\faster-whisper-large-v3` accanto all'exe, altrimenti cache Hugging Face (scarica se manca).

## Risultati su questo PC (RTX PRO 4000 Blackwell 24 GB, driver 597.16)
| Prova | Trascrizione 60 s* | Claude | Esito |
|---|---|---|---|
| Da sorgente | 49,7 s (primo caricamento del modello) | 7,5 s | 13 segmenti, IT 100%, JSON valido |
| `vox_smoke.exe` | 17,1 s | 5,2 s | 13 segmenti, IT 100%, JSON valido |
| `vox_smoke.exe` ridotto, offline, modello in `models\` | 28,0 s (prima lettura del modello copiato) | 11,4 s | 13 segmenti, IT 100%, JSON valido |
| Ricostruito da zero (2026-11-02), offline, PATH minimo, da `%TEMP%` | 33,9 s (prima lettura del modello copiato) | 5,5 s | 13 segmenti, IT 100%, JSON valido |

\* comprende il caricamento del modello; la trascrizione vera è una frazione.

Pacchetto: **1,0 GB** senza modello (era 2,3 GB con cuDNN e NVRTC completi). Con il modello large-v3 (~3 GB) si arriva a ~4 GB.

## Scoperte e decisioni
- **PyAV 19 rompe `faster_whisper.audio.decode_audio`** (parametro `metadata_errors` rimosso). Decodifica audio scritta in `transcribe.decode_audio`: elimina la dipendenza e servirà comunque per i blocchi dei video lunghi.
- **Claude Code `--tools ""`** disattiva tutti gli strumenti: le chiamate di sola scrittura testo non possono toccare file né rete. Gli strumenti (Read per i fotogrammi, WebSearch/WebFetch per le fonti) si abilitano per singola chiamata.
- **Account Claude:** su questo PC la CLI è collegata a un account personale (`pro`); gli utenti avranno solo Team. Il controllo accetta qualsiasi account collegato e si limita a mostrare account e piano.
- **DLL NVIDIA:** durante la trascrizione ctranslate2 carica solo `cublas64_12` e `cublasLt64_12` (più il suo `cudnn64_9.dll`); cuDNN e NVRTC dei pacchetti `nvidia-*` sono esclusi nello spec (−1,3 GB). Runtime Visual C++ già inclusi da PyInstaller.
- **Icona provvisoria** (`build/make_icon.py`): il marchio è una fascia 1011×163, a 16–32 px è illeggibile. Da rifare in Fase 5 (meglio da vettoriale o da un simbolo dedicato).

## Esito
**Fase 0 chiusa il 2026-11-02.** Si sviluppa e si usa solo su questo PC: la prova su un secondo PC non è prevista. Se in futuro servisse un altro PC e fallisse per cuDNN mancante, rimettere cuDNN in `CUDA_KEEP` nello spec.

## Pronto per la Fase 1
Serve una **registrazione di call reale** (con esito atteso) come test di accettazione.
