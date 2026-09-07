#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#ifndef BuildRoot
  #define BuildRoot "..\\dist\\VoxFlow"
#endif
#ifndef OutputRoot
  #define OutputRoot "..\\releases\\fase-0"
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
OutputBaseFilename=VoxFlow-{#MyAppVersion}-fase-0-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "autostart"; Description: "Iniciar o VoxFlow com o Windows"; GroupDescription: "Opções adicionais:"; Flags: checkedonce

[Files]
Source: "{#BuildRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VoxFlow"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\VoxFlow"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VoxFlow"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar VoxFlow"; Flags: nowait postinstall skipifsilent

