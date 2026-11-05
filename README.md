# Ingeniotec Vox

Programma Windows nato per uso interno in Ingeniotec che, da una registrazione video, produce documenti in .docx e PDF:

- **Dispense di studio** di una lezione online: dispensa con mappa, indice del video, capitoli con i minuti, schermate ritagliate e box VERIFICA FONTI; scheda di ripasso; aggiornamento della guida all'esame del corso.
- **Report di una call**: report snello (1–2 pagine) e allegato con i dettagli e gli interventi di ogni persona (voci riconosciute in locale e abbinate ai nomi dei riquadri di Teams).

La trascrizione gira in locale sulla GPU (faster-whisper large-v3): il video non lascia il PC. Testi, scelta delle schermate e verifica delle fonti sono affidati a Claude Code in modalità non interattiva (`claude -p`), con l'abbonamento Claude dell'utente e senza chiavi API.

> Stato: interfaccia grafica e riga di comando (Fasi 0–5). L'installer è previsto nella Fase 6 (vedi [ARCHITETTURA.md](ARCHITETTURA.md)).

## Requisiti
- Windows 10/11 x64 con GPU NVIDIA e driver aggiornati
- Python 3.13
- [Claude Code](https://claude.com/claude-code) installato e con accesso effettuato (`claude` nel PATH)
- Microsoft Word (esportazione PDF e controllo dell'impaginazione)

## Installazione
```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```
Il modello Whisper viene scaricato al primo uso, oppure si legge da `models\faster-whisper-large-v3` o dalla cartella indicata in `VOX_MODEL_DIR` (o con `--model`).

Modello delle voci per i report di call (libero, senza token, ~40 MB), da mettere in `models\diarizzazione\` (o nella cartella indicata in `VOX_DIARIZE_DIR`):
```powershell
New-Item -ItemType Directory -Force models\diarizzazione
curl.exe -L -o models\diarizzazione\3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx `
    https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx
```
Senza il modello il report si fa lo stesso, con gli interventi attribuiti dal solo contenuto.

## Uso
### Finestra
```powershell
.venv\Scripts\python -m ingeniotec_vox.app
```
Si sceglie cosa produrre (report di call o dispense), si trascina il video nella finestra e si preme **Avvia**. La finestra mostra le fasi e l'avanzamento, permette di annullare e, da «Lavori recenti», di riprendere un lavoro interrotto, rifarlo da capo o correggere i nomi di chi parla in una call. Dal pulsante **Impostazioni** si cambiano il tema (chiaro, scuro, come Windows), si apre il codice sorgente su GitHub e si legge la versione. I risultati vanno in `Documenti\Ingeniotec Vox\<nome lavoro>\` (cambiabile). Dettagli in [FASE5.md](FASE5.md).

### Riga di comando
Dispense di una lezione di un corso con esame:
```powershell
.venv\Scripts\python -m ingeniotec_vox.cli lezione "<video>" --corso "Certificazione BIM" --numero 9 `
    [--guida "<cartella corso>\00 - Guida all'esame e glossario.docx"] [--docente "Nome Cognome"]
```
Lezione senza esame (corso, webinar, presentazione tecnica):
```powershell
.venv\Scripts\python -m ingeniotec_vox.cli lezione "<video>" --profilo generico [--corso "..."] [--numero N]
```
Report di una call:
```powershell
.venv\Scripts\python -m ingeniotec_vox.cli call "<video>" [--trascrizione]
```
I risultati vanno in `_out\<nome lavoro>\` (cambiabile con `--out` e `--nome`); i file intermedi, il log `vox.log` e le anteprime delle pagine in `_lavoro\`.

Il lavoro è diviso in fasi salvate su disco: se si interrompe (errore, limite d'uso di Claude), rilanciando lo stesso comando riparte dalla fase mancante. `--rifai <fase>` rifà il lavoro da quella fase in poi. Elenco completo delle opzioni con `--help`.

Con `--guida` la versione precedente della guida viene copiata in `_versioni_precedenti\` accanto alla guida prima di modificarla.

## Struttura
```
ingeniotec_vox/
  app/                 interfaccia grafica (PySide6)
  cli.py               riga di comando (usata anche dalla finestra)
  pipeline_call.py     report di una call
  pipeline_lezione.py  dispense di una lezione
  core/                trascrizione, fotogrammi, wrapper di Claude Code, checkpoint, controllo dell'ambiente
  docs/                composizione dei documenti, PDF con Word, impaginazione, guida all'esame
  profiles/            prompt e schemi JSON per tipo di documento (call_report, lesson_exam, lesson_generic)
assets/                loghi e icona
build/                 build PyInstaller (build.ps1 → dist\Vox\Vox.exe e vox_cli.exe), icona
```

## Documentazione
- [REQUISITI.md](REQUISITI.md): cosa deve fare il programma
- [ARCHITETTURA.md](ARCHITETTURA.md): scelte tecniche e piano a fasi
- [FASE0.md](FASE0.md) … [FASE5.md](FASE5.md): diario di ogni fase, con prove, tempi e costi

## Contribuire
Il codice è pubblico perché chiunque possa correggerlo e mantenerlo. Problemi e proposte: [issue su GitHub](https://github.com/EmanueleIngeniotec/ingeniotec-vox/issues) (dal programma: Impostazioni → Segnala un problema…). Modifiche: fork, ramo, pull request. Il diario delle fasi (`FASE*.md`) spiega le scelte fatte e le prove.

Nuova versione: aggiornare `__version__` in `ingeniotec_vox/__init__.py`, ricostruire con `build\build.ps1` e pubblicare una release su GitHub con tag `v<versione>`: i programmi già installati la segnalano all'avvio.

## Licenza
[MIT](LICENSE). Il marchio e i loghi Ingeniotec in `assets/` restano di Ingeniotec: chi distribuisce una versione modificata non li usa senza permesso.

