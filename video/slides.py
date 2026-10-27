"""Result slides for the film's montage: each run opened in the app, its Verdict and Details cards captured, set
on a 1920x1080 slide under one title line (no explanation — the screen speaks).

    ~/venvs/video/bin/python video/slides.py      -> video/raw/slide_<n>.png
"""
import base64
import json
import pathlib

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "raw"
URL = "http://localhost:8090"
SLIDES = json.loads((HERE / "slides.json").read_text())

FRAME = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;width:1920px;height:1080px;display:flex;align-items:center;justify-content:center;background:#2f3a4a}
.page{position:relative;width:1760px;height:1000px;border-radius:10px;box-shadow:0 20px 60px rgba(0,0,0,.45);
 background:repeating-linear-gradient(#fdfcf6 0 49px,#c9d6ea 49px 50px);background-color:#fdfcf6;display:flex;flex-direction:column;align-items:center}
.margin{position:absolute;left:150px;top:0;bottom:0;width:3px;background:#e7a3a3}
.ring{position:absolute;left:44px;width:52px;height:52px;border-radius:50%;background:#2f3a4a;box-shadow:inset 0 3px 6px rgba(0,0,0,.6)}
h1{font-family:'DejaVu Serif',Georgia,serif;font-style:italic;font-size:48px;color:#23324d;margin:46px 60px 26px 200px;align-self:flex-start}
.box{margin-left:140px;display:flex;flex-direction:column;gap:20px;align-items:flex-start}
.box img{zoom:1.6;max-width:880px;border-radius:12px;box-shadow:0 6px 18px rgba(24,32,47,.12)}
.n{position:absolute;right:50px;bottom:28px;font-family:'DejaVu Serif',serif;font-style:italic;font-size:30px;color:#7a869a}
</style></head><body><div class="page"><div class="margin"></div>
<div class="ring" style="top:120px"></div><div class="ring" style="top:330px"></div><div class="ring" style="top:540px"></div><div class="ring" style="top:750px"></div>
<h1>__TITLE__</h1><div class="box"><img src="data:image/png;base64,__IMG__"><img src="data:image/png;base64,__KEY__"></div>
<div class="n">__N__</div></div></body></html>"""


def main():
    RAW.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for i, s in enumerate(SLIDES, 1):
            ctx = b.new_context(viewport={"width": 1920, "height": 1400}, device_scale_factor=1)
            ctx.add_init_script(f"try{{localStorage.setItem('ztl-engineer.session','{s['session']}')}}catch(e){{}}")
            pg = ctx.new_page()
            pg.goto(URL)
            pg.wait_for_function("typeof S !== 'undefined' && S && S.id")
            pg.evaluate(f"openRun({s['run']})")
            pg.wait_for_timeout(1200)
            pg.evaluate("document.querySelectorAll('.where, #details details, .downloads').forEach(e => e.style.display='none')")
            head = pg.locator("#verdict").first.screenshot()
            focus = pg.locator(s["focus"]).first
            focus.scroll_into_view_if_needed()
            key = focus.screenshot()
            ctx.close()
            pg = b.new_page(viewport={"width": 1920, "height": 1080})
            pg.set_content(FRAME.replace("__TITLE__", s["title"]).replace("__IMG__", base64.b64encode(head).decode())
                           .replace("__KEY__", base64.b64encode(key).decode()).replace("__N__", f"{i} / {len(SLIDES)}"))
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(RAW / f"slide_{i}.png"))
            pg.close()
            print("slide", i, s["title"])
        b.close()


if __name__ == "__main__":
    main()
