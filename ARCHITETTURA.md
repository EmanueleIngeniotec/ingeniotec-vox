# Ingeniotec Vox – Architettura e piano a fasi (bozza v0.1, 2026-10-28)

Requisiti in `REQUISITI.md`. Qui: come costruirlo.

## Principi
1. **Locale ciò che è pesante** (video, audio, trascrizione): il video non lascia il PC. **Claude gira sempre in headless** (`claude -p` lanciato dal .exe, nessun upload manuale, l'utente non lo vede) e riceve solo la trascrizione a blocchi e un sottoinsieme di fotogrammi salvati come file nella cartella di lavoro, che legge da disco (`--allowedTools`, `--add-dir`).
2. **Python che pilota processi esterni**: GPU (Whisper), Claude Code CLI, Word. Il .exe è un involucro con interfaccia semplice.
3. **Pipeline a fasi con checkpoint su disco**: ogni fase scrive il risultato in una cartella di lavoro; se si interrompe o fallisce, riparte dalla fase fallita (utile con video da 3–4 h e limiti d'uso).
4. **Contenuto separato dall'impaginazione**: Claude produce JSON strutturato; il motore di documento (derivato da `builder.py`) lo impagina. Così lo stile è identico per ogni lezione.

## Stack proposto
| Parte | Scelta | Motivo |
|---|---|---|
| Interfaccia | PySide6 (Qt) | Aspetto professionale, barra di avanzamento, thread per non bloccare la finestra |
| Trascrizione | faster-whisper large-v3 (CUDA), VAD integrato | Già usato nel kit; italiano e inglese |
| Video/audio | PyAV (già nel kit) + ffmpeg incluso | Estrazione audio e fotogrammi |
| Diarizzazione | sherpa-onnx (impronta della voce ERes2Net, CPU) sui segmenti di Whisper + clustering agglomerativo (Fase 4) | Offline, nessun token, modelli liberi in `models\diarizzazione`; pyannote scartato (token Hugging Face) |
| Nomi a schermo | Bordo di Teams su chi parla rilevato in locale sui fotogrammi chiave + Claude con Read sui riquadri (Fase 4) | Abbinamento voce–nome tramite chi risulta evidenziato mentre parla; OCR locale non servito |
| Rilevamento schermate | differenza tra fotogrammi (SSIM/istogrammi) con PyAV/OpenCV | Candidati per ritagli, poi scelti da Claude |
| LLM | Claude Code CLI in modalità non interattiva (`claude -p`, `--output-format json`, `--json-schema`, `--allowedTools`, `--no-session-persistence`) | Usa l'abbonamento Team; legge immagini; fa ricerca web per le fonti |
| Documenti | python-docx + motore stile (`builder.py`), loghi da `assets/` | Stile L5/L9 |
| PDF e controllo | Word COM (pywin32) + PyMuPDF | Come oggi; Word su tutti i PC |
| Pacchetto | PyInstaller (cartella) + `setup.exe` Inno Setup con modello Whisper incluso | Python, CUDA e modello già dentro: sul PC servono solo driver NVIDIA, Word e Claude Code |

Verificato su questo PC: Claude Code 2.1.292 con le opzioni headless necessarie, faster-whisper 1.2.1, python-docx, PyAV.

## Struttura del repository
```
ingeniotec_vox/
  app/            # GUI (PySide6): schermate, thread, icona
  core/
    env_check.py  # GPU, Claude Code (installato/login), Word, disco
    jobs.py       # cartella di lavoro, checkpoint, ripresa
    transcribe.py # Whisper
    diarize.py    # voci e nomi (solo call)
    frames.py     # fotogrammi e rilevamento schermate
    claude.py     # wrapper di `claude -p`, JSON schema, retry, limiti
  profiles/
    lesson_exam/  # prompt + schema + template (corso con esame)
    lesson_generic/
    call_report/
  docs/           # builder.py adattato, componenti (box, tabelle, didascalie)
  assets/         # loghi, icona
  build/          # spec PyInstaller, installer
  tests/
```
Ogni **profilo** è dati, non codice: prompt per Claude, schema JSON dell'output, mappatura sui componenti del documento. Aggiungere un profilo non richiede toccare la pipeline.

## Flusso (cartella di lavoro `<output>/<nome>/_lavoro/`)
**Comune**
1. `env_check` → messaggi guidati in italiano se manca Claude Code o il login.
2. Audio estratto → Whisper (con timestamp, lingua rilevata IT/EN) → `trascrizione.json`.

**Modalità A – dispense**
3. Fotogrammi candidati ogni cambio schermata → foglio di anteprima.
4. Claude (fase 1): indice e capitoli con minuti, scelta dei fotogrammi utili e dei ritagli (coordinate) → `struttura.json`.
5. Ritaglio automatico delle schermate.
6. Claude (fase 2, un capitolo per volta): testo, box DA RICORDARE/ATTENZIONE, domande di autoverifica; scheda di ripasso; guida 00 → `contenuto.json`.
7. Claude (fase 3): verifica fonti con ricerca web, link ufficiali → box VERIFICA FONTI.
8. Composizione .docx, esportazione PDF con Word, controllo impaginazione (porting di `fix00_layout.py` e `pgsheets.py`), correzioni automatiche.

**Modalità B – report call**
3. Voci separate (sherpa-onnx) + riquadro evidenziato mentre ogni voce parla → Claude dà il nome ai campioni → mappa voce–persona (dettagli in `FASE4.md`).
4. Claude: report snello (sintesi, decisioni, azioni) + allegato (argomenti con timeline, interventi per persona, screenshot) → JSON.
5. Composizione e PDF.

Per video lunghi la trascrizione si divide in blocchi con riassunto progressivo (map-reduce), così nessuna richiesta supera il contesto né i limiti d'uso, e una fase fallita si ripete da sola.

## Installazione (decisa il 28/10)
Un unico `setup.exe` (Inno Setup, ~3 GB compressi, anche da cartella di rete), comportamento da installer classico:
1. **Controlli iniziali:** driver NVIDIA e Word (solo verifica, con istruzioni se mancano).
2. **Cartella:** scelta dall'utente, predefinita `C:\Programmi\Ingeniotec Software\Vox`. Collegamento `Vox` sul desktop e nel menu Start, disinstallazione da Impostazioni.
3. **Claude Code + account:** installazione con l'installer ufficiale Anthropic (serve internet), poi `claude auth login` guidato e verifica che un account sia collegato (qualsiasi piano).
4. Dati di lavoro e log in `%LOCALAPPDATA%\Ingeniotec Vox`, mai nella cartella del programma.

**Diritti di amministratore non garantiti:** Claude Code si installa per utente, quindi se l'installer gira con le credenziali dell'IT finirebbe nel profilo sbagliato. Perciò il passo 3 si fa **come l'utente**: nell'installer se è lui ad avviarlo, altrimenti al primo avvio di Vox (stesso controllo, stessa guida). Python e Whisper non si installano: sono dentro il pacchetto.

## Rischi principali
| Rischio | Mitigazione |
|---|---|
| Limiti d'uso del piano Team su video lunghi | Blocchi, checkpoint, ripresa, stima prima di partire, messaggio chiaro quando il limite è raggiunto |
| Qualità variabile dei testi senza supervisione umana | Schema rigido, regole del kit nei prompt, controllo automatico (fonti, struttura, impaginazione); prototipo confrontato con L5–L9 reali |
| Diarizzazione e abbinamento nomi poco affidabili | Provare 2 motori su una call reale; ripiego con correzione manuale dei nomi in GUI |
| Dimensione del pacchetto (CUDA + modello ≈ 4 GB) | Solo cuBLAS tra le DLL NVIDIA (Fase 0); modello incluso nel `setup.exe` |
| Dipendenza da Claude Code CLI (flag che cambiano) | Un solo punto di contatto (`claude.py`), test di compatibilità al primo avvio |
| Link o fonti inventati | Verifica con ricerca web e controllo HTTP dei link prima di inserirli |
| Word COM fragile (istanze Word aperte) | Istanza dedicata, timeout, pulizia dei processi |

## Piano a fasi
| Fase | Obiettivo | Esito verificabile |
|---|---|---|
| 0 | Setup repo, build "hello world" PyInstaller con GPU e Claude Code | .exe che trascrive 1 min di audio e chiama Claude |
| 1 | Pipeline **call** senza GUI (CLI) su una registrazione reale | PDF snello + allegato corretti |
| 2 | Pipeline **lezione** senza GUI su una lezione già nota (es. L9) | Dispensa confrontabile con quella esistente |
| 3 | Profilo "lezione generica", guida 00, controllo impaginazione automatico | Stesso stile L5/L9, nessun box/tabella spezzato |
| 4 | Diarizzazione e nomi a schermo | Attribuzione corretta su 2 call reali |
| 5 | GUI PySide6, checkpoint/ripresa, messaggi d'errore, icona e loghi | Utente non tecnico completa un lavoro da solo (GUI fatta, vedi `FASE5.md`) |
| 6 | Installer, test su 2–3 PC diversi, documentazione, versione | Distribuzione interna (setup.exe 0.1.0 fatto e provato qui, vedi `FASE6.md`) |

Ordine scelto per ridurre il rischio: prima il valore (call è più semplice, lezione è più lunga), la GUI solo quando la pipeline è stabile.

## Da decidere subito
- Una call reale e una lezione di prova (con esito atteso) da usare come test di accettazione.
