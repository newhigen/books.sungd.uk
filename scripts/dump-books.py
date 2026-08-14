#!/usr/bin/env python3
"""책마다 정리를 쓸 때 보려고, 있는 자료를 한자리에 펼친다.

    python3 scripts/dump-books.py 40 80     # 41번째부터 80번째까지
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
D = REPO / "data"

lib = json.loads((D / "library.json").read_text())
desc = json.loads((D / "descriptions.json").read_text())
cats = json.loads((D / "categories.json").read_text())
tags = json.loads((D / "tags.json").read_text())

a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
b = int(sys.argv[2]) if len(sys.argv) > 2 else len(lib["books"])

for i, book in enumerate(lib["books"][a:b], a + 1):
    t = book["title"]
    print(f"[{i}] {t} | {book.get('author','')[:30]}")
    paths = cats.get(t, {}).get("paths", [])
    if paths:
        print("   분류:", " / ".join(">".join(p) for p in paths[:2]))
    if tags.get(t):
        print("   태그:", ",".join(tags[t]))
    s = desc.get(t, {}).get("summary", "")
    print("   소개:", s if s else "(없음)")
