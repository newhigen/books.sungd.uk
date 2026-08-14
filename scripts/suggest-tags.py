#!/usr/bin/env python3
"""추천 태그를 만든다. 사람이 붙인 것을 보고 배운다.

규칙을 손으로 적는 대신, 이미 붙인 태그에서 배운다 — 어떤 분류·제목의 책에 어떤 태그를
붙였는지 세어 두고, 같은 특징을 가진 다른 책에 그 태그를 권한다. 사람이 태그를 더 붙일수록
추천이 그 사람 말에 가까워진다.

추천은 어디까지나 추천이라 화면에서 켜져 있지 않다. 눌러야 붙는다.

    python3 scripts/suggest-tags.py
"""
import json, re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
lib = json.loads((REPO / "data" / "library.json").read_text())
cats = json.loads((REPO / "data" / "categories.json").read_text())
mine = json.loads((REPO / "data" / "tags.json").read_text())
mine = {k: v for k, v in mine.items() if v}

STOP = set("그 이 저 것 수 등 및 위한 대한 하는 되는 있는 없는 나는 내가 우리 당신 the a of to and for in on with your my is are how what why".split())

# 책 내용이 아니라 서점 진열 코너 이름 — 이것들이 섞이면 엉뚱한 태그가 딸려 온다
# (실제로 '2019 청소년 추천도서' 한 칸 때문에 습관 책에 '건축' 이 붙었다)
SHELF = re.compile(
    r"추천도서|베스트셀러|대학교재|전문서적|청소년|외부/전문기관|한국출판문화|우수출"
    r"|세종도서|올해의 책|독자 선정|문학상|과학창의재단|^\d{4}년?$"
)


def feats(b):
    """책의 특징 — 분류 경로 칸, 손으로 쓴 주제어와 형식, 제목·소개 낱말."""
    out = set()
    c = cats.get(b["title"], {})
    for p in c.get("paths", []):
        for name in p:
            if not SHELF.search(name):
                out.add("분류:" + name)
    if b.get("field"):
        out.add("갈래:" + b["field"])
    # 서점 분류보다 이쪽이 책 내용에 가깝다
    for t in b.get("topics", []):
        out.add("주제:" + t)
    if b.get("form"):
        out.add("꼴:" + b["form"])
    words = re.findall(
        r"[가-힣A-Za-z]{2,}",
        b["title"] + " " + b.get("englishTitle", "") + " " + b.get("gist", ""),
    )
    for w in words:
        if w.lower() not in STOP:
            out.add("말:" + w.lower())
    if b.get("author"):
        out.add("이:" + b["author"].split(",")[0].strip())
    return out


books = {b["title"]: b for b in lib["books"]}

# 특징마다 믿음이 다르다. 손으로 쓴 주제어가 가장 정확하고, 낱말은 우연히 겹치기 쉽다.
WEIGHT = {"주제": 1.3, "분류": 1.0, "이": 1.0, "꼴": 0.6, "갈래": 0.8, "말": 0.4}

# 여러 책에 두루 나오는 낱말은 그 책을 가리키지 못한다 — "이론", "방법" 같은 것들
word_books = Counter()
for b in books.values():
    for x in feats(b):
        if x.startswith("말:"):
            word_books[x] += 1
COMMON = {w for w, n in word_books.items() if n >= 10}


def weighted(b):
    return [(x, WEIGHT.get(x.split(":", 1)[0], 1.0)) for x in feats(b) if x not in COMMON]


# ── 배우기 ──
tag_count = Counter()
feat_tag = defaultdict(Counter)
for title, tags in mine.items():
    b = books.get(title)
    if not b:
        continue
    f = weighted(b)
    for t in tags:
        tag_count[t] += 1
        for x, _ in f:
            feat_tag[x][t] += 1

# ── 권하기 ──
out = {}
for title, b in books.items():
    have = set(mine.get(title, []))
    score = Counter()
    for x, w in weighted(b):
        seen = feat_tag.get(x)
        if not seen:
            continue
        total = sum(seen.values())
        for t, n in seen.items():
            if t in have:
                continue
            # 그 특징에서 그 태그가 나온 비율 × 특징이 드물수록 가산 × 특징의 믿음
            score[t] += (n / total) * (1.0 + 1.0 / total) * w
    # 1등과 너무 벌어진 것은 우연히 걸린 쪽이다
    top = score.most_common(1)[0][1] if score else 0
    picked = [t for t, s in score.most_common(6) if s >= max(0.7, top * 0.5)][:3]
    out[title] = picked

(REPO / "data" / "tags-suggested.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")

c = Counter(t for v in out.values() for t in v)
none = sum(1 for v in out.values() if not v)
notag = [t for t in books if t not in mine]
print(f"배운 것 — 사람이 붙인 {len(mine)}권 · 태그 {len(tag_count)}종")
print(f"추천 — {len(out)}권 · 평균 {round(sum(len(v) for v in out.values())/len(out),1)}개 · 못 짚은 책 {none}권")
print(f"아직 태그 없는 책 {len(notag)}권 중 추천이 붙은 것 {sum(1 for t in notag if out.get(t))}권")
print()
print("많이 권한 것:", ", ".join(f"{k} {n}" for k, n in c.most_common(12)))
