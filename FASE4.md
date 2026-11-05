# Ingeniotec Vox – Fase 4: voci e nomi a schermo nel report di call (2026-11-04)

Riferimenti: `REQUISITI.md` (Modalità B, interventi per persona), `ARCHITETTURA.md` (piano a fasi, riga 4; rischio «diarizzazione e abbinamento nomi poco affidabili»), `FASE1.md` (limite noto: senza voci solo 1–2 persone su 8 attribuite).

## Obiettivo
Attribuire gli interventi della call alle persone giuste, **senza token né servizi esterni**: voci separate in locale con modelli liberi, nomi presi dal riquadro che Teams evidenzia mentre una persona parla.

## Piano
| # | Attività | Stato |
|---|---|---|
| 1 | Prova di sherpa-onnx (segmentazione pyannote + impronta della voce + clustering) e di un metodo sui segmenti di Whisper | ✅ |
| 2 | `core/diarize.py`: voci sui segmenti di Whisper, riquadro evidenziato sui fotogrammi chiave, fogli dei campioni, abbinamento dei nomi | ✅ |
| 3 | `profiles/call_report/nomi.md` + schema: Claude dà un nome a ogni campione | ✅ |
| 4 | `pipeline_call.py`: fasi `voci` e `nomi` con checkpoint, nomi nella trascrizione dei blocchi, `--rifai voci\|nomi` | ✅ |
| 5 | Allegato: nota sull'attribuzione solo se serve; trascrizione in appendice con chi parla | ✅ |
| 6 | Prove su 3 registrazioni (2 call) e verifica a campione (`tests/verifica_voci.py`) | ✅ |
| 7 | Conferma dei casi dubbi da parte di chi era alla call | ⏳ |

