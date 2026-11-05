# Ingeniotec Vox – Fase 2: pipeline "dispense di una lezione" da riga di comando (2026-11-02)

Riferimenti: `REQUISITI.md` (Modalità A), `ARCHITETTURA.md` (piano a fasi, riga 2), `FASE1.md`, kit delle dispense fatte a mano del corso.

## Obiettivo
Da una lezione già nota, senza GUI, ottenere **dispensa + scheda di ripasso** in .docx e PDF nello stile delle dispense del kit, confrontabili con quelle fatte a mano.

**Caso di prova:** una lezione reale di un corso con esame, qui «L9» (~3 h 25 min, 1,5 GB), confrontata con la dispensa e la scheda di ripasso fatte a mano per la stessa lezione.

## Piano
| # | Attività | Stato |
|---|---|---|
| 1 | `docs/builder.py`: temi `report` e `dispensa` (stile L5/L9: titoli e tabelle rossi, Calibri 11) con logo Ingeniotec; domande di autoverifica; schermate alte ridotte | ✅ |
| 2 | `profiles/lesson_exam/`: prompt e schemi (struttura, capitolo, fonti, scheda) come dati | ✅ |
| 3 | `docs/lezione.py`: dispensa (mappa, indice del video, capitoli, domande in aula, checklist prova pratica, autoverifica) e scheda di ripasso | ✅ |
| 4 | `pipeline_lezione.py` + comando `lezione` in `cli.py`: fasi con ripresa, capitoli in parallelo con le schermate, verifica fonti con ricerca web e controllo HTTP dei link | ✅ |
| 5 | Prima prova completa sulla L9 | ✅ (troppo lunga, vedi sotto) |
| 6 | Limiti di lunghezza per capitolo, box fonti più brevi, scheda entro 1.300 parole, colonne delle tabelle | ✅ |
| 7 | Seconda prova sulla L9 con i limiti e confronto con la dispensa fatta a mano | ✅ (35 pagine) |
| 8 | Verifiche senza numero fisso, box «non verificabile» con il minuto, doppioni tolti | ✅ (37 pagine, 32 box) |

## Come si usa
```
.venv\Scripts\python -m ingeniotec_vox.cli lezione "<video>" --corso "Certificazione BIM" --numero 9
    [--docente "Nome Cognome"] [--out _out] [--nome NOME] [--max-schermate 3]
    [--rifai trascrizione|fotogrammi|struttura|capitoli|fonti|scheda]
```
Risultati in `<out>/<nome>/`: `L<n> - Dispensa - <titolo>.docx/.pdf` e `L<n> - Scheda di ripasso.docx/.pdf`.
In `_lavoro/`: trascrizione, fotogrammi e fogli, `struttura.json`, `capitoli/`, `fonti/`, `link.json`, `scheda.json`, `schermate/`, `controllo_*.png`, `vox.log`.

## Pipeline
1. **Trascrizione** Whisper large-v3 su GPU → `trascrizione.json`.
2. **Fotogrammi** candidati (solo fotogrammi chiave, max 240 per le lezioni lunghe) e fogli di anteprima.
3. **Struttura** (una richiesta con la trascrizione intera a paragrafi di 30 s): titolo, docente, 10–22 capitoli con minuti e peso per l'esame, indice del video, box DA RICORDARE iniziale.
4. **Capitoli** (3 in parallelo, Claude con Read sui fotogrammi del proprio intervallo): elementi tipizzati (paragrafo, sottotitolo, elenco, passi, tabella, ricorda, attenzione, schermata con ritaglio, verifica), domande fatte in aula, autoverifica, cose da saper fare per la prova.
5. **Fonti** (lotti di 6 affermazioni, Claude con WebSearch/WebFetch): esito e testo del box VERIFICA FONTI con link ufficiali; ogni link viene poi aperto da Vox e quelli non raggiungibili si tolgono; senza fonti valide il box non compare.
6. **Scheda di ripasso** (una richiesta sul contenuto della dispensa già verificato).
7. **Documenti** e PDF con Word, fogli di controllo dell'impaginazione.

## Prima prova sulla L9 (RTX PRO 4000 Blackwell, account Pro)
| Fase | Tempo |
|---|---|
| Trascrizione 3 h 25 min | 17 min 7 s |
| Fotogrammi (240) + fogli | 40 s |
| Struttura | 2 min 19 s |
| 22 capitoli, 3 in parallelo | ~9 min 30 s |
| 46 affermazioni in 8 lotti, 2 in parallelo | ~11 min |
| Scheda + documenti + PDF | ~1 min 15 s |
| **Totale** | **~42 min** |

Costo riportato da Claude Code (equivalente API): ~23 USD.

| | L9 fatta a mano | Vox, 1ª prova |
|---|---|---|
| Pagine dispensa / scheda | 33 / 4 | 84 / 6 |
| Parole della dispensa | 9.345 | 30.098 |
| Schermate | 24 | 46 |
| Box VERIFICA FONTI | 21 | 43 (su 46 affermazioni; 3 senza fonti valide) |

