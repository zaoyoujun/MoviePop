<#!
.SYNOPSIS
Build the MoviePop FastAPI backend into the executable bundled by Electron.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$DistPath = Join-Path $ProjectRoot 'backend-dist'
$WorkPath = Join-Path $ProjectRoot 'backend-build'
$PlayerRoot = Join-Path $PSScriptRoot 'player'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found: $Python. Run 'uv venv .venv' and 'uv pip install --python .venv\Scripts\python.exe -r backend\requirements.txt' first."
}

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $Uv) {
    throw "uv is required to install the isolated build dependency PyInstaller."
}

$MpvDll = if ($env:MPV_DLL_PATH) {
    Get-Item -LiteralPath $env:MPV_DLL_PATH -ErrorAction Stop
} else {
    Get-ChildItem -LiteralPath $PlayerRoot -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @('mpv-2.dll', 'libmpv-2.dll', 'mpv-1.dll') } |
        Select-Object -First 1
}

if ($null -eq $MpvDll) {
    throw "libmpv DLL not found. Place mpv-2.dll, libmpv-2.dll, or mpv-1.dll in $PlayerRoot, or set MPV_DLL_PATH to its absolute path."
}

& $Uv.Source pip install --python $Python pyinstaller 'PySide6-Essentials>=6.8,<7'
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to install PyInstaller or PySide6 into .venv.'
}

$PlayerData = @(
    @{ Source = (Join-Path $PlayerRoot 'qml'); Destination = 'backend\player\qml' },
    @{ Source = (Join-Path $PlayerRoot 'shaders'); Destination = 'backend\player\shaders' },
    @{ Source = (Join-Path $PlayerRoot 'vapoursynth'); Destination = 'backend\player\vapoursynth' }
)
foreach ($item in $PlayerData) {
    if (-not (Test-Path -LiteralPath $item.Source)) {
        throw "Required player resource is missing: $($item.Source)"
    }
}

$PyInstallerArguments = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--onefile',
    '--name', 'MoviePopBackend',
    '--paths', $ProjectRoot,
    '--distpath', $DistPath,
    '--workpath', $WorkPath,
    '--specpath', $WorkPath,
    '--collect-all', 'PySide6',
    '--hidden-import', 'backend.player.modern_player',
    '--hidden-import', 'backend.player.mpv',
    '--add-binary', "$($MpvDll.FullName);backend\player"
)
foreach ($item in $PlayerData) {
    $PyInstallerArguments += '--add-data', "$($item.Source);$($item.Destination)"
}
$PyInstallerArguments += (Join-Path $PSScriptRoot 'run.py')

& $Python @PyInstallerArguments

if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller failed to build MoviePopBackend.exe.'
}

$Executable = Join-Path $DistPath 'MoviePopBackend.exe'
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Build finished without producing $Executable."
}

Write-Host "Backend executable created: $Executable"
