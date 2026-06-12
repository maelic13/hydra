"""Validation suite for hydra_lite/hydra_lite.py (ChessAgents Open submission).

Run:
    pytest tests/test_lite_agent.py -q

Tests cover:
  - Syntax (py_compile)
  - File size < SIZE_LIMIT bytes
  - No forbidden API patterns
  - Spot-check: all tested book moves are legal in their positions
  - Legal move output for a variety of positions
  - History replay / repetition table consistency
  - Promotion output format (e7e8q style)
  - Wall-time under WALL_LIMIT_S per move (subprocess path, includes cold-start)
  - Perft node counts vs known values (A2 guardrail: proves move-gen correctness)
  - Eval determinism after make+unmake (prerequisite for A1)
  - Incremental score equivalence (A1 guardrail: auto-activates when p.score exists)
"""

import importlib.util
import py_compile
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ENGINE = REPO_ROOT / "hydra_lite" / "hydra_lite.py"

SIZE_LIMIT = 50_000        # bytes — Open section cap
WALL_LIMIT_S = 5.5         # platform is 5.0 s; allow 0.5 s overhead for process launch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_engine():
    """Load the engine script as a module without running main()."""
    spec = importlib.util.spec_from_file_location("hydra_lite_mod", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_subprocess(line: str, timeout: float = WALL_LIMIT_S + 0.5) -> tuple[str, float]:
    """Cold-spawn the engine, return (move_str, elapsed_s)."""
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(ENGINE)],
        input=line + "\n",
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip(), time.perf_counter() - t0


def _legal_set(mod, line: str) -> set[str]:
    p, rep, hist = mod.build(line)
    return {mod.uci(m) for m in mod.legal(p)}


# ---------------------------------------------------------------------------
# Static checks (fast, no subprocess)
# ---------------------------------------------------------------------------

def test_syntax():
    py_compile.compile(str(ENGINE), doraise=True)


def test_size_under_limit():
    size = ENGINE.stat().st_size
    assert size < SIZE_LIMIT, (
        f"File is {size} bytes — exceeds Open-section cap of {SIZE_LIMIT} bytes"
    )


def test_no_forbidden_apis():
    src = ENGINE.read_text()
    forbidden = [
        "subprocess", "socket.", "urllib", "requests",
        "http.client", "os.system", "os.popen", "pathlib",
        "__import__(",
    ]
    for token in forbidden:
        assert token not in src, f"Forbidden API found: '{token}'"


# ---------------------------------------------------------------------------
# Book validator (in-process, fast)
# ---------------------------------------------------------------------------

def _book_data(mod):
    """Extract book()'s opening dict B and line block L from the engine source.

    They are function-locals, so pull them out of the AST rather than poking
    at runtime internals. literal_eval keeps this purely mechanical.
    """
    import ast
    tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
    B = L = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "book":
            for st in ast.walk(node):
                if isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name):
                    if st.targets[0].id == "B":
                        B = ast.literal_eval(st.value)
                    elif st.targets[0].id == "L":
                        L = ast.literal_eval(st.value)
    assert B is not None and L is not None, "could not extract B/L from book()"
    return B, [ln.split() for ln in L.splitlines() if ln.strip()]


def _replay_moves(mod, moves, ctx):
    """Replay a UCI move sequence from startpos; fail on the first illegal ply."""
    p, _, _ = mod.build(START_FEN)
    for ply, s in enumerate(moves):
        m = mod.parseuci(p, s)
        assert m is not None, f"{ctx}: move {ply+1} '{s}' illegal after {moves[:ply]}"
        mod.make(p, m)
    return p


def test_book_every_line_replays_legally():
    """P6 gate: every ply of every line in the book's line block must be legal."""
    mod = _load_engine()
    _, lines = _book_data(mod)
    for n, line in enumerate(lines):
        _replay_moves(mod, line, f"L[{n}]")


def test_book_dict_entries_legal():
    """Every dict key must replay legally and every candidate reply must be legal."""
    mod = _load_engine()
    B, _ = _book_data(mod)
    for key, vals in B.items():
        p = _replay_moves(mod, list(key), f"B key {key}")
        for s in vals:
            assert mod.parseuci(p, s) is not None, f"B[{key}]: reply '{s}' illegal"