## Come si usa
Nessuna opzione nuova: `cli call "<video>"` fa anche le fasi voci e nomi se trova il modello.
```
.venv\Scripts\python -m ingeniotec_vox.cli call "<video>" [--trascrizione] [--rifai voci|nomi|...]
```
- Modello: `models\diarizzazione\3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx` (~40 MB, rilascio `speaker-recongition-models` di k2-fsa/sherpa-onnx su GitHub, download libero; comando nel README). Altra cartella con `VOX_DIARIZE_DIR`.
- Senza modello o senza `sherpa-onnx` il report si fa come in Fase 1 (attribuzione dal contenuto, con la nota).
- In `_lavoro/`: `voci.json` (voce di ogni segmento), `voci_impronte.npy`, `riquadri.json` (riquadri evidenziati per fotogramma chiave), `evidenze.json` e `voci_fogli/voce_V*.jpg` (campioni), `nomi.json` (nome di ogni voce e segmento, risposta di Claude).
- Verifica a campione: `.venv\Scripts\python tests\verifica_voci.py "<video>" <_lavoro> [--n 40]` → fogli in `_lavoro\verifica\`.

## Pipeline
1. **Voci** (CPU, nessuna GPU necessaria): ogni segmento di Whisper è diviso in pezzi di ~3 s; per ogni pezzo l'impronta della voce (ERes2Net di 3D-Speaker via sherpa-onnx). Clustering agglomerativo sul coseno, soglia 0,60; voci sotto 8 s unite alla più simile se abbastanza vicina. Ogni segmento prende la voce prevalente. Le voci sono V1, V2… in ordine di tempo parlato.
2. **Riquadri evidenziati**: su tutti i fotogrammi chiave (OBS: uno ogni ~8 s) si cerca il rettangolo col bordo viola di Teams (#7F84F5): quattro lati quasi pieni, interno libero. Funziona sia con la griglia sia con la striscia di miniature durante la condivisione.
3. **Campioni**: per ogni voce, fino a 8 fotogrammi in cui parla solo lei da almeno 0,8 s (Teams evidenzia in ritardo) e c'è un solo riquadro evidenziato, sparsi nel tempo; se non bastano, fotogrammi cercati dentro i suoi pezzi più lunghi. Foglio per voce: fotogramma ridotto con il riquadro in rosso + riquadro ingrandito.
4. **Nomi** (Claude con Read): un nome per **ogni campione** (dal nome nel riquadro o riconoscendo volto, abiti e sfondo nella griglia con i nomi), più nome, certezza e motivo per la voce.
5. **Abbinamento** (locale): voce con lo stesso nome in ≥ 75% dei campioni → tutta la voce a quella persona. Voce **mista** (due persone con voce simile unite) → ogni pezzo va alla persona, tra quelle viste nei campioni, con l'impronta media più simile. Voce senza campioni → nome proposto da Claude solo con certezza alta o media.
6. **Blocchi**: la trascrizione passata a Claude ha `Nome: testo` su ogni riga (`?` se non identificato); il prompt dice di usare questi nomi per gli interventi.
7. **Allegato**: se ≥ 90% del parlato è attribuito la nota sull'attribuzione sparisce, altrimenti dice quale quota manca; nella trascrizione in appendice i paragrafi cambiano a ogni cambio di persona.

## Scelta del metodo (call 17:31, 16 min, 4 persone)
| Metodo | Tempo (CPU) | Esito |
|---|---|---|
| sherpa-onnx completo (segmentazione pyannote 3.0 + ERes2Net + clustering veloce), soglia 0,5 | 88 s | 57 gruppi, voci principali frammentate |
| idem con 4 gruppi imposti | 190 s | 549/214/91/3 s, terzo gruppo misto |
| **ERes2Net sui pezzi dei segmenti di Whisper + agglomerativo** | **7 s** | 2 voci principali pulite + voci brevi; allineato a Whisper per costruzione |

Provato anche TitaNet (NeMo) nel metodo completo: stesso problema di frammentazione; tenuto solo ERes2Net. Soglia scelta sulla call lunga: a 0,5 un'unica voce da 73 min che conteneva anche altre persone, a 0,6 sette voci; troppe voci non sono un problema (Claude dà lo stesso nome a più voci), troppo poche sì.

## Risultati
| | Call 17:31 (16 min) | Call 17:48 (10 min) | Call lunga (84 min) |
|---|---|---|---|
| Partecipanti nei riquadri | 4 | 4 | 8 |
| Voci ≥ 8 s | 5 | 2 | 7 |
| Campioni concordi per voce | 100, 88, 88, 100%; 1 mista | 100, 100% | 100% ×6; 1 mista (tre persone) |
| Parlato attribuito | 98% | 98% | 99% |
| Persone negli interventi | 3 | 2 | 5 (Fase 1: 1, con 3 contributi) |
| **Verifica a campione** (segmenti a caso, riquadro a metà segmento) | **30/30** (2 senza riquadro) | **13/13** (3 senza riquadro, 1 dubbio) | **34/35** (5 senza riquadro) |

**Accuratezza complessiva sui segmenti verificabili: 77/78 (99%).** La verifica usa segmenti scelti a caso (stratificati per persona) e un fotogramma diverso da quelli usati per dare i nomi; il campione è dominato da chi parla di più (call lunga: una persona 73 min su 81). Sulle persone che parlano poco (call lunga) 7 su 8.

Distribuzione nella call lunga: persona A 73,0 min, B 3,1, C 2,3, D 2,1, E 0,7. Nessun parlato attribuito a F, G e a chi registrava.

### Tempi (RTX PRO 4000 Blackwell, 24 core) e costi
| Fase | 17:31 | 17:48 | Call lunga |
|---|---|---|---|
| Voci | 9 s | 5 s | 53 s |
| Riquadri evidenziati | 12 s | 8 s | 64 s |
| Campioni | 17 s | 2 s | 24 s |
| Nomi (Claude) | 35 s, 0,48 USD | 12 s, 0,40 USD | 36 s, 0,50 USD |
| **Totale fasi nuove** | **~1 min 15 s** | **~30 s** | **~3 min** |
| Lavoro intero | 5 min 15 s + trascrizione 1 min 30 s; 1,94 USD | 3 min 30 s + 1 min; 1,63 USD | 9 min 30 s da `--rifai voci`; 3,59 USD |

Costi: equivalente API riportato da Claude Code; con l'abbonamento non si paga a consumo.

## Le due call del 15/10
`2026-10-15 17-31-22.mp4` e `2026-10-15 17-48-09.mp4` sono **due parti della stessa call**: stessa riunione Teams, stessi 4 partecipanti, la prima finisce alle 17:47:38 e la seconda parte 31 s dopo; lo schizzo aperto alla fine della prima è al centro della seconda. Vox oggi le tratta come due call (due report). L'ultimo pacchetto audio della prima è corrotto (registrazione interrotta): ora `decode_audio` salta i pacchetti illeggibili invece di fermarsi.

## Casi dubbi da confermare (chi era alla call)
| Call | Minuto | Vox dice | Dubbio |
|---|---|---|---|
| Call lunga | 0:13:08, 0:42:32, 0:58:11 | persona D | voce V2 mista con la persona C: separate per somiglianza; il riquadro conferma 0:13:08 |
| Call lunga | 1:17:26 | persona E | evidenziata la persona A (forse ritardo del riquadro) |
| Call lunga | – | – | F e G non hanno parlato? (chiarito, vedi sotto) |
| 17:48 | 0:07:40 | una persona | sembra evidenziato il riquadro dell'altra |

## Scoperte e decisioni
- **Nessun token:** sherpa-onnx (Apache 2.0) con il modello ERes2Net di 3D-Speaker, scaricabile senza account; pyannote scartato. Gira su CPU (~40 s di impronte per 84 min), quindi niente onnxruntime-gpu nel pacchetto.
- **Il riquadro non è un'identità:** Teams riordina le miniature (chi parla sale nelle prime posizioni) e nella striscia piccola il nome non è scritto. Serve riconoscere la persona: Claude lo fa bene confrontando i volti con la griglia con i nomi. L'OCR locale non è servito.
- **Nome per campione, non per voce:** chiedere un nome per ogni campione fa emergere le voci miste (call lunga, V2: due colleghi con voce simile); con un solo nome per voce sarebbero finite tutte a una persona.
- **Persona dominante:** nella call lunga una persona parla per il 90% del tempo e la sua voce è divisa in 4 gruppi (frasi brevi, tono diverso): tutti riportati a lui dai campioni.
- **Soglie:** somiglianza 0,60, voce minima 8 s, ritardo del riquadro 0,8 s, accordo 75% per dare il nome a tutta la voce.

## Non fatto in questa fase
- **Google Meet e altre piattaforme:** è verificato solo il bordo del nuovo Teams; per Meet va aggiunto il colore in `HIGHLIGHT_COLORS` dopo una prova.
- **Call senza riquadri** (condivisione a tutto schermo senza miniature, solo audio): le voci restano senza nome se la conversazione non lo rende evidente; si torna alla nota.
- **Call divise in più video** (come le due del 15/10): un video per lavoro.
- **Voce di chi registra:** nelle prove OBS catturava solo l'audio di Teams, non il microfono locale (confermato il 05/11): per questo nessun parlato è attribuito a lui. Per averlo nel report va aggiunta in OBS la sorgente «Cattura ingresso audio» col microfono; Vox poi lo tratta come le altre voci (il riquadro di chi registra si evidenzia anche nella sua finestra Teams). Da provare su una nuova registrazione.
- Correzione manuale dei nomi: in GUI (Fase 5), come previsto in `ARCHITETTURA.md`.
- Inclusione del modello nel pacchetto PyInstaller: Fase 6.
