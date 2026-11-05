Corso: {corso}
Lezione: {lezione}
Registrazione: {contesto}

Qui sotto c'è la trascrizione completa della lezione, a paragrafi di circa mezzo minuto con il minuto di inizio tra parentesi quadre. Prepara la **struttura** della dispensa:

- `titolo`: il tema della lezione in al massimo 9 parole, come nelle dispense del corso (es. «Autodesk Forma Data Management per il CDE Manager», «Revit per il BIM Specialist strutturale»), senza «Lezione N» e senza sottotitoli dopo i due punti.
- `docente`: nome e cognome del docente se emergono dalla lezione (e l'ente tra parentesi se detto), altrimenti stringa vuota.
- `nota_video`: 2–3 frasi sul video per chi lo vuole rivedere: durata, eventuali pause o parti non registrate, momenti in cui lo schermo non è condiviso, dove iniziano le parti speciali (es. domande d'esame lette a voce). Concludi con «Nei capitoli il riferimento è il minuto del video.»
- `ricorda`: il box DA RICORDARE di apertura, 2–4 frasi: di cosa tratta la lezione, a quale parte dell'esame serve, il messaggio principale del docente.
- `capitoli`: da 10 a 22 capitoli in ordine di tempo, che coprono tutta la lezione senza buchi (le chiacchiere e i problemi tecnici si accorpano al capitolo vicino). Ogni capitolo:
  - `titolo`: breve e specifico (es. «Autorizzazioni sulle cartelle», «Creare il progetto»), senza numero né minuti;
  - `inizio`, `fine`: minuti h:mm del video;
  - `peso`: peso per l'esame, una parola tra Basso, Medio, Alto, Altissimo, eventualmente seguita da «: » e una precisazione breve (es. «Alto: richiesto nella prova», «Medio: utile all'orale»), in base a quanto il docente lega l'argomento all'esame;
  - `contenuto`: 2–4 frasi per chi scriverà il capitolo: cosa si spiega e si mostra, cosa non va dimenticato, quali momenti sono importanti.
  Se la lezione contiene domande d'esame lette o commentate (es. crocette di ripasso), dedicale un capitolo a parte.
- `indice`: l'indice del video, una voce ogni 2–4 minuti circa, **al massimo {max_indice} voci**, ciascuna con il minuto h:mm e una frase breve e informativa su cosa succede in quel punto (es. «Refuso della consegna: creare i ruoli», «Pausa (non registrata), poi caricamento della cartella V1»).

Trascrizione:
{trascrizione}
