"""Downloadable results of one run: a readable report (HTML, prints to PDF), the full results (JSON), the brick.

The brick is the reproducible part: with it, anyone can re-run the proof on ztl-stand alone — no model, no app —
and get the same verdict:  python3 -m ustand.stand brick.json
"""
from __future__ import annotations

import html
import json
import re

from . import meta, runner

H = html.escape


def _approx(v) -> str:
    """The stand writes "exact fraction (~approx)"; a person reads the approximation."""
    if isinstance(v, list):
        return " … ".join(_approx(x) for x in v)
    if isinstance(v, dict):
        return ", ".join(f"{k} {_approx(x)}" for k, x in v.items())
    s = str(v)
    m = re.search(r"\(~([^)\s]+)\)", s) or re.match(r"^~(\S+)", s)
    return f"≈ {m.group(1)}" if m else s


def _choice(d) -> str:
    """{"catalog":"engines","T":{"nominal":"60","tolerance":"0"}} -> "T 60 (engines)"."""
    if not isinstance(d, dict):
        return _approx(d)
    cat, item, parts = d.get("catalog", ""), "", []
    for k, v in d.items():
        if k == "catalog":
            continue
        if k in ("item", "name", "part", "id"):
            item = str(v)
        elif isinstance(v, dict) and "nominal" in v:
            t = str(v.get("tolerance", "0")).split(" ")[0]
            try:
                num, _, den = t.partition("/")
                tv = float(num) / float(den or 1)
            except ValueError:
                tv = 0
            parts.append(f"{k} {_approx(v['nominal'])}" + (f" ±{tv * 100:g}%" if tv else ""))
        else:
            parts.append(f"{k} {_approx(v)}")
    return " ".join(x for x in (item, ", ".join(parts), f"({cat})" if cat else "") if x)


def _ztl_commit() -> str:
    try:
        from ustand import judge_ztl
        return judge_ztl.ztl_commit()
    except Exception:          # noqa: BLE001
        return "?"


def _stand_commit() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(runner.STAND_DIR), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip() or "?"
    except Exception:          # noqa: BLE001
        return "?"


def bundle(session, run: dict) -> dict:
    return {"app": "ZTL Engineer", "session": session.id, "run": run["n"], "time": run["at"],
            "question": run["question"], "task": run["preset"], "files": run.get("files", []),
            "model": meta.MODEL, "stand": f"ztl-stand {_stand_commit()}", "judge": f"ZTL {_ztl_commit()}",
            "verdict": (run.get("result") or {}).get("verdict"), "values": run.get("values"),
            "brick": run.get("brick"), "stand_answer": run.get("result")}


