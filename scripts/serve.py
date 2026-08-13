#!/usr/bin/env python3
"""책장 편집 서버.

정적 파일을 서빙하면서, 태그 편집 화면(tools/tagger.html)이 파일에 바로 저장할 수 있게
몇 가지 창구를 연다. 로컬에서만 쓴다 — 바깥에 열지 말 것.

    python3 scripts/serve.py            # http://localhost:8912
    python3 scripts/serve.py 9000

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
sys.argv = ["enrich.py"]
spec.loader.exec_module(enrich)


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


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8912
    print(f"책장 편집 서버 · http://localhost:{port}")
    print(f"  책장   http://localhost:{port}/")
    print(f"  태그   http://localhost:{port}/tools/tagger.html")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