def test_book_ply_matches_longest_line():
    """BOOK_PLY must cover the longest book line (no dead plies, no overshoot)."""
    mod = _load_engine()
    _, lines = _book_data(mod)
    assert max(len(l) for l in lines) == mod.BOOK_PLY


@pytest.mark.parametrize("moves", [
    [],
    ["e2e4"],
    ["e2e4", "e7e5"],
    ["e2e4", "e7e5", "g1f3"],
    ["e2e4", "e7e5", "g1f3", "b8c6"],
    ["e2e4", "c7c5"],
    ["d2d4"],
    ["d2d4", "d7d5"],
    ["d2d4", "d7d5", "c2c4"],
    ["d2d4", "g8f6"],
    ["d2d4", "g8f6", "c2c4"],
    ["g1f3"],
    ["g1f3", "d7d5"],
    ["c2c4"],
])
def test_book_move_legal(moves):
    mod = _load_engine()
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    line = start + (" moves " + " ".join(moves) if moves else "")
    legal = _legal_set(mod, line)
    p, rep, hist = mod.build(line)
    bm = mod.book(p, hist)
    if bm is None:
        pytest.skip(f"No book move for {moves}")
    assert mod.uci(bm) in legal, (
        f"Book move '{mod.uci(bm)}' not legal after {moves}. Legal: {sorted(legal)}"
    )


# ---------------------------------------------------------------------------
# Protocol compliance (subprocess path — includes cold-start)
# ---------------------------------------------------------------------------

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.mark.parametrize("fen", [
    START_FEN,
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",  # endgame
])
def test_returns_legal_move(fen):
    mod = _load_engine()
    legal = _legal_set(mod, fen)
    assert legal, f"No legal moves in test position {fen}"
    move, elapsed = _run_subprocess(fen)
    assert move in legal, f"'{move}' not in {sorted(legal)}"
    assert elapsed < WALL_LIMIT_S, f"Took {elapsed:.2f}s (limit {WALL_LIMIT_S}s)"


def test_history_line_legal_move():
    """Engine parses 'moves' history and returns a legal move."""
    line = (
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        " moves e2e4 e7e5"
    )
    mod = _load_engine()
    legal = _legal_set(mod, line)
    move, elapsed = _run_subprocess(line)
    assert move in legal
    assert elapsed < WALL_LIMIT_S


def test_long_history_legal_move():
    """Engine handles a longer game history without error."""
    line = (
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq - 0 6"
        " moves e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 b1c3 g8f6 d2d3"
    )
    mod = _load_engine()
    legal = _legal_set(mod, line)
    move, elapsed = _run_subprocess(line)
    assert move in legal
    assert elapsed < WALL_LIMIT_S


def test_promotion_format():
    """Promotion move must use 5-char format: srcdestp (e.g. a7a8q)."""
    # Pawn on a7, kings far apart — a7a8 is unblocked.
    fen = "8/P7/8/8/8/8/8/K6k w - - 0 1"
    mod = _load_engine()
    legal = _legal_set(mod, fen)
    # Should have queen/rook/bishop/knight promotion moves
    promo_moves = [m for m in legal if len(m) == 5]
    assert promo_moves, f"Expected promotion moves, got: {sorted(legal)}"

    move, elapsed = _run_subprocess(fen)
    assert move in legal, f"'{move}' not legal. Legal: {sorted(legal)}"
    if len(move) == 5:
        assert move[4] in "qrbn", f"Invalid promotion piece in '{move}'"
    assert elapsed < WALL_LIMIT_S


def test_castling_legal():
    """Engine can produce castling moves (O-O = e1g1)."""
    fen = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    mod = _load_engine()
    legal = _legal_set(mod, fen)
    # Castling should be legal here
    assert "e1g1" in legal, f"O-O expected. Legal: {sorted(legal)}"
    move, elapsed = _run_subprocess(fen)
    assert move in legal
    assert elapsed < WALL_LIMIT_S


@pytest.mark.parametrize("fen,best", [
    # Back-rank mate, White to move: Rd1-d8#
    ("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", "d1d8"),
    # Queen mate, White to move: Qf7-g7#
    ("7k/5Q2/5K2/8/8/8/8/8 w - - 0 1", "f7g7"),
    # Back-rank mate, Black to move: Rd8-d1#
    ("3r2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1", "d8d1"),
])
def test_mate_in_one(fen, best):
    """Engine must find the forced mate-in-one. This is the search-correctness
    gate for the pseudo-legal/king-capture refactor (P1): perft proves move
    generation, but only a real mate-find proves the search still scores
    illegal king-escapes correctly and detects mate at the leaf."""
    move, elapsed = _run_subprocess(fen)
    assert move == best, f"Expected mate {best}, got '{move}' for {fen}"
    assert elapsed < WALL_LIMIT_S


