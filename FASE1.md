# Ingeniotec Vox – Fase 1: pipeline "report di call" da riga di comando (2026-11-02)

Riferimenti: `REQUISITI.md` (Modalità B), `ARCHITETTURA.md` (piano a fasi, riga 1), `FASE0.md`.

## Obiettivo
Da una registrazione reale di call, senza GUI, ottenere **report snello (1–2 pagine) + allegato** in .docx e PDF.

**Caso di prova:** una call Teams reale di progetto (84 min, 3,9 GB, 8 partecipanti, CAD/Word/Excel condivisi).

## Piano
| # | Attività | Stato |
|---|---|---|
| 1 | `core/jobs.py`: cartella di lavoro `_lavoro/`, checkpoint atomici per fase, log `vox.log` | ✅ |
| 2 | `core/transcribe.py`: avanzamento durante la trascrizione | ✅ |
| 3 | `core/frames.py`: fotogrammi candidati (solo fotogrammi chiave, cambio di schermata), fogli di anteprima 4×3, ritaglio | ✅ |
| 4 | `profiles/call_report/`: prompt e schemi JSON (partecipanti, blocco, report, schermate) come dati | ✅ |
| 5 | `docs/builder.py`: motore documento derivato dal kit, senza template, stile report Ingeniotec (logo, numeri di pagina) | ✅ |
| 6 | `docs/call_report.py` (report + allegato) e `docs/pdf.py` (Word COM in istanza dedicata, fogli di controllo) | ✅ |
| 7 | `pipeline_call.py` + `cli.py`: fasi con ripresa, map-reduce in parallelo, `--rifai <fase>` | ✅ |
| 8 | Prova sulla call reale e correzioni (report da 4 a 2 pagine, trascrizione compatta) | ✅ |
| 9 | Revisione dei contenuti da parte di chi era alla call | ⏳ |

## Come si usa
```
.venv\Scripts\python -m ingeniotec_vox.cli call "<video>" [--out _out] [--nome NOME] [--trascrizione]
    [--max-schermate 12] [--blocco-min 20] [--rifai trascrizione|fotogrammi|partecipanti|blocchi|report|schermate]
```
Risultati in `<out>/<nome>/`: `<data> <titolo> - Report.docx/.pdf` e `- Allegato.docx/.pdf`.
In `_lavoro/`: trascrizione, fotogrammi, fogli, JSON di ogni fase, schermate ritagliate, `controllo_*.png` (pagine del PDF in miniatura), `vox.log`.
Se il lavoro si interrompe (errore, limite d'uso di Claude), rilanciando lo stesso comando riparte dalla fase mancante.

## Pipeline
1. **Trascrizione** Whisper large-v3 su GPU → `trascrizione.json`.
2. **Fotogrammi**: decodifica dei soli fotogrammi chiave, nuovo candidato se cambia ≥ 8% della miniatura e sono passati ≥ 20 s (max 144) → `fotogrammi/`, fogli `fogli/foglio_NN.jpg` con id e minuto.
3. **Partecipanti** (Claude con Read sui fogli e fotogrammi): nomi dai riquadri Teams, piattaforma, titolo finestra, cosa si vede nel video.
4. **Blocchi** (map, 3 richieste in parallelo): trascrizione a blocchi di 20 min → argomenti, decisioni, azioni, punti aperti, interventi, termini.
5. **Report** (reduce): report snello + allegato in un unico JSON (schema rigido).
6. **Schermate** (Claude con Read): max 12 fotogrammi utili, argomento, didascalia, ritaglio in frazioni → `schermate/`.
7. **Documenti**: report (dati, sintesi, decisioni, azioni, punti aperti) e allegato (indice, argomenti con schermate, interventi per persona, glossario, trascrizione opzionale), PDF con Word.

## Risultati sulla call di prova (RTX PRO 4000 Blackwell, account Pro)
| Fase | Tempo |
|---|---|
| Trascrizione 84 min | 7 min 9 s (2.759 segmenti, IT) |
| Fotogrammi + fogli | 19 s (93 candidati, 8 fogli) |
| Partecipanti | 29 s |
| 5 blocchi in parallelo | ~2 min 30 s |
| Report | ~2 min 20 s |
| Schermate | ~1 min 40 s |
| Documenti + PDF | ~20 s |
| **Totale** | **~15 min** |

Costo riportato da Claude Code (equivalente API, con l'abbonamento non si paga a consumo): ~3,5 USD per l'intera call.

Esito: **Report 2 pagine**, **Allegato 18 pagine** (13 di contenuto + 5 di trascrizione). Partecipanti letti tutti correttamente dalla griglia Teams (8/8). Decisioni e scopo coerenti con il verbale di sintesi fatto a mano per la stessa call. Schermate pertinenti e ritagliate senza barre di Teams né riquadri dei volti.

## Scoperte e decisioni
- **Report snello:** con limiti generici ("fino a 10 decisioni") Claude scriveva 4 pagine. Servono limiti espliciti di numero e parole per campo (prompt `report.md`); i dettagli restano negli argomenti dell'allegato.
- **Interventi per persona deboli senza diarizzazione:** dalla sola trascrizione Claude attribuisce con sicurezza pochi interventi (1–2 persone su 8); gli altri restano "un partecipante". È atteso: si risolve in Fase 4 (voci + riquadro evidenziato di Teams). Nell'allegato c'è una nota che lo dichiara.
- **Partecipanti dai fotogrammi:** basta Claude con Read sui fogli di anteprima e 2–4 fotogrammi a piena risoluzione; l'OCR locale non è servito per i nomi.
- **Fotogrammi chiave:** OBS registra un fotogramma chiave ogni ~8 s; decodificare solo quelli scansiona 84 min di 1080p in ~20 s.
- **Trascrizione in appendice:** una riga per segmento Whisper occupava ~40 pagine; raggruppata in paragrafi da ~1 min sono 5.
- **Stile:** report Ingeniotec (Calibri, titoli blu 1F4E78, logo nell'intestazione, "Pagina X di Y"), non il modello delle dispense del corso. Box del kit mantenuti, aggiunto il box NOTA.
- **Nuove dipendenze:** `python-docx`, `pymupdf` (in `requirements.txt`).

## Non fatto in questa fase
- Pacchetto .exe della CLI (la build resta quella della prova di fumo): si impacchetta con la GUI in Fase 5.
- Diarizzazione e abbinamento voce–nome: Fase 4.
- Lingua dei documenti con call in inglese: i prompt producono sempre italiano (punto aperto in `REQUISITI.md`).
