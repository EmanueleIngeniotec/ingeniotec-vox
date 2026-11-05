; Inno Setup – setup.exe di Ingeniotec Vox (Fase 6), costruito da build\installer.ps1 su dist\Vox\.
; Requisiti in ARCHITETTURA.md, «Installazione (decisa il 28/10)».
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Ingeniotec Vox"
#define RepoUrl "https://github.com/EmanueleIngeniotec/ingeniotec-vox"
#define ClaudeScript "{app}\_internal\ingeniotec_vox\core\claude_setup.ps1"

[Setup]
AppId={{6F1B8C2E-5A41-4D7B-9E3C-2B7A1D4F8E90}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Ingeniotec
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Ingeniotec Software\Vox
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=..\assets\vox.ico
UninstallDisplayIcon={app}\Vox.exe
UninstallDisplayName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=Vox-{#AppVersion}-setup
; i modelli (3 GB) si comprimono poco: compressione veloce, a blocchi, in un processo separato
Compression=lzma2/fast
SolidCompression=no
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=8
CloseApplications=yes

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Collegamento sul desktop"; GroupDescription: "Collegamenti:"

[InstallDelete]
; aggiornamento: via le librerie della versione precedente, i modelli restano sovrascritti dai nuovi
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Vox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Vox"; Filename: "{app}\Vox.exe"; Comment: "Report di call e dispense da registrazioni video"
Name: "{autodesktop}\Vox"; Filename: "{app}\Vox.exe"; Tasks: desktopicon; Comment: "Report di call e dispense da registrazioni video"

[Run]
; Claude Code si installa per utente: gira come l'utente che ha avviato setup.exe, non come
; l'amministratore. Se l'installazione la fa l'IT con il proprio account, Vox ripropone il passo
; al primo avvio («Installa e collega Claude»).
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{#ClaudeScript}"""; \
  Description: "Installa Claude Code e collega l'account (serve internet)"; \
  Flags: postinstall runasoriginaluser skipifsilent
Filename: "{app}\Vox.exe"; Description: "Avvia Vox"; Flags: postinstall runasoriginaluser nowait skipifsilent

[Code]
function HasNvidiaDriver(): Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\nvidia-smi.exe'))
    or RegKeyExists(HKLM, 'SYSTEM\CurrentControlSet\Services\nvlddmkm');
end;

function HasWord(): Boolean;
begin
  Result := RegKeyExists(HKCR, 'Word.Application\CLSID')
    or RegKeyExists(HKCR64, 'Word.Application\CLSID');
end;

function InitializeSetup(): Boolean;
var
  Missing: String;
begin
  Result := True;
  Missing := '';
  if not HasNvidiaDriver() then
    Missing := Missing + #13#10 + '• Driver della scheda video NVIDIA: non trovato.' + #13#10 +
      '   Vox trascrive con una GPU NVIDIA. Installa il driver da nvidia.com/drivers' + #13#10 +
      '   (o chiedi all''IT); senza GPU NVIDIA Vox non può funzionare.' + #13#10;
  if not HasWord() then
    Missing := Missing + #13#10 + '• Microsoft Word: non trovato.' + #13#10 +
      '   Serve per creare i PDF. Installa Microsoft 365 / Office (o chiedi all''IT).' + #13#10;
  if Missing <> '' then
    Result := SuppressibleMsgBox('Su questo PC manca qualcosa che serve a Vox:' + #13#10 + Missing + #13#10 +
      'Puoi installare Vox lo stesso e sistemare dopo: Vox ricontrolla tutto a ogni avvio.' + #13#10 + #13#10 +
      'Continuare con l''installazione?', mbConfirmation, MB_YESNO, IDYES) = IDYES;
end;
