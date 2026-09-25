#!/usr/bin/env python3
"""출간 연도를 모은다 — 한국어판은 알라딘, 원서는 Open Library.

data/years.json 에 쌓아 두고 다시 돌리면 이미 있는 것은 건너뛴다.
  python3 scripts/years.py              아직 없는 것만
  python3 scripts/years.py --limit 20   시험 삼아 스무 권만
  python3 scripts/years.py --again      전부 다시
"""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "years.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def get(url, enc="utf-8"):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode(enc, "replace")

def korean_year(aladin_url):
    """알라딘 상품 페이지의 JSON-LD 에 박힌 출간일."""
    if not aladin_url:
        return ""
    html = get(aladin_url)
    m = re.search(r'"datePublished"\s*:\s*"(\d{4})-(\d{2})-(\d{2})"', html)
    return m.group(1) + "-" + m.group(2) if m else ""

def original_year(title, author=""):
    """Open Library 가 아는 초판 연도. 원제로 물어야 맞는 게 나온다."""
    q = {"title": title, "limit": 3, "fields": "title,first_publish_year,author_name"}
    d = json.loads(get("https://openlibrary.org/search.json?" + urllib.parse.urlencode(q)))
    want = re.sub(r"[^a-z0-9]", "", title.lower())
    for doc in d.get("docs") or []:
        got = re.sub(r"[^a-z0-9]", "", (doc.get("title") or "").lower())
        # 제목이 사실상 같을 때만 받는다 — 비슷한 제목의 남의 책을 물어오면 연도가 엉킨다
        if got and (got == want or got.startswith(want) or want.startswith(got)):
            y = doc.get("first_publish_year")
            if y and 1000 < y <= 2100:
                return str(y)
    return ""

def is_korean_book(author):
    """한글 이름 한 사람이면 한국 책으로 본다.

    번역서는 「미우라 시온, 권남희」처럼 역자가 붙어 쉼표가 생긴다. 한국 책에
    englishTitle 이 붙어 있는 경우가 있는데(「에디토리얼 씽킹」→ Editorial Thinking)
    그것으로 물으면 같은 제목의 남의 옛 책이 걸려 연도가 엉킨다.
    """
    a = (author or "").strip()
    if not a or "," in a or ";" in a:
        return False
    # 한국 이름은 붙여 쓴 두세 글자다. 외국 저자를 한글로 적은 것은 띄어쓰기가 있거나
    # 길다 — 「알베르 카뮈」·「무라카미 하루키」·「생텍쥐페리」. 그들은 번역서이므로
    # 원서 연도를 찾아야 한다.
    return bool(re.fullmatch(r"[가-힣]{2,4}", a))


def main():
    args = sys.argv[1:]
    again = "--again" in args
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 0

    books = json.loads((REPO / "data" / "library.json").read_text())["books"]
    have = json.loads(OUT.read_text()) if OUT.exists() and not again else {}
    # 손으로 고쳐 둔 값은 언제나 이긴다 — 자동으로 찾은 연도가 틀릴 때 여기에 적는다
    MANUAL = REPO / "data" / "years-manual.json"
    manual = json.loads(MANUAL.read_text()) if MANUAL.exists() else {}
    manual.pop("_설명", None)
    todo = [b for b in books if b["title"] not in have]
    if limit:
        todo = todo[:limit]
    print(f"{len(books)}권 중 {len(todo)}권을 본다")

    for i, b in enumerate(todo, 1):
        rec = {}
        try:
            rec["ko"] = korean_year(b.get("aladin", ""))
        except Exception as e:
            rec["ko"] = ""
            print(f"  ! 알라딘 {b['title']}: {type(e).__name__}")
        # 원제가 있으면 그것으로 묻는다. 「舟を編む」처럼 영어가 아니어도 그대로 물어야
        # 원작 연도가 나온다 — 영역본 제목으로 물으면 번역판이 나온 해가 잡힌다.
        probe = b.get("englishTitle") or (b["title"] if re.fullmatch(r"[\x00-\x7f]+", b["title"]) else "")
        if is_korean_book(b.get("author")):
            probe = ""
        if probe:
            try:
                rec["orig"] = original_year(probe, b.get("author", ""))
            except Exception as e:
                rec["orig"] = ""
                print(f"  ! OpenLibrary {probe}: {type(e).__name__}")
        else:
            rec["orig"] = ""
        have[b["title"]] = rec
        mark = (rec["ko"] or "—") + " / " + (rec["orig"] or "—")
        print(f"  [{i}/{len(todo)}] {mark}  {b['title'][:34]}")
        OUT.write_text(json.dumps(have, ensure_ascii=False, indent=1))
        time.sleep(0.7)

    for title, rec in manual.items():
        have.setdefault(title, {}).update(rec)
    OUT.write_text(json.dumps(have, ensure_ascii=False, indent=1))
    if manual:
        print(f"손으로 고친 값 {len(manual)}권을 덮었다")

    ko = sum(1 for v in have.values() if v.get("ko"))
    orig = sum(1 for v in have.values() if v.get("orig"))
    print(f"\n모은 것 {len(have)}권 — 한국어판 연도 {ko}권, 원서 연도 {orig}권")

if __name__ == "__main__":
    main()
