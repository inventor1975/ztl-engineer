"""The Muse Spark agent: conversation + photos/PDFs/CAD files -> a stand brick, repaired until the stand reads it.

Two roads, chosen by what the person gave:
- CAD files (a SPICE netlist with its BOM, an ANSYS truss deck): the stand's own importers build the brick from
  the file; the model only turns the person's words into the requirement lines those importers take.
- Everything else (a photo of a nameplate, a datasheet PDF, plain words): the model writes the whole brick in the
  stand's format (BRICKS.md, given to it in full), and lists every number it put in with where it read it.

Either way the stand may answer BRICK ERROR (a unit that does not match, a law that does not parse). The agent
then gets the error back and repairs the brick — at most REPAIRS times — before anything is shown as a verdict.
"""
from __future__ import annotations

import json
import re

from . import meta
from .runner import STAND_DIR

REPAIRS = 2
BRICKS_MD = (STAND_DIR / "BRICKS.md").read_text(encoding="utf-8")

ROLE = """You are the reading and modelling half of an engineering design stand. The other half is a proof engine
(the ZTL stand) that takes a JSON "brick" and returns EARNED (the design holds for every value the tolerances
allow), REFUTED (it fails at a concrete point) or OPEN. You never decide the verdict yourself; you build the brick.

Rules:
- Read numbers from the images/documents exactly as printed. Never pass off an invented number as read.
- If a number the problem needs is not given, take a clearly standard value (g = 9.81 m/s^2, water density
  1000 kg/m^3) and label it "assumption". If the person ASKS you to propose or assume values ("make up the
  aircraft", "pick reasonable parameters"), do it: choose typical, defensible values, label every one "assumption"
  with a one-line reason in "where", and build the brick — do not ask for them back.
- If the person states no explicit requirement, pose the natural engineering check for the question (e.g. "the
  smallest static thrust that keeps thrust-to-weight >= 1.1 and sustains level flight at cruise speed"), say so in
  "reply", and build it. Ask ("ready": false) only when even a reasonable assumption cannot fill the gap.
- Every given quantity you put in the brick must appear in "values" with where it came from: "photo", "pdf",
  "user" (the person typed it), "assumption" (a standard value you chose) — and a short "where" (e.g.
  "nameplate: H max 32 m", "datasheet p.2 table 1", "user: 60 m of pipe").
- Use tolerances or ranges when the source gives them; a nameplate value with no tolerance is exact.
- Keep the brick as small as the question needs. Units always. Numbers always as strings.
- If the question truly cannot be posed yet, set "ready": false and ask in "reply" for exactly what is missing.

Answer with ONE JSON object and nothing else:
{"reply": "<2-5 sentences to the person: what you read, what you assumed, what you are checking>",
 "ready": true|false,
 "brick": {<the brick, or null when not ready>},
 "values": [{"quantity": "<name in the brick>", "value": "<as in the brick>", "unit": "<unit>",
             "from": "photo|pdf|user|assumption", "where": "<short>"}],
 "question": "<the question being checked, one line>"}

The stand's brick format, in full:
"""

CAD_ROLE = """You turn a person's words into requirement lines for an engineering stand that already has their
circuit (a SPICE netlist + BOM) or truss (an ANSYS deck). Requirement syntax:
- circuit: "V(node) within LO HI", "V(node) >= X", "I(Rname) <= X", "P(Rname) <= X" (SI units, SPICE suffixes ok)
- truss: [node, "X" or "Y", op, value] for a displacement U(node, dir); op one of <=, >=
Answer with ONE JSON object: {"reply": "<1-3 sentences>", "ready": true|false,
 "requirements": [...], "tolerance": "<truss only: modulus tolerance like 0.5%>", "question": "<one line>"}
The file's contents follow, then the person's words."""


def _json(text: str) -> dict:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise ValueError("the model did not return JSON")
        return json.loads(m.group(0))


def _attachments(files: list[dict]) -> list[dict]:
    parts = []
    for f in files:
        kind = f["kind"]
        if kind == "photo":
            parts.append({"type": "input_text", "text": f"[photo: {f['name']}]"})
            parts.append(meta.image_part(f["data"], f.get("mime") or "image/jpeg"))
        elif kind == "pdf":
            parts.append({"type": "input_text", "text": f"[PDF: {f['name']}, its first pages as images]"})
            parts.extend(meta.pdf_parts(f["data"]))
    return parts


