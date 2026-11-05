# Genera tests/fixtures/sample_it.wav (~1 min di parlato italiano) con la sintesi vocale di Windows.
# Serve solo come input ripetibile per la prova di Fase 0; i file .wav non vanno in git.
Add-Type -AssemblyName System.Speech
$out = Join-Path $PSScriptRoot "sample_it.wav"
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$it = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "it-*" } | Select-Object -First 1
if ($it) { $s.SelectVoice($it.VoiceInfo.Name) } else { Write-Warning "Nessuna voce italiana installata: uso la voce predefinita." }
$s.SetOutputToWaveFile($out)
$s.Speak(@"
Buongiorno a tutti e benvenuti alla riunione di avanzamento del progetto.
Oggi parliamo di tre argomenti: lo stato della progettazione BIM, il calendario delle consegne e la gestione delle revisioni.
Per quanto riguarda il modello architettonico, il coordinamento con le strutture è quasi completato.
Restano da risolvere alcune interferenze tra le travi del secondo piano e i canali dell'impianto di ventilazione.
Marco si occuperà di aggiornare il modello entro venerdì prossimo.
Sul calendario, la consegna del progetto esecutivo resta fissata alla fine di novembre.
Infine, abbiamo deciso che tutte le revisioni passeranno dall'ambiente di condivisione dei dati, con una nomenclatura dei file comune.
Ci aggiorniamo la prossima settimana per verificare le interferenze. Grazie a tutti.
"@)
$s.Dispose()
Write-Output "Creato $out"
