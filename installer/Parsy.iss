#define MyAppName "Parsy"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Parsy"
#define MyAppExeName "Parsy.exe"

[Setup]
AppId={{430557C9-5801-4534-A64A-24B655B0BE67}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Parsy-Setup-{#MyAppVersion}
SetupIconFile=..\assets\parsy.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
AppMutex=ParsyDesktopApp
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Parsy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\vendor\MicrosoftEdgeWebView2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not IsWebView2Installed

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: runhidden waituntilterminated; Check: not IsWebView2Installed
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2In(BaseDir: String): Boolean;
var
  FindRec: TFindRec;
begin
  Result := False;
  if not FindFirst(BaseDir + '\*', FindRec) then
    Exit;
  try
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
         FileExists(BaseDir + '\' + FindRec.Name + '\msedgewebview2.exe') then
      begin
        Result := True;
        Exit;
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

function IsWebView2Installed: Boolean;
begin
  Result :=
    HasWebView2In(ExpandConstant('{commonpf32}\Microsoft\EdgeWebView\Application')) or
    HasWebView2In(ExpandConstant('{commonpf}\Microsoft\EdgeWebView\Application')) or
    HasWebView2In(ExpandConstant('{localappdata}\Microsoft\EdgeWebView\Application'));
end;
