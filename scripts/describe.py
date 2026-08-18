#!/usr/bin/env python3
"""책마다 "무슨 내용인가" 를 모은다.

알라딘 상세 페이지의 본문 책소개는 화면에서 스크립트로 채워져서 받아지지 않는다.
대신 페이지 머리(meta)에 들어 있는 짧은 소개와 ISBN 을 가져오고, 편집장의 선택처럼
본문에 이미 실려 있는 긴 글이 있으면 함께 담는다.

    python3 scripts/describe.py            # 아직 안 모은 책만
    python3 scripts/describe.py --limit 5
    python3 scripts/describe.py --redo     # 이미 모은 것도 다시
"""
import html as htmllib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = REPO / "data" / "library.json"
OUT = REPO / "data" / "descriptions.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def text_of(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    t = htmllib.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def meta(html, key):
    m = re.search(r'<meta[^>]*(?:property|name)="%s"[^>]*content="([^"]*)"' % key, html)
    return htmllib.unescape(m.group(1)).strip() if m else ""


def long_blocks(html):
    """본문에 이미 실려 있는 긴 글 — 편집장의 선택, 추천사 같은 것."""
    out = []
    for frag in re.findall(r'Ere_prod_mconts_R">(.*?)</div>\s*</div>', html, re.S):
        t = text_of(frag)
        # 배송·이벤트 안내가 같은 상자에 들어와서 걸러낸다
        if len(t) < 80 or "적립금" in t or "쿠폰" in t or "이벤트" in t:
            continue
        out.append(t)
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 0
    redo = "--redo" in args

    lib = json.loads(LIB.read_text())
    done = json.loads(OUT.read_text()) if OUT.exists() else {}

    todo = [b for b in lib["books"] if b.get("aladin")]
    if not redo:
        todo = [b for b in todo if b["title"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"소개 대상 {len(todo)}권 (이미 {len(done)}권)")

    for i, b in enumerate(todo, 1):
        try:
            page = fetch(b["aladin"])
        except Exception as e:
            print(f"  ! {b['title'][:24]} — {e}")
            continue

        rec = {
            "isbn": meta(page, "books:isbn"),
            "summary": meta(page, "og:description"),
            "extra": long_blocks(page)[:2],
            "aladin": b["aladin"],
        }
        if not rec["summary"] and not rec["extra"]:
            print(f"  {i:3d}/{len(todo)} {b['title'][:26]:<28} → 소개 없음")
        else:
            print(f"  {i:3d}/{len(todo)} {b['title'][:26]:<28} → {rec['summary'][:40]}")
        done[b["title"]] = rec

        if i % 10 == 0:
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
        time.sleep(0.6)

    OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
    got = sum(1 for v in done.values() if v.get("summary"))
    print(f"\n소개 있음 {got} / {len(done)}권")


if __name__ == "__main__":
    main()
