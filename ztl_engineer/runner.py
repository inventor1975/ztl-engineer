"""Run the ZTL stand on a brick in a background thread and expose its progress.

The stand (ztl-stand, a pre-existing dependency) already keeps a progress record while it searches designs —
`ustand.stand._PROGRESS` with `tried` and `total` — and prints it to stderr every 30 s. We read the same record
from the running thread, so the progress the page shows is the stand's own count, not a guess from the clock.
Where the stand has no count (one fixed design being proved, an inverse `find`), the page shows elapsed time and
the phase instead of a percentage.

The stand keeps module-level state, so one run at a time: a second request waits for the lock.
"""
from __future__ import annotations

import os
import pathlib
import sys
import threading
import time
import traceback
import uuid

HERE = pathlib.Path(__file__).resolve().parent.parent
STAND_DIR = pathlib.Path(os.environ.get("ZTL_ENGINEER_STAND", HERE.parent / "ztl-stand")).resolve()
if str(STAND_DIR) not in sys.path:
    sys.path.insert(0, str(STAND_DIR))

from ustand import stand as S          # noqa: E402  (pre-existing dependency: github.com/inventor1975/ztl-stand)
from ustand import stopflag as SF      # noqa: E402

_RUN_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}
TIME_LIMIT_S = int(os.environ.get("ZTL_ENGINEER_STAND_TIME_LIMIT", "600"))


def _watch(job):
    """Copy the stand's progress record into the job while it runs; stop it at the time limit."""
    while job["state"] == "running":
        p = S._PROGRESS
        job["tried"], job["total"] = p.get("tried", 0), p.get("total", 0)
        job["elapsed"] = round(time.time() - job["t0"], 1)
        if job["elapsed"] > TIME_LIMIT_S and not SF.STOP[0]:
            SF.STOP[0] = True          # seen at the stand's next safe point; it returns a partial, honest report
            job["note"] = f"stopped at the {TIME_LIMIT_S} s limit"
        time.sleep(0.4)


def _work(job, brick):
    with _RUN_LOCK:
        job["t0"] = time.time()
        job["state"] = "running"
        threading.Thread(target=_watch, args=(job,), daemon=True).start()
        try:
            job["result"] = S.run(brick)
        except BaseException as e:      # noqa: BLE001 — S.run should never raise; if it does, say so, do not hide it
            job["result"] = {"verdict": "STAND ERROR", "why": f"{type(e).__name__}: {e}",
                             "trace": traceback.format_exc()[-1500:]}
        finally:
            job["elapsed"] = round(time.time() - job["t0"], 1)
            p = S._PROGRESS
            job["tried"], job["total"] = p.get("tried", 0), p.get("total", 0)
            job["state"] = "done"


def start(brick: dict, on_done=None) -> str:
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "state": "queued", "tried": 0, "total": 0, "elapsed": 0.0, "t0": time.time(),
           "result": None, "note": "", "on_done": on_done}

    def go():
        _work(job, brick)
        if on_done:
            try:
                on_done(job)
            except Exception:           # noqa: BLE001
                job["note"] += " (post-processing failed: " + traceback.format_exc()[-300:] + ")"

    JOBS[jid] = job
    threading.Thread(target=go, daemon=True).start()
    return jid


def run_now(brick: dict) -> dict:
    """Synchronous run (tests, the CLI)."""
    with _RUN_LOCK:
        return S.run(brick)


def status(jid: str) -> dict | None:
    j = JOBS.get(jid)
    if not j:
        return None
    pct = round(100 * j["tried"] / j["total"], 1) if j["total"] else None
    return {k: j[k] for k in ("id", "state", "tried", "total", "elapsed", "note")} | {"percent": pct}
