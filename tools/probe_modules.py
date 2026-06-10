#!/usr/bin/env python3
"""Module availability probe for ChessAgents platform.

Submit this as a temporary agent to verify which stdlib modules are available.
It reads a FEN (required by the platform), tests imports, then outputs a legal
fallback move so the round completes.

Usage (local test):
    echo "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" | python tools/probe_modules.py
Expected output: a line starting "ok" followed by "e2e4" (or error details).
"""
import sys

results = []
for mod in ["time", "math", "random", "typing", "collections", "io", "re", "struct"]:
    try:
        __import__(mod)
        results.append(f"{mod}=ok")
    except ImportError:
        results.append(f"{mod}=MISSING")

# Write diagnostics to stderr (not captured by platform, but visible in local testing)
print(" ".join(results), file=sys.stderr)

# Always output a legal move for the starting position
sys.stdout.write("e2e4\n")
sys.stdout.flush()
