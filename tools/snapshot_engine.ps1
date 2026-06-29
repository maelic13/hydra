<#
.SYNOPSIS
    Freeze the current `hydra` package as a named baseline for A/B SPRT testing.

.DESCRIPTION
    Copies the working-tree `hydra/` package into tools/engines/<Name>/hydra so
    it can be run as a fixed opponent while you keep editing the working tree.
    Run via run_hydra.cmd with this snapshot dir as ENGINE_ROOT.

    tools/engines/ is git-ignored (regenerable, not source).

.EXAMPLE
    .\tools\snapshot_engine.ps1 -Name baseline
    # then: .\tools\sprt.ps1 -EngineB (Resolve-Path tools\engines\baseline)
#>
param(
    [Parameter(Mandatory = $true)][string]$Name
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$src  = Join-Path $repo "hydra"
$dest = Join-Path $PSScriptRoot "engines\$Name"

if (-not (Test-Path $src)) { throw "Source package not found: $src" }

if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force $src (Join-Path $dest "hydra")
# Drop bytecode so the snapshot is pristine source.
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $dest | Remove-Item -Recurse -Force

Write-Host "Snapshot '$Name' -> $dest"
Write-Host "Run it with:  .\tools\run_hydra.cmd `"$dest`""
