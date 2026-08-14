#!/usr/bin/env node
// sources/* 를 하나로 합쳐 data/library.json 을 만든다.
//
//   sources/read-log.csv   읽은 책 (writing.sungd.uk 의 books.csv 사본)
//   sources/<service>.json 서비스별 소장 목록 (수집기가 채운다)
//                          → { service, collectedAt, books: [{title, author, cover, link, ...}] }
//
// 같은 책이 여러 서비스에 있으면 한 줄로 합치고 sources 배열에 서비스를 쌓는다.
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs'
import { join, dirname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const repo = dirname(dirname(fileURLToPath(import.meta.url)))
const SRC = join(repo, 'sources')
const OUT = join(repo, 'data', 'library.json')

// 서비스 표시 이름·순서. 여기 없는 소스 파일은 파일명을 그대로 쓴다.
const SERVICES = [
  { id: 'ridi', name: '리디북스', kind: 'ebook' },
  { id: 'kyobo', name: '교보 sam', kind: 'ebook' },
  { id: 'kindle', name: '킨들', kind: 'ebook' },
  { id: 'google', name: '구글 북스', kind: 'ebook' },
  { id: 'pdf', name: 'PDF', kind: 'file' },
  { id: 'paper', name: '종이책', kind: 'paper' },
  { id: 'company', name: '회사 대여', kind: 'borrowed' },
  { id: 'friend', name: '지인 대여', kind: 'borrowed' },
  { id: 'library', name: '도서관', kind: 'borrowed' },
]

// ---- 제목 정규화 (같은 책 찾기) ----
// 부제·판형·괄호를 떼고 공백·기호를 지운 것을 키로 쓴다.
// 저자는 키에 넣지 않는다 — 읽은 기록(read-log.csv)에는 저자가 없어서, 저자를 섞으면
// 수집 목록과 읽은 기록이 같은 책인데도 영영 안 만난다.
function keyOf(title) {
  const t = String(title || '')
    .replace(/\([^)]*\)/g, ' ')
    .replace(/\[[^\]]*\]/g, ' ')
    .replace(/[:：—-].*$/, ' ')
    .replace(/(개정|증보|전면개정|리커버|특별|합본)?\s*(판|호|권)\b/g, ' ')
    .replace(/[^\p{L}\p{N}]/gu, '')
    .toLowerCase()
  return t
}

// ---- 읽은 책 로그 (title, english-title, year, month) ----
function readLog() {
  const f = join(SRC, 'read-log.csv')
  if (!existsSync(f)) return []
  const lines = readFileSync(f, 'utf8').trim().split('\n')
  const head = lines.shift().split(',')
  return lines.map((line) => {
    // 따옴표 안 쉼표까지 다루는 최소 CSV 파서
    const cell = []
    let cur = ''
    let q = false
    for (const ch of line) {
      if (ch === '"') q = !q
      else if (ch === ',' && !q) {
        cell.push(cur)
        cur = ''
      } else cur += ch
    }
    cell.push(cur)
    const row = Object.fromEntries(head.map((h, i) => [h, (cell[i] || '').trim()]))
    return {
      title: row.title,
      englishTitle: row['english-title'] || '',
      readAt: row.year && row.month ? `${row.year}-${String(row.month).padStart(2, '0')}` : '',
    }
  })
}

// ---- 서비스별 소장 목록 ----
function loadSources() {
  if (!existsSync(SRC)) return []
  return readdirSync(SRC)
    .filter((f) => f.endsWith('.json'))
    .map((f) => {
      const raw = JSON.parse(readFileSync(join(SRC, f), 'utf8'))
      const id = raw.service || basename(f, '.json')
      return { id, collectedAt: raw.collectedAt || '', books: raw.books || [] }
    })
}

// ---- 표지·저자 보강분 (scripts/enrich.py 가 만든 캐시) ----
const COVERS = join(repo, 'data', 'covers.json')
const covers = existsSync(COVERS) ? JSON.parse(readFileSync(COVERS, 'utf8')) : {}