Struttura (22 capitoli, peso per l'esame, indice) e contenuti pertinenti; il problema è la lunghezza. Risultati in `_out/<lezione>/_lavoro/prova1/`.

## Scoperte e decisioni
- **Limiti espliciti per capitolo:** come per il report di call, senza numeri Claude scrive il triplo. Ora `budgets()` ripartisce sui capitoli 8.000 parole, 24 schermate e 30 domande di autoverifica in base a durata e peso; 1–2 verifiche e 0–3 sottotitoli per capitolo. Nei primi 5 capitoli della seconda prova i limiti sono stati rispettati (anzi Claude resta ~15% sotto: da qui 8.000 invece di 7.000).
- **Struttura in una richiesta:** la trascrizione intera di 3 h 25 min (paragrafi da 30 s) sta in una sola richiesta; non serve il map-reduce a blocchi della call.
- **Schermate scelte dai capitoli:** ogni capitolo apre con Read i fotogrammi del proprio intervallo, così le schermate stanno nel punto giusto del testo.
- **Link:** Vox apre ogni link proposto da Claude; si tengono anche le risposte 401/403/405/429 (molti siti ufficiali bloccano i client automatici), quindi un link sbagliato su questi siti non viene scartato.
- **Limite d'uso:** il messaggio «You've hit your session limit» non era riconosciuto come limite (si ritentava); corretto in `core/claude.py`. Le richieste in parallelo si fermano al primo limite (`parallel()`).
- **Stile:** tema `dispensa` nel builder (rosso B01E23, Calibri 11, margini 2,2/2,0 cm) con logo Ingeniotec in intestazione e «Pagina X di Y».

## Seconda prova sulla L9 (con i limiti, 2026-11-03)
Interrotta due volte dal limite d'uso del piano e ripresa dal punto in cui si era fermata (capitoli già fatti riusati).

| | L9 fatta a mano | Vox, 1ª prova | Vox, 2ª prova |
|---|---|---|---|
| Pagine dispensa / scheda | 33 / 4 | 84 / 6 | **35 / 4** |
| Parole della dispensa / scheda | 9.345 / – | 30.098 / – | **10.782 / 1.056** |
| Schermate | 24 | 46 | **20** |
| Tabelle | 13 | – | 24 |
| Affermazioni verificate / box VERIFICA FONTI | 21 | 46 / 43 | **12 / 8** |

Tempi: 22 capitoli ~25–55 s l'uno (3 in parallelo), fonti 2 lotti in ~3 min, scheda 40 s. Costo equivalente API ~12 USD (capitoli, fonti, scheda; la struttura era già fatta).

Lunghezza, schermate e scheda ora sono in linea con la dispensa fatta a mano. Da migliorare:
- **Poche verifiche:** con il limite «al massimo una/due» Claude ne propone solo 12 (13 capitoli su 22 senza nessuna) e i box finali sono 8 contro 21. Nella prossima fase chiedere un numero minimo (es. «una per capitolo se c'è un'affermazione tecnica o normativa») invece di un massimo.
- **Indice del video lungo:** 78 voci occupano quasi 3 pagine; valutare un massimo più basso (durata/240).
- Contenuti da far rileggere a chi ha seguito la lezione: la prova misura forma e lunghezza, non l'esattezza riga per riga.

Risultati in `_out/<lezione>/`, prima prova in `_lavoro/prova1/`.

## Terza prova: verifiche senza numero fisso (2026-11-03)
- **Nessun limite alle verifiche:** il capitolo segnala ogni affermazione tecnica o normativa da controllare (0 o 100), non ciò che si vede a video né opinioni e consigli; il testo delle verifiche non conta nel limite di parole. Oltre 60 affermazioni Vox scrive un avviso nel log (non taglia nulla).
- **Box «non verificabile»:** se non ci sono fonti valide (nessuna trovata o link non raggiungibili) il box resta: «Non verificabile: <affermazione>. Nessuna fonte ufficiale trovata: controllare nella registrazione al min. h:mm». Ogni verifica ha ora il minuto del video (`min`).
- **Doppioni:** prima delle fonti una richiesta breve (`doppioni.md`, ~0,04 USD) segnala le affermazioni ripetute in più capitoli; il box resta solo alla prima.

Risultato con i capitoli nuovi, prima dei doppioni: 38 pagine, 12.612 parole, 19 schermate, 36 affermazioni (32 confermate con fonti, 4 non verificabili). Doppioni trovati: 4 (es. la stessa regola sui ruoli nei capitoli 7, 8 e 9) → 32 affermazioni.

Risultato finale della terza prova (fonti riprese il 2026-11-04 dopo il limite d'uso):

| | L9 fatta a mano | 2ª prova | 3ª prova |
|---|---|---|---|
| Pagine dispensa / scheda | 33 / 4 | 35 / 4 | **37 / 4** |
| Parole della dispensa | 9.345 | 10.782 | **12.428** |
| Schermate | 24 | 20 | **19** |
| Box VERIFICA FONTI | 21 | 8 | **32** (27 con fonti, 5 «non verificabile» con il minuto) |

Fonti e scheda della terza prova: ~5,2 USD equivalenti (6 lotti da 2–3,5 min, 2 in parallelo). Risultati in `_out/<lezione>/`, seconda prova in `_lavoro/prova2/`.

Da controllare a mano: i 5 box «non verificabile» (es. min. 0:31) sono comportamenti del software che il docente dice a voce; vanno visti nella registrazione.

## Non fatto in questa fase
- Lezioni divise in più video (es. L5): un video per lezione.
- Aggiornamento della guida 00 e controllo automatico dell'impaginazione: Fase 3 (`FASE3.md`).
