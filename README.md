# 모니터링 AI (Monitoring AI)

범용 온라인 여론 모니터링 시스템. **노트북에서 도는 수집·분석 엔진**과 **클라우드(Firebase) 대시보드**로 구성된다.
임의의 대상(인물·키워드·채널)을 등록하면 뉴스·유튜브·SNS·커뮤니티를 수집하고, 같은 사건을 자동으로 묶어(이슈 클러스터) 위기 등급을 매기고, 관리자가 대응 방안·순서를 정하면 회원이 보고 대응한다.

> 1차 타깃: **민주당 전당대회** (당대표 후보 김민석·정청래·김용민, 최고위원 후보, 이재명 대통령 메시지)

---

## 구성

```
모니터링 Ai/
├── engine/        # 노트북에서 도는 Python 수집·분석 엔진
├── dashboard/     # 클라우드(Firebase Hosting) React 대시보드
└── docs/          # 설계 문서 (아키텍처·데이터 모델)
```

### 데이터 흐름

```
[노트북 engine]
  수집(네이버·유튜브·RSS·스크래핑)
   → 필터(노이즈·날짜·관련성·환각) → 거부 큐
   → 임베딩 → 클러스터링(같은 사건 묶기)
   → 위기 등급(A/B/C/D 패턴 + red/orange/yellow) + Claude 감정·요약
   → Firestore write
          │
          ▼  (클라우드 공유 DB)
[Firebase]  Firestore + Auth(이메일 로그인, 관리자/회원) + Hosting
          │
          ▼
[dashboard]  React+Vite (PC/모바일)
   이슈클러스터 · 위기알림 · 보고서 · 키워드 · 작성자영향력 · 거부검토
   + 관리자 대응방안/대응순서 입력 → 회원 조회·링크클릭 확인(읽음/대응 추적)
```

자세한 내용은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATA_MODEL.md](docs/DATA_MODEL.md) 참고.

---

## 빠른 시작 (엔진, 노트북)

```bash
cd engine
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell
pip install -r requirements.txt
# (선택) 고정밀 한국어 임베딩을 쓰려면:
pip install -r requirements-embed.txt
playwright install chromium       # 스크래핑용

copy .env.example .env            # 키 채우기 (네이버·유튜브·Anthropic·Firebase)
python -m engine.main             # 스케줄러 시작 (주기적 수집·분석·저장)
# 1회만 돌려보기:
python -m engine.pipeline --target <targetId> --once
```

## 빠른 시작 (대시보드, 클라우드)

```bash
cd dashboard
npm install
copy .env.example .env.local      # Firebase 웹 설정 채우기
npm run dev                       # 로컬 미리보기
npm run build && firebase deploy  # Firebase Hosting 배포
```

---

## 필요한 키 / 계정

| 용도 | 키/계정 | 비고 |
|------|---------|------|
| 네이버 뉴스·블로그·카페 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | [developers.naver.com](https://developers.naver.com) |
| 유튜브 채널·영상·댓글 | `YOUTUBE_API_KEY` | Google Cloud Console |
| 감정·요약·대응안 추천 | `ANTHROPIC_API_KEY` | Claude API |
| 공유 DB·인증·호스팅 | Firebase 프로젝트 + 서비스계정 JSON | engine은 Admin SDK, dashboard는 Web SDK |
| (선택) SNS 스크래핑 | `APIFY_API_TOKEN` | 페북/인스타 등 |

SNS/커뮤니티 중 API가 없는 소스는 Playwright 스크래퍼로, 그래도 막히면 Claude for Chrome(수동 보조)로 보완한다.

---

## 상태 / 검증

엔진·대시보드 구현 완료, 코드 레벨 검증 통과. 실배포는 사용자 Firebase 키 발급 후 진행([docs/SETUP.md](docs/SETUP.md)).

| 검증 항목 | 방법 | 결과 |
|-----------|------|------|
| 코어 로직(필터·클러스터·등급) | `python -m engine.tests.test_core` | ✅ |
| 전체 파이프라인 E2E 시뮬레이션 | `python -m engine.tests.test_pipeline_sim` | ✅ (수집→…→보고서, dedup·증분·누적) |
| 엔진 모듈 import 무결성 | 20개 모듈 import | ✅ |
| 직렬화 라운드트립 | item/cluster doc ↔ 객체 | ✅ |
| 대시보드 타입체크+빌드 | `npm run build` (tsc+vite) | ✅ 72 modules |
| 엔진↔대시보드 사이트 키 정합성 | 20키 대조 | ✅ |
| 설정 JSON 유효성 | firebase/indexes/.firebaserc | ✅ |

| 수집 사이트 실접속 검증 | Playwright 8개 사이트 접속·추출 | ✅ (디시·클리앙·루리웹·뽐뿌·엠팍·네이트판·다음/네이트뉴스) |

> 검증 중 발견·수정: ① TF-IDF용 클러스터 임계값 분리(0.62→0.30, 같은 사건 묶임 보장), ② 작성자 영향력 누적(Increment)로 전환, ③ 사이트별 글 링크 패턴(link_pattern) 도입 + 중복 글 제목 제거(실접속 검증으로 잡링크·중복 노출 문제 해결).
> 기본 활성 8개 사이트는 실접속 검증 완료. 나머지(에펨·더쿠·인스티즈 등)는 봇보호/로그인으로 기본 비활성(`probe_sites` 로 점검·튜닝).
> Firestore 보안규칙 에뮬레이터 테스트는 Java 미설치로 보류(코드/배포 가이드는 준비됨).