// ---- 분야·태그 (scripts/categorize.py 가 만든 캐시) ----
const CATS = join(repo, 'data', 'categories.json')
const cats = existsSync(CATS) ? JSON.parse(readFileSync(CATS, 'utf8')) : {}

// ---- 병합 ----
const books = new Map() // key → 책

function upsert(key, patch) {
  const cur = books.get(key)
  if (!cur) {
    books.set(key, { sources: [], ...patch })
    return books.get(key)
  }
  // 이미 채워진 값은 덮지 않는다 — 먼저 들어온 수집 원본이 더 정확하다
  for (const [k, v] of Object.entries(patch)) {
    if (v && !cur[k]) cur[k] = v
  }
  return cur
}

for (const src of loadSources()) {
  for (const b of src.books) {
    if (!b.title) continue
    const book = upsert(keyOf(b.title), {
      title: b.title,
      author: b.author || '',
      cover: b.cover || '',
      publisher: b.publisher || '',
      addedAt: b.addedAt || '',
    })
    if (!book.sources.some((s) => s.id === src.id)) {
      book.sources.push({ id: src.id, link: b.link || '' })
    }
  }
}

for (const r of readLog()) {
  if (!r.title) continue
  const book = upsert(keyOf(r.title), { title: r.title, englishTitle: r.englishTitle })
  book.read = true
  // 같은 책을 두 번 읽었으면 최근 것을 남긴다
  if (!book.readAt || r.readAt > book.readAt) book.readAt = r.readAt
}

// 같은 책이 두 이름으로 들어온 경우 한 줄로 합친다 (남길 쪽, 지울 쪽).
function mergeInto(keepKey, dropKey) {
  const keep = books.get(keepKey)
  const drop = books.get(dropKey)
  if (!keep || !drop || keep === drop) return false
  for (const src of drop.sources) {
    if (!keep.sources.some((x) => x.id === src.id)) keep.sources.push(src)
  }
  for (const k of ['author', 'cover', 'publisher', 'addedAt', 'englishTitle', 'aladin']) {
    if (!keep[k] && drop[k]) keep[k] = drop[k]
  }
  if (drop.read) keep.read = true
  if (drop.readAt && (!keep.readAt || drop.readAt > keep.readAt)) keep.readAt = drop.readAt
  books.delete(dropKey)
  return true
}

// 읽은 기록의 english-title 열을 별칭 삼아, 원서 제목으로 들어온 책을 한글 기록과 합친다.
for (const r of readLog()) {
  if (r.englishTitle) mergeInto(keyOf(r.title), keyOf(r.englishTitle))
}

// 사람이 확인한 원서↔번역서 짝 (data/covers.json 의 alias). 한글 쪽으로 모은다.
for (const [title, c] of Object.entries(covers)) {
  if (c && c.alias) mergeInto(keyOf(c.alias), keyOf(title))
}

// 수집 원본에 없던 표지·저자를 채운다 (원본 값이 있으면 그대로 둔다)
for (const book of books.values()) {
  const c = covers[book.title]
  if (!c || c.notfound || c.uncertain) continue
  if (!book.author) book.author = c.author || ''
  if (!book.cover) book.cover = c.cover || ''
  if (!book.publisher) book.publisher = c.publisher || ''
  if (!book.aladin) book.aladin = c.aladin || ''
  // 알라딘에 없는 책은 교보에서 찾아 둔다
  if (!book.kyobo) book.kyobo = c.kyobo || ''
}

