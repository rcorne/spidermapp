; Inno Setup script for the Pidge Windows installer.
;
; PyInstaller produces dist\Pidge\ — a folder holding Pidge.exe plus its
; dependencies. That folder is the *program*, not something you can hand
; someone: it has no shortcuts, no uninstaller, and copying it by hand is a
; poor first impression. This wraps it into a single Pidge-Setup-x.y.z.exe
; that installs to Program Files, adds Start Menu (and optional desktop)
; shortcuts, and registers a proper uninstaller in Apps & Features.
;
; Compiled by ISCC.exe on a Windows runner — see .github/workflows/build.yml.
; It cannot be compiled from macOS.

#define AppName "Pidge"
#define AppVersion "2.0.0"
#define AppPublisher "rcorne"
#define AppURL "https://github.com/rcorne/spidermapp"
#define AppExeName "Pidge.exe"

[Setup]
; A stable GUID identifies the app across versions, so installing 2.1 over
; 2.0 upgrades in place instead of leaving two entries in Apps & Features.
AppId={{7B3C1E92-4D5A-4F18-9C6E-2A8F5D3B7E14}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\installer
OutputBaseFilename=Pidge-Setup-{#AppVersion}
SetupIconFile=..\icon\Pidge.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; PyInstaller builds a 64-bit binary, so refuse to install on 32-bit Windows
; rather than installing something that can't run. Spelled "x64" rather than
; the newer "x64compatible" because that alias only exists in Inno Setup 6.3+
; and this has to compile on whatever version the CI runner ships.
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
; Let the user install without admin rights (into their own profile) if they
; prefer — the wizard asks rather than hard-failing on a locked-down machine.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The whole PyInstaller output folder, recursively.
Source: "..\..\dist\Pidge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; PyInstaller and Qt drop caches next to the binary at runtime; without this
; the uninstall leaves an orphaned folder behind.
Type: filesandordirs; Name: "{app}"
