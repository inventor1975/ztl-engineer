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
        state["files"] = [{k: f.get(k) for k in ("name", "mime", "kind", "size", "msg", "preset")} for f in self.files]
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
                          "files": [f["name"] for f in self.active],
                          "result": self.result, "warranty": self.warranty,
                          "values": copy.deepcopy(self.values), "brick": copy.deepcopy(self.brick)})
        self.save()

    # ---------- inputs
    def add_file(self, name: str, mime: str, data: bytes) -> dict:
        """A file waits beside the input box (msg None) until the next message is sent, then belongs to it."""
        name = pathlib.Path(name).name or "file"
        self.files = [f for f in self.files if not (f["name"] == name and f.get("msg") is None)]
        f = {"name": name, "mime": mime, "data": data, "kind": _kind(name, mime), "size": len(data), "msg": None}
        self.files.append(f)
        (STORE / self.id / "files").mkdir(parents=True, exist_ok=True)
        (STORE / self.id / "files" / name).write_bytes(data)
        self.save()
        return {k: f[k] for k in ("name", "kind", "size")}

    def remove_pending(self, name: str):
        self.files = [f for f in self.files if not (f["name"] == name and f.get("msg") is None)]
        self.save()

    def file_data(self, name: str) -> dict | None:
        for f in reversed(self.files):
            if f["name"] == name:
                return f
        return None

    @property
    def active(self) -> list[dict]:
        """The files the current question uses: those sent with the latest message; if it carried none, those of
        the latest message that did — but only while the task in the list is the same. A new task does not
        inherit another task's netlist (measured 26.10: a battery question after the circuit example was sent
        down the circuit road with the old files)."""
        users = [i for i, m in enumerate(self.history) if m["role"] == "user"]
        if not users:
            return []
        own = [f for f in self.files if f.get("msg") == users[-1]]
        if own:
            return own
        for i in reversed(users[:-1]):
            prev = [f for f in self.files if f.get("msg") == i]
            if prev:
                return prev if all(f.get("preset") == self.preset["id"] for f in prev) else []
        return []

    def say(self, text: str, preset_id: str | None = None):
        if self.job["phase"] not in ("idle", "done", "error"):
            raise RuntimeError("a run is already in progress")
        if preset_id:
            self.preset = presets.by_id(preset_id)
        idx = len(self.history)
        sent = [f for f in self.files if f.get("msg") is None]
        for f in sent:
            f["msg"], f["preset"] = idx, self.preset["id"]
        self.history.append({"role": "user", "text": text, "files": [f["name"] for f in sent],
                             "preset": self.preset["id"]})
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

    @property
    def thread(self) -> list[dict]:
        """The conversation the model sees: the messages since the task in the list last changed. An earlier task's
        messages are not this question's context (measured 26.10: after a circuit run, an ADC-budget question was
        answered with 'please paste sensor-divider.cir' — the model read the old task into the new one)."""
        out = []
        for m in reversed(self.history):
            if m.get("preset", self.preset["id"]) != self.preset["id"]:
                break
            out.append(m)
        return list(reversed(out))

    def _pipeline(self):
        # a new question starts with a clean panel: the previous answer stays in self.runs, not on screen as if
        # it were this question's
        self.result = self.warranty = self.brick = None
        self.values, self.question = [], ""
        self.job["phase"] = "reading"
        files = self.active
        bricks = [f for f in files if f["kind"] == "brick"]
        if bricks:
            import json
            self.brick = json.loads(bricks[-1]["data"])
            self.values, self.question = [], self.history[-1]["text"] if self.history else ""
            self._log(f"using your brick {bricks[-1]['name']} as it is")
            reply = "I took your brick file as it is and sent it to the stand."
        else:
            n_img = sum(f["kind"] in ("photo", "pdf") for f in files)
            self._log(f"Muse Spark reads the conversation and {n_img} image/PDF file(s)")
            d = agent.build(self.thread, files, self.preset)
            self.usd += d.get("usd", 0)
            reply = d.get("reply", "")
            self.question = d.get("question", "") or self.question
            if not d.get("ready"):
                self.history.append({"role": "assistant", "text": reply, "preset": self.preset["id"]})
                self._log("the model needs more information")
                return
            if d.get("road") == "cad":
                try:
                    self.brick, self.values = self._from_cad(d), []
                except Exception as e:          # noqa: BLE001 — an importer's refusal is the file's fault, said as such
                    self.history.append({"role": "assistant", "text": reply, "preset": self.preset["id"]})
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
        self.history.append({"role": "assistant", "text": reply, "preset": self.preset["id"]})
        self._judge_with_repair()

    def _from_cad(self, d) -> dict:
        net = [f for f in self.active if f["kind"] == "netlist"]
        if net:
            bom = [f for f in self.active if f["kind"] == "bom"]
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
        deck = [f for f in self.active if f["kind"] == "deck"][-1]
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
        if res.get("verdict") == "OPEN" and self.values:
            # one more agentic step: the reading was too wide; the model rewrites the form (never the data)
            self.job["phase"] = "repairing"
            self._log("OPEN — Muse Spark rewrites the laws so the stand can decide (same numbers)")
            first = res
            d = agent.reformulate(self.brick, " ".join(
                str(x.get("why", "")) for x in (res.get("designs") or [])[:3]) or str(res.get("why")), self.values)
            self.usd += d.get("usd", 0)
            if d.get("brick") and self._same_data(d["brick"]):
                self.job["phase"] = "proving"
                self._log("the ZTL stand judges the rewritten design")
                res2 = self._run_stand(copy.deepcopy(d["brick"]))
                if res2.get("verdict") in ("EARNED", "REFUTED"):
                    self.brick, res = d["brick"], res2
                else:
                    self._log(f"still {res2.get('verdict')} — the first answer stands")
                    res = first
            else:
                self._log("the rewrite changed the data — rejected")
        self.result = res
        self.warranty = warranty.judge(res.get("verdict", ""), self.values)
        self._log(f"verdict: {res.get('verdict')}; warranty: {self.warranty['status']}")
        self._record_run()

    def _same_data(self, new: dict) -> bool:
        """A rewrite may change laws and derived names, never a given's value, tolerance or range."""
        old_q, new_q = (self.brick or {}).get("quantities", {}), new.get("quantities", {})
        keys = ("value", "tolerance", "range")
        for name, q in old_q.items():
            if q.get("role") == "given":
                n = new_q.get(name)
                if not n or any(str(q.get(k)) != str(n.get(k)) for k in keys):
                    return False
        return True

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
                "files": [{k: f.get(k) for k in ("name", "kind", "size", "msg")} for f in self.files],
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
