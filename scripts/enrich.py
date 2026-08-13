#!/usr/bin/env python3
"""제목만 있는 책에 표지·저자·출판사를 붙인다.

알라딘 검색 결과의 첫 항목을 쓰되, 제목이 충분히 비슷할 때만 받아들인다.
결과는 data/covers.json 에 쌓아 두고 다음 실행 때 재사용한다(재요청 안 함).

    python3 scripts/enrich.py            # 아직 안 채운 것만
    python3 scripts/enrich.py --limit 5  # 몇 권만 시험
    python3 scripts/enrich.py --redo "제목"  # 잘못 붙은 책만 다시
"""
import json, re, sys, time, urllib.parse, urllib.request
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "data" / "library.json"
CACHE = REPO / "data" / "covers.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
SEARCH = "https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=Book&SearchWord="


def norm(s):
    s = re.sub(r"\([^)]*\)", " ", s or "")
    s = re.sub(r"[^\w가-힣]", "", s)
    return s.lower()


def short(title):
    """부제와 기호를 떼어 검색어를 줄인다. 원제와 같으면 빈 문자열."""
    t = re.split(r"[:：]", title)[0]
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"[&/·,]", " ", t)
    t = " ".join(t.split())
    return "" if t == title else t


def fetch(title):
    url = SEARCH + urllib.parse.quote(title)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "replace")

    # 검색 결과는 ss_book_box 단위. 첫 상자에서 제목·저자·표지를 뽑는다.
    boxes = html.split("ss_book_box")[1:]
    for box in boxes[:3]:
        # 속성 순서가 페이지마다 달라서 태그를 먼저 잡고 href 를 그 안에서 찾는다
        m = re.search(r"<a([^>]*bo3[^>]*)>(.*?)</a>", box, re.S)
        if not m:
            continue
        found = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        item = re.search(r"ItemId=(\d+)", m.group(1))
        # 검색 상자에는 책등(SpineShelf) 그림이 먼저 나온다 — 앞표지(cover*)만 받는다
        cover = re.search(r"https://image\.aladin\.co\.kr/product/\d+/\d+/cover\w*/[^\"']+?\.jpg", box)
        authors = re.findall(r"AuthorSearch[^>]*>([^<]+)</a>", box)
        pub = re.search(r"PublisherSearch[^>]*>([^<]+)</a>", box)
        return {
            "title": found,
            "author": ", ".join(a.strip() for a in authors[:2]),
            "publisher": (pub.group(1).strip() if pub else ""),
            "cover": (cover.group(0).replace("cover200", "cover500") if cover else ""),
            "aladin": ("https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=" + item.group(1)) if item else "",
        }
    return None


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 0
    redo = args[args.index("--redo") + 1] if "--redo" in args else None

    lib = json.loads(LIB.read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if redo:
        cache.pop(redo, None)

    todo = [b for b in lib["books"] if b["title"] not in cache and (not redo or b["title"] == redo)]
    if limit:
        todo = todo[:limit]
    print(f"보강 대상 {len(todo)}권 (이미 {len(cache)}권 저장됨)")

    hit = miss = 0
    for i, b in enumerate(todo, 1):
        title = b["title"]
        got = None
        for attempt in (title, short(title)):
            if not attempt or (got and not got.get("uncertain")):
                break
            try:
                cand = fetch(attempt)
            except Exception as e:
                print(f"  ! {title} — {e}")
                cand = None
            if not cand:
                continue
            score = SequenceMatcher(None, norm(title), norm(cand["title"])).ratio()
            cand["match"] = round(score, 2)
            if score < 0.6:
                cand["uncertain"] = True
            if not got or cand["match"] > got.get("match", 0):
                got = cand
            if attempt != title:
                time.sleep(0.5)
        if got and not got.get("uncertain"):
            hit += 1
            print(f"  {i:3d}/{len(todo)} {title[:28]:<30} → {got['author'][:18]:<20} {got['match']}")
        else:
            miss += 1
            print(f"  {i:3d}/{len(todo)} {title[:28]:<30} → 못 찾음{' (제목 어긋남: ' + got['title'][:20] + ')' if got else ''}")
        cache[title] = got or {"notfound": True}
        if i % 10 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n")
        time.sleep(0.7)

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n")
    print(f"\n찾음 {hit} · 못 찾음 {miss} → data/covers.json")


if __name__ == "__main__":
    main()
