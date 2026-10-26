"""Scripted screen recording of ZTL Engineer for the demo video (Playwright, headless Chromium, 1920x1080).

A headless recording has no system cursor, so the page gets its own: an arrow that glides to each target and a
ripple on every click. Every scene writes a log of when things happened (seconds from the scene's start), which the
editing step (make.py) uses to cut the waits and lay the narration over the right moments.

    ~/venvs/video/bin/python video/rec.py SCENE [--session ID]     -> video/raw/SCENE.webm + SCENE.json
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "raw"
URL = "http://localhost:8090"
W, H = 1920, 1080

CURSOR_JS = """
(() => {
  if (window.__curInit) return; window.__curInit = true;
  const add = () => {
    const c = document.createElement('div');
    c.id = '__cur';
    c.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.6L20 11z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'960px', top:'540px', zIndex:2147483647, pointerEvents:'none',
      transition:'left .6s cubic-bezier(.3,.1,.2,1), top .6s cubic-bezier(.3,.1,.2,1)', filter:'drop-shadow(0 2px 3px rgba(0,0,0,.35))'});
    document.body.appendChild(c);
  };
  if (document.body) add(); else document.addEventListener('DOMContentLoaded', add);
  window.__move = (x, y, ms) => { const c = document.getElementById('__cur'); if (!c) return;
    c.style.transition = `left ${ms}ms cubic-bezier(.3,.1,.2,1), top ${ms}ms cubic-bezier(.3,.1,.2,1)`;
    c.style.left = (x - 3) + 'px'; c.style.top = (y - 2) + 'px'; };
  window.__ripple = (x, y) => { const r = document.createElement('div');
    Object.assign(r.style, {position:'fixed', left:(x-22)+'px', top:(y-22)+'px', width:'44px', height:'44px', borderRadius:'50%',
      border:'3px solid #3b5bdb', background:'rgba(59,91,219,.18)', zIndex:2147483646, pointerEvents:'none',
      transform:'scale(.3)', opacity:'1', transition:'transform .45s ease-out, opacity .55s ease-out'});
    document.body.appendChild(r); requestAnimationFrame(() => { r.style.transform = 'scale(1.6)'; r.style.opacity = '0'; });
    setTimeout(() => r.remove(), 700); };
})();
"""


class Rec:
    def __init__(self, page, name):
        self.page, self.name, self.t0, self.log = page, name, time.time(), []
        self.pos = (W // 2, H // 2)

    def mark(self, what, **kw):
        self.log.append({"t": round(time.time() - self.t0, 2), "what": what, **kw})
        print(f"[{self.log[-1]['t']:7.2f}] {what} {kw if kw else ''}", flush=True)

    def wait(self, s):
        self.page.wait_for_timeout(int(s * 1000))

    def move(self, sel=None, x=None, y=None, ms=650):
        if sel is not None:
            loc = self.page.locator(sel).first
            loc.scroll_into_view_if_needed()
            b = loc.bounding_box()
            x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        self.page.evaluate(f"window.__move({x}, {y}, {ms})")
        self.wait(ms / 1000 + 0.15)
        self.pos = (x, y)

    def click(self, sel, wait_after=0.6):
        self.move(sel)
        self.page.evaluate(f"window.__ripple({self.pos[0]}, {self.pos[1]})")
        self.wait(0.18)
        self.page.locator(sel).first.click()
        self.wait(wait_after)

    def type(self, sel, text, delay=28):
        self.click(sel, wait_after=0.2)
        self.page.locator(sel).first.press_sequentially(text, delay=delay)

    def scroll_to(self, sel, block="center"):
        self.page.locator(sel).first.evaluate(f"e => e.scrollIntoView({{behavior: 'smooth', block: '{block}'}})")
        self.wait(1.0)

    def until(self, js, timeout=1200, every=0.5):
        t = time.time()
        while time.time() - t < timeout:
            if self.page.evaluate(js):
                return True
            self.wait(every)
        return False


def session_of(page):
    return page.evaluate("localStorage.getItem('ztl-engineer.session')")


# ------------------------------------------------------------------ scenes
DONE = "typeof S !== 'undefined' && S && ['done','error'].includes(S.job.phase)"


def scene_pump(r: Rec):
    p = r.page
    r.mark("start")
    r.wait(1.5)
    r.move("#preset")
    p.select_option("#preset", "pump")
    p.dispatch_event("#preset", "change")
    r.mark("task picked")
    r.wait(1.2)
    r.click("#useEx", wait_after=1.5)
    r.mark("example + nameplate attached")
    r.click("#send", wait_after=0.5)
    r.mark("sent")
    r.until(DONE, timeout=300)
    r.mark("verdict")
    r.wait(1.0)
    r.scroll_to("#verdict")
    r.move("#verdict")
    r.wait(2.0)
    r.move("#vals tr:first-child")
    r.mark("values")
    for i in range(1, 4):
        r.move(f"#vals tr:nth-child({i}) .where", ms=450)
        r.wait(0.6)
    r.wait(1.5)
    r.mark("end")


def scene_borehole(r: Rec):
    """the film's main case: a village borehole, the question in French, the first (seller's) solar pump"""
    p = r.page
    r.mark("start")
    r.wait(1.2)
    r.move("#preset")
    p.select_option("#preset", "borehole")
    p.dispatch_event("#preset", "change")
    r.mark("task picked")
    r.wait(1.2)
    r.click("#useEx", wait_after=1.8)
    r.mark("example + nameplate attached")
    r.move("#text")
    r.wait(1.5)
    r.click("#send", wait_after=0.5)
    r.mark("sent")
    r.until(DONE, timeout=300)
    r.mark("verdict")
    r.wait(0.8)
    r.scroll_to("#verdict")
    r.move("#verdict")
    r.wait(2.0)
    r.scroll_to("#detailsCard", block="start")
    r.move("#details .limit")
    r.mark("range")
    r.wait(3.0)
    r.scroll_to("#valuesCard", block="start")
    q = p.evaluate("(S.values.find(v => /draw/i.test(v.quantity)) || S.values[0]).quantity")
    r.move(f'#vals input[data-q="{q}"]')
    r.wait(2.0)
    r.mark("end")


def scene_borehole2(r: Rec):
    """continues the borehole session: a second plate attached, "Et celle-ci ?" """
    p = r.page
    r.mark("start")
    r.wait(1.0)
    r.scroll_to("#text")
    with p.expect_file_chooser() as fc:
        r.click("#attach", wait_after=0.3)
    fc.value.set_files(str(HERE.parent / "demo" / "nameplate-solar-sp750.png"))
    r.wait(1.5)
    r.mark("second plate attached")
    r.type("#text", "Et celle-ci ?", delay=90)
    r.wait(0.6)
    r.click("#send", wait_after=0.5)
    r.mark("sent")
    r.until(DONE, timeout=300)
    r.mark("verdict")
    r.wait(0.8)
    r.scroll_to("#verdict")
    r.move("#verdict")
    r.wait(2.0)
    r.scroll_to("#detailsCard", block="start")
    r.move("#details .kv")
    r.wait(3.0)
    r.mark("end")


def scene_fix(r: Rec):
    """continues the pump session: the person corrects the rated head and recalculates"""
    p = r.page
    r.mark("start")
    r.wait(1.0)
    r.scroll_to("#valuesCard", block="start")
    q = p.evaluate("(S.values.find(v => /rated/i.test(v.quantity) && /h/i.test(v.quantity)) || {}).quantity")
    sel = f'#vals input[data-q="{q}"]'
    r.mark("edit", quantity=q)
    r.click(sel, wait_after=0.2)
    p.locator(sel).fill("")
    p.locator(sel).press_sequentially("21", delay=120)
    p.locator(sel).dispatch_event("input")
    r.wait(0.8)
    r.click("#recalc", wait_after=0.5)
    r.mark("recalc")
    r.until(DONE, timeout=300)
    r.mark("verdict")
    r.scroll_to("#verdict")
    r.move("#verdict")
    r.wait(2.0)
    r.scroll_to("#detailsCard", block="start")
    r.move("#details")
    r.wait(3.0)
    r.mark("end")


def _pick_and_send(r: Rec, preset, timeout):
    p = r.page
    r.move("#preset")
    p.select_option("#preset", preset)
    p.dispatch_event("#preset", "change")
    r.mark("task picked", preset=preset)
    r.wait(1.5)
    r.move("#hint")
    r.wait(1.5)
    r.click("#useEx", wait_after=1.5)
    r.mark("example in")
    r.click("#send", wait_after=0.5)
    r.mark("sent")
    r.until(DONE, timeout=timeout, every=1.0)
    r.mark("verdict")


def scene_published(r: Rec):
    r.mark("start")
    r.wait(1.0)
    _pick_and_send(r, "pub-tps25221", 300)
    r.wait(0.8)
    r.scroll_to("#verdict")
    r.move("#verdict .head")
    r.wait(2.0)
    r.move("#verdict .why")
    r.wait(2.0)
    r.scroll_to("#detailsCard", block="start")
    r.move("#details .limit")
    r.wait(3.0)
    r.mark("end")


def scene_heavy(r: Rec):
    r.mark("start")
    r.wait(1.0)
    _pick_and_send(r, "heavy-bridge", 1800)
    r.wait(0.8)
    r.scroll_to("#verdict")
    r.move("#verdict")
    r.wait(2.0)
    r.scroll_to("#detailsCard", block="start")
    r.move("#details .limit")
    r.wait(2.5)
    r.move("#details .kv")
    r.wait(2.5)
    r.mark("end")


def scene_muhanna(r: Rec):
    """Muhanna's interval-FEM benchmark: the proved range of the top corner over 2^101 tolerance corners"""
    r.mark("start")
    r.wait(1.0)
    _pick_and_send(r, "heavy-muhanna", 1800)
    r.wait(0.8)
    r.scroll_to("#verdict")
    r.move("#verdict")
    r.wait(2.0)
    r.scroll_to("#detailsCard", block="start")
    r.move("#details .limit")
    r.wait(3.0)
    r.move("#details .limit:last-of-type")
    r.wait(3.0)
    r.mark("end")


