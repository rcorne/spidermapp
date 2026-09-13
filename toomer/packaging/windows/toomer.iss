; Inno Setup script for the Toomer Windows installer.
;
; PyInstaller produces dist\Toomer\ — a folder holding Toomer.exe plus its
; dependencies. That folder is the *program*, not something you can hand
; someone: it has no shortcuts, no uninstaller, and copying it by hand is a
; poor first impression. This wraps it into a single Toomer-Setup-x.y.z.exe
; that installs to Program Files, adds Start Menu (and optional desktop)
; shortcuts, and registers a proper uninstaller in Apps & Features.
;
; Compiled by ISCC.exe on a Windows runner — see .github/workflows/build-toomer.yml.
; It cannot be compiled from macOS.

#define AppName "Toomer"
#define AppVersion "1.0.0"
#define AppPublisher "rcorne"
#define AppURL "https://github.com/rcorne/designsystem"
#define AppExeName "Toomer.exe"

[Setup]
; A stable GUID identifies the app across versions, so installing 2.1 over
; 2.0 upgrades in place instead of leaving two entries in Apps & Features.
AppId={{A4E27C51-8B3D-4F6A-9E12-5C7D0B9F3A61}
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
OutputBaseFilename=Toomer-Setup-{#AppVersion}
SetupIconFile=..\icon\Toomer.ico
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
Source: "..\..\dist\Toomer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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
