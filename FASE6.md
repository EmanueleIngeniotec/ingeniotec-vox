# Ingeniotec Vox – Fase 6: installer, prove su altri PC, documentazione, versione (2026-11-05)

Riferimenti: `ARCHITETTURA.md` («Installazione (decisa il 28/10)», «Rischi principali», piano a fasi riga 6), `FASE5.md` («Pacchetto», «Non fatto in questa fase»), `build/build.ps1`.

## Obiettivo
Distribuzione interna: un `setup.exe` che un collega installa da solo, con la guida, e una release con numero di versione che i programmi installati riconoscono.

## Piano
| # | Attività | Stato |
|---|---|---|
| 1 | Passo «Claude Code + account» in uno script unico (`core/claude_setup.ps1`), usato da setup.exe e da Vox | ✅ |
| 2 | `setup.exe` con Inno Setup (`build/vox_setup.iss`, `build/installer.ps1`) | ✅ |
| 3 | Versione 0.1.0, pacchetto ricostruito | ✅ |
| 4 | Installazione, prova completa dal programma installato, reinstallazione, disinstallazione su questo PC | ✅ |
| 5 | Guida per chi lo usa (`GUIDA.md`) e lista di prova per gli altri PC | ✅ |
| 6 | Distribuzione: `setup.exe` intero e guida PDF nella cartella di rete aziendale dei programmi | ✅ |
| 7 | Release `v0.1.0` su GitHub con solo tag e note (nessun binario), `releases/latest` la restituisce | ✅ |
| 8 | Prove su 2–3 PC diversi (lista sotto) | ⏳ |

## Come si costruisce
```
build\build.ps1        -> dist\Vox\ (4,1 GB, modelli compresi)
build\installer.ps1    -> dist\installer\Vox-<versione>-setup.exe
.venv\Scripts\python build\guida_pdf.py   -> dist\installer\Guida Ingeniotec Vox.pdf (GUIDA.md via Word)
```
`installer.ps1` legge la versione da `ingeniotec_vox/__init__.py` e la passa a Inno Setup (`/DAppVersion`). Inno Setup 6.7.3 installato con `winget install JRSoftware.InnoSetup` (per utente, `%LOCALAPPDATA%\Programs\Inno Setup 6`).

| | |
|---|---|
| `setup.exe` | 3,32 GB, un solo file |
| Compressione | `lzma2/fast` non solida, 8 thread: i modelli si comprimono poco (4,1 → 3,3 GB), la build dura ~30 s |
| Installazione silenziosa qui | 3,6 min |

## Cosa fa setup.exe
| Requisito (ARCHITETTURA.md) | Come |
|---|---|
| Controlli iniziali di driver NVIDIA e Word | All'avvio: `nvidia-smi.exe` in System32 o servizio `nvlddmkm`; chiave `Word.Application\CLSID`. Se manca qualcosa: messaggio con le istruzioni e «Continuare?» (solo verifica, nessuna installazione) |
| Cartella `C:\Programmi\Ingeniotec Software\Vox` | `{autopf}\Ingeniotec Software\Vox`, modificabile (su Windows italiano `C:\Programmi` è il nome mostrato di `C:\Program Files`) |
| Collegamenti e disinstallazione | `Vox` nel menu Start (tutti gli utenti) e sul desktop (casella, spuntata); voce «Ingeniotec Vox» in App installate con icona e versione |
| Claude Code + account come l'utente | Ultima pagina: «Installa Claude Code e collega l'account» (spuntata), lanciata con `runasoriginaluser`, cioè con l'utente che ha avviato setup.exe anche se UAC ha chiesto le credenziali dell'IT |
| Dati e log in `%LOCALAPPDATA%\Ingeniotec Vox` | Già così da Fase 5 (`app/main.py`); il programma non scrive nella sua cartella |
| Aggiornamento | Stesso `AppId`: si installa sopra; `_internal\` della versione precedente si cancella prima della copia |

Diritti: `PrivilegesRequired=admin` (cartella in Program Files). Se un utente senza diritti avvia setup.exe, UAC chiede le credenziali dell'IT ma il passo di Claude resta dell'utente. Se invece l'IT installa dal proprio account, Claude Code finisce nel profilo dell'IT: al primo avvio l'utente vede ✖ Claude Code e il pulsante.

### Claude Code: `core/claude_setup.ps1`
Script unico (Windows PowerShell 5.1, UTF-8 con BOM per gli accenti):
1. cerca `claude` nel PATH o in `%USERPROFILE%\.local\bin\claude.exe` (dove lo mette l'installer ufficiale);
2. se manca, `irm https://claude.ai/install.ps1 | iex` (installer ufficiale Anthropic);
3. `claude auth status`; se non collegato `claude auth login` (apre il browser) e ricontrolla;
4. messaggio finale e «Premi Invio».

In Vox il pulsante si chiama ora **«Installa e collega Claude»**, compare per Claude mancante o non collegato e lancia lo stesso script. `env_check.claude_exe()` cerca anche in `.local\bin`: il PATH aggiornato dall'installer non arriva a un Vox già aperto, quindi «Ricontrolla» funziona senza riavviare.

