"""One conversation: files, messages, the current brick, the values and their confirmations, the running pipeline.

A pipeline run is: the model reads and builds (or, for CAD files, the stand's importer builds) -> the stand judges,
its progress visible -> on BRICK ERROR the model repairs the form and the stand judges again -> the warranty
(warranty.py) says what the person may rely on. Confirming or correcting a value re-runs only what it touches:
a confirmation changes the warranty alone; a corrected value changes the brick, so the stand judges again.
"""
from __future__ import annotations

import copy
import json
import os
import pathlib
import threading
import time
import traceback
import uuid

from . import agent, meta, presets, runner, warranty
from ustand import spice as SPICE, truss as TRUSS  # noqa: E402  (pre-existing importers of ztl-stand)

SESSIONS: dict[str, "Session"] = {}
# sessions survive a server restart: each is saved under runs/<id>/ (files beside it), gitignored
STORE = pathlib.Path(os.environ.get("ZTL_ENGINEER_RUNS", pathlib.Path(__file__).resolve().parent.parent / "runs"))
_SAVED = ("preset_id", "history", "brick", "values", "question", "result", "warranty", "usd", "runs")


def _kind(name: str, mime: str) -> str:
    n = name.lower()
    if n.endswith(".pdf") or mime == "application/pdf":
        return "pdf"
    if n.endswith((".cir", ".net", ".sp", ".spice")):
        return "netlist"
    if n.endswith((".csv", ".tsv")):
        return "bom"
    if n.endswith(".json"):
        return "brick"
    if n.endswith((".txt", ".dat", ".inp", ".ans")):
        return "deck"
    if mime.startswith("image/") or n.endswith((".png", ".jpg", ".jpeg", ".webp", ".heic")):
        return "photo"
    return "other"


