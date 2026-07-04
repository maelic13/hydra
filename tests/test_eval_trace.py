"""Phase 1.3 gate: the eval coefficient trace must reconstruct evaluate() exactly.

For the Texel campaign (Phase 4) the eval is decomposed into a sparse coefficient
vector over EvalParams weights (plus king-safety / eg-centralization residuals).
This test guards that decomposition: reconstruct_eval(trace(b), p) == evaluate(b).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hydra.board import Board
from hydra.evaluation import ClassicalEvaluator, reconstruct_eval

_CORPUS = Path(__file__).parent / "data" / "eval_corpus.epd"

_SPOT_FENS = [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "8/8/p1p5/1p5p/1P5P/P1P5/8/K1k5 w - - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
]


def _corpus_fens(limit: int = 2000) -> list[str]:
    if not _CORPUS.exists():
        pytest.skip("eval corpus not present")
    return [ln.strip() for ln in _CORPUS.read_text().splitlines() if ln.strip()][:limit]


@pytest.mark.parametrize("fen", _SPOT_FENS)
def test_trace_reconstructs_spot(fen: str) -> None:
    ev = ClassicalEvaluator()
    board = Board.from_fen(fen)
    assert reconstruct_eval(ev.trace(board), ev.p) == ev.evaluate(board)


def test_trace_reconstructs_corpus() -> None:
    ev = ClassicalEvaluator()
    mismatches = 0
    for fen in _corpus_fens():
        board = Board.from_fen(fen)
        if reconstruct_eval(ev.trace(board), ev.p) != ev.evaluate(board):
            mismatches += 1
    assert mismatches == 0


def test_trace_tracks_weight_change() -> None:
    """A reconstructed score must follow a weight change (coeffs are wired)."""
    ev = ClassicalEvaluator()
    board = Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    base = reconstruct_eval(ev.trace(board), ev.p)
    ev.p.tempo += 25
    assert reconstruct_eval(ev.trace(board), ev.p) == base + 25
