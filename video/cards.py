"""Title and end cards (1920x1080 PNG), in the app's own light colours."""
import pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
BASE = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;width:1920px;height:1080px;display:flex;flex-direction:column;align-items:center;justify-content:center;
font-family:'Inter','Segoe UI',system-ui,sans-serif;color:#18202f;background:radial-gradient(1400px 700px at 15% 0%,#eaf0fb,transparent),#f4f6fb}
.logo{width:120px;height:120px;border-radius:30px;display:grid;place-items:center;color:#fff;font-size:64px;font-weight:800;
background:linear-gradient(135deg,#3b5bdb,#8b5cf6);box-shadow:0 20px 50px rgba(59,91,219,.3)}
h1{font-size:96px;margin:40px 0 10px;letter-spacing:-2px}.sub{font-size:40px;color:#5d6879}
.line{font-size:30px;color:#5d6879;margin-top:14px}.url{font-size:40px;color:#3b5bdb;font-weight:700;margin-top:40px}
.chips{display:flex;gap:18px;margin-top:46px}.chip{font-size:26px;font-weight:700;padding:10px 24px;border-radius:999px;color:#fff}
small{position:absolute;bottom:40px;font-size:20px;color:#8a93a3}
.stats{display:flex;flex-direction:column;gap:46px;width:1720px}.stat{display:grid;grid-template-columns:600px 1fr;align-items:baseline}
.stat b{font-size:88px;letter-spacing:-2px;color:#3b5bdb;white-space:nowrap}.stat span{font-size:40px}.stat i{grid-column:2;font-size:22px;color:#8a93a3;font-style:normal}
.opts{display:flex;gap:40px}.opt{width:440px;padding:40px;border-radius:24px;background:#fff;box-shadow:0 12px 40px rgba(24,32,47,.08);display:flex;flex-direction:column;gap:12px}
.opt b{font-size:46px}.opt span{font-size:34px;color:#18202f}.opt i{font-size:26px;color:#d64545;font-style:normal}</style></head><body>__BODY__</body></html>"""
CARDS = {
 "title": """<div class="logo">Z</div><h1>ZTL Engineer</h1><div class="sub">Muse Spark reads · ZTL proves</div>
   <div class="chips"><span class="chip" style="background:#1f9d55">EARNED</span><span class="chip" style="background:#d64545">REFUTED</span>
   <span class="chip" style="background:#6b7280">OPEN</span></div>""",
 "problem": """<div class="stats">
   <div class="stat"><b>2.1 billion</b><span>people lack safely managed drinking water</span><i>WHO/UNICEF JMP, 2025 report (2024 data)</i></div>
   <div class="stat"><b>666 million</b><span>people have no electricity</span><i>Tracking SDG7, 2025 report (2023 data)</i></div>
   <div class="stat"><b>&lt; 5</b><span>engineers per 10,000 people in developing countries</span><i>UNESCO estimate, as reported</i></div>
   </div>""",
 "options": """<div class="opts">
   <div class="opt"><b>Engineer</b><span>$40–150 an hour</span><i>freelance rates</i></div>
   <div class="opt"><b>Seller's tool</b><span>its own catalogue</span><i>nominal values</i></div>
   <div class="opt"><b>AI chat</b><span>sounds sure</span><i>shows no proof</i></div>
   </div><div class="logo" style="margin-top:70px;width:90px;height:90px;font-size:48px;border-radius:24px">Z</div>
   <div class="sub" style="margin-top:16px">ZTL Engineer — Muse Spark reads · ZTL proves</div>""",
 "end": """<div class="logo">Z</div><h1>ZTL Engineer</h1>
   <div class="line">Built during the Meta Global AI Developer Hackathon: the app and the Muse Spark agent.</div>
   <div class="line">ZTL and ztl-stand: the author's earlier open-source work (Apache-2.0).</div>
   <div class="url">github.com/inventor1975/ztl-engineer</div>
   <small>Vitaly Reznik · Muse Spark 1.3 (Meta Model API) · code written with Claude (Anthropic) · voice synthesized (Kokoro-82M)</small>""",
}
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1920, "height": 1080})
    for k, body in CARDS.items():
        pg.set_content(BASE.replace("__BODY__", body)); pg.wait_for_timeout(300)
        pg.screenshot(path=str(HERE / "raw" / f"card_{k}.png")); print(k)
    b.close()
