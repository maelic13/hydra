import pytest

from hydra import syzygy
from hydra.board import Board
from hydra.syzygy import TB_PROMOTES_NONE, TB_WIN, RootProbeResult, SyzygyTablebase


class _FakeFathom:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def init(self, path: str) -> int:
        self.calls.append(("init", path))
        return 5

    def probe_wdl(self, *args):
        self.calls.append(("wdl", args))
        return TB_WIN

    def probe_root(self, *args):
        self.calls.append(("root", args))
        return (TB_WIN, 7, 15, TB_PROMOTES_NONE, 0, 9)


def test_syzygy_path_and_probe_arguments(monkeypatch) -> None:
    fake = _FakeFathom()
    monkeypatch.setattr(syzygy, "_fathom", fake)
    tablebase = SyzygyTablebase()
    board = Board.from_fen("8/8/8/8/4k3/8/8/5RK1 w - - 37 1")

    assert tablebase.set_path("<empty>") == 5
    assert tablebase.can_probe(board, 5)
    assert tablebase.probe_wdl(board, use_50_move_rule=True) == TB_WIN
    assert tablebase.probe_wdl(board, use_50_move_rule=False) == TB_WIN
    assert tablebase.probe_root(board) == RootProbeResult(TB_WIN, 7, 15, TB_PROMOTES_NONE, False, 9)

    assert fake.calls[0] == ("init", "")
    assert fake.calls[1][1][8] == 37
    assert fake.calls[2][1][8] == 0


def test_syzygy_can_probe_respects_limit_and_loaded_cardinality(monkeypatch) -> None:
    fake = _FakeFathom()
    monkeypatch.setattr(syzygy, "_fathom", fake)
    tablebase = SyzygyTablebase()
    board = Board.from_fen("8/8/8/8/4k3/8/8/5RK1 w - - 0 1")

    assert not tablebase.can_probe(board, 7)
    tablebase.set_path("D:/tb")
    assert not tablebase.can_probe(board, 2)
    assert tablebase.can_probe(board, 3)


def test_syzygy_set_path_requires_native_extension(monkeypatch) -> None:
    monkeypatch.setattr(syzygy, "_fathom", None)

    with pytest.raises(RuntimeError, match="native Fathom extension"):
        SyzygyTablebase().set_path("D:/tb")


def test_syzygy_native_available_reflects_extension_import(monkeypatch) -> None:
    monkeypatch.setattr(syzygy, "_fathom", None)
    assert not syzygy.native_available()

    monkeypatch.setattr(syzygy, "_fathom", object())
    assert syzygy.native_available()


def test_syzygy_probe_methods_return_none_for_native_probe_failure(monkeypatch) -> None:
    class FailingFathom(_FakeFathom):
        def probe_wdl(self, *args):
            self.calls.append(("wdl", args))

        def probe_root(self, *args):
            self.calls.append(("root", args))

    fake = FailingFathom()
    monkeypatch.setattr(syzygy, "_fathom", fake)
    tablebase = SyzygyTablebase()
    board = Board.from_fen("8/8/8/8/4k3/8/8/5RK1 w - - 0 1")

    tablebase.set_path("D:/tb")

    assert tablebase.probe_wdl(board) is None
    assert tablebase.probe_root(board) is None
