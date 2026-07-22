; FingerprintLauncher installer
; Build the application first with: python build.py
; Then compile this file with Inno Setup Compiler.

#define MyAppName "Fingerprint Launcher"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "dedovk"
#define MyAppExeName "FingerprintLauncher.exe"
#define MyAppId "{{923E8106-DDF7-4707-8945-16CAD6EAD1DD}"
#define MyAppDataDir "FingerprintLauncher"
#define MyRunValue "FingerprintLauncher"
#define MyLegacyTask "FingerprintLauncher"

[Setup]
; Keep this AppId unchanged between releases so upgrades and uninstall work.
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
OutputDir=..\installer-dist
OutputBaseFilename=FingerprintLauncher_Setup_{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
SolidCompression=yes
Compression=lzma2/ultra64
WizardStyle=modern dynamic windows11
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"

[CustomMessages]
english.DeleteUserData=Also delete your fingerprint actions and application settings?%n%nThis removes:%n{localappdata}\FingerprintLauncher
french.DeleteUserData=Supprimer également les actions d'empreinte et les paramètres de l'application ?%n%nCela supprime :%n{localappdata}\FingerprintLauncher
spanish.DeleteUserData=¿Eliminar también las acciones de huellas y la configuración de la aplicación?%n%nEsto elimina:%n{localappdata}\FingerprintLauncher
russian.DeleteUserData=Также удалить действия отпечатков и настройки приложения?%n%nБудет удалена папка:%n{localappdata}\FingerprintLauncher
ukrainian.DeleteUserData=Також видалити налаштовані дії пальців і параметри програми?%n%nБуде видалено:%n{localappdata}\FingerprintLauncher

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Package the Nuitka standalone output, but take assets from the repository so
; stale files in dist cannot omit newly added themes or icons.
Source: "..\dist\main.dist\*"; DestDir: "{app}"; Excludes: "assets\*"; Flags: ignoreversion recursesubdirs createallsubdirs
; Recursively includes icon.ico plus every SVG from all current and future
; theme directories.
Source: "..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; {app} is a dedicated application directory. This also removes files left by
; older standalone builds that were not registered in the current uninstall log.
Type: filesandordirs; Name: "{app}"

[Code]
var
  DeleteUserData: Boolean;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    { The application can remain hidden in the notification area. }
    Exec(
      ExpandConstant('{sys}\taskkill.exe'),
      '/F /IM "{#MyAppExeName}"',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    );

    { Remove the scheduled task used by older releases. A missing task is OK. }
    Exec(
      ExpandConstant('{sys}\schtasks.exe'),
      '/Delete /TN "{#MyLegacyTask}" /F',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    );

    { The application creates this value at runtime, so it is not tracked by }
    { Inno Setup's [Registry] section and must be removed explicitly. }
    RegDeleteValue(
      HKCU,
      'Software\Microsoft\Windows\CurrentVersion\Run',
      '{#MyRunValue}'
    );

    DeleteUserData :=
      MsgBox(ExpandConstant('{cm:DeleteUserData}'), mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2) = IDYES;
  end;

  if (CurUninstallStep = usPostUninstall) and DeleteUserData then
  begin
    DelTree(
      ExpandConstant('{localappdata}\{#MyAppDataDir}'),
      True,
      True,
      True
    );
  end;
end;
