#!/usr/bin/env python3
"""책마다 추천 태그를 만든다. 사람이 tools/tagger.html 에서 고친다.

재료는 셋이다.
  1) 분야 규칙이 정한 갈래 (build.mjs 의 field)
  2) 알라딘 분류 경로의 아래 칸들 — 다만 표현이 거칠어 다듬는다
  3) 제목에서 바로 읽히는 말 (글쓰기·습관 같은 것)
"""
import json, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
lib = json.loads((REPO / "data" / "library.json").read_text())
cats = json.loads((REPO / "data" / "categories.json").read_text())

# 알라딘 소분류 → 쓸 만한 말로 바꾸기. 없으면 슬래시로 쪼개 첫 조각만 쓴다.
RENAME = {
    "프로그래밍 개발/방법론": "개발 방법론", "프로그래밍 기초/개발 방법론": "개발 방법론",
    "컴퓨터 공학": "컴퓨터 공학", "소프트웨어 공학": "소프트웨어 공학",
    "CEO/비즈니스맨을 위한 능력계발": "일하는 법", "간부학/리더십": "리더십",
    "기업 경영": "경영", "경영전략/혁신": "전략", "마케팅/세일즈": "마케팅",
    "성공": "성공", "성공학": "성공", "시간관리/정보관리": "시간 관리",
    "창의적사고/두뇌계발": "생각법", "취업/진로/유망직업": "커리어",
    "협상/설득/화술": "말하기", "화술": "말하기", "인간관계": "관계",
    "심리학/정신분석학": "심리", "교양 인문학": "인문", "책읽기/글쓰기": "글쓰기",
    "세계의 문학": "소설", "서양고전문학": "고전", "한국에세이": "에세이",
    "외국에세이": "에세이", "명사에세이": "에세이", "건강정보": "건강",
    "그래픽/멀티미디어": "그래픽", "웹디자인/홈페이지": "웹디자인",
    "디자인/공예": "디자인", "디자인이론/비평/역사": "디자인",
    "e비즈니스/창업": "창업", "프로그래밍 언어": "프로그래밍 언어",
}
DROP = re.compile(r"일반$|기타$|^\d{4}년$|추천도서|베스트|우수출|전문기관|대학교재|국내도서|외국도서")

# 제목에서 바로 읽히는 것
TITLE_TAGS = [
    ("글쓰기", r"글쓰기|문장|writing"), ("독서", r"독서|책 읽|읽었더라면|책을 읽"),
    ("노트", r"노트|제텔카스텐|메모"), ("습관", r"습관"), ("학습", r"학습|공부|배우기"),
    ("실패", r"실패"), ("리더십", r"리더|리더십"), ("면접", r"면접|인터뷰"),
    ("머신러닝", r"머신러닝|머신 러닝|딥러닝|ML"), ("리팩터링", r"리팩터|리팩토링|refactor"),
    ("애자일", r"애자일|스크럼|린 "), ("생산성", r"시간|딥 워크|메이크 타임|정리"),
    ("의사결정", r"선택|결정|판단|예측"), ("커리어", r"커리어|이직|채용|진로"),
    ("대화", r"대화|말투|말하는|설득|화술"), ("여행기", r"여행|유럽|뉴욕"),
]

def clean(tag):
    t = RENAME.get(tag)
    if t:
        return t
    if DROP.search(tag):
        return None
    t = tag.split("/")[0].strip()
    return t if 1 < len(t) <= 12 else None

out = {}
for b in lib["books"]:
    tags = []
    if b.get("field"):
        tags.append(b["field"])
    c = cats.get(b["title"], {})
    for p in c.get("paths", []):
        for name in p[1:]:
            t = clean(name)
            if t and t not in tags:
                tags.append(t)
    hay = b["title"] + " " + b.get("englishTitle", "")
    for name, pat in TITLE_TAGS:
        if re.search(pat, hay, re.I) and name not in tags:
            tags.append(name)
    out[b["title"]] = tags[:5]

(REPO / "data" / "tags-suggested.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")

from collections import Counter
cnt = Counter(t for v in out.values() for t in v)
print(f"{len(out)}권에 추천 태그 붙임 · 태그 {len(cnt)}종")
print("많은 것:", ", ".join(f"{k} {n}" for k, n in cnt.most_common(12)))
print("한 번뿐:", sum(1 for k, n in cnt.items() if n == 1), "종")
