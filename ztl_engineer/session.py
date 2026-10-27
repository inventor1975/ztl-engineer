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
        name = safe_name(name)
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

    def recalc(self, changes: dict):
        """The person edited values in the table and pressed Recalculate: their numbers replace the model's reading
        (the model's is kept as read_as), they become the person's own data (from: "you"), and the stand judges
        again. A value written "[a, b]" or "a .. b" is a range; a single number keeps the quantity's tolerance."""
        import re
        if not changes:
            return
        for v in self.values:
            new = changes.get(v["quantity"])
            if new is None or not str(new).strip() or str(new).strip() == str(v["value"]):
                continue
            new = str(new).strip()
            v["read_as"] = v.get("read_as", v["value"])
            v["value"], v["from"], v["confirmed"] = new, "you", True
            q = (self.brick or {}).get("quantities", {}).get(v["quantity"])
            if q is None:
                continue
            m = re.match(r"^\[?\s*(-?[\d.eE+-]+)\s*(?:,|\.\.|…|\bto\b)\s*(-?[\d.eE+-]+)\s*\]?$", new)
            if m:
                q.pop("value", None); q.pop("tolerance", None)
                q["range"] = [m.group(1), m.group(2)]
            else:
                q.pop("range", None)
                q["value"] = new
        self._start(self._rejudge)

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
            self.job["phase"] = "error"
            self.job["error"] = str(e) if isinstance(e, meta.ModelError) else f"{type(e).__name__}: {e}"
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
        self._cad = None
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
            d = agent.build_agentic(self.thread, files, self.preset, self._check_for_model)
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
        cad = getattr(self, "_cad", None) or {}
        if cad.get("kind") == "truss" and cad.get("ranges") and not (self.brick or {}).get("requirements"):
            self._truss_ranges(cad)
            return
        checks = None if bricks else d.get("checks")
        if checks:
            self._finish_checked(checks)
            return
        self._judge_with_repair()

    def _check_for_model(self, brick: dict) -> dict:
        """Muse Spark's check_design: the stand judges the model's brick (progress shown as for any run)"""
        self.job["phase"] = "proving"
        n = getattr(self, "_model_checks", 0) + 1
        self._model_checks = n
        self._log(f"Muse Spark asks the ZTL stand to check its brick (call {n})")
        res = self._run_stand(copy.deepcopy(brick))
        self._log(f"the stand answers Muse Spark: {res.get('verdict')}")
        self.job["phase"] = "reading"
        return res

    def _finish_checked(self, checks):
        """the model checked its own brick: the answer shown is the stand's answer to the brick the model ended with;
        if its final JSON carries a different brick, the stand judges that one too (the stand decides, not the model)"""
        self._model_checks = 0
        last_brick, res = checks[-1]
        judged = [b for b, r in checks if r.get("verdict") != "BRICK ERROR"]
        same = lambda b: not judged or (agent._givens(b) == agent._givens(judged[0])            # noqa: E731
                                        and agent._reqs(b) == agent._reqs(judged[0]))
        if self.brick and json.dumps(self.brick, sort_keys=True) != json.dumps(last_brick, sort_keys=True) \
                and same(self.brick) and res.get("verdict") not in ("EARNED", "REFUTED"):
            self._log("the final brick differs from the last one checked — the stand judges it")
            self.job["phase"] = "proving"
            res = self._run_stand(copy.deepcopy(self.brick))
        else:
            if self.brick and json.dumps(self.brick, sort_keys=True) != json.dumps(last_brick, sort_keys=True):
                self._log("the final brick differs from the last one checked — the checked one stands")
            self.brick = last_brick
        self.result = res
        self.warranty = warranty.judge(res.get("verdict", ""), self.values)
        self._log(f"verdict: {'FOUND (' + str(res.get('verdict')) + ')' if res.get('find') and res.get('proved') else res.get('verdict')}")
        self._record_run()

    def _truss_ranges(self, cad):
        """The proved range of each asked displacement: each END (min, max) in its own process (truss_end.py says
        why — the judgement does not split, the ends are independent), all side by side. Progress is the stand's
        own line per run on stderr ({"min": {"run": k, "bound": b, "verdict": v}})."""
        import json as _json
        import subprocess as _sp
        import sys as _sys
        import tempfile as _tf
        self.job["phase"] = "proving"
        with _tf.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(cad["text"])
            deck = f.name
        here = pathlib.Path(__file__).resolve().parent.parent
        env = dict(os.environ, PYTHONPATH=f"{here}{os.pathsep}{runner.STAND_DIR}", OPENBLAS_NUM_THREADS="1")
        procs, state, outs = {}, {}, {}
        targets = cad["ranges"][:4]
        for t in targets:
            self._log(f"the stand proves the range of {t}: its two ends in two processes")
            for side in ("min", "max"):
                key = (t, side)
                procs[key] = _sp.Popen([_sys.executable, "-m", "ztl_engineer.truss_end", deck, str(cad["tol"]), t,
                                        side], cwd=str(here), stdout=_sp.PIPE, stderr=_sp.PIPE, text=True, env=env)
                state[key] = {}

                def read_err(key=key):
                    for line in procs[key].stderr:
                        try:
                            state[key] = _json.loads(line).get(key[1]) or state[key]
                        except ValueError:
                            pass

                def read_out(key=key):
                    outs[key] = procs[key].stdout.read()

                threading.Thread(target=read_err, daemon=True).start()
                threading.Thread(target=read_out, daemon=True).start()
        self.job["procs"] = [p.pid for p in procs.values()]
        while any(p.poll() is None for p in procs.values()):
            self.job["elapsed"] = round(time.time() - self.job["t0"], 1)
            done = sum(1 for p in procs.values() if p.poll() is not None)
            runs = sum(int(e.get("runs") or e.get("run") or 0) for e in state.values())
            self.job["note"] = f"{done} of {len(procs)} ends proved · {runs} stand runs so far"
            time.sleep(1.0)
        time.sleep(0.5)
        res = {"verdict": "EARNED", "range_only": True, "exact_range": {},
               "reproduce": [f'python3 -m ustand.truss {cad.get("name", "deck.txt")} --tol {cad["tol"]} --range "{t}"'
                             for t in targets]}
        for t in targets:
            res["exact_range"][t] = {}
            for side in ("min", "max"):
                try:
                    e = _json.loads(outs.get((t, side)) or "").get(side) or {}
                except ValueError:
                    e = {"why": (outs.get((t, side)) or "no answer")[-300:]}
                res["exact_range"][t][side] = {"value": e.get("proved"), "approx": e.get("proved_approx"),
                                               "at": e.get("attained_at"), "exact": e.get("exact"),
                                               "runs": e.get("runs"), "why": e.get("why")}
                if not e.get("proved"):
                    res["verdict"] = "OPEN"
        os.unlink(deck)
        self.result = res
        self.warranty = warranty.judge(res["verdict"], self.values)
        self._log(f"ranges proved: {', '.join(res['exact_range'])}" if res["verdict"] == "EARNED"
                  else f"verdict: {res['verdict']}")
        self._record_run()

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
            text = net[-1]["data"].decode("utf-8", "replace")
            br = SPICE.to_brick(text, table, d.get("requirements") or [])
            # what the requirements bound, for the exact worst case afterwards: "V(adc) within 3.2 3.6" -> V(adc)
            self._cad = {"kind": "spice", "text": text, "bom": table,
                         "targets": [str(r).split()[0] for r in d.get("requirements") or [] if str(r).strip()]}
            return {k: v for k, v in br.items() if not k.startswith("_")}
        deck = [f for f in self.active if f["kind"] == "deck"][-1]
        self._log(f"the stand imports the truss deck {deck['name']}")
        reqs = [tuple(r) for r in d.get("requirements") or []]
        text = deck["data"].decode("utf-8", "replace")
        self._cad = {"kind": "truss", "name": deck["name"], "text": text, "tol": d.get("tolerance") or "0",
                     "ranges": [str(t) for t in d.get("ranges") or []]}
        return TRUSS.to_brick(text, d.get("tolerance") or "0", reqs)

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
        if res.get("verdict") in ("EARNED", "REFUTED") and getattr(self, "_cad", None):
            self._exact_ranges(res)
        self.result = res
        self.warranty = warranty.judge(res.get("verdict", ""), self.values)
        self._log(f"verdict: {'FOUND (' + str(res.get('verdict')) + ')' if res.get('find') and res.get('proved') else res.get('verdict')}")
        self._record_run()

    def _exact_ranges(self, res):
        """An EARNED verdict proves each bounded quantity stays INSIDE its window — when the proof is a certificate,
        the stand reports the window itself as the guaranteed range (measured 26.10: V(adc) 'guaranteed' 3.2..3.6,
        the requirement verbatim). The stand can also find the exact worst case, each end attained at a named point
        (ustand.spice.range_of): the person wants that number, so it is computed and shown beside the verdict."""
        cad, out = self._cad, {}
        self.job["phase"] = "proving"
        for t in cad.get("targets", [])[:4]:
            self._log(f"the stand finds the exact worst case of {t}")
            try:
                with runner._RUN_LOCK:
                    r = SPICE.range_of(cad["text"], cad["bom"], t)
                out[t] = {side: {"value": r[side].get("proved"), "approx": r[side].get("proved_approx"),
                                 "at": r[side].get("attained_at"), "exact": r[side].get("exact")}
                          for side in ("min", "max") if isinstance(r.get(side), dict)}
            except Exception as e:      # noqa: BLE001 — a missing extra is said, the verdict stands
                out[t] = {"error": f"{type(e).__name__}: {e}"}
        if out:
            res["exact_range"] = out

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
            self.job.update(tried=s["tried"], total=s["total"], percent=s["percent"], stand_elapsed=s["elapsed"],
                            note=s.get("note", ""))
            self.job["elapsed"] = round(time.time() - self.job["t0"], 1)
            if s["state"] == "done":
                return runner.JOBS[jid]["result"] or {"verdict": "STAND ERROR", "why": "no result"}
            time.sleep(0.3)

    # ---------- what the page reads
    def view(self) -> dict:
        r = self.result or {}
        keep = ("verdict", "why", "design", "guaranteed", "objective", "how", "rests_on", "minimal_conflicts",
                "closest_design", "its_violating_point", "value_there", "overshoot", "reasons", "fails", "limit",
                "find", "decision", "designs_count", "designs_tried", "designs_total", "quantity", "unit", "exact_range",
                "guaranteed_unit", "range_only", "reproduce",
                "proved", "proved_means", "beyond", "beyond_is", "precision")
        return {"id": self.id, "preset": self.preset["id"], "history": self.history, "question": self.question,
                "files": [{k: f.get(k) for k in ("name", "kind", "size", "msg")} for f in self.files],
                "values": self.values, "warranty": self.warranty, "job": {k: v for k, v in self.job.items()
                                                                          if k != "trace"},
                "result": {k: r[k] for k in keep if k in r}, "brick": self.brick, "usd": round(self.usd, 4),
                "runs": [{"n": x["n"], "at": x["at"], "preset": x["preset"], "question": x["question"],
                          "verdict": "FOUND" if (x["result"] or {}).get("find") and (x["result"] or {}).get("proved")
                          else (x["result"] or {}).get("verdict"), "status": (x["warranty"] or {}).get("status")}
                         for x in self.runs],
                "spent": meta.spent(), "cap": meta.CAP_USD}


    def run_view(self, n: int) -> dict | None:
        for x in self.runs:
            if x["n"] == n:
                return x
        return None


def safe_name(name: str) -> str:
    """a file name that is only a name: no folders, no "." or "..", no quotes or line breaks (it goes into a response
    header), letters/digits/space/._- and nothing else, at most 120 characters (security review, 2026-10-27)"""
    import re
    base = pathlib.Path(str(name).replace("\\", "/")).name
    base = re.sub(r"[^\w .\-]", "_", base).strip(" .")[:120]
    return base or "file"


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
