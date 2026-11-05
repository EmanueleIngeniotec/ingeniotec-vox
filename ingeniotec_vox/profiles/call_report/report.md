Riunione: {contesto}

Partecipanti visibili nel video: {partecipanti}

Cosa si vede nel video: {video}

La trascrizione è stata analizzata in {tot} parti; qui sotto trovi l'estratto di ciascuna (JSON). Componi il report finale, che avrà due documenti:

**Report (al massimo 2 pagine A4, per chi non era presente):** deve leggersi in tre minuti. I dettagli vanno nell'allegato, non qui.
- `titolo`: breve e specifico (progetto/cliente e tema), senza la data, al massimo 8 parole.
- `oggetto`: una frase sullo scopo della riunione.
- `sintesi`: 2–3 paragrafi, ciascuno di al massimo 60 parole: contesto, cosa si è chiarito, conseguenze principali. Non parlare della qualità della trascrizione o delle attribuzioni.
- `decisioni`: al massimo 8, ciascuna di al massimo 30 parole; unisci quelle sullo stesso tema.
- `azioni`: al massimo 10; `cosa` di al massimo 20 parole.
- `punti_aperti`: al massimo 6, ciascuno di al massimo 30 parole.
- Unisci i duplicati tra le parti e ordina per minuto. Se devi scegliere, tieni ciò che ha conseguenze su scopo, costi o tempi.
- `partecipanti`: nome e, se emerge dalla conversazione, ruolo o azienda (altrimenti stringa vuota). Includi chi interviene nella conversazione anche se non visibile nella griglia.

**Allegato (dettaglio):**
- `argomenti`: gli argomenti della riunione in ordine di tempo (unisci quelli spezzati tra due parti), ognuno con minuto di inizio e fine, una sintesi di 2–4 frasi e i punti salienti con i dettagli tecnici. Indicativamente 6–15 argomenti.
- `interventi`: per ogni persona con contributi attribuibili, i contributi principali con il minuto (al massimo 8 per persona, i più significativi).
- `termini`: glossario delle sigle e dei termini tecnici utili a capire il report, senza duplicati; il significato solo se certo.

Estratti delle parti:
{blocchi}