// ---- 분야 정하기 ----
// 알라딘은 책 하나를 여러 분류에 건다. 그중 첫 번째를 그냥 쓰면 '차곡차곡 글쓰기' 가
// 저자 때문에 컴퓨터/모바일 로 가고 '디자인 구구단' 이 그래픽 툴 책이 된다.
// 그래서 서점 진열 이름 대신, 경로에 담긴 말로 내 분야를 고른다. 위에 있는 규칙이 이긴다.
const FIELD_RULES = [
  ['신앙', /기독교|개신교|천주교|종교|신앙|성경/],
  ['디자인', /디자인|그래픽|웹디자인|UI|UX|타이포/],
  ['글쓰기·읽기', /글쓰기|책읽기|독서/],
  ['개발', /프로그래밍|컴퓨터 ?공학|소프트웨어|웹 ?개발|데이터베이스|인공지능|머신러닝|알고리즘|운영체제|네트워크|모바일 ?프로그/],
  // '인문학' 안에 '문학' 이 들어 있어서, 인문을 문학보다 먼저 본다
  ['인문·심리', /인문|철학|심리|정신분석|교양/],
  ['문학', /소설|희곡|시집|고전문학|세계의 문학|테마문학|한국문학|외국문학|문학론|서양현대고전|동양고전/],
  ['에세이', /에세이/],
  ['일·경영', /경영|비즈니스|창업|리더십|마케팅|세일즈|투자|재테크|경제|간부학|직장/],
  ['자기계발', /자기계발|성공|시간관리|정보관리|인간관계|화술|협상|설득|창의|두뇌계발|취업|진로|공부법|학습/],
  ['역사·사회', /역사|사회|정치|법학/],
  ['건강·생활', /건강|다이어트|운동|요리|살림|육아|취미|반려/],
  ['여행', /여행/],
  ['과학', /과학|수학|물리|생물/],
]
// 분야가 아니라 서점 진열 코너인 것들 — 분야를 정할 때도 태그에도 넣지 않는다
const SHELF_ONLY = /추천도서|베스트셀러|대학교재|전문서적|청소년|외부\/전문기관|한국출판문화|우수출|^\d{4}년$/

const overridePath = join(repo, 'data', 'field-overrides.json')
const overrides = existsSync(overridePath) ? JSON.parse(readFileSync(overridePath, 'utf8')) : {}

function decideField(paths) {
  const words = paths.flat().filter((n) => !SHELF_ONLY.test(n))
  for (const [name, re] of FIELD_RULES) {
    if (words.some((w) => re.test(w))) return name
  }
  return ''
}

for (const book of books.values()) {
  const c = cats[book.title]
  if (!c) continue
  const paths = (c.paths || []).filter((p) => !p.some((n) => SHELF_ONLY.test(n)))
  book.field = overrides[book.title] || decideField(paths.length ? paths : c.paths || [])
  // 태그는 경로의 아래 칸들 — 진열 코너 이름은 뺀다
  const tags = []
  for (const p of paths) {
    for (const n of p.slice(1)) {
      if (!tags.includes(n) && !SHELF_ONLY.test(n)) tags.push(n)
    }
  }
  book.tags = tags.slice(0, 6)
}

// ---- 태그는 손으로 붙인 것이 먼저 (data/tags.json) ----
// 서점 분류에서 뽑은 태그는 '성공학' 처럼 진열대 말이라, 있으면 내 태그로 갈아 끼운다.
const MINE = join(repo, 'data', 'tags.json')
const mine = existsSync(MINE) ? JSON.parse(readFileSync(MINE, 'utf8')) : {}
for (const book of books.values()) {
  if (mine[book.title]?.length) book.tags = mine[book.title]
}

// ---- 무슨 책인지 한 줄 (data/summaries.json — 손으로 쓴다) ----
const GISTS = join(repo, 'data', 'summaries.json')
const gists = existsSync(GISTS) ? JSON.parse(readFileSync(GISTS, 'utf8')) : {}
for (const book of books.values()) {
  const g = gists[book.title]
  if (!g) continue
  book.gist = g.gist || ''
  book.topics = g.topics || []
  book.form = g.form || ''
}

