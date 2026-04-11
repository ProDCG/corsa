; CorsaConnect Sled Installer — Inno Setup Script
; Produces a professional Setup.exe for rig machines.
;
; What it does:
;   1. Installs CorsaConnect-Sled.exe to Program Files
;   2. Preserves config in %APPDATA%\CorsaConnect (survives reinstall)
;   3. Opens firewall ports (UDP 5001, TCP 5000, etc.)
;   4. Creates Desktop shortcut + Windows Startup entry
;   5. Provides clean uninstaller
;
; Build: iscc deploy/setup_sled.iss

#define MyAppName "CorsaConnect Sled"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Ridge Racing"
#define MyAppExeName "CorsaConnect-Sled.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\CorsaConnect\Sled
DefaultGroupName=CorsaConnect
OutputDir=build\installer
OutputBaseFilename=CorsaConnect-Sled-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; Keep config across reinstalls
UninstallRestartComputer=no
SetupIconFile=deploy\ridge-link.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Main executable
Source: "build\sled\CorsaConnect-Sled.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Desktop shortcut
Name: "{autodesktop}\CorsaConnect Sled"; Filename: "{app}\{#MyAppExeName}"; Comment: "CorsaConnect Rig Agent"
; Start menu
Name: "{group}\CorsaConnect Sled"; Filename: "{app}\{#MyAppExeName}"
; Startup folder (auto-launch on login)
Name: "{userstartup}\CorsaConnect Sled"; Filename: "{app}\{#MyAppExeName}"; Comment: "Auto-start CorsaConnect on login"

[Registry]
; Persist rig identity across reinstalls
Root: HKCU; Subkey: "Software\CorsaConnect"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\CorsaConnect"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"
Root: HKCU; Subkey: "Software\CorsaConnect"; ValueType: string; ValueName: "Role"; ValueData: "sled"

[Run]
; Firewall rules (silent)
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect Heartbeat"" dir=in action=allow protocol=UDP localport=5001"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect Command"" dir=in action=allow protocol=TCP localport=5000"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect API"" dir=in action=allow protocol=TCP localport=8000"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect AC UDP"" dir=in action=allow protocol=UDP localport=9600-9605"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect AC TCP"" dir=in action=allow protocol=TCP localport=9600-9605"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect AC HTTP"" dir=in action=allow protocol=TCP localport=8080-8085"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect Mumble"" dir=in action=allow protocol=TCP localport=64738"; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""CorsaConnect Mumble UDP"" dir=in action=allow protocol=UDP localport=64738"; Flags: runhidden
; Launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch CorsaConnect Sled now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Clean up firewall rules
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect Heartbeat"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect Command"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect API"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect AC UDP"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect AC TCP"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect AC HTTP"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect Mumble"""; Flags: runhidden
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""CorsaConnect Mumble UDP"""; Flags: runhidden

[UninstallDelete]
; Clean up install dir (but NOT AppData — config survives)
Type: filesandordirs; Name: "{app}"

[Code]
// Prompt user for config on first install (no existing AppData config)
var
  AdminIPPage: TInputQueryWizardPage;
  RigIDPage: TInputQueryWizardPage;

procedure InitializeWizard();
var
  AppDataDir: String;
  ConfigFile: String;
begin
  AppDataDir := ExpandConstant('{userappdata}\CorsaConnect');
  ConfigFile := AppDataDir + '\config.json';

  // Only show config pages if no existing config
  if not FileExists(ConfigFile) then
  begin
    AdminIPPage := CreateInputQueryPage(wpSelectDir,
      'Admin PC Connection',
      'Enter the Admin PC IP address',
      'The sled will connect to this IP to receive commands.');
    AdminIPPage.Add('Admin IP Address:', False);
    AdminIPPage.Values[0] := '192.168.9.119';

    RigIDPage := CreateInputQueryPage(AdminIPPage.ID,
      'Rig Identity',
      'Enter a name for this rig',
      'This identifier will show up on the Admin Dashboard.');
    RigIDPage.Add('Rig ID:', False);
    RigIDPage.Values[0] := GetComputerNameString();
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDataDir: String;
  ConfigFile: String;
  ConfigContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    AppDataDir := ExpandConstant('{userappdata}\CorsaConnect');
    ConfigFile := AppDataDir + '\config.json';

    // Only write config if we showed the config pages (first install)
    if not FileExists(ConfigFile) then
    begin
      ForceDirectories(AppDataDir);
      ConfigContent :=
        '{' + #13#10 +
        '    "orchestrator_ip": "' + AdminIPPage.Values[0] + '",' + #13#10 +
        '    "rig_id": "' + RigIDPage.Values[0] + '",' + #13#10 +
        '    "admin_shared_folder": "\\\\' + AdminIPPage.Values[0] + '\\RidgeContent",' + #13#10 +
        '    "local_ac_folder": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\assettocorsa",' + #13#10 +
        '    "ac_path": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\assettocorsa\\acs.exe"' + #13#10 +
        '}';
      SaveStringToFile(ConfigFile, ConfigContent, False);
    end;
  end;
end;
