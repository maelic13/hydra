<#
.SYNOPSIS
    Run a fastchess SPRT (or fixed-games match) between two Hydra source trees.

.DESCRIPTION
    EngineA = candidate (defaults to the working-tree repo root).
    EngineB = baseline  (defaults to the repo root too -> calibration / self-play).
    For a real gain test, freeze a baseline first:
        .\tools\snapshot_engine.ps1 -Name baseline
        .\tools\sprt.ps1 -EngineB (Resolve-Path tools\engines\baseline)

    Both engines launch via run_hydra.cmd (python -S isolation, see that file).
    The default gate is the plan's clock TC 8+0.08, elo0=0 elo1=5, a=b=0.05.

    NOTE (workflow rule): the dev agent never runs this. The user runs it and
    reports the result line back.

.EXAMPLE
    # Calibration — must accept H0 (~0 Elo, zero forfeits):
    .\tools\sprt.ps1 -Elo0 -3 -Elo1 3 -NameA S1 -NameB S2
#>
param(
    [string]$EngineA = (Split-Path $PSScriptRoot -Parent),
    [string]$EngineB = (Split-Path $PSScriptRoot -Parent),
    [string]$NameA = "A",
    [string]$NameB = "B",
    [string]$TC = "8+0.08",
    [int]$Concurrency = 8,
    [int]$Hash = 64,
    [int]$MoveOverhead = 50,
    [int]$Elo0 = 0,
    [int]$Elo1 = 5,
    [double]$Alpha = 0.05,
    [double]$Beta = 0.05,
    [int]$Rounds = 100000,
    [int]$FixedGames = 0,                      # >0 -> fixed N games instead of SPRT
    [string]$Book = (Join-Path $PSScriptRoot "book\openings.epd"),
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$fastchess = Join-Path $PSScriptRoot "bin\fastchess.exe"
$shim      = Join-Path $PSScriptRoot "run_hydra.cmd"
$resultDir = Join-Path $PSScriptRoot "results"

foreach ($p in @($fastchess, $shim)) {
    if (-not (Test-Path $p)) { throw "Missing required file: $p (run Phase 0 setup)" }
}
if (-not (Test-Path $Book)) { throw "Opening book not found: $Book (build it with tools\build_book.py)" }
if (-not (Test-Path $resultDir)) { New-Item -ItemType Directory -Force -Path $resultDir | Out-Null }

$EngineA = (Resolve-Path $EngineA).Path
$EngineB = (Resolve-Path $EngineB).Path
if ($Output -eq "") {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $Output = Join-Path $resultDir "${NameA}_vs_${NameB}_$stamp.pgn"
}

$args = @(
    "-engine", "name=$NameA", "cmd=$shim", "args=$EngineA",
    "-engine", "name=$NameB", "cmd=$shim", "args=$EngineB",
    "-each", "proto=uci", "tc=$TC", "option.Hash=$Hash", "option.Move Overhead=$MoveOverhead",
    "-openings", "file=$Book", "format=epd", "order=random",
    "-games", "2", "-repeat", "-concurrency", "$Concurrency",
    "-ratinginterval", "10", "-pgnout", "file=$Output"
)
if ($FixedGames -gt 0) {
    $args += @("-rounds", "$([math]::Ceiling($FixedGames / 2.0))")
} else {
    $args += @("-rounds", "$Rounds",
               "-sprt", "elo0=$Elo0", "elo1=$Elo1", "alpha=$Alpha", "beta=$Beta", "model=normalized")
}

Write-Host "A (candidate): $EngineA"
Write-Host "B (baseline) : $EngineB"
Write-Host "TC=$TC  Hash=$Hash  Concurrency=$Concurrency  Book=$(Split-Path $Book -Leaf)"
if ($FixedGames -gt 0) { Write-Host "Mode: fixed $FixedGames games" }
else { Write-Host "Mode: SPRT elo0=$Elo0 elo1=$Elo1 a=$Alpha b=$Beta" }
Write-Host ("-" * 70)

& $fastchess @args

Write-Host ("-" * 70)
Write-Host "PGN: $Output"
Write-Host "Report back: games / score% / elo+-err / LOS / sprt verdict / timeouts / crashes."