## Distribuzione (scelta dell'utente, 05/11)
| | |
|---|---|
| `setup.exe` | **intero** (un file da 3,3 GB) nella cartella di rete aziendale dei programmi, insieme a `Guida Ingeniotec Vox.pdf`; copia verificata con SHA-256 |
| GitHub | **solo il codice** per mantenere il programma: nessun binario. Ogni versione ha una release con tag `v<versione>` e note, senza allegati |
| Avviso in Vox | invariato nel meccanismo (`releases/latest`); il testo ora dice di prendere il nuovo setup dalla cartella di rete e il link porta alle note («Novità») |

Scartati: setup diviso in pezzi < 2 GB allegati alla release, link cloud. Nelle note pubbliche non compare il percorso di rete.

## Versione
**0.1.0**: prima distribuzione interna, funzioni complete ma non ancora provate da un utente non tecnico né su altri PC. **1.0.0** dopo le prove della riga 8 e la prova di Fase 5 riga 7. Tag `v<versione>`; Vox confronta il tag di `releases/latest` con `__version__`.

## Prove su questo PC
| Prova | Esito |
|---|---|
| `claude_setup.ps1` con Claude già installato e collegato (PowerShell 5.1) | accenti corretti, riconosce installazione e account |
| Installazione silenziosa (`/VERYSILENT /LOG`, UAC confermato) | 3,6 min; 4,10 GB in `C:\Program Files\Ingeniotec Software\Vox`; collegamenti in Desktop pubblico e Start; voce in App installate con versione 0.1.0 |
| Programma installato: `vox_cli --help` | «Ingeniotec Vox 0.1.0» |
| Programma installato: call 17:48 da zero in `_out\prova_setup\` (GPU, voci, Claude, Word) | 5,5 min, report 2 pagine + allegato 7; nella cartella del programma nessun file nuovo |
| Programma installato: `Vox.exe` | finestra «Ingeniotec Vox 0.1.0», nessun errore in `vox_gui.log` |
| Reinstallazione sopra | `_internal\` tolta e ricreata (log di setup), programma presente |
| Disinstallazione silenziosa | cartella (anche `Ingeniotec Software\`), collegamenti e voce in App installate tolti |

Non provati qui: le pagine della procedura guidata (installazione silenziosa), il messaggio dei controlli iniziali (driver e Word presenti), `claude_setup.ps1` su un PC senza Claude Code: righe 3–5 e 14 della lista sotto.

## Lista di prova per gli altri PC
Scegliere PC diversi tra loro: almeno uno **senza Claude Code**, uno con **utente senza diritti di amministratore**, possibilmente una GPU con meno memoria (≤ 6 GB) e un PC con Office diverso (Microsoft 365 / Office 2021).

| # | Prova | Atteso | PC 1 | PC 2 | PC 3 |
|---|---|---|---|---|---|
| 1 | Annotare GPU e memoria (`nvidia-smi`), Windows, Office, utente admin sì/no | – | | | |
| 2 | Copia di setup.exe dalla cartella di distribuzione e avvio | Avviso SmartScreen possibile («Ulteriori informazioni → Esegui comunque»): annotarlo | | | |
| 3 | Controlli iniziali | Nessun messaggio se driver e Word ci sono; messaggio chiaro se mancano | | | |
| 4 | Installazione con UAC (credenziali IT se l'utente non è admin) | Cartella `C:\Program Files\Ingeniotec Software\Vox`, ~5 min | | | |
| 5 | Ultima pagina: «Installa Claude Code e collega l'account» | Finestra blu, installazione, browser, «Fatto: collegato come …» con l'account dell'**utente** | | | |
| 6 | Collegamenti desktop e Start | Icona Vox, si apre | | | |
| 7 | Primo avvio: Controllo del PC | Tutto ✔; GPU con il nome della scheda | | | |
| 8 | Report di una call breve (5–15 min) | Report e allegato in Word e PDF, nomi plausibili | | | |
| 9 | Annulla a metà, poi Riprendi | Riparte dalla fase interrotta | | | |
| 10 | Dispense di una lezione breve (≤ 30 min, profilo generico) | Dispensa e scheda, schermate leggibili | | | |
| 11 | Durata dei lavori 8 e 10 | Annotare per la guida | | | |
| 12 | Impostazioni → Versione, Controlla aggiornamenti | 0.1.0; «Hai già l'ultima versione (0.1.0)» | | | |
| 13 | Disinstallazione da Impostazioni di Windows | Cartella del programma e collegamenti spariti; documenti e `%LOCALAPPDATA%\Ingeniotec Vox` restano | | | |
| 14 | Caso IT: installare dall'account dell'IT, poi entrare come utente | Vox mostra ✖ Claude Code e «Installa e collega Claude»; il pulsante lo sistema | | | |

Rischio da guardare: GPU con poca memoria (large-v3 in float16 vuole ~4,5 GB); se fallisce, annotare il messaggio.

## Documentazione
- `GUIDA.md`: per chi lo usa (requisiti, installazione, primo avvio, problemi comuni, disinstallazione). In PDF accanto a setup.exe nella cartella di rete (`build\guida_pdf.py`); su GitHub resta il .md.
- `README.md`: sezione installazione per chi sviluppa e build di setup.exe.

## Non fatto in questa fase
- Firma digitale di setup.exe e Vox.exe: senza certificato Windows SmartScreen può avvisare al primo avvio.
- Disinstallazione di Claude Code e dei dati in `%LOCALAPPDATA%`: lasciati di proposito (possono servire ad altro, sono dell'utente).
