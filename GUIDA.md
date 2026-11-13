# Ingeniotec Vox – Guida per chi lo usa

Vox prende una registrazione video (una call di Teams o una lezione online) e prepara i documenti in Word e PDF: il **report della call** oppure le **dispense della lezione**. Il video resta sul tuo PC; a Claude va solo il testo trascritto e qualche immagine.

## Cosa serve
| | |
|---|---|
| PC | Windows 10 o 11 a 64 bit, con **scheda video NVIDIA** e driver aggiornato |
| Programmi | **Microsoft Word** (per i PDF) |
| Account | Un account **Claude** (qualsiasi piano a pagamento) |
| Spazio | 5 GB per il programma, almeno 10 GB liberi per i lavori |
| Internet | Per collegare Claude e durante il lavoro (la trascrizione no) |

## Installazione
1. Avvia `Vox-<versione>-setup.exe`. Windows chiede il permesso di modificare il PC: rispondi **Sì** (se non hai i diritti, lo fa l'IT con le sue credenziali).
2. Se manca il driver NVIDIA o Word, il programma di installazione lo dice e spiega cosa fare. Puoi installare lo stesso e sistemare dopo.
3. Cartella proposta: `C:\Program Files\Ingeniotec Software\Vox` (in italiano compare come `C:\Programmi\…`). Va bene così.
4. L'installazione copia circa 4 GB: qualche minuto.
5. Alla fine lascia spuntato **«Installa Claude Code e collega l'account»** e premi **Fine**:
   - si apre una finestra blu che installa Claude Code (serve internet);
   - poi si apre il browser: accedi con il tuo account Claude e conferma;
   - quando la finestra blu scrive «Fatto: collegato come …», premi Invio per chiuderla.

Trovi **Vox** sul desktop e nel menu Start.

> Se l'installazione l'ha fatta l'IT con il proprio account, il passo 5 va rifatto da te: al primo avvio Vox mostra il pulsante **«Installa e collega Claude»**.

## Primo avvio
Vox controlla il PC (riquadro «Controllo del PC»):
- ✔ verde: tutto a posto;
- ✖ rosso: manca qualcosa, il messaggio dice cosa. Per Claude c'è il pulsante **«Installa e collega Claude»**; dopo aver sistemato, premi **«Ricontrolla»**.

Poi:
1. Scegli **Report di call** o **Dispense**.
2. Trascina il video nella finestra (o premi «Scegli…»).
3. Premi **Avvia**. Puoi usare il PC nel frattempo; il PC non va in sospensione finché il lavoro è in corso.
4. Alla fine: **Apri il report** / **Apri la dispensa**, oppure **Apri cartella**.

I risultati vanno in `Documenti\Ingeniotec Vox\` (si cambia da **Impostazioni → Cartella dei risultati**).

Tempi indicativi (misurati su questo tipo di PC): una call di 1 ora e mezza circa 20 minuti, una lezione di 3 ore e mezza circa 45–60 minuti.

## Problemi comuni
| Cosa vedi | Cosa fare |
|---|---|
| «Nessuna GPU NVIDIA rilevata» | Aggiorna il driver da nvidia.com/drivers (o chiedi all'IT) e riavvia il PC. Senza scheda NVIDIA Vox non funziona. |
| «Claude Code non è installato» / «non è collegato» | Premi **Installa e collega Claude**, segui la finestra blu e il browser, poi **Ricontrolla**. |
| La finestra blu dice «Download non riuscito» | Manca internet o un firewall blocca `claude.ai`: riprova da un'altra rete o chiedi all'IT. |
| «In attesa – limite Claude» nei lavori recenti | Hai esaurito l'uso di Claude per qualche ora (il messaggio dice quando si azzera). Più tardi premi **Riprendi**: il lavoro riparte da dove si era fermato. |
| Finestra «Limite d'uso di Claude» | L'account ha i crediti a pagamento (uso extra) e Vox si è fermato al 90% del limite per non consumarli. **Aspetta**: riprendi quando il limite si azzera, senza costi. **Continua a pagamento**: il lavoro prosegue subito e la parte oltre il limite viene addebitata sull'account. |
| Lavoro interrotto (PC spento, errore) | In **Lavori recenti** premi **Riprendi**. **Rifai da capo** solo se il risultato era sbagliato. |
| Nomi sbagliati nel report di una call | **Correggi nomi…**: scegli il nome giusto per ogni voce, Vox rifà il report. |
| Errore su Word o sul PDF | Chiudi le finestre di dialogo aperte in Word e premi **Riprendi**. |
| «Spazio libero insufficiente» | Libera spazio o scegli un'altra cartella dei risultati. |
| Avviso «È disponibile la versione …» | Prendi il nuovo `setup.exe` dalla cartella di rete aziendale dei programmi e installalo sopra: lavori e impostazioni restano. Il link «Novità» spiega cosa cambia. |

Qualcosa non va? **Impostazioni → Segnala un problema…** prepara la segnalazione con i dettagli tecnici (senza i contenuti del video). Serve un account GitHub; in alternativa scrivi a chi ti ha dato il programma e allega `vox.log` dalla cartella `_lavoro` del lavoro.

## Disinstallare
**Impostazioni di Windows → App → App installate → Ingeniotec Vox → Disinstalla.**
Restano, perché sono tuoi: i documenti in `Documenti\Ingeniotec Vox\`, le impostazioni di Vox e il registro errori (`%LOCALAPPDATA%\Ingeniotec Vox\`), e Claude Code (si toglie a parte, se non serve ad altro).
