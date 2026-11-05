Corso: {corso}
Lezione: {lezione} – {titolo_lezione}

Nella dispensa ogni affermazione tecnica o normativa del docente ha un box **VERIFICA FONTI** con l'esito del controllo su fonti ufficiali e i link. Verifica le affermazioni qui sotto usando la ricerca web (WebSearch) e leggendo le pagine (WebFetch).

Fonti, in ordine di preferenza: documentazione ufficiale del produttore del software (guide, help, note di rilascio), testi delle norme o pagine degli enti (UNI, ISO, buildingSMART, Gazzetta Ufficiale, normattiva, ministeri, ACN), siti istituzionali; solo se mancano, articoli tecnici di editori di settore riconosciuti. Mai forum anonimi, video o siti che copiano altri siti. Preferisci le pagine in italiano se esistono.

Per ogni affermazione restituisci:
- `chiave`: quella indicata;
- `esito`: `confermato`, `precisazione` (vero in parte, va corretto o completato), `smentito`, oppure `non_verificabile` (nessuna fonte affidabile trovata);
- `testo`: il contenuto del box, 1–3 frasi e **al massimo 60 parole**. Inizia con «Confermato.», «In parte confermato.», «Precisazione:» o «Non confermato:» e poi spiega cosa dicono le fonti, con i dettagli utili allo studio (nomi corretti, date, numeri di articolo, percorsi di menu attuali). Non ripetere l'affermazione per intero. Vuoto se `non_verificabile`;
- `fonti`: 1–2 fonti che hai effettivamente aperto e che sostengono il testo, ciascuna con `titolo` (ente o produttore – titolo della pagina, es. «Autodesk Forma – Gestione delle autorizzazioni per le cartelle») e `url` esatto della pagina aperta. Non inventare URL e non costruirli a mano: solo indirizzi che hai visitato.

Affermazioni da verificare:
{verifiche}