class Session:
    def __init__(self, preset_id: str = "pump"):
        self.id = uuid.uuid4().hex[:12]
        self.preset = presets.by_id(preset_id)
        self.history: list[dict] = []
        self.files: list[dict] = []
        self.brick: dict | None = None
        self.values: list[dict] = []
        self.question = ""
        self.result: dict | None = None
        self.warranty: dict | None = None
        self.usd = 0.0
        self.runs: list[dict] = []      # every judged question of this session, newest last
        self.job = {"phase": "idle", "tried": 0, "total": 0, "elapsed": 0.0, "log": []}
        self._lock = threading.Lock()

    # ---------- persistence
    @property
    def preset_id(self):
        return self.preset["id"]

    def save(self):
        d = STORE / self.id
        (d / "files").mkdir(parents=True, exist_ok=True)
        state = {k: getattr(self, k) for k in _SAVED}
        state["files"] = [{k: f[k] for k in ("name", "mime", "kind", "size")} for f in self.files]
        tmp = d / "session.json.tmp"
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(d / "session.json")

    @classmethod
    def load(cls, sid: str) -> "Session | None":
        d = STORE / sid
        try:
            state = json.loads((d / "session.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        s = cls(state.get("preset_id") or "pump")
        s.id = sid
        for k in _SAVED:
            if k != "preset_id" and k in state:
                setattr(s, k, state[k])
        for f in state.get("files", []):
            fp = d / "files" / f["name"]
            if fp.is_file():
                s.files.append(dict(f, data=fp.read_bytes()))
        return s

    def _record_run(self):
        self.runs.append({"n": len(self.runs) + 1, "at": time.strftime("%H:%M:%S"), "preset": self.preset["id"],
                          # the run is labelled by what the person asked, not by the model's paraphrase
                          "question": next((m["text"] for m in reversed(self.history) if m["role"] == "user"),
                                           self.question),
                          "files": [f["name"] for f in self.files],
                          "result": self.result, "warranty": self.warranty,
                          "values": copy.deepcopy(self.values), "brick": copy.deepcopy(self.brick)})
        self.save()

    # ---------- inputs
    def add_file(self, name: str, mime: str, data: bytes) -> dict:
        name = pathlib.Path(name).name or "file"
        f = {"name": name, "mime": mime, "data": data, "kind": _kind(name, mime), "size": len(data)}
        self.files.append(f)
        (STORE / self.id / "files").mkdir(parents=True, exist_ok=True)
        (STORE / self.id / "files" / name).write_bytes(data)
        self.save()
        return {k: f[k] for k in ("name", "kind", "size")}

    def say(self, text: str, preset_id: str | None = None):
        if preset_id:
            self.preset = presets.by_id(preset_id)
        self.history.append({"role": "user", "text": text})
        self.save()
        self._start(self._pipeline)

    def confirm(self, quantity: str, value: str | None = None):
        changed = False
        for v in self.values:
            if v["quantity"] == quantity:
                if value is not None and str(value).strip() and str(value).strip() != v["value"]:
                    v["read_as"] = v.get("read_as", v["value"])
                    v["value"] = str(value).strip()
                    changed = True
                    if self.brick and quantity in self.brick.get("quantities", {}):
                        q = self.brick["quantities"][quantity]
                        q["value"] = v["value"]
                        q.pop("range", None)
                v["confirmed"] = True
        if changed:
            self._start(self._rejudge)
        elif self.result:
            self.warranty = warranty.judge(self.result.get("verdict", ""), self.values)
            self._sync_last_run()

    def confirm_all(self):
        for v in self.values:
            v["confirmed"] = True
        if self.result:
            self.warranty = warranty.judge(self.result.get("verdict", ""), self.values)
        self._sync_last_run()

    def _sync_last_run(self):
        """A confirmation without a new judgement changes the warranty of the latest run, not a new run."""
        if self.runs and self.runs[-1]["result"] == self.result:
            self.runs[-1]["warranty"] = self.warranty
            self.runs[-1]["values"] = copy.deepcopy(self.values)
        self.save()

    # ---------- the pipeline
    def _start(self, fn):
        if self.job["phase"] not in ("idle", "done", "error"):
            raise RuntimeError("a run is already in progress")
        self.job = {"phase": "starting", "tried": 0, "total": 0, "elapsed": 0.0, "log": [], "t0": time.time()}
        threading.Thread(target=self._guard, args=(fn,), daemon=True).start()

    def _guard(self, fn):
        try:
            fn()
            self.job["phase"] = "done"
        except meta.SpendCapReached as e:
            self._log(str(e))
            self.job["phase"] = "error"
            self.job["error"] = str(e)
        except Exception as e:          # noqa: BLE001 — shown to the person, never swallowed
            self._log(f"{type(e).__name__}: {e}")
            self.job["phase"] = "error"
            self.job["error"] = f"{type(e).__name__}: {e}"
            self.job["trace"] = traceback.format_exc()[-1500:]
        self.job["elapsed"] = round(time.time() - self.job["t0"], 1)
        self.save()

    def _log(self, s: str):
        self.job["log"].append({"t": round(time.time() - self.job.get("t0", time.time()), 1), "msg": s})

    def _pipeline(self):
        self.job["phase"] = "reading"
        bricks = [f for f in self.files if f["kind"] == "brick"]
        if bricks:
            import json
            self.brick = json.loads(bricks[-1]["data"])
            self.values, self.question = [], self.history[-1]["text"] if self.history else ""
            self._log(f"using your brick {bricks[-1]['name']} as it is")
            reply = "I took your brick file as it is and sent it to the stand."
        else:
            n_img = sum(f["kind"] in ("photo", "pdf") for f in self.files)
            self._log(f"Muse Spark reads the conversation and {n_img} image/PDF file(s)")
            d = agent.build(self.history, self.files, self.preset)
            self.usd += d.get("usd", 0)
            reply = d.get("reply", "")
            self.question = d.get("question", "") or self.question
            if not d.get("ready"):
                self.history.append({"role": "assistant", "text": reply})
                self._log("the model needs more information")
                return
            if d.get("road") == "cad":
                try:
                    self.brick, self.values = self._from_cad(d), []
                except Exception as e:          # noqa: BLE001 — an importer's refusal is the file's fault, said as such
                    self.history.append({"role": "assistant", "text": reply})
                    self.result = {"verdict": "BRICK ERROR", "why": f"the file could not be imported: {e}"}
                    self.warranty = warranty.judge("BRICK ERROR", [])
                    self._log(f"import refused: {e}")
                    return
            else:
                self.brick = d.get("brick")
                target = ((self.brick or {}).get("find") or {})
                sought = {target.get("largest"), target.get("smallest")} - {None}
                # the quantity a `find` searches is an unknown, not a reading: nothing to confirm
                self.values = [dict(v, confirmed=False) for v in d.get("values") or []
                               if v.get("quantity") not in sought]
                for v in self.values:
                    if v.get("from") == "user":
                        v["confirmed"] = False     # typed by the person, but transcribed by the model: still dirty
            self._log(f"brick built: {len((self.brick or {}).get('quantities', {}))} quantities, "
                      f"{len((self.brick or {}).get('laws', []))} laws, "
                      f"{len((self.brick or {}).get('requirements', []))} requirements")
        self.history.append({"role": "assistant", "text": reply})
        self._judge_with_repair()

    def _from_cad(self, d) -> dict:
        net = [f for f in self.files if f["kind"] == "netlist"]
        if net:
            bom = [f for f in self.files if f["kind"] == "bom"]
            bom_path = None
            if bom:
                import tempfile
                tf = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
                tf.write(bom[-1]["data"]); tf.close()
                bom_path = tf.name
            self._log(f"the stand imports {net[-1]['name']}" + (f" with {bom[-1]['name']}" if bom else ""))
            table = SPICE.read_bom(bom_path) if bom_path else None
            br = SPICE.to_brick(net[-1]["data"].decode("utf-8", "replace"), table, d.get("requirements") or [])
            return {k: v for k, v in br.items() if not k.startswith("_")}
        deck = [f for f in self.files if f["kind"] == "deck"][-1]
        self._log(f"the stand imports the truss deck {deck['name']}")
        reqs = [tuple(r) for r in d.get("requirements") or []]
        return TRUSS.to_brick(deck["data"].decode("utf-8", "replace"), d.get("tolerance") or "0", reqs)

    def _rejudge(self):
        self._log("a value was corrected — the stand judges again")
        self._judge_with_repair()

    def _judge_with_repair(self):
        for attempt in range(agent.REPAIRS + 1):
            self.job["phase"] = "proving"
            self._log("the ZTL stand judges the design" + (f" (after repair {attempt})" if attempt else ""))
            res = self._run_stand(copy.deepcopy(self.brick))
            if res.get("verdict") != "BRICK ERROR" or attempt == agent.REPAIRS or not self.values:
                break
            self.job["phase"] = "repairing"
            self._log(f"BRICK ERROR: {str(res.get('why'))[:200]} — the model repairs the form")
            d = agent.repair(self.brick, str(res.get("why")), self.values)
            self.usd += d.get("usd", 0)
            if d.get("brick"):
                self.brick = d["brick"]
        self.result = res
        self.warranty = warranty.judge(res.get("verdict", ""), self.values)
        self._log(f"verdict: {res.get('verdict')}; warranty: {self.warranty['status']}")
        self._record_run()

    def _run_stand(self, brick) -> dict:
        jid = runner.start(brick)
        while True:
            s = runner.status(jid)
            self.job.update(tried=s["tried"], total=s["total"], percent=s["percent"], stand_elapsed=s["elapsed"])
            self.job["elapsed"] = round(time.time() - self.job["t0"], 1)
            if s["state"] == "done":
                return runner.JOBS[jid]["result"] or {"verdict": "STAND ERROR", "why": "no result"}
            time.sleep(0.3)

    # ---------- what the page reads
    def view(self) -> dict:
        r = self.result or {}
        keep = ("verdict", "why", "design", "guaranteed", "objective", "how", "rests_on", "minimal_conflicts",
                "closest_design", "its_violating_point", "value_there", "overshoot", "reasons", "fails", "limit",
                "find", "decision", "designs_count", "designs_tried", "designs_total", "quantity", "unit",
                "proved", "proved_means", "beyond", "beyond_is", "precision")
        return {"id": self.id, "preset": self.preset["id"], "history": self.history, "question": self.question,
                "files": [{k: f[k] for k in ("name", "kind", "size")} for f in self.files],
                "values": self.values, "warranty": self.warranty, "job": {k: v for k, v in self.job.items()
                                                                          if k != "trace"},
                "result": {k: r[k] for k in keep if k in r}, "brick": self.brick, "usd": round(self.usd, 4),
                "runs": [{"n": x["n"], "at": x["at"], "preset": x["preset"], "question": x["question"],
                          "verdict": (x["result"] or {}).get("verdict"), "status": (x["warranty"] or {}).get("status")}
                         for x in self.runs],
                "spent": meta.spent(), "cap": meta.CAP_USD}


    def run_view(self, n: int) -> dict | None:
        for x in self.runs:
            if x["n"] == n:
                return x
        return None


def get(sid: str) -> Session | None:
    s = SESSIONS.get(sid)
    if s is None and sid.isalnum():
        s = Session.load(sid)
        if s:
            SESSIONS[sid] = s
    return s


def new(preset_id: str = "pump") -> Session:
    s = Session(preset_id)
    SESSIONS[s.id] = s
    return s
