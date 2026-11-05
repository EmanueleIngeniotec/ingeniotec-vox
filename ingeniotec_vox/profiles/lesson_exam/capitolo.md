Corso: {corso}
Lezione: {lezione} – {titolo_lezione}
Docente: {docente}

Capitoli della dispensa (per sapere cosa tratteranno gli altri ed evitare doppioni):
{capitoli}

Scrivi il **capitolo {n}. {titolo}** (min. {inizio}–{fine}, peso per l'esame: {peso}).
Indicazioni dalla struttura: {contenuto}

Il capitolo deve permettere di studiare l'argomento senza rivedere il video: spiega i concetti, riporta i passaggi operativi così come li fa il docente (menu, comandi, campi, valori), le motivazioni, gli errori da evitare e i consigli per l'esame. Prediligi elenchi puntati con frasi complete e tabelle quando ci sono confronti, campi o valori; un paragrafo introduttivo breve se serve.

**Lunghezza: al massimo {parole} parole in tutto** (testi, voci, celle e box insieme). È un limite rigido: la dispensa intera deve stare in circa 30 pagine. Scegli ciò che serve all'esame e scrivi in modo asciutto; non ripetere la stessa cosa in un paragrafo, in un elenco e in un box. Niente chiacchiere d'aula, problemi tecnici del collegamento o digressioni senza contenuto.

`elementi`, in ordine di lettura. Ogni elemento ha `tipo` e i campi indicati:
- `paragrafo`: `testo`.
- `sottotitolo`: `testo` e `min` (h:mm) – solo per dividere i capitoli lunghi (sottotitoli consentiti in questo capitolo: {sottotitoli}).
- `elenco`: `voci` (frasi complete, al massimo 12 per elenco).
- `passi`: `voci` – una procedura numerata (al massimo 12 passi).
- `tabella`: `intestazione` (2–4 colonne) e `righe` (stesse colonne; celle brevi).
- `ricorda`: `testo` – box DA RICORDARE (concetto chiave per l'esame), al massimo uno per capitolo, 1–3 frasi.
- `attenzione`: `testo` – box ATTENZIONE (errore tipico, trabocchetto, comportamento inatteso del software), al massimo uno e solo se serve, 1–2 frasi.
- `schermata`: `id`, `testo` (didascalia), `ritaglio` – vedi sotto.
- `verifica`: `testo` e `min` (h:mm, il minuto del video in cui il docente lo dice) – un'affermazione tecnica o normativa del docente da controllare su fonti ufficiali (date, nomi di prodotti, articoli di norme, limiti, comportamenti del software non mostrati a video). Scrivi l'affermazione in modo autonomo e verificabile (es. «Il docente afferma che il rebranding da Autodesk Construction Cloud ad Autodesk Forma è avvenuto circa un anno fa»). Mettila subito dopo l'elemento a cui si riferisce. **Non c'è un numero fisso:** una verifica per ogni affermazione che va controllata, quante ce ne sono (anche nessuna, se il capitolo è solo operativo e tutto si vede a video, o molte se il docente cita norme, date e regole). Non verificare ciò che si vede a video né le opinioni o i consigli del docente. Il testo delle verifiche non conta nel limite di parole.

**Schermate.** I fotogrammi del video in questo intervallo sono in `fotogrammi/` (cartella di lavoro): {fotogrammi}
Aprine con lo strumento Read quelli che sembrano utili (al massimo 12) e inserisci **al massimo {max_schermate}** schermate, solo se aiutano davvero a studiare: una finestra di dialogo con i campi da compilare, uno schema, una tabella, il risultato di un comando. Una schermata che mostra solo dove si clicca o una pagina quasi vuota non serve. Evita schermate quasi uguali, schermi neri o di transizione, desktop, posta, e **mai** documenti d'esame riservati (testi delle prove). Per ciascuna:
- `id`: l'id del fotogramma (es. f042);
- `testo`: didascalia di una frase che dice cosa mostra (es. «Impostazioni di autorizzazione della cartella L1 Condivisione con i livelli assegnati ai membri»), senza inventare dettagli che non si vedono e senza il minuto;
- `ritaglio`: [x0, y0, x1, y1] in frazioni dell'immagine (0–1) stretto sulla parte utile (il dialogo, il pannello, lo schema, la tabella), togliendo barre del browser, della videoconferenza e del sistema operativo e le zone vuote; [0, 0, 1, 1] solo se serve davvero tutto lo schermo.

Oltre agli elementi:
- `domande_aula`: le domande fatte da un partecipante in questo intervallo, con la risposta del docente in breve e il minuto. Solo domande di contenuto, non organizzative.
- `autoverifica`: al massimo {autoverifica} domande di autoverifica sul capitolo con risposta breve (una frase), su ciò che serve all'esame.
- `saper_fare`: 0–3 attività pratiche che chi fa l'esame deve saper fare dopo questo capitolo (es. «Creare le cartelle L0–L3 con sottocartelle per disciplina»); vuoto se il capitolo è solo teorico.

Trascrizione del capitolo:
{trascrizione}
