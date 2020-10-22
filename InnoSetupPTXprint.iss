; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

#define MyAppName "PTXprint"
#define MyAppVersion "1.2.9.5"
#define MyAppPublisher "SIL International"
#define MyAppURL "http://software.sil.org/"
#define MyAppExeName "PTXprint.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{8C357785-AE61-4E0E-80BE-C537715D914B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
;AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
DisableProgramGroupPage=yes
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
;PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=docs\inno-docs\MIT License.txt
InfoBeforeFile=docs\inno-docs\AboutPTXprint.txt
InfoAfterFile=docs\inno-docs\ReleaseNotes.txt
OutputBaseFilename=SetupPTXprint(1.2.9.5)
SetupIconFile=icon\Google-Noto-Emoji-Objects-62859-open-book.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\ptxprint\PTXprint.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ptxprint\ptxprint\gspawn-win64-helper.exe"; DestDir: "{app}"; Flags: ignoreversion
;Source: "python\scripts\diglotMerge.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\ptxprint\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "icons,locale,libcrypto-1_1-x64.dll,librsvg-2-2.dll,gspawn-win64-helper.exe"
Source: "dist\ptxprint\share\locale\es\*"; DestDir: "{app}\share\locale\es\"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\ptxprint\share\locale\fr\*"; DestDir: "{app}\share\locale\fr\"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\ptxprint\share\locale\zh_CN\*"; DestDir: "{app}\share\locale\zh_CN\"; Flags: ignoreversion recursesubdirs createallsubdirs
#include "AdwaitaIcons.txt"
Source: "dist\ptxprint\share\icons\Adwaita\index.theme"; DestDir: "{app}\share\icons\Adwaita"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
