#!/usr/bin/env python3
"""이미 모은 원서 연도 중 한국 책에 잘못 붙은 것을 턴다. years.py 와 같은 잣대."""
import json, re
from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("years", Path(__file__).parent / "years.py")
years = importlib.util.module_from_spec(spec); spec.loader.exec_module(years)

y = json.loads((REPO / "data" / "years.json").read_text())
books = {b["title"]: b for b in json.loads((REPO / "data" / "library.json").read_text())["books"]}
hit = 0
for title, rec in y.items():
    b = books.get(title)
    if b and rec.get("orig") and years.is_korean_book(b.get("author")):
        print("  뗌", title, "|", b.get("author"), "|", rec["orig"])
        rec["orig"] = ""
        hit += 1
(REPO / "data" / "years.json").write_text(json.dumps(y, ensure_ascii=False, indent=1))
print(f"{hit}권에서 잘못 붙은 원서 연도를 뗐다")
