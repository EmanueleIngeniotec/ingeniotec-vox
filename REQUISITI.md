# Ingeniotec Vox – Requisiti (bozza v0.1, 2026-10-28)

## Obiettivo
Programma Windows (.exe) per uso interno Ingeniotec che, da una registrazione video, produce a scelta:

- **A. Dispense di studio** da una lezione online: dispensa, scheda di ripasso, aggiornamento guida/glossario. Stile di riferimento: le dispense fatte a mano di un corso (L5 per la struttura, L9 per l'impaginazione).
- **B. Report PDF esaustivo** da una call video.

## Decisioni prese
| Tema | Decisione |
|---|---|
| Trascrizione | Locale, faster-whisper large-v3 su GPU NVIDIA (tutti i PC target hanno GPU NVIDIA) |
| Scrittura testi, scelta fotogrammi, verifica fonti | Claude Team tramite **Claude Code CLI** installato su ogni PC, lanciato in background dal .exe (nessuna chiave API) |
| Verifica fonti | Mantenuta come nelle dispense di esempio (box VERIFICA FONTI con link ufficiali, verificati) |
| Input | Entrambi: schermo condiviso (lezioni) e call con volti (Teams/Meet con nomi visibili) |
| Output A | .docx + PDF nello stile delle dispense esistenti, con loghi Ingeniotec nell'impaginazione |
| Output B | PDF esaustivo (vedi struttura sotto) |
| Esportazione PDF | Via Word (COM); Word presente su tutti i PC |
| Interfaccia | Finestra desktop semplice: scelta modalità, selezione video, barra di avanzamento, apri cartella output |
| Identità | Icona e loghi Ingeniotec (da fornire) |
| Call: partecipanti | Separazione voci (diarizzazione) + lettura dei nomi a schermo (OCR / Claude con immagini) per attribuire gli interventi |

## Modalità A – contenuti da produrre (da `dispense-lezioni-criteri.md`)
1. Dispensa: titolo/sottotitolo con data, docente, fonti; mappa della lezione con peso per l'esame; indice del video con minuti; capitoli numerati "· min. h:mm"; box DA RICORDARE / ATTENZIONE / VERIFICA FONTI; schermate ritagliate con didascalia; checklist prova pratica; domande fatte in aula; autoverifica.
2. Scheda di ripasso (3–4 pagine).
3. Aggiornamento della guida 00 (con backup in `_versioni_precedenti`).
4. Regole di impaginazione automatiche (box e tabelle non spezzati, ecc.) con controllo finale sul PDF.
5. Regole di contenuto: niente screenshot di documenti d'esame riservati; partecipanti anonimi ("un partecipante"), docente per nome.

## Modalità B – struttura del report (da confermare)
Dati della call (titolo, data, durata, partecipanti), sintesi esecutiva, argomenti con timeline, decisioni, azioni (chi, cosa, entro quando), punti aperti, interventi per persona, screenshot rilevanti, trascrizione in appendice (opzionale).

## Pipeline prevista
1. Controllo ambiente (GPU, Claude Code autenticato, Word, spazio disco).
2. Estrazione audio e trascrizione locale con tempi.
3. Call: diarizzazione, lettura nomi a schermo, abbinamento voci-nomi.
4. Lezione: rilevamento cambi schermata, estrazione fotogrammi candidati, scelta dei più utili e ritaglio.
5. Claude Code (headless): struttura, testi, box, domande di autoverifica, ricerca e verifica fonti.
6. Composizione documenti (motore stile derivato da `builder.py`) con loghi Ingeniotec.
7. Esportazione PDF via Word e controllo impaginazione.
8. Cartella output con documenti, log e file intermedi.

## Requisiti non funzionali
- Uso da parte di utenti non tecnici; errori chiari in italiano; possibilità di annullare e riprendere.
- Video lunghi (le lezioni sono 3–4 h, ~700 MB): elaborazione a blocchi, avanzamento reale.
- Riservatezza: la trascrizione e i fotogrammi selezionati escono verso Claude Team (termini commerciali Team); il video integrale non esce dal PC. Da validare con chi gestisce la privacy aziendale.
- Distribuzione: installer o cartella con .exe; il modello Whisper (~3 GB) e le librerie CUDA aumentano molto la dimensione; aggiornamenti interni.

## Decisioni del 28/10 (punti aperti chiusi)
- **Lingua:** italiano + inglese (Whisper in rilevamento/scelta lingua; documenti in italiano, da confermare se nella lingua del video).
- **Profili dispense:** due. "Corso con esame" (struttura attuale: peso per l'esame, prova pratica, guida 00) e "Lezione generica" (senza esame e prova pratica).
- **Report di call:** snello. 1–2 pagine con sintesi, decisioni, azioni (chi, cosa, quando); il resto (argomenti con timeline, interventi per persona, screenshot) in un allegato a parte.
- **Loghi:** ricavati dalla presentazione aziendale, in `assets/`: `logo_wordmark.png` (marchio INGENIOTEC su fascia verde, pulito) e `logo_cover.png` (con palazzi, su sfondo fotografico, non trasparente). Per icona .ico e uso su sfondi scuri servirebbe il file vettoriale originale.

## Ultime decisioni (28/10)
- **Logo:** si usa quello estratto (`assets/logo_wordmark.png`); l'icona .ico si genera da lì. Eventuale vettoriale in futuro.
- **Claude Code:** controllo al primo avvio (installato, versione, autenticato con account Team), con messaggi guidati in italiano se manca qualcosa. Il .exe non lo installa.
- **Riservatezza:** nessuna schermata di avviso; si assume Claude Team già approvato dall'azienda per uso interno.
- **Manutenzione:** non definita. Si progetta con build documentata e riproducibile e versione visibile nel programma.

## Decisioni installazione e account (28/10, dopo Fase 0)
- **Distribuzione:** un `setup.exe` (va bene anche da cartella di rete; ISO non necessaria) con modello Whisper incluso. Installer classico: controllo prerequisiti, scelta cartella (es. `C:\Programmi\Ingeniotec Software`), collegamento Vox sul desktop.
- **Claude Code:** lo installa l'installer (download ufficiale, internet disponibile) con guida al collegamento dell'account. Sostituisce "il .exe non lo installa" della decisione precedente.
- **Diritti di amministratore:** non noti/misti; installazione e login di Claude Code sempre come utente (nell'installer o al primo avvio).
- **Account:** gli utenti avranno solo l'account Team (app e CLI). Vox accetta **qualsiasi account Claude** collegato alla CLI (nessun controllo su piano od organizzazione); mostra solo account e piano. Sul PC di sviluppo la CLI è collegata a un account personale Pro.

## Da verificare in sviluppo
- Limiti d'uso del piano Team con video lunghi (3–4 h): elaborazione a blocchi e gestione dei limiti raggiunti.
- Lingua dei documenti con video in inglese (italiano o lingua del video).
