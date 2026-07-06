$ErrorActionPreference = "Stop"

$frontendDir = Split-Path -Parent $PSScriptRoot
$repoDir = Split-Path -Parent $frontendDir
$backendDir = Join-Path $repoDir "backend"

$runPy = Join-Path $backendDir "run.py"
$playerDir = Join-Path $backendDir "player"
$openlistDir = Join-Path $backendDir "openlist"
$staticDir = Join-Path $backendDir "static"
$distDir = Join-Path $frontendDir "backend-dist"
$workDir = Join-Path $frontendDir "backend-build"
$backendExe = Join-Path $distDir "MoviePopBackend.exe"

if (Test-Path $backendExe) {
  Remove-Item -LiteralPath $backendExe -Force
}

pyinstaller $runPy `
  --name MoviePopBackend `
  --clean `
  --onefile `
  --noconsole `
  --distpath $distDir `
  --workpath $workDir `
  --specpath $workDir `
  --add-data "$playerDir;player" `
  --add-data "$openlistDir;openlist" `
  --add-data "$staticDir;static" `
  --hidden-import player.modern_player `
  --hidden-import deep_translator `
  --hidden-import deep_translator.google

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
