Riunione: {contesto}

Partecipanti letti nei riquadri: {partecipanti}

Cosa si vede nel video: {video}

L'audio della riunione è stato diviso in **voci** (V1, V2, … in ordine di tempo parlato) confrontando il timbro. Il raggruppamento non è perfetto: due persone con voce simile possono finire nella stessa voce, e una persona può essere divisa in più voci.

Per ogni voce, nella cartella di lavoro c'è un foglio `voci_fogli/voce_<voce>.jpg` con fino a 8 campioni, presi in momenti in cui parla solo quella voce. Ogni campione ha un'etichetta gialla (`V2 #3 · 0:51:30`: voce, numero del campione, minuto) e due immagini affiancate:
- a sinistra il fotogramma intero ridotto, con un rettangolo rosso attorno al riquadro che la piattaforma evidenziava in quel momento (il bordo colorato che indica chi sta parlando);
- a destra lo stesso riquadro ingrandito.

Chi registra la riunione non si riconosce dal video (il suo riquadro non viene evidenziato). Se la registrazione ha la traccia del solo microfono, la sua voce è separata e indicata come **voce di chi registra**: non ha campioni; dalle il nome indicato, oppure, se non è indicato, ricavalo dalle frasi solo se è chiaro (es. si presenta). Le altre voci sono di altre persone: se in un loro campione il riquadro evidenziato è quello di chi registra, lascia vuoto il nome di quel campione. Una voce indicata come **persona nella stanza di chi registra** si sente dal suo stesso microfono: è un'altra persona, non chi registra, e non ha campioni: ricava il nome dalle frasi solo se è chiaro (es. qualcuno la chiama per nome e lei risponde), altrimenti lascialo vuoto.

Voci e campioni:
{voci}

Compito:
1. Apri con lo strumento Read ogni foglio delle voci.
2. Per riconoscere le persone, apri anche i fotogrammi in cui si vede la griglia dei partecipanti con i nomi (fogli di anteprima `fogli/foglio_*.jpg`, fotogrammi a piena risoluzione `fotogrammi/<id>_*.jpg`; elenco: {fotogrammi}). Nei riquadri piccoli il nome spesso non è scritto: riconosci la persona dal volto, dagli abiti e dallo sfondo confrontandola con la griglia. Un riquadro con le sole iniziali (camera spenta) si riconosce dalle iniziali.
3. Per **ogni campione** di ogni voce indica in `campioni` il numero `n` e il `nome` della persona nel riquadro evidenziato, scritto esattamente come nell'elenco dei partecipanti. Lascia il nome vuoto se il riquadro non è riconoscibile o se il campione non mostra un riquadro di una persona. Valuta ogni campione da solo, senza uniformarlo agli altri della stessa voce: se una voce mostra persone diverse, deve risultare.
4. Per ogni voce indica anche `nome` (la persona prevalente nei campioni; per una voce senza campioni, solo se dalle frasi è chiaro chi parla, es. si presenta o risponde quando viene chiamato per nome), `certezza` (alta, media, bassa) e `motivo` (una frase: cosa hai visto).

Non inventare: se non sai chi è, lascia il nome vuoto.