def scene_reproduce(r: Rec):
    """the latest run's downloads: the report shown, the brick re-run on the stand alone (real output)"""
    import subprocess
    p = r.page
    r.mark("start")
    r.wait(1.0)
    r.scroll_to("#verdict")
    r.move("#verdict .downloads a")
    r.wait(1.2)
    sid = p.evaluate("S.id")
    n = p.evaluate("(S.runs.filter(x => x.verdict === 'EARNED').pop() || S.runs[S.runs.length-1]).n")
    if p.evaluate(f"S.runs[S.runs.length-1].n") != n:          # show that run in the page before its downloads
        p.locator(f'[data-run="{n}"]').click()
        r.wait(1.0)
        r.scroll_to("#verdict")
        r.move("#verdict .downloads a")
    report = p.evaluate(f"fetch('/api/session/{sid}/run/{n}/report.html').then(r => r.text())")
    brick = p.evaluate(f"fetch('/api/session/{sid}/run/{n}/brick.json').then(r => r.text())")
    r.page.evaluate(f"window.__ripple({r.pos[0]}, {r.pos[1]})")
    r.mark("report")
    p.set_content(report)
    p.add_script_tag(content=CURSOR_JS)
    r.wait(0.5)
    r.move(x=960, y=300, ms=400)
    for y in (300, 700, 1100):
        p.mouse.wheel(0, 400)
        r.wait(1.4)
    r.mark("terminal")
    bp = HERE / "raw" / "brick.json"
    bp.write_text(brick)
    t = time.time()
    out = subprocess.run([sys.executable.replace("venvs/video", "venvs/torch") if False else "python3", "-m", "ustand.stand",
                          str(bp)], cwd=str(HERE.parent.parent / "ztl-stand"), capture_output=True, text=True).stdout
    secs = round(time.time() - t, 1)
    d = json.loads(out)
    lines = [f'"verdict": "{d.get("verdict")}"']
    for k in ("proved", "design", "guaranteed", "objective"):
        if d.get(k):
            lines.append(f'"{k}": ' + json.dumps(d[k], ensure_ascii=False)[:150] + ("…" if len(json.dumps(d[k])) > 150 else ""))
    term = TERMINAL_HTML.replace("__OUT__", "\n".join(lines).replace("<", "&lt;")).replace("__SECS__", str(secs))
    p.set_content(term)
    p.add_script_tag(content=CURSOR_JS)
    r.wait(9.0)
    r.mark("end", verdict=d.get("verdict"), seconds=secs)


