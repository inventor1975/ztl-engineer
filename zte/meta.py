"""Muse Spark through the Meta Model API, behind a hard spending stop.

Meta's own "spend limit" only sends an e-mail; once the free credits are gone the card is charged. So the stop
lives here: every call is priced from the usage the API returns, the running total is kept on disk, and a call
whose worst case would cross the cap is refused before it is sent.

    MEASURED 2026-10-26: "Reply with exactly: OK" cost 13 input + 166 output tokens, 156 of them reasoning —
    reasoning tokens are billed as output, so the price of a call is mostly the model thinking, not answering.
    reasoning.effort accepts minimal/low/medium/high/xhigh/max ("none" is refused); "low" cut the same call to 51.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request

API = "https://api.meta.ai/v1/responses"
MODEL = os.environ.get("ZTE_MODEL", "muse-spark-1.3")

# USD per token, from dev.meta.ai/docs/pricing-rate-limits (read 2026-10-26)
PRICES = {
    "muse-spark-1.3": {"input": 1.25e-6, "cached": 0.15e-6, "output": 4.25e-6},
    "muse-spark-1.2": {"input": 1.25e-6, "cached": 0.15e-6, "output": 4.25e-6},
    "muse-spark-1.3-contributor": {"input": 0.10e-6, "cached": 0.002e-6, "output": 0.20e-6},
}

CAP_USD = float(os.environ.get("ZTE_SPEND_CAP_USD", "100"))
LEDGER = pathlib.Path(os.environ.get(
    "ZTE_LEDGER", pathlib.Path.home() / ".local" / "state" / "zero-trust-engineer" / "spend.json"))
_LOCK = threading.Lock()


class SpendCapReached(RuntimeError):
    pass


class ModelError(RuntimeError):
    pass


def _key() -> str:
    k = os.environ.get("META_API_KEY")
    if k:
        return k.strip()
    f = pathlib.Path.home() / ".config" / "meta-api-key"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    raise ModelError("no API key: set META_API_KEY or put the key in ~/.config/meta-api-key")


def spent() -> dict:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"usd": 0.0, "calls": 0}


def _record(usd: float) -> dict:
    s = spent()
    s["usd"] = round(s["usd"] + usd, 6)
    s["calls"] += 1
    s["last"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(s), encoding="utf-8")
    tmp.replace(LEDGER)
    return s


def price(usage: dict, model: str = MODEL) -> float:
    p = PRICES.get(model, PRICES["muse-spark-1.3"])
    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
    fresh = usage.get("input_tokens", 0) - cached
    return fresh * p["input"] + cached * p["cached"] + usage.get("output_tokens", 0) * p["output"]


def image_part(data: bytes, mime: str) -> dict:
    return {"type": "input_image", "image_url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}


def pdf_parts(data: bytes, max_pages: int = 6, dpi: int = 110) -> list[dict]:
    """A PDF as page images: the Responses API takes a PDF only as an uploaded file id or a public URL, and a
    datasheet's numbers are on its first pages anyway. Rendered locally with pdftoppm (poppler)."""
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / "in.pdf"
        src.write_bytes(data)
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", "1", "-l", str(max_pages), str(src),
                        str(pathlib.Path(d) / "p")], check=True, capture_output=True, timeout=120)
        return [image_part(p.read_bytes(), "image/png") for p in sorted(pathlib.Path(d).glob("p*.png"))]


def ask(content: list[dict] | str, *, instructions: str | None = None, effort: str = "low",
        max_output_tokens: int = 6000, model: str = MODEL) -> dict:
    """One call. Returns {"text", "usage", "usd", "spent"}. Refused before sending if the worst case of this call
    (its input estimate + max_output_tokens at the output price) would cross the cap."""
    if isinstance(content, str):
        content = [{"type": "input_text", "text": content}]
    body = {"model": model, "input": [{"type": "message", "role": "user", "content": content}],
            "reasoning": {"effort": effort}, "max_output_tokens": max_output_tokens}
    if instructions:
        body["instructions"] = instructions
    raw = json.dumps(body).encode()
    p = PRICES.get(model, PRICES["muse-spark-1.3"])
    # worst case: every byte of the request a token (images are far fewer tokens than base64 bytes — an over-count)
    worst = min(len(raw), 400_000) * p["input"] + max_output_tokens * p["output"]
    with _LOCK:
        s = spent()
        if s["usd"] + worst > CAP_USD:
            raise SpendCapReached(f"spending stop: ${s['usd']:.2f} spent of the ${CAP_USD:.0f} cap; "
                                  f"this call could cost up to ${worst:.2f}")
    req = urllib.request.Request(API, data=raw, method="POST",
                                 headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ModelError(f"Meta Model API {e.code}: {e.read().decode()[:300]}") from None
    usage = d.get("usage") or {}
    usd = price(usage, model)
    with _LOCK:
        s = _record(usd)
    text = "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                   for c in o.get("content", []) if c.get("type") == "output_text")
    return {"text": text, "usage": usage, "usd": usd, "spent": s, "status": d.get("status")}