@pytest.mark.parametrize("fen", [
    # Checkmate: white king on a1, mated by rook+queen
    "8/8/8/8/8/1q6/r7/K7 w - - 0 1",
    # Stalemate: black king in corner
    "k7/2Q5/1K6/8/8/8/8/8 b - - 0 1",
])
def test_no_legal_moves_returns_0000(fen):
    mod = _load_engine()
    legal = _legal_set(mod, fen)
    if legal:
        pytest.skip(f"Position has {len(legal)} legal moves; adjust FEN")
    move, elapsed = _run_subprocess(fen)
    assert move == "0000", f"Expected '0000' for no-legal-moves position, got '{move}'"
    assert elapsed < WALL_LIMIT_S


def test_move_output_format():
    """Move must be 4 or 5 lowercase chars in valid square notation."""
    move, _ = _run_subprocess(START_FEN)
    if move == "0000":
        return  # starting position has no legal moves - should not happen
    assert 4 <= len(move) <= 5, f"Bad move length: '{move}'"
    assert move[0] in "abcdefgh", f"Bad from-file: '{move}'"
    assert move[1] in "12345678", f"Bad from-rank: '{move}'"
    assert move[2] in "abcdefgh", f"Bad to-file: '{move}'"
    assert move[3] in "12345678", f"Bad to-rank: '{move}'"


# ---------------------------------------------------------------------------
# Timing: wall-time including cold-start
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fen", [
    START_FEN,
    # Middle game
    "r1bq1rk1/ppp2pbp/2np1np1/4p3/2PPP3/2N2N2/PP2BPPP/R1BQ1RK1 w - - 0 8",
    # Tactical (lots of captures)
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    # Late endgame
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
])
def test_wall_time_under_limit(fen):
    _, elapsed = _run_subprocess(fen)
    assert elapsed < WALL_LIMIT_S, f"Took {elapsed:.2f}s on: {fen}"


# ---------------------------------------------------------------------------
# Perft — A2 guardrail (move-gen correctness)
#
# A green perft at depth N is a complete proof that legal() + make() +
# unmake() agree with the known combinatorial tree for that position.
# Run this before and after implementing A2 (pseudo-legal search).
# Depths chosen to keep the full suite under ~5s on dev hardware.
# Known values from chessprogramming.org/Perft_Results.
# ---------------------------------------------------------------------------

def _perft(mod, p, depth: int) -> int:
    if depth == 0:
        return 1
    nodes = 0
    for m in mod.legal(p):
        u = mod.make(p, m)
        nodes += _perft(mod, p, depth - 1)
        mod.unmake(p, u)
    return nodes


@pytest.mark.parametrize("fen,depth,expected", [
    # Starting position
    (START_FEN, 1, 20),
    (START_FEN, 2, 400),
    (START_FEN, 3, 8_902),
    # Kiwipete — exercises castling, en-passant, promotions
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 1, 48),
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 2, 2_039),
    # Endgame with passed pawns and en-passant
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 1, 14),
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 2, 191),
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 3, 2_812),
    # Promotion-heavy position
    ("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 1, 6),
    ("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 2, 264),
])
def test_perft(fen, depth, expected):
    mod = _load_engine()
    p, _, _ = mod.build(fen)
    got = _perft(mod, p, depth)
    assert got == expected, (
        f"perft({depth}) on {fen[:40]}... = {got}, expected {expected}"
    )


# ---------------------------------------------------------------------------
# Eval correctness — A1 guardrail (two complementary checks)
#
# 1. test_eval_unmake_consistency: evalp must be identical before and after
#    make+unmake. Proves unmake has no side effects on board state.
#    Must pass NOW (before A1) and must keep passing after A1.
#
# 2. test_incremental_score_matches_evalp: auto-activates once A1 adds a
#    running `score` attribute to the position. After each make, asserts
#    p.score == evalp(p). Skipped (not failed) until A1 lands.
# ---------------------------------------------------------------------------

