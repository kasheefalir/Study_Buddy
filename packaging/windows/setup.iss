[Setup]
AppId={{86F8EE1D-9481-4F48-B00C-316E34C96E08}
AppName=Study Buddy
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\Study Buddy
DefaultGroupName=Study Buddy
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installer
OutputBaseFilename=StudyBuddy-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
UninstallDisplayIcon={app}\StudyBuddy.exe

[Files]
Source: "..\..\dist\StudyBuddy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Study Buddy"; Filename: "{app}\StudyBuddy.exe"
Name: "{autodesktop}\Study Buddy"; Filename: "{app}\StudyBuddy.exe"

[Run]
Filename: "{app}\StudyBuddy.exe"; Description: "Open Study Buddy"; Flags: nowait postinstall skipifsilent
