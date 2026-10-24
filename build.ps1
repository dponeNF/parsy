param(
    [switch]$Clean,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Venv = Join-Path $Root ".venv-build"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Creating build environment..."
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        & py -3 -m venv $Venv
    } else {
        & python -m venv $Venv
    }
}

Write-Host "Installing build dependencies..."
& $Python -m pip install --disable-pip-version-check --upgrade pip wheel | Out-Host
& $Python -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements-desktop.txt") | Out-Host

if ($Clean) {
    Remove-Item -LiteralPath (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Root "dist") -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Building Parsy.exe..."
& $Python -m PyInstaller --noconfirm --clean (Join-Path $Root "Parsy.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed."
}

$Dist = Join-Path $Root "dist"
$AppDir = Join-Path $Dist "Parsy"
$Exe = Join-Path $AppDir "Parsy.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "Portable build was not created: $Exe"
}

$Zip = Join-Path $Dist "Parsy-Portable.zip"
if (Test-Path -LiteralPath $Zip) {
    Remove-Item -LiteralPath $Zip -Force
}
Write-Host "Creating portable archive..."
Compress-Archive -Path $AppDir -DestinationPath $Zip -CompressionLevel Optimal
Write-Host "Portable: $Zip"

if ($SkipInstaller) {
    Write-Host "Installer build skipped."
    exit 0
}

$IsccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    "C:\Program Files\Inno Setup 7\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Iscc) {
    Write-Warning "Inno Setup 6 was not found. Install it and run: ISCC.exe installer\Parsy.iss"
    exit 0
}

$Vendor = Join-Path $Root "vendor"
New-Item -ItemType Directory -Path $Vendor -Force | Out-Null
$WebViewInstaller = Join-Path $Vendor "MicrosoftEdgeWebView2Setup.exe"
if (-not (Test-Path -LiteralPath $WebViewInstaller)) {
    Write-Host "Downloading Microsoft Edge WebView2 bootstrapper..."
    $downloadUrl = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if ($curl) {
        & curl.exe -L --fail --retry 3 --retry-delay 2 --connect-timeout 20 -o $WebViewInstaller $downloadUrl
    }
    if (-not (Test-Path -LiteralPath $WebViewInstaller)) {
        Invoke-WebRequest -Uri $downloadUrl -OutFile $WebViewInstaller -UseBasicParsing
    }
    if (-not (Test-Path -LiteralPath $WebViewInstaller) -or
        (Get-Item -LiteralPath $WebViewInstaller).Length -lt 1MB) {
        throw "Failed to download the Microsoft Edge WebView2 bootstrapper."
    }
}

Write-Host "Building Windows installer..."
& $Iscc (Join-Path $Root "installer\Parsy.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed."
}

$Installer = Get-ChildItem -LiteralPath $Dist -Filter "Parsy-Setup-*.exe" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($Installer) {
    Write-Host "Installer: $($Installer.FullName)"
    $ChecksumTargets = @($Installer, (Get-Item -LiteralPath $Zip))
    $ChecksumLines = foreach ($Artifact in $ChecksumTargets) {
        $Hash = (Get-FileHash -LiteralPath $Artifact.FullName -Algorithm SHA256).Hash
        "$Hash  $($Artifact.Name)"
    }
    $Checksums = Join-Path $Dist "SHA256SUMS.txt"
    Set-Content -LiteralPath $Checksums -Value $ChecksumLines -Encoding ASCII
    Write-Host "Checksums: $Checksums"
}
