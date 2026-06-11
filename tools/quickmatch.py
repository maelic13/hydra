"""Quick in-process match between two engine versions at short TC (sanity tool).

Fast local W/L/D signal without fastchess: feeds each engine the deployment
input line, plays from a small opening set with colors alternating.
Used to expose the 2026-06-11 PVS bug. Not a substitute for the tripwire.

Usage:
    python tools/quickmatch.py <engineA.py> <engineB.py> [sec=0.25] [pairs=12]

Feeds each engine the exact deployment input line (FEN + moves history),
plays out games from a few openings with colors alternating, reports
W/L/D for engine A and termination reasons.
"""
import importlib.util, sys, time

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

OPENINGS = [
    [],  # fresh start
    ["e2e4", "e7e5", "g1f3", "b8c6"],
    ["d2d4", "d7d5", "c2c4", "e7e6"],
    ["e2e4", "c7c5", "g1f3", "d7d6"],
    ["g1f3", "g8f6", "c2c4", "g7g6"],
    ["e2e4", "e7e6", "d2d4", "d7d5"],
]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def game_over(mod, line):
    """Return None if game continues, else result string from White's view."""
    p, rep, _ = mod.build(line)
    ms = mod.legal(p)
    if not ms:
        if mod.incheck(p, p.w):
            return "0-1" if p.w else "1-0"  # side to move is mated
        return "1/2 stalemate"
    if rep.get(mod.key(p), 0) >= 3:
        return "1/2 threefold"
    if p.h >= 100:
        return "1/2 fifty"
    return None


def play(mod_w, mod_b, opening, sec):
    hist = list(opening)
    for ply in range(300):
        line = START + (" moves " + " ".join(hist) if hist else "")
        # check terminal with either module (they agree on rules)
        r = game_over(mod_w, line)
        if r:
            return r, len(hist)
        mod = mod_w if (len(hist) % 2 == 0) else mod_b
        p, rep, h = mod.build(line)
        m = mod.search(p, rep, sec)
        if m is None:
            return "ERR none", len(hist)
        u = mod.uci(m)
        # verify legality against the OTHER module (cross-check)
        other = mod_b if mod is mod_w else mod_w
        po, _, _ = other.build(line)
        if other.parseuci(po, u) is None:
            return f"ERR illegal {u} by {'W' if mod is mod_w else 'B'}", len(hist)
        hist.append(u)
    return "1/2 maxlen", len(hist)


def main():
    a_path, b_path = sys.argv[1], sys.argv[2]
    sec = float(sys.argv[3]) if len(sys.argv) > 3 else 0.25
    pairs = int(sys.argv[4]) if len(sys.argv) > 4 else 12
    A = load(a_path, "engA")
    B = load(b_path, "engB")
    aw = al = dr = 0
    t0 = time.time()
    for i in range(pairs):
        op = OPENINGS[i % len(OPENINGS)]
        for a_is_white in (True, False):
            mw, mb = (A, B) if a_is_white else (B, A)
            r, plies = play(mw, mb, op, sec)
            if r.startswith("ERR"):
                print(f"  pair {i} ({'A-white' if a_is_white else 'A-black'}): {r} after {plies} plies", flush=True)
                continue
            if r == "1-0":
                res = "W" if a_is_white else "L"
            elif r == "0-1":
                res = "L" if a_is_white else "W"
            else:
                res = "D"
            aw += res == "W"; al += res == "L"; dr += res == "D"
            print(f"  pair {i} {'A-white' if a_is_white else 'A-black'}: {r:>14s} ({plies} plies) -> {res}   [A: +{aw}-{al}={dr}]", flush=True)
    n = aw + al + dr
    print(f"\nA={a_path} vs B={b_path} @ {sec}s/move")
    print(f"games={n}  A: +{aw} -{al} ={dr}  score={100*(aw+0.5*dr)/max(n,1):.1f}%  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