def build(history: list[dict], files: list[dict], preset: dict) -> dict:
    """history: [{"role": "user"|"assistant", "text": ...}]; files: [{"kind","name","data","mime"}].
    Returns the model's JSON plus "usd" (the cost of the calls)."""
    cad = [f for f in files if f["kind"] in ("netlist", "bom", "deck")]
    convo = "\n".join(f"{m['role'].upper()}: {m['text']}"
                      + (f"  [attached: {', '.join(m['files'])}]" if m.get("files") else "") for m in history)
    if cad:
        listing = "\n\n".join(f"--- {f['name']} ---\n{f['data'].decode('utf-8', 'replace')[:20000]}"
                              for f in cad if f["kind"] != "bom")
        out = meta.ask(f"{listing}\n\n--- the conversation ---\n{convo}", instructions=CAD_ROLE, effort="low",
                       max_output_tokens=3000)
        d = _json(out["text"])
        d["usd"], d["road"] = out["usd"], "cad"
        return d
    content = [{"type": "input_text",
                "text": f"Task area picked in the app's list: {preset['title']} — a HINT only. The person may ask about "
                        "something else; the newest message decides what to build.\n\n"
                        "The conversation, newest last. If the newest message starts a new question unrelated to the "
                        "earlier ones, build for the newest message ALONE and do not mention the earlier ones. Answer "
                        "in the language of the newest message.\n\n" + convo}] + _attachments(files)
    out = meta.ask(content, instructions=ROLE + BRICKS_MD, effort="medium", max_output_tokens=12000)
    d = _json(out["text"])
    d["usd"], d["road"] = out["usd"], "model"
    return d


def repair(brick: dict, error: str, values: list[dict]) -> dict:
    """The stand refused the brick (BRICK ERROR): give the model the brick and the stand's reason, get it fixed.
    The values must stay the ones read — a repair fixes form, never the data."""
    msg = ("The stand refused this brick with BRICK ERROR. Fix the brick so the stand can read it. Do NOT change "
           "any number that was read from the person's sources; fix only the form (units, names, laws, roles).\n\n"
           f"The stand's reason: {error}\n\nThe brick:\n{json.dumps(brick, ensure_ascii=False)}\n\n"
           f"The values and their sources:\n{json.dumps(values, ensure_ascii=False)}")
    out = meta.ask(msg, instructions=ROLE + BRICKS_MD, effort="medium", max_output_tokens=12000)
    d = _json(out["text"])
    d["usd"] = out["usd"]
    return d


def reformulate(brick: dict, why: str, values: list[dict]) -> dict:
    """The stand answered OPEN: its interval reading of the bounded quantity was too wide to decide. The usual cause
    is DEPENDENCY — one toleranced quantity appearing several times in the expression (an interval reading cannot
    cancel x - x). Ask the model to rewrite the laws, same physics, same numbers, with each toleranced or ranged
    given appearing as few times as possible in what a requirement bounds (expanded and cancelled by hand), or as a
    SUM of terms each reading few data (the stand proves a sum term by term)."""
    msg = ("The stand could not decide this brick (OPEN). Its reason: " + why + "\n\nRewrite the laws so the stand "
           "can decide: the SAME physics and the SAME numbers, but the quantity each requirement bounds written as one "
           "explicit expression in which every toleranced or ranged given appears AS FEW TIMES AS POSSIBLE — expand "
           "and cancel symbolically (e.g. instead of Vout - Videal with Vin in both, write Vin*(G*k - 10) + ...), or "
           "write it as a SUM of terms that each read few quantities. Do NOT change any value, tolerance or range.\n\n"
           f"The brick:\n{json.dumps(brick, ensure_ascii=False)}\n\nThe values and their sources:\n"
           f"{json.dumps(values, ensure_ascii=False)}")
    out = meta.ask(msg, instructions=ROLE + BRICKS_MD, effort="medium", max_output_tokens=12000)
    d = _json(out["text"])
    d["usd"] = out["usd"]
    return d