TERMINAL_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#1e1f24;color:#e6e6e6;font:34px/1.5 'DejaVu Sans Mono',monospace;padding:70px 90px}
.bar{color:#9aa0aa;font:24px sans-serif;margin-bottom:30px}.p{color:#7ee787}.c{color:#79c0ff}
#cmd{white-space:pre}#out{white-space:pre-wrap;color:#d2a8ff;opacity:0;transition:opacity .6s;margin-top:18px}
.v{color:#7ee787;font-weight:700}</style></head><body>
<div class="bar">terminal — the stand alone, no AI, no app</div>
<div><span class="p">$</span> <span class="c">cd ztl-stand</span></div>
<div><span class="p">$</span> <span id="cmd" class="c"></span></div>
<div id="out">__OUT__

<span class="v">done in __SECS__ s — the same verdict the app showed</span></div>
<script>
const cmd = "python3 -m ustand.stand brick.json"; let i = 0;
const t = setInterval(() => { document.getElementById('cmd').textContent = cmd.slice(0, ++i);
  if (i >= cmd.length) { clearInterval(t); setTimeout(() => document.getElementById('out').style.opacity = 1, 700); } }, 70);
</script></body></html>"""


SCENES = {"borehole": scene_borehole, "borehole2": scene_borehole2, "pump": scene_pump, "fix": scene_fix, "published": scene_published, "heavy": scene_heavy, "muhanna": scene_muhanna,
          "reproduce": scene_reproduce}


def main():
    name = sys.argv[1]
    sid = sys.argv[sys.argv.index("--session") + 1] if "--session" in sys.argv else None
    RAW.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(RAW / "tmp"),
                            record_video_size={"width": W, "height": H}, color_scheme="light")
        init = CURSOR_JS + (f"\ntry{{localStorage.setItem('ztl-engineer.session','{sid}')}}catch(e){{}}" if sid
                            else "\ntry{if(!sessionStorage.getItem('__fresh')){localStorage.removeItem('ztl-engineer.session');sessionStorage.setItem('__fresh','1')}}catch(e){}")
        ctx.add_init_script(init)
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_function("typeof S !== 'undefined' && S && S.id")
        r = Rec(page, name)
        SCENES[name](r)
        log = {"scene": name, "session": session_of(page), "events": r.log}
        video = page.video
        ctx.close()
        b.close()
        src = pathlib.Path(video.path())
        dst = RAW / f"{name}.webm"
        src.replace(dst)
        (RAW / f"{name}.json").write_text(json.dumps(log, indent=1))
        print("saved", dst, "session", log["session"])


if __name__ == "__main__":
    main()
