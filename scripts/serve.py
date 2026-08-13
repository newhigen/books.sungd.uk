#!/usr/bin/env python3
"""책장 편집 서버.

정적 파일을 서빙하면서, 태그 편집 화면(tools/tagger.html)이 파일에 바로 저장할 수 있게
몇 가지 창구를 연다. 로컬에서만 쓴다 — 바깥에 열지 말 것.

    python3 scripts/serve.py            # 이 맥에서만
    python3 scripts/serve.py --phone    # 폰에서도 (Tailscale 주소에만 연다)

창구
    POST /api/tags     {tags:{…}, notes:{…}}  → data/tags.json · data/notes.json
    GET  /api/search?q= 알라딘 검색           → 후보 목록
    POST /api/add      {title, sources:[…]}  → sources/manual.json 에 추가
"""
import json, sys, importlib.util
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

REPO = Path(__file__).resolve().parent.parent

# 알라딘 검색은 enrich.py 것을 그대로 쓴다
spec = importlib.util.spec_from_file_location("enrich", REPO / "scripts" / "enrich.py")
enrich = importlib.util.module_from_spec(spec)
_argv = sys.argv[:]          # enrich 가 argv 를 읽으므로 잠시 비웠다가 돌려놓는다
sys.argv = ["enrich.py"]
spec.loader.exec_module(enrich)
sys.argv = _argv


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(REPO), **kw)

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # 편집 화면은 고칠 때마다 바로 보여야 한다
        if self.path.startswith("/tools/") or self.path.startswith("/data/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/search":
            q = (parse_qs(u.query).get("q") or [""])[0].strip()
            if not q:
                return self._json({"error": "검색어가 없다"}, 400)
            try:
                got = enrich.fetch(q)
            except Exception as e:
                return self._json({"error": str(e)}, 502)
            return self._json({"found": got})
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._json({"error": f"본문을 못 읽었다: {e}"}, 400)

        if u.path == "/api/tags":
            # 예전 형태({제목: [태그]})도 받아 준다
            tags = data.get("tags", data if not isinstance(data.get("tags"), dict) else {})
            notes = data.get("notes", {})
            if "tags" not in data and "notes" not in data:
                tags, notes = data, {}
            (REPO / "data" / "tags.json").write_text(
                json.dumps(tags, ensure_ascii=False, indent=1) + "\n")
            notes = {k: v for k, v in notes.items() if str(v).strip()}
            (REPO / "data" / "notes.json").write_text(
                json.dumps(notes, ensure_ascii=False, indent=1) + "\n")
            return self._json({"ok": True, "tags": len(tags), "notes": len(notes)})

        if u.path == "/api/add":
            p = REPO / "sources" / "manual.json"
            cur = json.loads(p.read_text()) if p.exists() else {
                "service": "manual", "collectedAt": "", "books": []}
            title = (data.get("title") or "").strip()
            if not title:
                return self._json({"error": "제목이 없다"}, 400)
            if any(b["title"] == title for b in cur["books"]):
                return self._json({"error": "이미 있는 책"}, 409)
            cur["books"].append({k: v for k, v in data.items() if k != "sources"})
            cur["collectedAt"] = data.get("addedAt", "") or cur.get("collectedAt", "")
            p.write_text(json.dumps(cur, ensure_ascii=False, indent=1) + "\n")
            return self._json({"ok": True, "count": len(cur["books"])})

        return self._json({"error": "모르는 창구"}, 404)


def tailscale_ip():
    """이 맥의 tailnet 주소. 꺼져 있으면 빈 문자열."""
    import subprocess
    for cmd in (["tailscale", "ip", "-4"], ["/Applications/Tailscale.app/Contents/MacOS/Tailscale", "ip", "-4"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=4).stdout.strip()
            if out and out.split("\n")[0].startswith("100."):
                return out.split("\n")[0]
        except Exception:
            pass
    return ""


if __name__ == "__main__":
    args = sys.argv[1:]
    port = int(next((a for a in args if a.isdigit()), 8912))
    # 폰에서 쓰려면 --phone. tailnet 주소에만 연다 — 같은 와이파이의 남에게는 안 열린다.
    want_phone = "--phone" in args

    print(f"책장 편집 서버")
    print(f"  책장   http://localhost:{port}/")
    print(f"  태그   http://localhost:{port}/tools/tagger.html")

    servers = [ThreadingHTTPServer(("127.0.0.1", port), Handler)]
    if want_phone:
        ip = tailscale_ip()
        if not ip:
            print("  ! tailscale 이 꺼져 있다. 켜고 다시 실행할 것.")
        else:
            servers.append(ThreadingHTTPServer((ip, port), Handler))
            print(f"  폰    http://{ip}:{port}/tools/tagger.html   (Tailscale 켠 기기만)")

    import threading
    for srv in servers[1:]:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    servers[0].serve_forever()
