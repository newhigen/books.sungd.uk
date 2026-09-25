#!/usr/bin/env python3
"""한국어판 출간일을 가장 이른 판으로 바로잡는다.

책에 걸린 알라딘 링크는 우리가 가진 판이고, 그게 재출간이면 출간일이 최근이다
(「진작 이렇게 책을 읽었더라면」이 2026-05 로 섰지만 초판은 2020-11 이다).
제목과 저자로 알라딘을 검색해 같은 책의 판을 모두 찾고 그중 가장 이른 날을 쓴다.

  python3 scripts/earliest.py            원서 연도가 없는 책만 (원서가 있으면 그게 이긴다)
  python3 scripts/earliest.py --all      전부
  python3 scripts/earliest.py --limit 10 시험 삼아 열 권
"""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "years.json"
SEEN = REPO / "data" / "earliest-seen.json"      # 이미 본 책 — 다시 돌릴 때 건너뛴다
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8", "replace")

def norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())

def product(item_id):
    html = get("https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=" + item_id)
    t = re.search(r'property="og:title"[^>]*content="([^"]*)"', html)
    d = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2})-\d{2}"', html)
    a = re.search(r'AuthorSearch=[^"]*"[^>]*>([^<]+)</a>', html)
    return {"title": (t.group(1) if t else "").split("|")[0].strip(),
            "date": d.group(1) if d else "", "author": a.group(1).strip() if a else ""}

def earliest(title, author):
    """제목과 저자가 같은 판들 중 가장 이른 출간일."""
    url = ("https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=Book&SearchWord="
           + urllib.parse.quote(title))
    ids = []
    for i in re.findall(r"ItemId=(\d+)", get(url)):
        if i not in ids:
            ids.append(i)
    want_t, want_a = norm(title), norm(author.split(",")[0])
    dates = []
    for i in ids[:6]:
        try:
            p = product(i)
        except Exception:
            continue
        got_t = norm(p["title"])
        same_title = got_t and (got_t == want_t or got_t.startswith(want_t))
        same_author = not want_a or want_a in norm(p["author"])
        if same_title and same_author and p["date"]:
            dates.append((p["date"], i, p["title"]))
        time.sleep(0.4)
    return min(dates) if dates else None

def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 0
    books = json.loads((REPO / "data" / "library.json").read_text())["books"]
    years = json.loads(OUT.read_text())
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()

    todo = []
    for b in books:
        rec = years.get(b["title"]) or {}
        if b["title"] in seen or not rec.get("ko") or not b.get("aladin"):
            continue
        if rec.get("orig") and "--all" not in args:
            continue     # 원서 연도가 이미 있으면 그게 정렬에 쓰이니 건드릴 것 없다
        todo.append(b)
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)}권을 본다\n")

    fixed = 0
    for n, b in enumerate(todo, 1):
        now = years[b["title"]]["ko"]
        try:
            got = earliest(b["title"], b.get("author", ""))
        except Exception as e:
            print(f"  ! {b['title']}: {type(e).__name__}")
            got = None
        if got and got[0] < now:
            print(f"  [{n}/{len(todo)}] {now} → {got[0]}  {b['title'][:34]}")
            years[b["title"]]["ko"] = got[0]
            fixed += 1
        elif n % 20 == 0:
            print(f"  … {n}/{len(todo)}")
        seen.add(b["title"])
        OUT.write_text(json.dumps(years, ensure_ascii=False, indent=1))
        SEEN.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=1))
        time.sleep(0.4)
    print(f"\n{fixed}권을 더 이른 판으로 바로잡았다")

if __name__ == "__main__":
    main()
