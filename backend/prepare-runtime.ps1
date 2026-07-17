<#
.SYNOPSIS
Downloads the Windows-only runtime files required for MoviePop packaging.

The files live in a GitHub Release because both are larger than GitHub's
regular Git single-file limit. Existing local files are never replaced.
#>

[CmdletBinding()]
param(
    [string]$Repository = $(if ($env:MOVIEPOP_RUNTIME_REPOSITORY) { $env:MOVIEPOP_RUNTIME_REPOSITORY } else { 'ZHTodd223/MoviePop' }),
    [string]$Tag = $(if ($env:MOVIEPOP_RUNTIME_TAG) { $env:MOVIEPOP_RUNTIME_TAG } else { 'runtime-dependencies-v1' })
)

$ErrorActionPreference = 'Stop'
$Targets = @(
    @{ Asset = 'libmpv-2.dll'; Destination = (Join-Path $PSScriptRoot 'player\libmpv-2.dll') },
    @{ Asset = 'openlist.exe'; Destination = (Join-Path $PSScriptRoot 'openlist\openlist.exe') }
)

$missing = @($Targets | Where-Object { -not (Test-Path -LiteralPath $_.Destination) })
if ($missing.Count -eq 0) {
    Write-Host 'Bundled runtime files are already available.'
    exit 0
}

$headers = @{ 'User-Agent' = 'MoviePop-runtime-bootstrap' }
$release = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$Repository/releases/tags/$Tag"

foreach ($target in $missing) {
    $asset = $release.assets | Where-Object { $_.name -eq $target.Asset } | Select-Object -First 1
    if ($null -eq $asset) {
        throw "Release $Repository@$Tag does not contain $($target.Asset)."
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target.Destination) | Out-Null
    Write-Host "Downloading $($target.Asset) from $Repository@$Tag"
    Invoke-WebRequest -Headers $headers -Uri $asset.browser_download_url -OutFile $target.Destination
}
