#!/usr/bin/env python3
"""어떤 특징이 그 태그를 끌어왔는지 본다.

    python3 scripts/why-tag.py "철학은 날씨를 바꾼다" 데이터
"""
import importlib.util
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("sug", REPO / "scripts" / "suggest-tags.py")
sug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sug)

title, want = sys.argv[1], sys.argv[2]
b = sug.books[title]
rows = []
for x, w in sug.weighted(b):
    seen = sug.feat_tag.get(x)
    if not seen or want not in seen:
        continue
    total = sum(seen.values())
    s = (seen[want] / total) * (1.0 + 1.0 / total) * w
    rows.append((s, x, seen[want], total))
for s, x, n, total in sorted(rows, reverse=True):
    print(f"  {s:5.2f}  {x:<28} {n}/{total}")
print(f"  합계 {sum(r[0] for r in rows):.2f}")
