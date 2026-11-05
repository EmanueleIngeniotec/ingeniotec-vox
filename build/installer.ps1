# setup.exe di Vox da dist\Vox\ (prima build\build.ps1) -> dist\installer\Vox-<versione>-setup.exe
# Prerequisito: Inno Setup 6 (winget install JRSoftware.InnoSetup).
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
if (-not (Test-Path "dist\Vox\Vox.exe")) { throw "Manca dist\Vox\Vox.exe: eseguire prima build\build.ps1" }
$version = (Select-String -Path "ingeniotec_vox\__init__.py" -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 non trovato (winget install JRSoftware.InnoSetup)" }
& $iscc /Q "/DAppVersion=$version" "build\vox_setup.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC uscito con codice $LASTEXITCODE" }
Get-ChildItem "dist\installer\Vox-$version-setup*" | ForEach-Object { "{0}  {1:N2} GB" -f $_.FullName, ($_.Length / 1GB) }
