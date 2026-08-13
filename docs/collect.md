# 서비스별 목록 모으기

서비스들은 서재를 공개 API 로 내주지 않는다. 로그인한 브라우저에서 서재 페이지를 열고,
그 화면의 목록을 긁어 `sources/<service>.json` 으로 저장한다.

작업 순서는 매번 같다.

1. 크롬에서 해당 서비스에 **직접 로그인**한다 (비밀번호는 사람이 넣는다).
2. 서재 페이지를 연다. 무한 스크롤이면 끝까지 내려 전부 불러온다.
3. 그 페이지에서 목록을 뽑아 JSON 으로 저장한다.
4. `node scripts/build.mjs` → `python3 scripts/enrich.py` → `node scripts/build.mjs`.

3번은 서비스마다 화면 구조가 달라서 그 자리에서 맞춰 만든다. 아래는 서재 주소와,
지금까지 확인한 것.

| 서비스 | 서재 주소 | 확인한 것 |
|---|---|---|
| 리디북스 | https://ridibooks.com/library | 로그인해야 목록이 뜬다 (2026-08-13 확인) |
| 교보 sam | https://ebook-lib.kyobobook.co.kr | 미확인 |
| 크레마 (예스24) | https://ebook.yes24.com/hottracks/mybook | 미확인 |
| 킨들 | https://read.amazon.com/kindle-library | 미확인 |
| 구글 북스 | https://play.google.com/books | 미확인 |

## PDF

클라우드에 흩어진 PDF 중 무엇이 책인지는 파일명만으로 안 갈린다 — 논문·공고문·영수증이
훨씬 많다. 쪽수(예: 80쪽 이상)와 파일명으로 후보를 추린 뒤 사람이 확인하는 편이 빠르다.

## 종이책

책장을 칸별로 찍어서 주면 책등을 읽어 목록으로 만든다. 흐릿하거나 가려진 것은 추측해서
채우지 않고 빼둔다 — 빠진 게 잘못 들어간 것보다 낫다.
