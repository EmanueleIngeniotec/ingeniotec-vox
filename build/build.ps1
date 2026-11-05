# Build riproducibile di Vox -> dist\Vox\Vox.exe (GUI) e dist\Vox\vox_cli.exe (riga di comando)
# Prerequisiti: Python 3.13 x64 (py launcher). Crea .venv se manca.
# La prova di Fase 0 si costruisce ancora con: .venv\Scripts\pyinstaller build\vox_smoke.spec ...
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (-not (Test-Path .venv)) {
    py -3.13 -m venv .venv
    .venv\Scripts\python -m pip install --upgrade pip
}
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python build\make_icon.py
.venv\Scripts\pyinstaller build\vox.spec --noconfirm --clean --distpath dist --workpath build\_work
$dist = "dist\Vox"
# PyInstaller svuota dist\Vox: rimette i modelli.
# Whisper dalla cartella models\ del repository o dalla cache Hugging Face, se c'è.
$dst = "$dist\models\faster-whisper-large-v3"
$src = if (Test-Path "models\faster-whisper-large-v3\model.bin") { Get-Item "models\faster-whisper-large-v3" } else {
    Get-ChildItem "$env:USERPROFILE\.cache\huggingface\hub\models--Systran--faster-whisper-large-v3\snapshots" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1 }
if ($src) {
    New-Item -ItemType Directory -Force $dst | Out-Null
    Get-ChildItem $src.FullName -File | Where-Object Name -ne ".gitattributes" | Copy-Item -Destination $dst
    Write-Output "Modello Whisper copiato in $dst"
} else {
    Write-Output "Modello Whisper non trovato: l'exe lo scaricherà al primo uso"
}
# Voci (diarizzazione), ~40 MB
if (Test-Path "models\diarizzazione") {
    New-Item -ItemType Directory -Force "$dist\models\diarizzazione" | Out-Null
    Copy-Item "models\diarizzazione\*.onnx" "$dist\models\diarizzazione"
    Write-Output "Modello delle voci copiato"
}
Write-Output "Pronto: $root\$dist\Vox.exe"
