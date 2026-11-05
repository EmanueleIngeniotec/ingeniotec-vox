Riunione: {contesto}

Scegli le schermate da inserire nell'allegato del report. Nella cartella di lavoro ci sono i fogli di anteprima (`fogli/foglio_*.jpg`, 12 miniature ciascuno con id e minuto in alto a sinistra) e i fotogrammi a piena risoluzione (`fotogrammi/<id>_*.jpg`).

Argomenti dell'allegato (titolo, inizio–fine):
{argomenti}

Fotogrammi disponibili (id, minuto): {fotogrammi}

Compito:
1. Guarda tutti i fogli di anteprima con lo strumento Read.
2. Scegli al massimo {max} fotogrammi utili a capire la discussione: disegni, tavole, documenti, tabelle o slide condivise mentre se ne parla. Preferisci il contenuto condiviso alla griglia dei volti (al massimo una griglia, solo se non c'è altro). Evita fotogrammi quasi uguali tra loro, schermi neri o di transizione, caselle di posta e finestre non pertinenti.
3. Per ciascuno apri il fotogramma a piena risoluzione e indica:
   - `argomento`: il titolo esatto dell'argomento a cui si riferisce (dall'elenco sopra), in base al minuto;
   - `didascalia`: una frase che dice cosa mostra la schermata e perché è rilevante (es. "Planimetria del sito con il percorso delle tubazioni principali"), senza inventare dettagli che non si vedono;
   - `ritaglio`: [x0, y0, x1, y1] in frazioni dell'immagine (0–1) che tengono solo il contenuto condiviso, togliendo barre di Teams, menu del programma e riquadri dei partecipanti; [0, 0, 1, 1] per tenere tutto.

Ordina le schermate per minuto.