def html_report(session, run: dict) -> str:
    r = run.get("result") or {}
    b = run.get("brick") or {}
    Q = b.get("quantities", {})
    verdict = r.get("verdict", "—")
    color = {"EARNED": "#1f9d55", "REFUTED": "#d64545"}.get(verdict, "#6b7280")
    head = {"EARNED": "Proved: the design holds for every value the tolerances allow.",
            "REFUTED": "Refuted: the design fails at a concrete point.",
            "OPEN": "Undecided: the stand could not prove it either way."}.get(verdict, str(r.get("why", "")))
    rows = []

    def sec(title, body):
        rows.append(f"<h2>{H(title)}</h2>{body}")

    def kv(d):
        return "<table>" + "".join(f"<tr><th>{H(str(k))}</th><td>{H(_approx(v))}</td></tr>" for k, v in d.items()) \
            + "</table>"

    reqs = b.get("requirements") or []
    if reqs:
        sec("What was checked", "<ul>" + "".join(
            f"<li><b>{H(q.get('quantity', ''))}</b> {H(str(q.get('op', '')))} "
            f"{H(' … '.join(q['value']) if isinstance(q.get('value'), list) else str(q.get('value', '')))} "
            f"{H(Q.get(q.get('quantity'), {}).get('unit', ''))}"
            f"{(' — ' + H(q['why'])) if q.get('why') else ''}</li>" for q in reqs) + "</ul>")
    if r.get("find") and r.get("proved"):
        sec(f"{'Largest' if r['find'] == 'largest' else 'Smallest'} {r.get('quantity', '')} that works",
            f"<p class='big'>{H(_approx(r['proved']))} {H(r.get('unit', ''))}</p><p>{H(r.get('proved_means', ''))}</p>"
            f"<p>{H(r.get('beyond_is', ''))}</p>")
    if r.get("exact_range"):
        sec("Exact worst case", "".join(
            f"<p><b>{H(t)}</b>: {H(_approx((e.get('min') or {}).get('value')))} … "
            f"{H(_approx((e.get('max') or {}).get('value')))}<br><small>min at {H(_approx((e.get('min') or {}).get('at') or {}))}"
            f"; max at {H(_approx((e.get('max') or {}).get('at') or {}))}</small></p>"
            for t, e in r["exact_range"].items() if not e.get("error")))
    ob = r.get("objective") or {}
    if ob.get("value") is not None:
        sec("Optimal" if ob.get("optimal") else "Best found",
            f"<p class='big'>{H(_approx(ob['value']))} {H(ob.get('unit', ''))}</p><p>minimize {H(ob.get('minimize', ''))}"
            f" — {H(ob.get('note', ''))}</p>")
    if r.get("design"):
        sec("Chosen design", kv({k: _choice(v) for k, v in r["design"].items()}))
    if r.get("guaranteed"):
        sec("Proved to stay within", kv(r["guaranteed"]) + (
            "<p><small>" + "<br>".join(f"{H(k)}: {H(v)}" for k, v in (r.get("how") or {}).items()) + "</small></p>"))
    if r.get("closest_design"):
        sec("Closest design", kv({k: _choice(v) for k, v in r["closest_design"].items()}))
    if r.get("its_violating_point"):
        sec("Where it fails", kv(r["its_violating_point"]) + (kv(r["value_there"]) if r.get("value_there") else ""))
    mc = (r.get("minimal_conflicts") or {}).get("sets") or []
    one, many = [x for x in mc if len(x) == 1], [x for x in mc if len(x) > 1]
    if one:
        sec("Fails on its own", "<ul>" + "".join(f"<li>{H(x[0])}</li>" for x in one) + "</ul>")
    if many:
        sec("Cannot hold together — relax one of each group", "<ul>" + "".join(
            f"<li>{H(' + '.join(x))}</li>" for x in many) + "</ul>")
    vals = run.get("values") or []
    if vals:
        sec("Values the answer rests on", "<table><tr><th>Quantity</th><th>Value</th><th>Source</th></tr>" + "".join(
            f"<tr><td><b>{H(v['quantity'])}</b></td><td>{H(str(v.get('value')))} {H(v.get('unit') or '')}"
            f"{(' ±' + H(str(round(float(Q[v['quantity']]['tolerance']) * 100, 4))) + '%') if Q.get(v['quantity'], {}).get('tolerance') not in (None, '') and str(Q[v['quantity']]['tolerance']).replace('.', '', 1).isdigit() else ''}"
            f"{(' <small>(AI read ' + H(str(v['read_as'])) + ')</small>') if v.get('read_as') else ''}</td>"
            f"<td>{'yours' if v.get('from') in ('file', 'you') else 'AI read'} — {H(v.get('where') or v.get('from') or '')}</td></tr>"
            for v in vals) + "</table>")
    b_json = H(json.dumps(b, ensure_ascii=False, indent=1))
    r_json = H(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ZTL Engineer — run {run['n']}</title>
<style>body{{font-family:Georgia,'DejaVu Serif',serif;max-width:860px;margin:30px auto;padding:0 20px;color:#1a1a1a;line-height:1.5}}
h1{{font-size:24px;margin:0}}h2{{font-size:17px;margin-top:26px;border-bottom:1px solid #ddd;padding-bottom:4px}}
.verdict{{border-left:6px solid {color};background:#f6f7f9;padding:12px 16px;margin:16px 0}}
.chip{{display:inline-block;background:{color};color:#fff;font-weight:700;padding:2px 10px;border-radius:999px;font-family:sans-serif;font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid #eee;vertical-align:top}}
.big{{font-size:22px;font-weight:700}}pre{{font-size:11px;background:#f6f7f9;padding:10px;overflow:auto;white-space:pre-wrap}}
.meta{{color:#555;font-size:13px}}small{{color:#555}}</style></head><body>
<h1>ZTL Engineer — run {run['n']}</h1>
<p class="meta">{H(run['at'])} · task: {H(run['preset'])} · model: {H(meta.MODEL)} · stand: ztl-stand {H(_stand_commit())} · judge: ZTL {H(_ztl_commit())}</p>
<p><b>Question:</b> {H(run['question'])}</p>
<div class="verdict"><span class="chip">{H(verdict)}</span> <b>{H(head)}</b><br><small>{H(str(r.get('why') or ''))}</small></div>
{''.join(rows)}
<h2>Reproduce it</h2><p>Save the brick below as <code>brick.json</code> and run the stand alone — no model, no app:
<code>python3 -m ustand.stand brick.json</code> (ztl-stand and ZTL from github.com/inventor1975).</p>
<details><summary>The brick</summary><pre>{b_json}</pre></details>
<details><summary>The stand's full answer</summary><pre>{r_json}</pre></details>
<p class="meta">Values marked "AI read" were read or assumed by Muse Spark from the person's words or files; the
proof holds for those values as stated.</p></body></html>"""
