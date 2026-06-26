# 셋업 가이드

노트북에서 수집 엔진을 돌리고, 클라우드(Firebase)에 대시보드를 올려 휴대폰/PC로 접속하는 전체 절차.

## 0. 준비물 (키 발급)

| 키 | 발급처 |
|----|--------|
| 네이버 검색 API | https://developers.naver.com → 애플리케이션 등록 → 검색 |
| 유튜브 Data API | https://console.cloud.google.com → API 및 서비스 → YouTube Data API v3 사용 설정 → API 키 |
| Anthropic | https://console.anthropic.com → API Keys |
| Firebase | https://console.firebase.google.com → 프로젝트 생성 |

## 1. Firebase 프로젝트 설정

1. [Firebase 콘솔](https://console.firebase.google.com)에서 프로젝트 생성.
2. **Firestore Database** 만들기 (프로덕션 모드, 리전 `asia-northeast3` 서울 권장).
3. **Authentication** → 로그인 방법 → **이메일/비밀번호** 사용 설정.
4. **Hosting** 시작.
5. 프로젝트 설정 → 일반 → "내 앱"에 **웹 앱(</>)** 추가 → `firebaseConfig` 값 복사 (대시보드용).
6. 프로젝트 설정 → **서비스 계정** → "새 비공개 키 생성" → 내려받은 JSON 을
   `engine/serviceAccountKey.json` 으로 저장 (엔진용, 절대 커밋 금지 — .gitignore 처리됨).
7. `.firebaserc` 의 `YOUR_FIREBASE_PROJECT_ID` 를 실제 프로젝트 ID 로 교체.

## 2. 엔진 (노트북)

```powershell
cd engine
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# (선택) 고정밀 한국어 임베딩:
pip install -r requirements-embed.txt   # 그리고 .env 의 EMBED_PROVIDER=kosimcse
playwright install chromium             # 스크래핑 쓸 때

copy .env.example .env
# .env 에 NAVER_*, YOUTUBE_API_KEY, ANTHROPIC_API_KEY, FIREBASE_PROJECT_ID 채우기
```

### (선택) 로그인 사이트 직접 수집 준비

네이버 카페·X·인스타·페북·스레드처럼 로그인이 필요한 곳은, 컴퓨터가 **로그인된 브라우저로 직접 수집**한다.
한 번만 수동 로그인하면 세션이 프로필(.browser_profile)에 저장된다.

```powershell
playwright install chromium
python -m engine.scripts.login --sites naver x instagram facebook threads
# 열린 브라우저 탭에서 각 사이트 로그인 → 터미널에서 Enter (세션 저장)
```

이후 대시보드 **설정 → 수집 소스**에서 해당 로그인 사이트를 체크하면 수집 대상에 포함된다.

### 사이트 동작 점검 (권장)

각 사이트가 실제로 글을 뽑는지 확인(로그인 사이트 포함). 0건이면 URL/패턴/로그인 튜닝 필요.

```powershell
python -m engine.scripts.probe_sites --keyword 이재명            # 전체 점검
python -m engine.scripts.probe_sites --keyword 전당대회 --sites dcinside clien x
python -m engine.scripts.probe_sites --headed                   # 브라우저 보면서
```
> 기본 활성 8곳(디시·클리앙·루리웹·뽐뿌·엠팍·네이트판·다음뉴스·네이트뉴스)은 실접속 검증 완료.

### 1차 타깃(전당대회) + 관리자 생성

```powershell
# 관리자 계정까지 한 번에:
python -m engine.scripts.seed_target --admin-email 본인@메일.com --admin-password "비번"
```

### 수집 1회 / 상시 실행

```powershell
python -m engine.pipeline --target minju-jeondaehoe --once   # 1회 테스트
python -m engine.main                                        # 30분 주기 상시
```

## 3. 보안 규칙·인덱스 배포

```powershell
npm install -g firebase-tools
firebase login
firebase deploy --only firestore:rules,firestore:indexes
```

## 4. 대시보드 (클라우드)

```powershell
cd dashboard
npm install
copy .env.example .env.local
# .env.local 에 1-5 에서 복사한 firebaseConfig 값 채우기
npm run dev                       # 로컬 미리보기 (http://localhost:5173)

npm run build
cd ..
firebase deploy --only hosting    # https://<project>.web.app 으로 배포
```

휴대폰에서 `https://<project>.web.app` 접속 → 시드로 만든 관리자 계정으로 로그인.

## 5. 회원 추가

회원이 대시보드에서 이메일/비번으로 가입한 뒤(또는 관리자가 생성), 노트북에서:

```powershell
python -m engine.scripts.add_member --target minju-jeondaehoe --email 회원@메일.com --role member
```

> 회원 가입 자체를 막고 "관리자 승인제"로 운영하려면, 가입은 허용하되 `members` 에 등록된
> 사용자만 데이터가 보이도록 보안 규칙이 강제한다(미등록자는 로그인돼도 빈 화면).

## 6. 점검 체크리스트

- [ ] `python -m engine.tests.test_core` 통과 (코어 로직)
- [ ] `--once` 실행 후 Firestore `targets/minju-jeondaehoe/clusters` 에 문서 생성 확인
- [ ] 대시보드 로그인 → 이슈 클러스터 표시
- [ ] 관리자: 클러스터 상세에서 대응 방안 작성 → 발행
- [ ] 회원 계정: 대응 조회 + 링크 클릭 → 관리자 화면에서 확인(ack) 표시
