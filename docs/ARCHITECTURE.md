# 아키텍처

## 1. 큰 그림

두 개의 독립 실행 단위 + 하나의 공유 클라우드.

| 단위 | 위치 | 언어/스택 | 역할 |
|------|------|-----------|------|
| **engine** | 노트북(로컬) | Python 3.11+ | 수집·필터·클러스터링·등급·보고서 생성 → Firestore 저장 |
| **Firebase** | 클라우드 | Firestore/Auth/Hosting | 공유 DB·로그인·정적 호스팅 |
| **dashboard** | 클라우드(Hosting) | React+Vite+TS | 조회·대응 워크플로우 (PC/모바일) |

노트북이 꺼지면 수집만 멈추고, 대시보드와 기존 데이터는 클라우드에 그대로 살아있다.

## 2. engine 파이프라인

`engine/pipeline.py` 가 target 하나에 대해 순서대로 실행:

```
1. collect    각 수집기에서 RawItem[] 수집 (네이버·유튜브·RSS·스크래퍼)
2. normalize  dedup 키 생성, 본문 정리, 날짜 파싱
3. filter     거부 규칙 적용 → 통과분 / 거부 큐 분리
4. enrich     관련성·감정 분류 (Claude/룰), 등장 인물 매칭
5. embed      통과분 임베딩 (KoSimCSE / API / TF-IDF)
6. cluster    기존 활성 클러스터와 유사도 매칭 or 신규 클러스터 생성
7. grade      클러스터별 A/B/C/D 패턴 감지 → red/orange/yellow 등급
8. alert      신규/승급 위기 → alerts 기록
9. persist    items/clusters/alerts/authors/keywordTrend 를 Firestore에 upsert
10. cleanup   30일 윈도우 밖 항목 정리 (자정 1회)
```

스케줄러(`engine/main.py`, APScheduler)가 target별 주기(기본 30분)로 1~9를, 자정에 10과 보고서 생성을 돌린다.

## 3. 수집기 (collectors/)

| 수집기 | 소스 | 방식 | 키 |
|--------|------|------|----|
| `naver.py` | 뉴스·블로그·카페 | 공식 검색 API | NAVER_CLIENT_ID/SECRET |
| `youtube.py` | 채널·검색·댓글 | Data API v3 | YOUTUBE_API_KEY |
| `rss.py` | 구글뉴스·구글알리미·언론사 RSS | feedparser | 불필요 |
| `scraper.py` (BrowserCollector) | 커뮤니티·포털·SNS (아래 레지스트리) | Playwright 영구 프로필(로그인 세션) | 선택 |

**사이트 레지스트리** (`collectors/sites.py`) — 검색 URL + 글 링크 패턴(link_pattern). 대시보드 설정에서 ON/OFF:
- **검증 완료(2026-06 Playwright 실접속, 기본 활성)**: 디시인사이드·클리앙·루리웹·뽐뿌·엠엘비파크·네이트판·오늘의유머·에펨코리아·보배드림·다음뉴스·네이트뉴스
- **튜닝 필요(기본 비활성)**: 더쿠·인스티즈(검색 로그인) · 인벤(게임 위주 저관련)·와이고수(검색 미동작)
- **로그인 필요(세션 사용)**: 네이버 카페·X·인스타그램·스레드·페이스북

각 사이트는 검색결과에서 `link_pattern`(정규식)에 맞는 링크만 '글'로 추출(목록·로그인·광고 배제) +
같은 글의 중복 링크는 제목으로 1건 정리.

**게시일 기준 수집(중요)**: 스크랩 시 각 글의 행에서 게시일을 추출(`dateparse.py` — 절대일자·시간·상대표현,
조회수/추천비율 오탐 차단)해 `publishedAt` 에 채운다. 30일 윈도우 밖이면 `old_date` 로 제외하고,
게시일을 못 구한 스크랩 글은 `scrape_require_date=True`(기본) 시 `no_date` 로 제외한다 →
"검색에 떴다는 이유만으로 작년 글이 수집되는" 문제를 차단. (네이버/유튜브/RSS API 는 자체 게시일 사용)

검색 방식은 사이트별로 다르며 `search_method` 로 처리: **GET**(기본), **POST**(폼 필드 제출 — 보배드림:
`startDate={since}` 기간필터 + `date_filtered=True` → 사이트가 최근글만 반환, no_date 면제), **FORM**(검색창에
입력 후 폼 제출 — 에펨코리아: `ds` 세션토큰 자동포함 → 구글 CSE 날짜순; 날짜는 행에서 추출). 로그인 사이트는 `scripts/login.py` 로 1회 로그인 →
영구 프로필 세션으로 **컴퓨터가 직접 수집**. 봇 차단이 심하면 Claude for Chrome 으로 수동 보조.

사이트 동작은 `python -m engine.scripts.probe_sites --keyword 이재명` 으로 언제든 점검(건수·샘플 출력).

## 4. 클러스터링 (analysis/cluster.py)

- 임베딩 후 **온라인(증분) 클러스터링**: 새 item을 최근 30일 활성 클러스터 중심과 코사인 유사도 비교.
  - 최고 유사도 ≥ `cluster_similarity_threshold` → 그 클러스터에 편입(중심 갱신).
  - 아니면 신규 클러스터.
- 임베딩 제공자는 교체 가능(`embed_provider`): `kosimcse`(로컬 고정밀) / `voyage`·`openai`(API) / `tfidf`(의존성 0, 폴백).

## 5. 위기 등급 (analysis/grade.py)

4가지 상승 패턴을 클러스터 단위로 감지:

| 패턴 | 정의(초기 기본값, 설정 가능) |
|------|------------------------------|
| 부정 다플랫폼 | 부정 글이 서로 다른 2개 매체 이상에서 발생 |
| 부정 키워드 | 위험 키워드(의혹·논란·비리·수사 등) 임계 빈도 초과 |
| 매체 다양성 | 한 이슈가 3개 이상 플랫폼에서 동시 발생 |
| 다플랫폼 집단 | 단기간(예: 6h) 글 급증 + 다플랫폼 |

등급: 🔴red = 패턴 3+ 또는 글 임계 상한 / 🟠orange = 패턴 2 / 🟡yellow = 패턴 1. (임계값은 target.schedule/설정에서 조정)

## 6. 대응 워크플로우

1. 관리자가 클러스터 상세에서 **대응 방안 + 대응 순서(steps) + 링크** 작성 → `responses`(status=published).
   - "AI 추천" 버튼: Claude가 초안 생성(관리자가 검토·수정). 외부 발송 콘텐츠는 변호사 검토 필요 표시.
2. 회원은 대시보드에서 published 대응을 조회.
3. 회원이 **링크를 클릭/확인**하면 `acks/{uid}` 에 readAt·clickedLinks 기록 → 관리자가 누가 대응했는지 추적.

## 7. 인증·권한

- Firebase Auth(이메일/비번). 가입은 관리자 초대 또는 관리자 승인제(승인된 회원만 접근).
- 역할은 `targets/{tid}/members/{uid}.role`(admin/member) + (선택) Auth custom claim.
- Firestore 보안 규칙이 역할 기반 읽기/쓰기를 강제(`dashboard/firestore.rules`).

## 8. 비용

네이버·유튜브·RSS 무료 범위 + Claude 사용량 + Firebase 무료 티어(초기 충분)로 시작. 스크래핑/유료 SNS는 필요 시 추가.
