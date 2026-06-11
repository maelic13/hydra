<#
.SYNOPSIS
    SPRT self-play match between two ChessAgents engine scripts using fastchess.

.DESCRIPTION
    Wraps ChessAgents-protocol Python scripts with a UCI adapter so fastchess
    can run SPRT between them.  Two adapter modes:

      coldspawn  (default for final / deployment-realistic testing)
          Spawns a fresh Python process per move.  Cold-start cost included.
          Use this for final acceptance SPRT and timeout validation.
          Default TC: st=5.0 (deployment budget), concurrency=3.

      persistent (fast, for feature/eval comparisons)
          Loads the engine once; no cold-start per move.  Faster, so use
          for high-iteration comparisons (eval, ordering, search margins).
          Default TC: st=0.7, concurrency=2.
          The old st=0.5/concurrency=8 setting produced intermittent time
          forfeits on long Windows runs even though sequential adapter timing
          was under budget. Keep persistent SPRTs boring: zero time forfeits
          matters more than maximum games/hour.
          NOTE: cold-start is excluded — do NOT use for time-manager tuning.

    Fastchess and the opening book are reused from the basilisk toolchain:
      Fastchess: D:\code\basilisk\tools\bin\fastchess.exe
      Book:      D:\code\basilisk\tools\books\SuperGM_4mvs.pgn

.PARAMETER EngineA
    Path to the new/candidate engine script (.py).

.PARAMETER EngineB
    Path to the baseline engine script (.py).

.PARAMETER NameA / NameB
    Display names. Defaults: "New" / "Base".

.PARAMETER Mode
    "gainer"   -> H0: elo<=0,  H1: elo>=Elo1  (default; test a real gain).
    "simplify" -> H0: elo<=-5, H1: elo>=0      (non-regression / cleanup).

.PARAMETER Elo1
    Upper SPRT bound for "gainer" mode. Default 5 (nElo).

.PARAMETER FixedGames
    If set, run exactly this many games with NO SPRT stopping rule and report
    the Elo estimate ("tripwire" mode for the safe-feature queue). Elo0/Elo1
    are ignored. Example: -FixedGames 300  (~15 min at persistent c=8).

.PARAMETER Adapter
    "coldspawn" or "persistent". Default: "coldspawn".

.PARAMETER TC
    Seconds per move (fastchess st=X).
    Default: 5.0 for coldspawn, 0.7 for persistent.

.PARAMETER Concurrency
    Parallel games. Default: 3 for coldspawn, 8 for persistent.
    WARNING: for coldspawn keep this LOW (each game spawns 2 Python processes).

.PARAMETER FastchessPath
    Path to fastchess.exe. Default: D:\code\basilisk\tools\bin\fastchess.exe.

.PARAMETER BookPath
    Opening book PGN. Default: D:\code\basilisk\tools\books\SuperGM_4mvs.pgn.

.EXAMPLE
    # Final acceptance SPRT (cold-spawn, deployment TC)
    .\tools\sprt_lite.ps1 `
        -EngineA "hydra_lite\hydra_lite.py" `
        -EngineB "hydra_lite\hydra_lite_baseline.py" `
        -NameA "New" -NameB "Base"

.EXAMPLE
    # Fast eval-comparison SPRT (persistent, short TC)
    .\tools\sprt_lite.ps1 `
        -EngineA "hydra_lite\hydra_lite.py" `
        -EngineB "hydra_lite\hydra_lite_baseline.py" `
        -Adapter persistent -TC 0.7 -Concurrency 2

