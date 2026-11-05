# Ingeniotec Vox – Fase 3: profilo "lezione generica", guida 00, controllo impaginazione (2026-11-04)

Riferimenti: `REQUISITI.md` (Modalità A: profilo generico, aggiornamento guida con backup), `ARCHITETTURA.md` (piano a fasi, riga 3), `FASE2.md`, kit delle dispense fatte a mano (`fix00_layout.py`, `update_00_lib.py`, `update_00_L9.py`).

## Obiettivo
Stesso stile L5/L9 anche per lezioni senza esame, aggiornamento automatico della guida 00 del corso, nessun box o tabella spezzato tra due pagine.

## Piano
| # | Attività | Stato |
|---|---|---|
| 1 | `docs/impaginazione.py`: controllo con Word (COM) di tabelle, titoli, schermate con didascalia e box; correzione con interruzione di pagina | ✅ |
| 2 | `docs/pdf.py`: controllo prima dell'esportazione (`layout=True`), salva il .docx corretto | ✅ |
| 3 | `docs/guida.py` + `profiles/lesson_exam/guida.md`: guida descritta con id, operazioni proposte da Claude, applicate copiando gli elementi esistenti | ✅ |
| 4 | Profili con ereditarietà (`profilo.json`), profilo `lesson_generic` (niente esame, prova pratica, crocette) | ✅ |
| 5 | Prove su L9: impaginazione, guida su copia, profilo generico | ✅ |

## Come si usa
```
.venv\Scripts\python -m ingeniotec_vox.cli lezione "<video>" --corso "Certificazione BIM" --numero 9
    [--guida "<cartella corso>\00 - Guida all'esame e glossario.docx"]
    [--rifai ...|scheda|guida]

.venv\Scripts\python -m ingeniotec_vox.cli lezione "<video>" --profilo generico [--corso "..."] [--numero N]
```
- `--profilo esame` (predefinito) richiede `--corso` e `--numero`; `--guida` vale solo con questo profilo.
- Con il profilo generico i file si chiamano `Dispensa - <titolo>` e `Scheda di ripasso` (prefisso `L<n> - ` solo se c'è `--numero`).

## Controllo dell'impaginazione
Per ogni documento, prima del PDF, Word ricalcola le pagine e controlla:
- **tabelle** da tenere intere (righe con «mantieni con il successivo»);
- **titoli** (livelli 1–3) separati dal paragrafo che segue;
- **schermate** separate dalla didascalia;
- **box** (paragrafi ombreggiati fuori tabella).

Un blocco spezzato che sta in una pagina riceve l'interruzione di pagina all'inizio della sua catena «mantieni con il successivo» (al massimo 3 paragrafi prima). Poi Word ripagina e ricontrolla. Un blocco più lungo di una pagina è segnalato nel log come problema.

| Documento | Correzioni | Problemi | Tempo |
|---|---|---|---|
| L9 fatta a mano (prima del controllo impaginazione) | 4 box (pag. 5, 8, 20, 22) | 0 | – |
| Vox L9, dispensa 37 pagine | 0 | 0 | ~1 min 25 s |
| Vox L9, scheda 4 pagine | 0 | 0 | ~15 s |
| Guida 00 aggiornata, 15 pagine | 0 | 0 | ~17 s |

Il controllo con PyMuPDF sul PDF aveva segnalato due possibili box spezzati (Vox pag. 5, kit pag. 12): erano due box diversi, uno a fine pagina e uno all'inizio della successiva.

## Aggiornamento della guida 00
1. **Backup:** prima di modificare, la guida viene copiata in `_versioni_precedenti/<nome> (prima della L<n>).docx`, come nel kit. Se la copia esiste già, Vox riparte da quella: rifare il passo (`--rifai guida`) non applica le modifiche due volte.
2. **Descrizione:** Claude riceve la guida con id (P1… paragrafi, T0… tabelle, righe da r0) e il contenuto della dispensa e della scheda.
3. **Operazioni:** `aggiungi_riga`, `modifica_cella`, `riscrivi_paragrafo`, `nuovo_punto`, `nuova_tabella`, ciascuna con il motivo, scritto nel log.
4. **Applicazione:** Vox copia righe, punti e tabelle esistenti (stile, ombreggiatura alternata, elenchi) e ci scrive i testi nuovi. Le operazioni con riferimenti sbagliati si saltano e si segnalano. Poi rende le tabelle non spezzabili come `fix00_layout.py` e passa il controllo dell'impaginazione.

Prova sulla copia della guida «prima della L9» (`_out/prova_guida/`): 8 operazioni su 8, in linea con `update_00_L9.py` fatto a mano:
- riga della dispensa L9 e riga delle schede nella tabella dei file;
- paragrafo delle lezioni pratiche;
- riga della nuova prova nella tabella delle prove;
- punto sulla prova pratica della lezione (nel punto giusto dell'elenco);
- RTP e GPU nel glossario;
- tabella riassuntiva della lezione 9, 14 domande.

Tempo ~50 s, costo 0,3–0,6 USD equivalenti. La guida reale nella cartella del corso **non è stata modificata**.

Da controllare a mano: una sigla del glossario è sciolta in modo diverso dalla guida fatta a mano; la forma viene dalla dispensa.

## Profilo "lezione generica"
`profiles/lesson_generic/profilo.json` eredita da `lesson_exam` (`"eredita": "lesson_exam", "esame": false`). Ridefinisce solo `sistema.md`, `struttura.md`, `capitolo.md`, `scheda.md` e i due schemi; fonti e doppioni sono quelli del profilo esame.
- La mappa ha la colonna **Importanza** al posto di «Peso per l'esame».
- Niente «cose da saper fare» e checklist della prova pratica, niente crocette nella scheda.
- «Trabocchetti» diventano **Errori da evitare**, «Domande fatte in aula» diventano **Domande dei partecipanti**.

Prova sulla stessa L9 (trascrizione e fotogrammi riusati), `_out/L9_generico/`:

| | L9 profilo esame (3ª prova) | L9 profilo generico |
|---|---|---|
| Capitoli | 22 | 21 |
| Pagine dispensa / scheda | 37 / 4 | **36 / 3** |
| Parole della dispensa | 12.428 | **12.706** |
| Affermazioni verificate | 32 (27 con fonti) | **31 (28 con fonti)** |
| Impaginazione | 0 correzioni | 0 correzioni |

Tempo ~20 min senza trascrizione, ~15 USD equivalenti. La L9 parla comunque dell'esame, quindi «esame» e «crocette» compaiono nei testi come contenuto della lezione, non nelle sezioni del modello.

## Errori trovati e corretti
- **Word «Comando fallito» su SaveAs2:** il PDF della guida andava in `_lavoro` con un percorso relativo, che Word risolve rispetto alla propria cartella. Ora `pdf.py` usa sempre percorsi assoluti.
- **Righe contate dopo gli inserimenti:** nella prima prova Claude ha numerato le righe tenendo conto di quelle appena aggiunte e 2 operazioni su 8 sono state saltate. Il prompt ora dice che id e righe si riferiscono sempre alla guida originale; il programma mantiene l'ordine di più inserimenti sullo stesso punto. Seconda prova: 8 su 8.

## Non fatto in questa fase
- Aggiornamento della guida con il profilo generico: non c'è una guida all'esame.
- Lezioni divise in più video (es. L5): ancora un video per lezione.
- Applicazione alla guida reale del corso: da fare con `--guida` quando la dispensa L9 di Vox sostituirà quella fatta a mano.
