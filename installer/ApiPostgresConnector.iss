; Скрипт инсталлятора Inno Setup 6 для ApiPostgresConnector.
;
; Требуется Inno Setup 6: https://jrsoftware.org/isinfo.php
; Сборка:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\ApiPostgresConnector.iss
; (перед сборкой выполните: pyinstaller pyinstaller.spec)
;
; Номер версии берётся из src/version.py при подготовке файла сборщиком,
; здесь его нужно синхронизировать вручную.

#define AppName "ApiPostgresConnector"
#define AppVersion "2.1.0"
#define AppPublisher "ApiPostgresConnector"
#define AppExeName "ApiPostgresConnector.exe"

[Setup]
AppId={{7C3E1B0A-9D64-4F52-9A1E-2B4C8D5E6F70}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ApiPostgresConnector_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Права администратора — приложение пишет конфиг рядом с EXE
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительно:"

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    ConfigDir := ExpandConstant('{app}\config');
    if not DirExists(ConfigDir) then
      CreateDir(ConfigDir);
  end;
end;
