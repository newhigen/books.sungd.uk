#!/usr/bin/env python3
"""알라딘 링크가 정말 그 책을 가리키는지 본다.

제목으로 검색해 붙인 링크라 세트 상품이나 다른 판을 물어오는 일이 있다
(「집밥 메뉴 54」가 「52+54+56 세트 전3권」으로 갔다). 결과는 화면에만 찍는다.
"""
import json, re, sys, time, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
SET_WORDS = ["세트", "전3권", "전2권", "전4권", "전5권", "합본", "박스", "전집"]

def norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())

def main():
    books = json.loads((REPO / "data" / "library.json").read_text())["books"]
    targets = [b for b in books if b.get("aladin")]
    print(f"알라딘 링크가 있는 책 {len(targets)}권을 본다\n")
    bad = []
    for i, b in enumerate(targets, 1):
        try:
            html = urllib.request.urlopen(
                urllib.request.Request(b["aladin"], headers=UA), timeout=20).read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  ! {b['title']}: {type(e).__name__}")
            continue
        m = re.search(r'property="og:title"[^>]*content="([^"]*)"', html)
        got = (m.group(1) if m else "").split("|")[0].strip()
        ours, theirs = norm(b["title"]), norm(got)
        is_set = any(w in got for w in SET_WORDS) and not any(w in b["title"] for w in SET_WORDS)
        # 우리 제목이 상대 제목 안에 통째로 들어 있으면 같은 책으로 본다
        same = ours and (ours in theirs or theirs.startswith(ours))
        if is_set or not same:
            bad.append((b["title"], got, b["aladin"]))
            print(f"  ✗ {b['title']}\n      → {got}")
        if i % 25 == 0:
            print(f"  … {i}/{len(targets)}")
        time.sleep(0.5)
    print(f"\n의심스러운 링크 {len(bad)}개 / {len(targets)}권")

if __name__ == "__main__":
    main()