.EXAMPLE
    # Calibration check (self vs self, expect H0)
    .\tools\sprt_lite.ps1 `
        -EngineA "hydra_lite\hydra_lite_baseline.py" `
        -EngineB "hydra_lite\hydra_lite_baseline.py" `
        -NameA "Self" -NameB "Self2" -Elo0 -3 -Elo1 3
#>
param(
    [Parameter(Mandatory)][string]$EngineA,
    [Parameter(Mandatory)][string]$EngineB,
    [string]$NameA = "New",
    [string]$NameB = "Base",
    [ValidateSet("gainer", "simplify")][string]$Mode = "gainer",
    [Nullable[int]]$Elo0 = $null,
    [Nullable[int]]$Elo1 = $null,
    [Nullable[int]]$FixedGames = $null,
    [double]$Alpha = 0.05,
    [double]$Beta  = 0.05,
    [ValidateSet("coldspawn", "persistent")][string]$Adapter = "coldspawn",
    [Nullable[double]]$TC = $null,
    [Nullable[int]]$Concurrency = $null,
    [string]$FastchessPath = "D:\code\basilisk\tools\bin\fastchess.exe",
    [string]$BookPath = "D:\code\basilisk\tools\books\SuperGM_4mvs.pgn"
)

$ErrorActionPreference = "Stop"

# Resolve SPRT bounds.
if ($null -eq $Elo0) { $Elo0 = if ($Mode -eq "simplify") { -5 } else { 0 } }
if ($null -eq $Elo1) { $Elo1 = if ($Mode -eq "simplify") {  0 } else { 5 } }

# Adapter defaults.
$adapterScript = if ($Adapter -eq "coldspawn") { "tools\ca_uci_coldspawn.py" } `
                 else                           { "tools\ca_uci_persistent.py" }
if ($null -eq $TC)          { $TC          = if ($Adapter -eq "coldspawn") { 5.0 } else { 0.7 } }
if ($null -eq $Concurrency) { $Concurrency = if ($Adapter -eq "coldspawn") { 3   } else { 2   } }

# Locate fastchess.
if (-not (Test-Path $FastchessPath)) {
    $onPath = Get-Command fastchess -ErrorAction SilentlyContinue
    if ($onPath) { $FastchessPath = $onPath.Source }
    else { throw "fastchess not found at '$FastchessPath'. Reuse from D:\code\basilisk\tools\bin\ or run D:\code\basilisk\tools\setup_tools.ps1." }
}

foreach ($p in @($EngineA, $EngineB, $BookPath, $adapterScript)) {
    if (-not (Test-Path $p)) { throw "Not found: $p" }
}

$EngineA = (Resolve-Path $EngineA).Path
$EngineB = (Resolve-Path $EngineB).Path
$adapterScript = (Resolve-Path $adapterScript).Path

$resultsDir = Join-Path $PSScriptRoot "results"
New-Item -ItemType Directory -Force -Path $resultsDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$pgnOut = Join-Path $resultsDir "sprt_${NameA}_vs_${NameB}_${timestamp}.pgn"

$cmdA = "python `"$adapterScript`" --script `"$EngineA`" --name `"$NameA`""
$cmdB = "python `"$adapterScript`" --script `"$EngineB`" --name `"$NameB`""

Write-Host ""
Write-Host "======================================================="
if ($null -ne $FixedGames) {
    Write-Host "  TRIPWIRE (fixed $FixedGames games): $NameA  vs  $NameB"
    Write-Host "  Pass rule: score >= 47% -> bank it; below -> escalate to SPRT"
} else {
    Write-Host "  SPRT ($Mode): $NameA  vs  $NameB"
    Write-Host "  H0: elo<=$Elo0   H1: elo>=$Elo1   alpha=$Alpha  beta=$Beta"
}
Write-Host "  Adapter: $Adapter   TC: st=$TC s/move   Concurrency: $Concurrency"
Write-Host "  Book: $(Split-Path $BookPath -Leaf)"
Write-Host "  PGN: $pgnOut"
Write-Host "======================================================="
Write-Host ""

$commonArgs = @(
    "-engine", "cmd=$cmdA", "name=$NameA",
    "-engine", "cmd=$cmdB", "name=$NameB",
    "-each", "st=$TC",
    "-openings", "file=$BookPath", "format=pgn", "order=random",
    "-games", "2", "-repeat",
    "-concurrency", "$Concurrency",
    "-draw", "movenumber=40", "movecount=8", "score=10",
    "-resign", "movecount=3", "score=600", "twosided=true",
    "-pgnout", "file=$pgnOut",
    "-output", "format=fastchess"
)

if ($null -ne $FixedGames) {
    $rounds = [math]::Ceiling($FixedGames / 2)
    & $FastchessPath @commonArgs -rounds $rounds -ratinginterval 50
} else {
    & $FastchessPath @commonArgs -rounds 50000 `
        -sprt "elo0=$Elo0" "elo1=$Elo1" "alpha=$Alpha" "beta=$Beta" model=normalized
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "fastchess exited with code $LASTEXITCODE"
} else {
    Write-Host ""
    Write-Host "Match finished. PGN saved to: $pgnOut"
}