// ---- 감출 것 빼기 ----
// data/hidden.json 에 적힌 분야·제목은 공개 데이터에 싣지 않는다. 화면에서 가리는 게
// 아니라 파일에서 빠지므로, 받아보더라도 흔적이 없다.
const HIDDEN = join(repo, 'data', 'hidden.json')
const hidden = existsSync(HIDDEN) ? JSON.parse(readFileSync(HIDDEN, 'utf8')) : {}
const hidFields = new Set(hidden.fields || [])
const hidTitles = new Set(hidden.titles || [])
let hiddenCount = 0
for (const [key, b] of books) {
  if (hidFields.has(b.field) || hidTitles.has(b.title)) {
    books.delete(key)
    hiddenCount++
  }
}

// ---- 출력 ----
const all = [...books.values()].map((b) => ({
  title: b.title,
  author: b.author || '',
  englishTitle: b.englishTitle || '',
  cover: b.cover || '',
  publisher: b.publisher || '',
  aladin: b.aladin || '',
  kyobo: b.kyobo || '',
  field: b.field || '',
  tags: b.tags || [],
  gist: b.gist || '',
  topics: b.topics || [],
  form: b.form || '',
  sources: b.sources,
  read: !!b.read,
  readAt: b.readAt || '',
  addedAt: b.addedAt || '',
}))

// 정렬: 읽은 달 최신 → 들인 달 최신 → 제목
all.sort((x, y) => {
  const kx = x.readAt || x.addedAt || ''
  const ky = y.readAt || y.addedAt || ''
  if (kx !== ky) return ky.localeCompare(kx)
  return x.title.localeCompare(y.title, 'ko')
})

// ---- 비슷한 책 ----
// 화면에서 매번 재는 대신 여기서 미리 골라 둔다. 겹치는 것이 많을수록 높은 점수.
const SCORE = { tag: 3, field: 2, author: 4, publisher: 1 }
const firstAuthor = (a) => String(a || '').split(/[,;·]/)[0].trim()

all.forEach((b, i) => {
  const scored = []
  for (let j = 0; j < all.length; j++) {
    if (j === i) continue
    const o = all[j]
    let n = 0
    for (const t of b.tags) if (o.tags.includes(t)) n += SCORE.tag
    if (b.field && b.field === o.field) n += SCORE.field
    if (b.author && firstAuthor(b.author) === firstAuthor(o.author)) n += SCORE.author
    if (b.publisher && b.publisher === o.publisher) n += SCORE.publisher
    if (n > 0) scored.push([n, j])
  }
  scored.sort((x, y) => y[0] - x[0])
  b.similar = scored.slice(0, 6).map(([, j]) => j)
})

const used = new Set(all.flatMap((b) => b.sources.map((s) => s.id)))
const services = [
  ...SERVICES.filter((s) => used.has(s.id)),
  ...[...used]
    .filter((id) => !SERVICES.some((s) => s.id === id))
    .map((id) => ({ id, name: id, kind: 'ebook' })),
].map((s) => ({ ...s, count: all.filter((b) => b.sources.some((x) => x.id === s.id)).length }))

const fieldCount = {}
for (const b of all) if (b.field) fieldCount[b.field] = (fieldCount[b.field] || 0) + 1
const fields = Object.entries(fieldCount)
  .sort((a, b) => b[1] - a[1])
  .map(([name, count]) => ({ name, count }))

const out = {
  updatedAt: new Date().toISOString().slice(0, 10),
  total: all.length,
  services,
  fields,
  books: all,
}
writeFileSync(OUT, JSON.stringify(out, null, 1) + '\n')

if (hiddenCount) console.log(`  (감춘 책 ${hiddenCount}권 — 공개 데이터에서 빠짐)`)
const unknown = all.filter((b) => !b.sources.length).length
console.log(`${all.length}권 → data/library.json`)
console.log(services.map((s) => `  ${s.name} ${s.count}`).join('\n') || '  (수집된 서비스 없음)')
if (unknown) console.log(`  소장처 미확인 ${unknown}`)
