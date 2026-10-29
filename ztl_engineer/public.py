"""The public demo mode (engineer.ztljudge.com, formerly engineer.vitalyreznik.com, 2026-10-28): the same app behind Apache on a small shared server
(2 cores, 3 GB, beside a blog and two other services), paid for by the author's Meta API key. Off unless
ZTL_ENGINEER_PUBLIC=1; on a person's own machine nothing here applies.

What it limits, and why:
  hosts      only the public name (ZTL_ENGINEER_HOSTS) and localhost — a DNS-rebinding page or a foreign site is refused
  per IP     questions and recalculations: 20 an hour, 60 a day; new sessions and uploads: 60 an hour each
             (raised 28.10 on the curator's word: judges sharing one office address must not be blocked)
  everyone   300 questions a day in all; the spending stop (ZTL_ENGINEER_SPEND_CAP_USD, $20 on the server) still holds
  heavy      no run over HEAVY_DESIGNS designs and no proved-range runs: minutes of all the server's cores
  size       uploads up to 10 MB
The client's address is the one Apache adds last to X-Forwarded-For (the server listens on 127.0.0.1 only, so every
request comes through Apache; a forged header from the client sits to the LEFT of the real address).
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

PUBLIC = os.environ.get("ZTL_ENGINEER_PUBLIC") == "1"
LOCAL = {"localhost", "127.0.0.1", "::1"}
HOSTS = LOCAL | {h.strip().lower() for h in os.environ.get("ZTL_ENGINEER_HOSTS", "").split(",") if h.strip()}
MAX_UPLOAD = 10 * 1024 * 1024
LIMITS = {"ask": [(3600, 20), (86400, 60)], "session": [(3600, 60)], "file": [(3600, 60)]}
ALL_DAY = 300

_LOCK = threading.Lock()
_SEEN: dict[tuple, deque] = defaultdict(deque)
_ALL: deque = deque()


def client_ip(handler) -> str:
    peer = handler.client_address[0]
    if PUBLIC and peer in LOCAL:
        fwd = handler.headers.get("X-Forwarded-For") or ""
        if fwd.strip():
            return fwd.split(",")[-1].strip()
    return peer


def refuse(kind: str, ip: str) -> str | None:
    """None if this request may go; else the reason to tell the person. Counts the request when it goes."""
    if not PUBLIC:
        return None
    now = time.time()
    with _LOCK:
        q = _SEEN[(kind, ip)]
        longest = max(w for w, _ in LIMITS[kind])
        while q and now - q[0] > longest:
            q.popleft()
        for window, n in LIMITS[kind]:
            if sum(1 for t in q if now - t <= window) >= n:
                span = "an hour" if window == 3600 else "a day"
                return (f"The public demo allows {n} of these {span} from one address — please try again later, or "
                        "run ZTL Engineer on your own machine (see the README).")
        if kind == "ask":
            while _ALL and now - _ALL[0] > 86400:
                _ALL.popleft()
            if len(_ALL) >= ALL_DAY:
                return "The public demo has answered its questions for today — please try again tomorrow."
            _ALL.append(now)
        q.append(now)
    return None
