; MetaKill — Inno Setup 6 installer script
; Build with: ISCC.exe metakill.iss

[Setup]
AppName=MetaKill
AppVersion=1.0
AppPublisher=MetaKill
AppComments=Deep metadata anonymizer for images and videos
DefaultDirName={autopf}\MetaKill
DefaultGroupName=MetaKill
OutputBaseFilename=MetaKill_Setup
OutputDir=dist
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\MetaKill.exe
SetupIconFile=icon.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\MetaKill\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MetaKill"; Filename: "{app}\MetaKill.exe"
Name: "{autodesktop}\MetaKill"; Filename: "{app}\MetaKill.exe"; \
  Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
  GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\MetaKill.exe"; \
  Description: "Launch MetaKill now"; \
  Flags: nowait postinstall skipifsilent
