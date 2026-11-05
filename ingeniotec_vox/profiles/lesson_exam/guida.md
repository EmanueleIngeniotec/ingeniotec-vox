Corso: {corso}
Lezione: {lezione} – {titolo_lezione}
Nuovi file: «{dispensa}» e «{scheda}»

La **guida all'esame** del corso (sotto, descritta riga per riga) riassume l'esame e rimanda alle dispense di tutte le lezioni. Va aggiornata con la lezione {numero}, come è stato fatto a mano per le lezioni precedenti. Di solito servono:
1. nella tabella dei file («Come usare queste dispense» o simile): una riga per la dispensa nuova, nella posizione coerente con le altre, con una descrizione di una o due frasi dei contenuti; la riga delle schede di ripasso aggiornata con il numero della lezione;
2. i paragrafi che elencano le lezioni (es. quali sono pratiche, durata delle registrazioni) aggiornati, se la lezione vi rientra;
3. la parte sulla prova pratica: la riga della figura interessata nella tabella delle prove e un punto «Prova pratica del …» con la lezione e i minuti, come quelli già presenti, se la lezione spiega una prova;
4. il glossario degli acronimi: le sigle nuove usate nella lezione che mancano (non quelle già presenti);
5. una tabella «… in un colpo d'occhio (lezione {numero})» con le domande e risposte secche della lezione (8–15 righe), dopo l'ultima tabella dello stesso tipo.

Regole:
- Modifica solo ciò che serve per la lezione {numero}; non togliere né riscrivere il resto. Se la guida contiene già la lezione {numero} (righe, punti o tabella), non aggiungere doppioni: correggi o completa quello che c'è.
- Stesso tono, lunghezza e forma delle voci vicine (es. «(lezione 9, min. 0:03 e 2:51)», «Checklist nella dispensa L9.»). **Grassetto** solo dove le voci vicine lo usano.
- Usa solo informazioni della dispensa qui sotto (già verificate con le fonti): niente aggiunte esterne.
- I riferimenti sono gli id della descrizione: P… per i paragrafi, T… per le tabelle; le righe delle tabelle partono da r0 (intestazione).
- **Id e numeri di riga si riferiscono sempre alla guida com'è descritta qui sotto**, anche dopo le operazioni precedenti: le righe e i punti aggiunti non spostano la numerazione. Per inserire più righe di seguito usa lo stesso `riga` per tutte: vengono inserite nell'ordine dato.

Operazioni (`operazioni`, nell'ordine in cui vanno applicate), ciascuna con `op`, `dove` e `motivo` (una frase breve) e i campi indicati:
- `aggiungi_riga`: `dove` una tabella, `riga` l'indice della riga dopo cui inserire, `celle` i testi delle colonne;
- `modifica_cella`: `dove` una tabella, `riga`, `colonna` (da 0) e `testo` (il nuovo testo completo della cella);
- `riscrivi_paragrafo`: `dove` un paragrafo, `testo` il nuovo testo completo;
- `nuovo_punto`: `dove` un paragrafo dell'elenco puntato dopo cui inserire il nuovo punto (lo stile viene copiato da quello), `testo`;
- `nuova_tabella`: `dove` la tabella dopo cui inserire (titolo e stile vengono copiati da quella), `titolo`, `intestazione`, `righe`.

Guida attuale:
{guida}

Contenuto della dispensa della lezione {numero} (JSON) e scheda di ripasso:
{dispensa_json}
