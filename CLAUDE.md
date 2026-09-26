# books.sungd.uk

종이책과 리디, 교보, 킨들, 구글북스에 흩어진 책을 한 장에. 빌드 도구 없는 정적 페이지.

## 실행

```sh
node scripts/build.mjs      # 원격 읽은 책 로그 + sources 를 합쳐 화면 데이터로
python3 scripts/enrich.py   # 새로 들어온 책의 표지와 저자 채우기 (채운 건 건너뜀)
node scripts/build.mjs      # 채운 값을 반영
python3 -m http.server 8912 # 로컬 확인
```

## 어디를 고치나

```
sources/<service>.json   서비스별 소장 목록 원본. 여기만 갱신하면 된다 (수집 방법은 docs/collect.md)
index.html               화면 전부 (스타일, 스크립트 인라인)
data/library.json        화면이 읽는 유일한 데이터 — build.mjs 가 만든다
data/covers.json         표지와 저자 캐시 (알라딘 검색분)
scripts/build.mjs        같은 책 합치기. 잘못 합쳐지면 keyOf 를 손본다
```

소스 파일은 `title` 만 있어도 된다. 나머지는 `enrich.py` 가 알라딘에서 채운다.

## 배포

GitHub Pages 가 main 루트를 그대로 서빙한다. `data/library.json` 을 다시 만들어 커밋하고 머지하면 반영된다.

## ⚠ 경고

- 읽은 책은 로컬 사본이 없다. `build.mjs` 가 매번 writing.sungd.uk 의 `src/data/books.csv` 를 원격에서 받는다. 빌드에 네트워크가 필요하다.
- `file://` 로 열면 브라우저가 데이터 읽기를 막는다. 로컬 확인은 http.server 로.
- 목록은 전부 공개다. 가릴 책이 생기면 `sources/` 에서 빼고 다시 빌드한다.