def _random_playout(mod, fen: str, n_moves: int, seed: int = 42):
    """Yield (position, move) for up to n_moves half-moves from fen."""
    rng = random.Random(seed)
    p, _, _ = mod.build(fen)
    for _ in range(n_moves):
        moves = mod.legal(p)
        if not moves:
            break
        m = rng.choice(moves)
        yield p, m
        mod.make(p, m)


@pytest.mark.parametrize("fen", [
    START_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
])
def test_eval_unmake_consistency(fen):
    """evalp(p) must be identical before and after make+unmake for every move."""
    mod = _load_engine()
    rng = random.Random(99)
    p, _, _ = mod.build(fen)
    for step in range(60):
        moves = mod.legal(p)
        if not moves:
            break
        m = rng.choice(moves)
        score_before = mod.evalp(p)
        u = mod.make(p, m)
        mod.unmake(p, u)
        score_after = mod.evalp(p)
        assert score_before == score_after, (
            f"step {step}: evalp changed after make+unmake of {mod.uci(m)} "
            f"in {fen[:40]}...: before={score_before}, after={score_after}"
        )
        # Advance the game for varied positions
        mod.make(p, m)


def _pesto_scratch(mod, p):
    """
    From-scratch (mg, eg, ph) — white-perspective PeSTO material+PST sums
    plus total phase weight, independent of the incremental accumulators.
    Mirrors _ps() exactly. Reference for test_incremental_score_matches_evalp.
    """
    mg = eg = ph = 0
    for i, x in enumerate(p.b):
        if x == ".":
            continue
        X = x.upper(); w = x.isupper(); si = i if w else i ^ 56
        pi = mod.PI.index(X)
        m = mod.MGV[pi] + mod.MGT[pi][si]
        e = mod.EGV[pi] + mod.EGT[pi][si]
        mg += m if w else -m
        eg += e if w else -e
        ph += mod.PHW[pi]
    return mg, eg, ph


@pytest.mark.parametrize("fen", [
    START_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
])
def test_incremental_score_matches_evalp(fen):
    """
    P5 guardrail: after each make, (p.mg, p.eg, p.ph) must equal the
    from-scratch PeSTO computation. A wrong delta fails here immediately
    on the offending move, no SPRT round-trip needed.
    """
    mod = _load_engine()
    p, _, _ = mod.build(fen)
    rng = random.Random(7)
    for step in range(80):
        moves = mod.legal(p)
        if not moves:
            break
        m = rng.choice(moves)
        mod.make(p, m)
        expected = _pesto_scratch(mod, p)
        actual = (p.mg, p.eg, p.ph)
        assert actual == expected, (
            f"step {step}: incremental (mg,eg,ph)={actual} != scratch={expected} "
            f"after {mod.uci(m)} in {fen[:40]}..."
        )


def test_pesto_tables_shape():
    """All 12 PeSTO tables must have exactly 64 entries; values/weights 6 each."""
    mod = _load_engine()
    assert len(mod.MGT) == 6 and len(mod.EGT) == 6
    for t in (*mod.MGT, *mod.EGT):
        assert len(t) == 64
    assert len(mod.MGV) == len(mod.EGV) == len(mod.PHW) == 6


def test_eval_startpos_zero():
    """The starting position is symmetric — evalp must be exactly 0."""
    mod = _load_engine()
    p, _, _ = mod.build(START_FEN)
    assert mod.evalp(p) == 0


def _mirror_fen(fen: str) -> str:
    """Vertically flip the board, swap colors, side to move and castling rights."""
    board, stm, castle, ep, h, f = fen.split()
    flipped = "/".join(r.swapcase() for r in reversed(board.split("/")))
    stm2 = "b" if stm == "w" else "w"
    castle2 = "".join(sorted(c.swapcase() for c in castle)) if castle != "-" else "-"
    return f"{flipped} {stm2} {castle2} - {h} {f}"


@pytest.mark.parametrize("fen", [
    START_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
])
def test_eval_mirror(fen):
    """
    Color-flipping a position (and the side to move) must give the exact
    same stm-relative eval. Catches ^56 orientation bugs in the tables.
    """
    mod = _load_engine()
    p1, _, _ = mod.build(fen)
    p2, _, _ = mod.build(_mirror_fen(fen))
    assert mod.evalp(p1) == mod.evalp(p2), f"mirror eval mismatch for {fen}"
