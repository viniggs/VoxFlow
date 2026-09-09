#ifndef MyAppVersion
  #define MyAppVersion "0.8.2"
#endif
#ifndef BuildRoot
  #define BuildRoot "..\\dist\\VoxFlow"
#endif
#ifndef MyAppPhase
  #define MyAppPhase "4.5"
#endif
#ifndef OutputRoot
  #define OutputRoot "..\\releases\\fase-" + MyAppPhase
#endif

#define MyAppName "VoxFlow"
#define MyAppPublisher "Vini"
#define MyAppExeName "VoxFlow.exe"

[Setup]
AppId={{5B592C8E-01CF-4AFE-97E5-5E91A7C7759D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#OutputRoot}
OutputBaseFilename=VoxFlow-{#MyAppVersion}-fase-{#MyAppPhase}-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icon.ico
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "autostart"; Description: "Iniciar o VoxFlow com o Windows"; GroupDescription: "Opções adicionais:"; Flags: checkedonce

[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Remove ICU 78 accidentally shipped by the previous Phase 1 installer. Qt 6
; must resolve Windows' system ICU compatibility DLL instead.
Type: files; Name: "{app}\_internal\icuuc.dll"
Type: files; Name: "{app}\_internal\icudt78.dll"

[Icons]
Name: "{group}\VoxFlow"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Encerrar VoxFlow"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--quit"
Name: "{userdesktop}\VoxFlow"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VoxFlow"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar VoxFlow"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingExe: String;
  ResultCode: Integer;
begin
  Result := '';
  ExistingExe := ExpandConstant('{app}\VoxFlow.exe');
  if FileExists(ExistingExe) then
  begin
    Exec(ExistingExe, '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(750);
  end;
end;
