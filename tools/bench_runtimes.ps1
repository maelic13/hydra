<#
.SYNOPSIS
    Compare bench NPS across runtimes: CPython (pure), CPython+mypyc, PyPy.

.DESCRIPTION
    All three run the SAME source (behaviour-identical: bench fingerprint 1002645 (40-pos suite)),
    so this measures pure speed. Use it to decide which runtime to ship.

    CPU-HEAVY — do NOT run while an SPRT/SPSA is in progress (it competes for
    cores and skews both). Run it only when the machine is idle.

    PyPy is JIT-compiled: the first run is interpreted (cold), later runs are
    traced/compiled (warm). -Runs 2 reports the WARM run — representative of
    gameplay (a UCI engine warms up over a game). mypyc/CPython are ~flat.

    Prereqs: tools\engines\compiled (build via build_mypyc.ps1) and tools\pypy
    (downloaded PyPy 3.11).

.EXAMPLE
    .\tools\bench_runtimes.ps1 -Depth 10 -Runs 2
#>
param(
    [int]$Depth = 10,
    [int]$Runs = 2
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$cpy = Join-Path $repo ".venv\Scripts\python.exe"
$pypy = Join-Path $PSScriptRoot "pypy\pypy.exe"
$compiled = Join-Path $PSScriptRoot "engines\compiled"

function Measure-Bench([string]$Exe, [string]$Root, [string]$Label) {
    if (-not (Test-Path $Exe)) { Write-Host ("{0,-20} SKIP (missing {1})" -f $Label, $Exe); return }
    if (-not (Test-Path $Root)) { Write-Host ("{0,-20} SKIP (missing {1})" -f $Label, $Root); return }
    $out = ""
    Push-Location $Root
    try {
        for ($i = 0; $i -lt $Runs; $i++) { $out = "bench $Depth`nquit" | & $Exe -S -m hydra 2>&1 }
    } finally { Pop-Location }
    $text = $out -join "`n"
    $nodes = if ($text -match "Nodes searched\s*:\s*(\d+)") { $Matches[1] } else { "?" }
    $nps = if ($text -match "Nodes/second\s*:\s*(\d+)") { [int]$Matches[1] } else { 0 }
    Write-Host ("{0,-20} nodes={1,-8} nps={2,8:N0}" -f $Label, $nodes, $nps)
    return $nps
}

Write-Host "bench depth=$Depth, runs=$Runs (last = measured). All should report nodes=1002645+.`n"
$base = Measure-Bench $cpy $repo "CPython (pure)"
$myc  = Measure-Bench $cpy $compiled "CPython + mypyc"
$pp   = Measure-Bench $pypy $repo "PyPy (warm)"

Write-Host ""
if ($base -and $myc) { Write-Host ("mypyc speedup : {0:N2}x over CPython" -f ($myc / $base)) }
if ($base -and $pp)  { Write-Host ("PyPy speedup  : {0:N2}x over CPython" -f ($pp / $base)) }
