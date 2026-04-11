; CorsaConnect Orchestrator (Admin) Installer — Inno Setup Script
;
; What it does:
;   1. Installs CorsaConnect-Admin.exe + frontend to Program Files
;   2. Preserves data in %APPDATA%\CorsaConnect (survives reinstall)
;   3. Opens firewall ports
;   4. Creates Desktop shortcut + Windows Startup entry
;   5. Provides clean uninstaller
;
; Build: iscc deploy/setup_orchestrator.iss

#define MyAppName "CorsaConnect Admin"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Ridge Racing"
#define MyAppExeName "CorsaConnect-Admin.exe"

[Setup]
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CorsaConnect\Admin
DefaultGroupName=CorsaConnect
OutputDir=build\installer
OutputBaseFilename=CorsaConnect-Admin-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallRestartComputer=no
SetupIconFile=deploy\ridge-link.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main executable
Source: "build\orchestrator\CorsaConnect-Admin.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\CorsaConnect Admin"; Filename: "{app}\{#MyAppExeName}"; Comment: "CorsaConnect Admin Dashboard"
Name: "{group}\CorsaConnect Admin"; Filename: "{app}\{#MyAppExeName}"
Name: "{userstartup}\CorsaConnect Admin"; Filename: "{app}\{#MyAppExeName}"; Comment: "Auto-start CorsaConnect Admin on login"

[Registry]
Root: HKCU; Subkey: "Software\CorsaConnect"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\CorsaConnect"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"
Root: HKCU; Subkey: "Software\CorsaConnect"; ValueType: string; ValueName: "Role"; ValueData: "admin"

[Run]
; Firewall rules
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect API"" dir=in action=allow protocol=TCP localport=8000"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect Heartbeat"" dir=in action=allow protocol=UDP localport=5001"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect AC UDP"" dir=in action=allow protocol=UDP localport=9600-9605"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect AC TCP"" dir=in action=allow protocol=TCP localport=9600-9605"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect AC HTTP"" dir=in action=allow protocol=TCP localport=8080-8085"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect Mumble"" dir=in action=allow protocol=TCP localport=64738"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect Mumble UDP"" dir=in action=allow protocol=UDP localport=64738"; Flags: runhidden
; Launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch CorsaConnect Admin now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect API"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect Heartbeat"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect AC UDP"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect AC TCP"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect AC HTTP"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect Mumble"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect Mumble UDP"""; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
