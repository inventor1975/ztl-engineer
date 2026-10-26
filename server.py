#!/usr/bin/env python3
"""ZTL Engineer — the web app. Standard library only.

    python3 server.py [--port 8090]     then open http://localhost:8090

Needs ZTL and ztl-stand cloned beside this repository (or ZTL_ENGINEER_STAND / USTAND_ZTL pointing at them) and a Meta
Model API key in META_API_KEY or ~/.config/meta-api-key.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ztl_engineer import meta, presets, session as SS  # noqa: E402

WEB = HERE / "web"
MAX_BODY = 40 * 1024 * 1024


class H(BaseHTTPRequestHandler):
    server_version = "ZTLEngineer/0.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("[web] " + fmt % a + "\n")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("upload too large (40 MB at most)")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html"):
            return self._file(WEB / "index.html")
        if p in ("/help", "/help.html"):
            return self._file(WEB / "help.html")
        if p.startswith("/static/"):
            f = (WEB / p[len("/static/"):]).resolve()
            if WEB.resolve() in f.parents and f.is_file():
                return self._file(f)
            return self._send(404, {"error": "not found"})
        if p.startswith("/demo/"):
            f = (HERE / "demo" / p[len("/demo/"):]).resolve()
            if (HERE / "demo").resolve() in f.parents and f.is_file():
                return self._file(f)
            return self._send(404, {"error": "not found"})
        if p == "/api/presets":
            return self._send(200, presets.PRESETS)
        if p == "/api/spend":
            return self._send(200, meta.spent() | {"cap": meta.CAP_USD})
        if p.startswith("/api/session/"):
            parts = p.split("/")
            s = SS.get(parts[3])
            if not s:
                return self._send(404, {"error": "no such session"})
            if len(parts) > 5 and parts[4] == "run" and parts[5].isdigit():
                r = s.run_view(int(parts[5]))
                return self._send(200, r) if r else self._send(404, {"error": "no such run"})
            return self._send(200, s.view())
        return self._send(404, {"error": "not found"})

    def _file(self, f: pathlib.Path):
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        return self._send(200, f.read_bytes(), ctype)

    def do_POST(self):
        p = self.path.split("?")[0]
        try:
            d = self._body()
            if p == "/api/session":
                s = SS.new(d.get("preset") or "pump")
                return self._send(200, s.view())
            parts = p.split("/")
            s = SS.get(parts[3]) if len(parts) > 4 else None
            if not s:
                return self._send(404, {"error": "no such session"})
            action = parts[4]
            if action == "file":
                data = base64.b64decode(d["b64"])
                return self._send(200, s.add_file(d["name"], d.get("mime") or "", data))
            if action == "message":
                s.say(d["text"], d.get("preset"))
                return self._send(200, s.view())
            if action == "confirm":
                s.confirm(d["quantity"], d.get("value"))
                return self._send(200, s.view())
            if action == "confirm_all":
                s.confirm_all()
                return self._send(200, s.view())
            return self._send(404, {"error": "unknown action"})
        except RuntimeError as e:
            return self._send(409, {"error": str(e)})
        except (ValueError, KeyError) as e:
            return self._send(400, {"error": f"{type(e).__name__}: {e}"})


def main():
    port = 8090
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.allow_reuse_address = True
    print(f"ZTL Engineer on http://localhost:{port}  (spent ${meta.spent()['usd']:.2f} of ${meta.CAP_USD:.0f})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
