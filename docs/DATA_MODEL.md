# 데이터 모델 (Firestore)

범용 다중 대상. 최상위 단위는 **target**(모니터링 대상 = 워크스페이스). 모든 데이터는 `targets/{targetId}` 하위에 격리된다.

```
targets/{targetId}
  name            string   # 예: "민주당 전당대회"
  description     string
  ownerUid        string
  createdAt       ts
  keywords        string[] # 검색 키워드 (예: 전당대회, 당대표, 최고위원)
  entities        map[]    # [{name:"김민석", role:"당대표후보", aliases:[...]}]
  channels        map[]    # [{platform:"youtube", url/handle, label}]
  sources         map      # {naver:true, youtube:true, x:false, community:["dcinside","fmkorea"]}
  schedule        map      # {collectEveryMin:30, reportDaily:"08:00", reportWeekly:"mon 10:00"}

targets/{targetId}/members/{uid}
  role            string   # "admin" | "member"
  email, displayName
  joinedAt        ts

# ── 원본 수집물 (개별 글/영상/기사) ─────────────────────────────
targets/{targetId}/items/{itemId}      # itemId = dedup 해시
  platform        string   # naver_news | naver_blog | naver_cafe | youtube | x | dcinside | fmkorea | clien ...
  sourceType      string   # news | blog | cafe | video | sns | community
  url             string
  title           string
  content         string   # 본문/요약
  author          string
  authorId        string   # 작성자 영향력 집계용
  publishedAt     ts
  collectedAt     ts
  metrics         map      # {views, likes, comments}
  keyword         string   # 매칭된 검색 키워드
  matchedEntities string[] # 본문에 등장한 등록 인물
  sentiment       string   # positive | neutral | negative | attack
  clusterId       string|null
  rejected        bool
  rejectReason    string   # noise | old_date | irrelevant | hallucination | duplicate

# ── 이슈 클러스터 (같은 사건 묶음) ─────────────────────────────
targets/{targetId}/clusters/{clusterId}
  title           string   # 대표 제목
  summary         string   # Claude 1~2줄 요약
  firstSeen       ts
  lastSeen        ts
  status          string   # active | resolved | archived
  grade           string   # red | orange | yellow | none
  patterns        string[] # ["부정다플랫폼","부정키워드","매체다양성","다플랫폼집단"]
  filterTag       string   # 대응필요 | 주의 | 위기 | 재발 | 전체
  reactivated     bool     # 대응완료 후 재활성(재발) 여부
  stats           map      # {posts, comments, likes, platforms:[], sentiment:{pos,neu,neg,attack}}
  itemCount       int
  topItemIds      string[] # 대표 글 일부 (전체는 items.clusterId 쿼리)

# 캠프 대응 (관리자가 작성 → 회원이 조회·대응)
targets/{targetId}/clusters/{clusterId}/responses/{respId}
  createdBy       string   # admin uid
  createdAt       ts
  updatedAt       ts
  status          string   # draft | published
  plan            string   # 대응 방안 (자유 서술)
  steps           map[]    # [{order:1, text:"...", assigneeRole:"member"|"admin", done:false}]
  links           map[]    # [{title, url}]  ← "눌러야 하는 링크"
  lawCheckRequired bool    # 외부 발송 콘텐츠 변호사 검토 필요 표시
  aiSuggested     bool     # AI 추천안 사용 여부

# 회원 확인/대응 추적 (읽음·링크클릭)
targets/{targetId}/clusters/{clusterId}/acks/{uid}
  uid, displayName
  readAt          ts
  clickedLinks    string[] # 클릭한 링크 url
  status          string   # read | acted
  note            string

# ── 위기 알림 히스토리 ─────────────────────────────────────────
targets/{targetId}/alerts/{alertId}
  createdAt       ts
  grade           string   # red | orange | yellow
  type            string   # "부정 키워드 폭발", "다플랫폼 확산" ...
  summary         string
  clusterIds      string[]
  keywords        map[]    # [{word:"의혹 제기", count:5}]
  platforms       string[]
  links           map[]    # 관련 글 링크

# ── 보고서 (일일/주간) ─────────────────────────────────────────
targets/{targetId}/reports/{reportId}
  type            string   # daily | weekly
  period          string   # "2026-06-14 오후" | "2026-W24"
  generatedAt     ts
  totals          map      # {mentions, uniqueIssues, alerts}
  bodyMarkdown    string
  excelUrl        string|null

# ── 키워드 동향 (동반 키워드 Top N, 일자별) ────────────────────
targets/{targetId}/keywordTrend/{yyyymmdd}
  date            string
  top             map[]    # [{word, count, deltaPct}]

# ── 작성자 영향력 (최근 90일 누적, 작성자 집계) ─────────────────
targets/{targetId}/authors/{authorId}
  name            string
  mainPlatform    string
  score           number
  postCount       int
  targetMentions  int      # 등록 대상 언급 수
  grade           string   # 영향력 등급
  flags           string[] # 위험/주의 플래그

# ── 거부 큐 (필터에 걸린 글, 오탐 검토용) ───────────────────────
targets/{targetId}/rejected/{itemId}
  (items 와 동일 구조 + rejectReason 강조, 24h~기간 보관)
```

## 규칙

- **격리**: 모든 읽기/쓰기는 `targets/{targetId}` 경로 포함. target 멤버만 접근.
- **권한**: `members/{uid}.role == admin` 만 `responses` 쓰기·클러스터 상태 변경 가능. 회원은 읽기 + 본인 `acks` 쓰기만.
- **dedup**: `itemId = sha256(platform + canonical_url)[:16]`. 같은 글 재수집 시 metrics만 갱신.
- **30일 윈도우**: `window_days` 이전 항목은 매일 자정 `daily_cleanup`이 archived/삭제.
- **재발(reactivated)**: status가 resolved인 클러스터에 새 item 유입 시 reactivated=true, filterTag="재발".

보안 규칙 구현은 `dashboard/firestore.rules` 참고.
