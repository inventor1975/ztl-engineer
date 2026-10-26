"""One end of a truss displacement's proved range, in its own process — the stand's own descent (ustand range_by),
unchanged, for one side only: the other side is answered at once and dropped.

    python -m ztl_engineer.truss_end DECK TOL TARGET min|max   -> {"min": {...}} on stdout, each run on stderr

Why one process per end (MEASURED 2026-10-26, Muhanna's 20-floor cantilever, one judgement of U(42,X)): 177.5 s on
one core, 179.8 s with the stand's --jobs 16 — the truss judgement does not split, so the four ends (UX/UY min/max),
which are independent, run side by side instead."""
import json
import sys

from ustand import truss as T
from ustand.spice import range_by


def main(argv):
    deck, tol, target, side = argv
    text = open(deck, encoding="utf-8").read()
    n, d = T._target(target)
    keep = ">=" if side == "min" else "<="

    def judge_one(op, bound):
        if op != keep:
            return {"verdict": "EARNED"}
        return T.judge(text, tol, [(n, d, op, bound)])

    def progress(s, e):
        if s == side:
            print(json.dumps({s: e}), file=sys.stderr, flush=True)

    out = range_by(judge_one, progress=progress)
    print(json.dumps({side: out[side]}))


if __name__ == "__main__":
    main(sys.argv[1:])
