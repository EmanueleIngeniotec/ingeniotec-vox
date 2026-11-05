# Ingeniotec Vox – Fase 5: interfaccia grafica, ripresa, errori, icona (2026-11-05)

Riferimenti: `ARCHITETTURA.md` (piano a fasi, riga 5; ripiego «correzione manuale dei nomi in GUI»), `REQUISITI.md` (finestra semplice, errori chiari in italiano, annullare e riprendere), `FASE0.md` (icona provvisoria), `FASE1.md` (exe con la GUI), `FASE4.md`.

## Obiettivo
Un utente non tecnico completa un lavoro da solo: sceglie il video, preme Avvia, vede l'avanzamento, apre il PDF; se qualcosa si ferma capisce perché e riprende.

## Piano
| # | Attività | Stato |
|---|---|---|
| 1 | Eventi di avanzamento dalle pipeline (`§VOX {json}`), registro del lavoro `lavoro.json`, codici di uscita della CLI | ✅ |
| 2 | GUI PySide6: nuovo lavoro, controllo del PC, avanzamento per fasi, annulla, lavori recenti con Riprendi / Rifai da capo | ✅ |
| 3 | Correzione dei nomi delle voci (`correzioni_nomi.json`, report rifatto dalla fase blocchi) | ✅ |
| 4 | Icona nuova e marchio nell'intestazione | ✅ |
| 5 | Prove della GUI su una copia della call 17:48 (ripresa, correzione nomi, annullamento) | ✅ |
| 6 | Pacchetto PyInstaller `dist\Vox\` con `Vox.exe` e `vox_cli.exe` | ✅ |
| 7 | Prova con un utente non tecnico | ⏳ |

## Come si usa
```
.venv\Scripts\python -m ingeniotec_vox.app          (sviluppo)
dist\Vox\Vox.exe                                     (pacchetto)
```
1. **Controllo del PC** all'avvio (GPU, Claude Code e account, Word, disco), in un thread: la finestra non si blocca. Se Claude Code non è collegato compare «Collega l'account Claude», che apre `claude auth login` in una console.
2. **Nuovo lavoro:** report di call o dispense (corso con esame / lezione generica, corso, numero, docente, guida all'esame facoltativa). Il video si sceglie o si trascina nella finestra. «Avvia» resta spento finché manca qualcosa, con il motivo accanto.
3. **Cartella dei risultati:** predefinita `Documenti\Ingeniotec Vox`, si cambia da Impostazioni → Cartella dei risultati ed è indicata sopra i lavori recenti. Le ultime scelte (corso, profilo, guida) restano ricordate.
4. **Lavoro già presente** per lo stesso video: «Continua» (riusa le fasi fatte) o «Rifai da capo».
5. **Avanzamento:** elenco delle fasi (✔ fatta, ▶ in corso, ✖ ferma), barra della fase (percentuale reale per trascrizione e voci, parti concluse per blocchi, capitoli e fonti) e barra totale stimata con pesi per fase; tempo trascorso; «Mostra dettagli» apre il log.
6. **Fine:** «Apri il report» / «Apri la dispensa», «Apri cartella», per le call «Correggi nomi…».
7. **Lavori recenti:** stato (Completato, Interrotto, In attesa – limite Claude, Errore), Riprendi, Rifai da capo, Correggi nomi, doppio clic apre la cartella.

## Come funziona
- **Processo separato:** la GUI lancia la riga di comando (`vox_cli.exe` nel pacchetto, `python -m ingeniotec_vox.cli` in sviluppo) con `VOX_EVENTI=1`. Annullare chiude l'intero albero di processi (`taskkill /T`: Whisper, `claude -p`); il Word aperto via COM non è un processo figlio, quindi si chiude solo quello con `/Automation` avviato dopo l'inizio del lavoro (mai il Word dell'utente).
- **Eventi:** `Job.step` sa a quale fase appartiene ogni checkpoint (`STEPS`) e scrive `§VOX {"fase": …}`; trascrizione e voci scrivono anche `avanzamento`; la CLI chiude con `fine` (file prodotti) o `errore` (tipo e messaggio).
- **`_lavoro/lavoro.json`:** tipo, video, opzioni, esito, messaggio, file prodotti, ultimo aggiornamento. Lo scrivono le pipeline (anche da CLI), lo legge la GUI per l'elenco e per rilanciare il lavoro con gli stessi parametri.
- **Errori → messaggi:** codici di uscita della CLI 2 ambiente, 3 Claude, 4 limite d'uso, 5 Word, 6 imprevisto; ognuno ha un testo per l'utente e il dettaglio sotto. Errori della finestra in `%LOCALAPPDATA%\Ingeniotec Vox\vox_gui.log`.
- **Sospensione:** durante un lavoro il PC non va in sospensione (`SetThreadExecutionState`), utile per le lezioni da 3–4 ore.
- **Chiusura con lavoro in corso:** chiede conferma, interrompe e segna il lavoro come interrotto.
- **Tema:** Fusion con palette esplicita (chiaro, scuro o come Windows, letto da `AppsUseLightTheme`): lasciando decidere a Fusion i due temi si mescolavano e i colori delle fasi non si leggevano. Colori del codice in `app/theme.py` (`col()`), ricolorati al cambio di tema.
- **Impostazioni** (pulsante nell'intestazione): Tema (Chiaro / Scuro / Come Windows, ricordato), Cartella dei risultati, Segnala un problema, Controlla aggiornamenti, Codice sorgente su GitHub, Versione (versione, Python e PySide6, cartella del programma, registro errori). Indirizzo della repo in `ingeniotec_vox.REPO_URL`.
- **Segnala un problema** (menu e pagina di un lavoro fermo): apre una issue GitHub già compilata con versione, Windows, esito del lavoro e solo le righe d'errore del log, con il nome utente tolto dai percorsi. Il resto del log non va: contiene nomi e titoli e le issue sono pubbliche. Serve un account GitHub.
- **Nuova versione:** all'avvio, in un thread, Vox chiede a GitHub l'ultima release (`releases/latest`); se il tag è più recente di `__version__` compare un avviso con il link. Senza rete o senza release nessun messaggio. Dal menu «Controlla aggiornamenti» risponde sempre.
- **Fine lavoro:** se la finestra non è in primo piano, l'icona nella barra delle applicazioni lampeggia e Windows mostra una notifica (lavoro finito o interrotto); un clic riporta Vox davanti. Con «Non disturbare» attivo Windows la tiene nel centro notifiche.

## Correzione dei nomi
Finestra con una riga per voce (≥ 8 s): minuti di parlato, nome dato da Vox (con l'avviso se la voce era mista), due frasi d'esempio, «Vedi campioni» (foglio `voci_fogli/voce_V*.jpg`) e il nome corretto (elenco dei partecipanti o testo libero; «lascia com'è»; «nessuno»).

Il salvataggio scrive `_lavoro/correzioni_nomi.json` (`{"voci": {"V2": "Nome"}}`) e rilancia il lavoro con `--rifai blocchi`: trascrizione, voci, nomi e fotogrammi restano; blocchi, report e schermate si rifanno. Il nome scelto vale per tutta la voce, anche se era mista. Il file si cancella se si rifà la fase voci (gli id V1, V2… cambierebbero). `apply_corrections` accetta anche `{"persone": {"vecchio": "nuovo"}}` per rinominare ovunque, non ancora esposto nella finestra.

## Prove (copia della call 17:48 in `_out\prova_gui\`)
| Prova | Esito | Tempo |
|---|---|---|
| Riprendi un lavoro con tutte le fasi fatte | documenti e PDF rifatti, `lavoro.json` completato con i file | 5 s |
| Correggi nomi: V2 → «Prova Correzione» | blocco rifatto con il nuovo nome (24 occorrenze), report e allegato ricomposti | 3 min 08 s |
| Annulla durante «Composizione del report» | lavoro segnato interrotto, nessun `claude -p` né Word rimasto aperto | 12 s |

Schermate controllate: pagina iniziale, avanzamento, fine, correzione nomi, annullato.

## Icona
`build/make_icon.py`: quadrato arrotondato nel verde del marchio (#43818D) con una «V» bianca a tratto spesso, disegnata a 1024 px e ridotta a 16–256 px (`assets/vox.ico`, `assets/vox.png`). Leggibile a 16 px, a differenza della fascia del marchio. L'intestazione della finestra usa `logo_wordmark.png` su fondo dello stesso verde.

## Pacchetto
`build\build.ps1` → `dist\Vox\` con `Vox.exe` (finestra) e `vox_cli.exe` (riga di comando, usata dalla GUI), librerie condivise, profili e loghi; poi copia i modelli Whisper e delle voci in `dist\Vox\models\`.

| | |
|---|---|
| Dimensione | 4,2 GB: modelli 3,0 GB, librerie 1,2 GB (PySide6 solo `Essentials`) |
| Build | ~3 min più la copia dei modelli |
| `vox_cli.exe` sulla copia della call 17:48 | report e allegato rifatti, PDF 2 + 9 pagine, eventi `§VOX` corretti |
| `Vox.exe` | si apre con icona e marchio, controllo del PC tutto verde, nessun errore in `vox_gui.log` |

Errore trovato provando il pacchetto: `pymupdf.layout` cerca i suoi modelli ONNX tra i dati del pacchetto (mancava `collect_data_files("pymupdf")`). Il messaggio è arrivato come previsto («Errore imprevisto…», codice 6) e il lavoro è ripartito dopo la correzione.

## Altre correzioni
- **Documenti con il titolo cambiato:** rifacendo il report Claude può dare un altro titolo, quindi altri nomi di file; i documenti del giro precedente (elencati in `lavoro.json`) ora vanno in `_lavoro\versioni_precedenti\` invece di restare accanto ai nuovi.
- **Checkpoint scritti da più thread:** il file temporaneo ha l'id del thread nel nome.

## Non fatto in questa fase
- Prova con un utente non tecnico (esito verificabile della fase): da fare con un collega su una call nuova.
- Installer `setup.exe`, test su altri PC, versione: Fase 6.
- Rinomina di una persona ovunque (es. nome scritto male nei riquadri) dalla finestra: oggi si corregge voce per voce.
- Stima del tempo residuo: non serve, la barra totale avanza abbastanza (prova dell'utente, 05/11).
