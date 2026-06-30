<#
.SYNOPSIS
    Build a mypyc-compiled Hydra (fast release/benchmark engine) into an
    isolated, git-ignored directory, leaving the working tree pure Python.

.DESCRIPTION
    mypyc compiles the hot modules to C extensions (.pyd) for a large NPS win
    (~1.8x). The working tree MUST stay pure Python: the test suite monkeypatches
    engine internals (which compiled code bakes in), so tests only pass against
    .py. This script therefore:
      1. compiles the hot modules in place (so mypyc sees the real source),
      2. copies the package + the compiled .pyd + the shared __mypyc runtime into
         tools/engines/compiled/,
      3. cleans the .pyd back out of the working tree (restoring pure Python).

    uci / bench / syzygy stay pure Python (syzygy uses ctypes/Fathom — left
    uncompiled so the tablebase path is unaffected).

    Run the result with the launch shim:
        .\tools\run_hydra.cmd "<repo>\tools\engines\compiled"

.NOTES
    Requires mypy (pip install mypy) and a C compiler (MSVC / VS Build Tools).
    Output dir is git-ignored (tools/engines/, *.pyd).
#>
param(
    [string]$Dest = (Join-Path $PSScriptRoot "engines\compiled")
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$py = Join-Path $repo ".venv\Scripts\python.exe"
$pkg = Join-Path $repo "hydra"

# Hot modules to compile (uci/bench/syzygy/__init__/__main__ stay pure Python).
$modules = @(
    "types", "bitboard", "moves", "zobrist", "attacks",
    "transposition", "board", "movegen", "evaluation", "engine"
)

function Clear-Artifacts {
    Get-ChildItem -Path $pkg -Filter "*.pyd" -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -Path $repo -Filter "*__mypyc*.pyd" -ErrorAction SilentlyContinue | Remove-Item -Force
    Remove-Item -Recurse -Force (Join-Path $repo "build") -ErrorAction SilentlyContinue
}

Write-Host "[1/3] Compiling hot modules in place ..."
Clear-Artifacts
$srcArgs = $modules | ForEach-Object { "hydra\$_.py" }
Push-Location $repo
try {
    & $py -m mypyc @srcArgs
    if ($LASTEXITCODE -ne 0) { throw "mypyc build failed" }
} finally {
    Pop-Location
}

Write-Host "[2/3] Assembling compiled engine -> $Dest ..."
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Recurse -Force $pkg (Join-Path $Dest "hydra")          # .py + freshly built .pyd
Get-ChildItem -Path $repo -Filter "*__mypyc*.pyd" | Copy-Item -Destination $Dest -Force
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $Dest | Remove-Item -Recurse -Force

Write-Host "[3/3] Restoring pure-Python working tree ..."
Clear-Artifacts

$n = (Get-ChildItem -Path (Join-Path $Dest "hydra") -Filter "*.pyd").Count
Write-Host "Done. $n compiled modules in $Dest"
Write-Host "Run:   .\tools\run_hydra.cmd `"$Dest`""
Write-Host "Bench: `"bench 9`nquit`" | .\tools\run_hydra.cmd `"$Dest`""
