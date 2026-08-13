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

// ---- 표지·저자 보강분 (scripts/enrich.py 가 만든 캐시) ----
const COVERS = join(repo, 'data', 'covers.json')
const covers = existsSync(COVERS) ? JSON.parse(readFileSync(COVERS, 'utf8')) : {}

for (const r of readLog()) {
  if (!r.title) continue
  const book = upsert(keyOf(r.title), { title: r.title, englishTitle: r.englishTitle })
  book.read = true
  // 같은 책을 두 번 읽었으면 최근 것을 남긴다
  if (!book.readAt || r.readAt > book.readAt) book.readAt = r.readAt
}

// 영문 제목으로 들어온 책을 한글 기록과 합친다.
// 읽은 기록에 english-title 이 있으므로, 그 열을 별칭 삼아 같은 책임을 알아본다.
for (const r of readLog()) {
  if (!r.englishTitle) continue
  const ko = books.get(keyOf(r.title))
  const en = books.get(keyOf(r.englishTitle))
  if (!ko || !en || ko === en) continue
  for (const src of en.sources) {
    if (!ko.sources.some((x) => x.id === src.id)) ko.sources.push(src)
  }
  for (const k of ['author', 'cover', 'publisher', 'addedAt']) {
    if (!ko[k] && en[k]) ko[k] = en[k]
  }
  books.delete(keyOf(r.englishTitle))
}

// 수집 원본에 없던 표지·저자를 채운다 (원본 값이 있으면 그대로 둔다)
for (const book of books.values()) {
  const c = covers[book.title]
  if (!c || c.notfound || c.uncertain) continue
  if (!book.author) book.author = c.author || ''
  if (!book.cover) book.cover = c.cover || ''
  if (!book.publisher) book.publisher = c.publisher || ''
  if (!book.aladin) book.aladin = c.aladin || ''
}

// ---- 출력 ----
const all = [...books.values()].map((b) => ({
  title: b.title,
  author: b.author || '',
  englishTitle: b.englishTitle || '',
  cover: b.cover || '',
  publisher: b.publisher || '',
  aladin: b.aladin || '',
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

const used = new Set(all.flatMap((b) => b.sources.map((s) => s.id)))
const services = [
  ...SERVICES.filter((s) => used.has(s.id)),
  ...[...used]
    .filter((id) => !SERVICES.some((s) => s.id === id))
    .map((id) => ({ id, name: id, kind: 'ebook' })),
].map((s) => ({ ...s, count: all.filter((b) => b.sources.some((x) => x.id === s.id)).length }))

const out = {
  updatedAt: new Date().toISOString().slice(0, 10),
  total: all.length,
  services,
  books: all,
}
writeFileSync(OUT, JSON.stringify(out, null, 1) + '\n')

const unknown = all.filter((b) => !b.sources.length).length
console.log(`${all.length}권 → data/library.json`)
console.log(services.map((s) => `  ${s.name} ${s.count}`).join('\n') || '  (수집된 서비스 없음)')
if (unknown) console.log(`  소장처 미확인 ${unknown}`)
