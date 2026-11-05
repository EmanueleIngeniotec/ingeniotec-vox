# Ingeniotec Vox: installa Claude Code con l'installer ufficiale e collega l'account.
# Gira sempre come l'utente che userà Vox (Claude Code si installa per utente):
# lo lancia setup.exe ("come l'utente originale") oppure Vox al primo avvio.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File claude_setup.ps1
$ErrorActionPreference = "Continue"
try { $Host.UI.RawUI.WindowTitle = "Ingeniotec Vox - Claude Code" } catch {}

function Find-Claude {
    $c = Get-Command claude -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $p = Join-Path $env:USERPROFILE ".local\bin\claude.exe"
    if (Test-Path $p) { return $p }
    return $null
}

function Get-AuthStatus($exe) {
    try { return (& $exe auth status 2>$null | Out-String | ConvertFrom-Json) } catch { return $null }
}

function Stop-Here($code) {
    Write-Host ""
    Read-Host "Premi Invio per chiudere questa finestra" | Out-Null
    exit $code
}

Write-Host "Ingeniotec Vox - preparazione di Claude Code" -ForegroundColor Cyan
Write-Host ""

$exe = Find-Claude
if ($exe) {
    Write-Host "Claude Code è già installato: $exe"
} else {
    Write-Host "Installazione di Claude Code con l'installer ufficiale Anthropic (serve internet)..."
    try {
        Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    } catch {
        Write-Host "Download non riuscito: $($_.Exception.Message)" -ForegroundColor Red
    }
    $exe = Find-Claude
    if (-not $exe) {
        Write-Host ""
        Write-Host "Claude Code non risulta installato." -ForegroundColor Red
        Write-Host "Controlla la connessione a internet e riprova da Vox con «Installa e collega Claude»,"
        Write-Host "oppure chiedi all'IT di installarlo (https://claude.com/claude-code)."
        Stop-Here 1
    }
    Write-Host "Claude Code installato: $exe" -ForegroundColor Green
}

$st = Get-AuthStatus $exe
if ($st -and $st.loggedIn) {
    Write-Host "Account già collegato: $($st.email)" -ForegroundColor Green
    Stop-Here 0
}

Write-Host ""
Write-Host "Ora colleghiamo l'account Claude." -ForegroundColor Cyan
Write-Host "Si aprirà il browser: accedi con l'account aziendale e conferma."
Write-Host "Se il browser non si apre, copia nel browser l'indirizzo che compare qui sotto."
Write-Host ""
& $exe auth login

$st = Get-AuthStatus $exe
Write-Host ""
if ($st -and $st.loggedIn) {
    Write-Host "Fatto: collegato come $($st.email). Puoi chiudere questa finestra e usare Vox." -ForegroundColor Green
    Stop-Here 0
}
Write-Host "L'account non risulta collegato. Potrai farlo più tardi da Vox con «Installa e collega Claude»." -ForegroundColor Yellow
Stop-Here 2
