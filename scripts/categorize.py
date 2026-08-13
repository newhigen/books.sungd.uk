#!/usr/bin/env python3
"""책마다 분야와 태그를 붙인다.

알라딘 상세 페이지의 분류 경로(`국내도서 > 자기계발 > 성공 > 성공학`)를 가져와
2단계를 분야로, 그 아래 단계를 태그로 쓴다. 한 책이 여러 분류에 걸리면 분야는
가장 앞선 것, 태그는 전부 모은다.

    python3 scripts/categorize.py            # 아직 안 붙인 책만
    python3 scripts/categorize.py --limit 5
"""
import json, re, sys, time, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "data" / "library.json"
COVERS = REPO / "data" / "covers.json"
OUT = REPO / "data" / "categories.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

# 맨 위 칸은 분야가 아니라 서점의 매장 구분이라 버린다
STORE = {"국내도서", "외국도서", "eBook", "중고", "전자책"}


def paths_of(html):
    m = re.search(r'<ul id="ulCategory">(.*?)</ul>', html, re.S)
    if not m:
        return []
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S):
        names = [re.sub(r"<[^>]+>", "", a).strip() for a in re.findall(r"<a[^>]*>(.*?)</a>", li, re.S)]
        names = [n for n in names if n and n != "접기" and len(n) < 30]
        if len(names) >= 2:
            out.append(names)
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 0

    lib = json.loads(LIB.read_text())
    done = json.loads(OUT.read_text()) if OUT.exists() else {}

    todo = [b for b in lib["books"] if b.get("aladin") and b["title"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"분류 대상 {len(todo)}권 (이미 {len(done)}권)")

    for i, b in enumerate(todo, 1):
        try:
            paths = paths_of(fetch(b["aladin"]))
        except Exception as e:
            print(f"  ! {b['title'][:24]} — {e}")
            paths = []

        trimmed = [[n for n in p if n not in STORE] for p in paths]
        trimmed = [p for p in trimmed if p]
        field = trimmed[0][0] if trimmed else ""
        tags = []
        for p in trimmed:
            for n in p[1:]:
                if n not in tags:
                    tags.append(n)

        done[b["title"]] = {"field": field, "tags": tags[:6], "paths": trimmed}
        mark = f"{field} · {'/'.join(tags[:3])}" if field else "분류 없음"
        print(f"  {i:3d}/{len(todo)} {b['title'][:26]:<28} → {mark}")

        if i % 10 == 0:
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
        time.sleep(0.6)

    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
    fields = {}
    for v in done.values():
        if v["field"]:
            fields[v["field"]] = fields.get(v["field"], 0) + 1
    print("\n분야별:", ", ".join(f"{k} {v}" for k, v in sorted(fields.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
