#!/usr/bin/env python3
"""ZTL Engineer as an MCP server: any AI agent can ask the ZTL stand for an independent check before it tells a
person "this will work". Standard library only; MCP over stdio (JSON-RPC 2.0, one message per line).

Tools:
  brick_format   the brick format (ztl-stand's BRICKS.md), so the calling AI can write the problem itself
  check_design   the stand judges a brick: EARNED (proved for every value the tolerances allow), REFUTED (a concrete
                 failing point), OPEN — no AI involved, no API cost
  ask_engineer   the whole ZTL Engineer road: Muse Spark reads the question and any photos/PDFs/CAD files, the stand
                 judges; spends Meta Model API credit (the app's spending stop applies)

Connect it, e.g. in Claude Desktop's config:
  {"mcpServers": {"ztl-engineer": {"command": "python3", "args": ["/path/to/ztl-engineer/mcp_server.py"]}}}
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PROTOCOL = "2025-06-18"
OUT = sys.stdout                 # the protocol's channel; everything else the code prints goes to stderr
sys.stdout = sys.stderr

from ztl_engineer import runner  # noqa: E402  (puts ztl-stand on the path)

MAX_FILE = 40 * 1024 * 1024
TOOLS = [
    {"name": "brick_format",
     "description": "The ZTL stand's brick format (BRICKS.md): how to write an engineering problem — quantities with "
                    "tolerances or ranges, laws, requirements, optional catalogue slots and an objective — so that "
                    "check_design can judge it. Read this before writing a brick.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "check_design",
     "description": "Independent check of an engineering design by the ZTL stand, with no AI involved. Give a brick "
                    "(JSON object, see brick_format). Answers EARNED (proved for every value the tolerances allow), "
                    "REFUTED (with a concrete failing point), or OPEN (cannot vouch either way), plus what it "
                    "proved (guaranteed ranges, the chosen design, an optimum). Free: runs locally.",
     "inputSchema": {"type": "object", "required": ["brick"], "properties": {
         "brick": {"type": "object", "description": "the problem as a ZTL stand brick"},
         "time_limit_s": {"type": "number", "description": "stop after this many seconds (default 300, at most 1800)"}}}},
    {"name": "ask_engineer",
     "description": "Ask ZTL Engineer in plain words, in any language, optionally with files (a nameplate photo, a "
                    "datasheet PDF, a SPICE netlist + BOM, a truss deck). Meta's Muse Spark reads them and writes the "
                    "brick; the ZTL stand judges it. Returns the verdict, the values the AI read (check them) and "
                    "where the report is. Spends Meta Model API credit.",
     "inputSchema": {"type": "object", "required": ["question"], "properties": {
         "question": {"type": "string"},
         "files": {"type": "array", "items": {"type": "string"}, "description": "paths of local files to attach"}}}},
]


def _text(obj) -> dict:
    return {"content": [{"type": "text", "text": obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False,
                                                                                            indent=1)}]}


def brick_format(_args):
    return _text((runner.STAND_DIR / "BRICKS.md").read_text(encoding="utf-8"))


def check_design(args):
    brick = args.get("brick")
    if not isinstance(brick, dict):
        raise ValueError("brick must be a JSON object")
    limit = min(float(args.get("time_limit_s") or 300), 1800.0)
    with tempfile.TemporaryDirectory() as d:          # a brick given as data: its own empty folder, nothing else
        path = pathlib.Path(d) / "brick.json"
        path.write_text(json.dumps(brick), encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(runner.STAND_DIR), OPENBLAS_NUM_THREADS="1")
        try:
            p = subprocess.run([sys.executable, "-m", "ustand.stand", str(path)], cwd=d, env=env,
                               capture_output=True, text=True, timeout=limit)
        except subprocess.TimeoutExpired:
            return _text({"verdict": "OPEN", "why": f"stopped after {limit:.0f} s (time_limit_s)"})
    try:
        return _text(json.loads(p.stdout))
    except ValueError:
        return _text({"verdict": "STAND ERROR", "why": (p.stderr or p.stdout)[-800:]})


def ask_engineer(args):
    from ztl_engineer import session as SS
    q = str(args.get("question") or "").strip()
    if not q:
        raise ValueError("question is empty")
    s = SS.new("any")
    for f in args.get("files") or []:
        fp = pathlib.Path(str(f)).expanduser()
        if not fp.is_file() or fp.stat().st_size > MAX_FILE:
            raise ValueError(f"not a file of at most 40 MB: {f}")
        import mimetypes
        s.add_file(fp.name, mimetypes.guess_type(fp.name)[0] or "", fp.read_bytes())
    s.say(q)
    while s.job.get("phase") not in ("done", "error", "idle"):
        time.sleep(1.0)
    if s.job.get("phase") == "error":
        return {**_text({"error": s.job.get("error")}), "isError": True}
    reply = next((m["text"] for m in reversed(s.history) if m["role"] == "assistant"), "")
    r = s.result or {}
    keep = ("verdict", "why", "guaranteed", "design", "objective", "its_violating_point", "value_there",
            "limit", "decision", "exact_range", "find", "proved", "quantity", "unit")
    return _text({"verdict": r.get("verdict"), "muse_spark_says": reply,
                  "values_the_ai_read": [{k: v.get(k) for k in ("quantity", "value", "unit", "from", "where")}
                                         for v in s.values],
                  "stand_answer": {k: r[k] for k in keep if k in r},
                  "session": s.id, "report": f"http://localhost:8090/api/session/{s.id}/run/{len(s.runs)}/report.html "
                                             "(when the app is running)"})


HANDLERS = {"brick_format": brick_format, "check_design": check_design, "ask_engineer": ask_engineer}


def handle(msg: dict):
    m, mid = msg.get("method"), msg.get("id")
    if m == "initialize":
        return {"protocolVersion": msg.get("params", {}).get("protocolVersion") or PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ztl-engineer", "version": "0.1"},
                "instructions": "Independent engineering checks: Muse Spark reads, the ZTL stand proves. "
                                "Call check_design before telling a person a design will work."}
    if m == "tools/list":
        return {"tools": TOOLS}
    if m == "tools/call":
        p = msg.get("params") or {}
        fn = HANDLERS.get(p.get("name"))
        if fn is None:
            raise KeyError(f"unknown tool {p.get('name')!r}")
        try:
            return fn(p.get("arguments") or {})
        except (ValueError, OSError, RuntimeError) as e:
            return {**_text(f"{type(e).__name__}: {e}"), "isError": True}
    if m == "ping":
        return {}
    if mid is None:
        return None                                   # a notification (e.g. notifications/initialized)
    raise KeyError(f"method not found: {m}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            OUT.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
                      + "\n")
            OUT.flush()
            continue
        mid = msg.get("id")
        try:
            res = handle(msg)
            if mid is None:
                continue
            out = {"jsonrpc": "2.0", "id": mid, "result": res}
        except KeyError as e:
            out = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": str(e)}}
        except Exception as e:                        # noqa: BLE001 — the server must answer, not die
            out = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"}}
        OUT.write(json.dumps(out, ensure_ascii=False) + "\n")
        OUT.flush()


if __name__ == "__main__":
    main()
