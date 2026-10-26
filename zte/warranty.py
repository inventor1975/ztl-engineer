"""The dirty -> confirmed layer: what the person may rely on, judged by ZTL itself.

The stand proves a design FOR THE DATA AS GIVEN (it says so: "ZTL disposition ON CREDIT ... taken as stated, not
verified"). Here the data are partly read by a model from a photo or a PDF — and a misread digit on a nameplate is
exactly the kind of thing no proof downstream can catch. So every value the model put in is a DIRTY atom of ZTL
(value Z: not ours — the model's reading may be wrong), and only a person's confirmation cleans it (value T).
Values from the person's own CAD files are their own data and enter clean.

The warranty is then a ZTL claim, evaluated by ZTL's own evaluator (a pre-existing dependency):

    earned  =  stand  AND  v1  AND  v2  AND ...

with stand = T when the stand's verdict (EARNED, or REFUTED with its witness) is proved. Zero trust: one dirty value and the conjunction is F — the claim
is not earned, whatever the stand said — and the page names the dirty values it rests on.
"""
from __future__ import annotations

from . import runner  # noqa: F401  (puts ztl-stand, and through it ZTL, on the path)
from ustand import judge_ztl  # noqa: E402,F401  (inserts the ZTL directory into sys.path)
import ztl  # noqa: E402  (ZTL's evaluator: ev(formula, env) over T/F/Z)


def _chain(atoms):
    f = atoms[0]
    for a in atoms[1:]:
        f = ("and", f, a)
    return f


def judge(verdict: str, values: list[dict]) -> dict:
    """values: [{"quantity", "from", "confirmed": bool}]. Returns the warranty the page shows."""
    dirty = [v["quantity"] for v in values if not v.get("confirmed") and v.get("from") not in ("file",)]
    env, atoms = {}, []
    if verdict in ("EARNED", "REFUTED"):
        # `stand` = "the stand's verdict, as stated, is proved" — T for a proof that the design holds AND for a
        # proof that it fails (each with its witness); what is then at stake is only the data under it
        env["stand"] = "T"
        atoms.append("stand")
    else:
        return {"status": verdict, "dirty": dirty,
                "headline": {"OPEN": "OPEN — the stand could not decide it either way",
                             "BRICK ERROR": "The problem could not be posed to the stand",
                             "STAND ERROR": "The stand failed on this problem (its bug, not a verdict)",
                             "STAND FAULT": "The stand's two checkers disagree — do not rely on it"}.get(
                                 verdict, verdict)}
    for i, v in enumerate(values):
        name = f"v{i}"
        env[name] = "Z" if v["quantity"] in dirty else "T"
        atoms.append(name)
    value = ztl.ev(_chain(atoms), env)
    if verdict == "EARNED":
        status = "EARNED" if value == "T" else "ON CREDIT"
        headline = ("Proved: the design holds for every value the tolerances allow — on data you gave in your own files or confirmed"
                    if value == "T" else
                    f"Holds for the values as read — but {len(dirty)} of them are still dirty (read by the model, "
                    "not yet confirmed). Confirm them to earn the result.")
    else:
        status = "REFUTED" if value == "T" else "REFUTED ON CREDIT"
        headline = ("Refuted: the design fails at a concrete point — on data you gave in your own files or confirmed"
                    if value == "T" else
                    f"Fails for the values as read — but {len(dirty)} of them are dirty. A misread value can "
                    "change this; confirm or correct them.")
    return {"status": status, "ztl_value": value, "dirty": dirty, "headline": headline,
            "formula": " AND ".join([f"stand({verdict})"] + [v["quantity"] for v in values])}
