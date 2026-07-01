[Setup]
AppName=Fingerprint Launcher
AppVersion=1.0.0
DefaultDirName={autopf}\Fingerprint Launcher
DefaultGroupName=Fingerprint Launcher
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\installer-dist
OutputBaseFilename=FingerprintLauncherSetup

[Files]
Source: "..\dist\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Fingerprint Launcher"; Filename: "{app}\FingerprintLauncher.exe"

[Run]
Filename: "{app}\FingerprintLauncher.exe"; Description: "Launch Fingerprint Launcher"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\schtasks.exe"; Parameters: "/Delete /TN FingerprintLauncher /F"; Flags: runhidden
