"""전당대회 여론조사 전용 수집기 — Poll Master 중심 구조.

기사 1개 = poll row가 아니라, 동일 조사 = poll master 1개.
같은 조사를 다룬 여러 기사는 sourceArticles 배열로 병합.
dedupeKey = sha256(pollster_canon|start_date|end_date|sample_size)[:16]
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from ..candidates import ALL_CANDIDATE_NAMES

CANDIDATES = ALL_CANDIDATE_NAMES

# ── 조사기관 정규화 ────────────────────────────────────────────
# 미디어토마토=조사기관, 뉴스토마토=의뢰/보도매체 (계열사 관계)
POLLSTER_CANON: dict[str, str] = {
    "뉴스토마토": "미디어토마토",  # 뉴스토마토는 의뢰사, 조사는 미디어토마토
}

def _canon_pollster(name: str) -> str:
    """조사기관명 표준화."""
    return POLLSTER_CANON.get(name.strip(), name.strip())


# ── 검색 키워드 ────────────────────────────────────────────────
POLL_KEYWORDS = [
    "민주당 당대표 적합도",
    "전당대회 당대표 적합도",
    "민주당 당대표 지지율",
    "전당대회 당대표 지지율",
    "당대표 후보 적합도",
    "민주당 전대 지지율",
    "민주당 당대표 여론조사",
    # poll watch — 기관별 정기 탐지
    "뉴스토마토 민주당 당대표",
    "미디어토마토 민주당 당대표",
    "김민석 정청래 여론조사",
    "당대표 지지도 김민석",
    "정기여론조사 민주당 당대표",
]

TOPIC_KW = ["당대표", "전당대회", "전대"]
POLL_KW  = ["지지율", "여론조사", "적합도", "지지도", "지지도조사"]

# 대통령/국정 관련 → 당대표 여론조사에서 제외
EXCLUDE_KW = [
    "대통령 지지율", "대통령 지지도", "국정지지율", "국정수행",
    "긍정평가", "부정평가", "이재명 지지율", "국정운영", "대통령 국정",
]

# ── 후보 수치 추출 ─────────────────────────────────────────────
FULL_RE = re.compile(
    r"(" + "|".join(CANDIDATES) + r")[^0-9\n]{0,20}?(\d{1,3}(?:\.\d+)?)\s*%"
)
ABBREV: dict[tuple[str, str], str] = {
    ("김", "총리"):   "김민석",
    ("정", "대표"):   "정청래",
    ("정", "의원"):   "정청래",
    ("송", "의원"):   "송영길",
    ("송", "전대표"): "송영길",
    ("고", "의원"):   "고민정",
    ("강", "의원"):   "강훈식",
}
ABBREV_RE = re.compile(
    r"([가-힣]{1,3})\s*(총리|대표|의원|전대표|의장|대통령|후보)\s*(\d{1,3}(?:\.\d+)?)\s*%"
)
OG_RE  = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']', re.I)
OG_RE2 = re.compile(r'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+property=["\']og:image["\']', re.I)


def _resolve(surname: str, title: str, full_names: set[str]) -> Optional[str]:
    key = (surname, title)
    if key in ABBREV and ABBREV[key] in full_names:
        return ABBREV[key]
    matches = [n for n in full_names if n.startswith(surname)]
    return matches[0] if len(matches) == 1 else None


def _parse_candidates(snippet: str, full_names: set[str]) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for m in FULL_RE.finditer(snippet):
        n = m.group(1)
        if n in CANDIDATES and n not in seen:
            seen.add(n)
            results.append({"name": n, "pct": float(m.group(2))})
    for m in ABBREV_RE.finditer(snippet):
        n = _resolve(m.group(1), m.group(2), full_names or set(CANDIDATES))
        if n and n not in seen:
            seen.add(n)
            results.append({"name": n, "pct": float(m.group(3))})
    return results


def extract_poll_sections(text: str) -> tuple[list[dict], list[dict]]:
    """기사 본문에서 일반·민주당지지층 후보 수치를 별도 추출."""
    full_names = {m.group(1) for m in FULL_RE.finditer(text)} & set(CANDIDATES)

    fi = min((text.find(n) for n in full_names if text.find(n) > 0), default=0)
    cut_keys = ["지역별로", "정당 지지층별", "이념성향별", "성별로", "연령별"]
    cuts = [text.find(k, fi) for k in cut_keys if text.find(k, fi) > 0]
    cut = min(cuts) if cuts else fi + 2000
    general = _parse_candidates(text[fi:cut], full_names)

    idx = text.find("민주당 지지층")
    party: list[dict] = []
    if idx >= 0:
        snip = text[idx: idx + 500]
        ends = [snip.find(k) for k in ["조국혁신", "국민의힘", "이념성향", "\n\n"] if snip.find(k) > 0]
        end = min(ends) if ends else len(snip)
        party = _parse_candidates(snip[:end], full_names)

    return general, party


# ── 기사 본문 가져오기 ─────────────────────────────────────────
async def _fetch_article(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    try:
        r = await client.get(url, timeout=10.0, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (Macintosh)"})
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        el = (soup.find("div", {"id": "article-view-content-div"}) or
              soup.find("article") or
              soup.find("div", id=re.compile(r"content|article", re.I)))
        text = el.get_text("\n") if el else soup.get_text("\n")
        og = (m.group(1) for m in (OG_RE.search(html[:8000]), OG_RE2.search(html[:8000])) if m)
        image_url = next(og, "")
        return text, image_url
    except Exception:
        return "", ""


# ── 조사기관·의뢰기관·메타 정규식 추출 ────────────────────────
_RESEARCH_FIRMS = (
    "한국갤럽|리얼미터|한국리서치|엠브레인|케이스탯|NBS|KSOI|윈지코리아|"
    "조원씨앤아이|리서치뷰|에이스리서치|피플네트웍스|미디어토마토|"
    "PNR|글로벌리서치|코리아리서치|알앤써치|칸타|입소스|닐슨IQ"
)
_MEDIA_FIRMS = (
    "KBS|MBC|SBS|YTN|JTBC|TV조선|채널A|MBN|연합뉴스|뉴시스|뉴스1|"
    "조선일보|중앙일보|동아일보|한겨레|경향신문|오마이뉴스|프레시안|"
    "문화일보|국민일보|서울신문|세계일보|한국일보|매일경제|한국경제|머니투데이|"
    "헤럴드경제|아시아경제|이데일리|파이낸셜뉴스|뉴스토마토|스트레이트뉴스|"
    "쿠키뉴스|노컷뉴스|천지일보|CBS|TBS|OBS"
)

_POLLSTER_RE     = re.compile(r"(" + _RESEARCH_FIRMS + r")", re.IGNORECASE)
_MEDIA_RE        = re.compile(r"(" + _MEDIA_FIRMS + r")", re.IGNORECASE)
# "A가 B에 의뢰" 또는 "B 의뢰, A 조사" 패턴
_UIROE_FULL_RE   = re.compile(r"([가-힣A-Za-z]{2,15})\s*(?:가|이|에서|측이|측에서)?\s*([가-힣A-Za-z]{2,15})\s*(?:에|에게|측에)?\s*(?:의뢰|위탁)")
_UIROE_RE        = re.compile(r"(.{2,15}?)\s*(?:의뢰|위탁)")
_JOSA_BEFORE_RE  = re.compile(r"([가-힣]{2,10}(?:리서치|미터|갤럽|조사|코리아|뷰|네트웍|데이터|토마토))\s*(?:가|이|에서|측이|측에서)?\s*(?:실시|조사|진행)")

_PERIOD_RE2 = re.compile(
    r"(\d{4})[.\-](\d{2})[.\-](\d{2})\s*[~\-]\s*(\d{4})[.\-](\d{2})[.\-](\d{2})"
)
_PERIOD_RE = re.compile(
    r"(\d{4})년?\s*(\d{1,2})월?\s*(\d{1,2})일?\s*[~\-]\s*(?:\d{4}년?\s*\d{1,2}월?\s*)?(\d{1,2})일?"
)
_SINGLE_DATE_RE = re.compile(r"(\d{4})[.\-](\d{2})[.\-](\d{2})")

_SAMPLE_RE  = re.compile(r"(?:표본|유효\s*표본|응답자)[:\s]*(\d[\d,]+)\s*명")
_SAMPLE_RE2 = re.compile(r"(\d[\d,]+)\s*명(?:을|을\s*대상|을\s*목표)")
_MARGIN_RE  = re.compile(r"오차\s*범위[^\d±]{0,5}([±＋\-\+]?\s*\d+\.?\d*\s*%p?)")
_GROUP_RE   = re.compile(r"(?:조사\s*대상|응답\s*대상)[:\s는]*([^\n,·]{4,40})")
_METHOD_RE  = re.compile(r"(?:조사\s*방법|조사\s*방식)[:\s는]*([^\n,·]{2,20})")
_TOPIC_RE   = re.compile(r"(?:조사\s*주제|조사\s*내용)[:\s는]*([^\n,·]{4,40})")


def _parse_body_meta(text: str) -> dict:
    """기사 본문에서 조사기관·의뢰기관·기간·표본 등을 정규식으로 추출.

    pollster = 실제 조사한 기관 (미디어토마토 등)
    sponsor  = 조사를 의뢰한 기관/보도매체 (뉴스토마토, KBS 등)
    """
    meta: dict = {}
    snippet = text[:4000]

    # 1) "A가 B에 의뢰해 실시" 패턴 — 가장 명확
    for m in _UIROE_FULL_RE.finditer(snippet):
        sponsor_cand = m.group(1).strip()
        pollster_cand = m.group(2).strip()
        if _POLLSTER_RE.search(pollster_cand):
            meta.setdefault("pollster", pollster_cand)
            if _MEDIA_RE.search(sponsor_cand):
                meta.setdefault("sponsor", sponsor_cand)
            break
        elif _POLLSTER_RE.search(sponsor_cand):
            # 순서 반대인 경우
            meta.setdefault("pollster", sponsor_cand)
            if _MEDIA_RE.search(pollster_cand):
                meta.setdefault("sponsor", pollster_cand)
            break

    # 2) 알려진 조사기관명 직접 매칭
    pm = _POLLSTER_RE.search(snippet)
    if pm:
        meta.setdefault("pollster", pm.group(1))

    # 3) "○○가 조사/실시" 패턴
    if not meta.get("pollster"):
        mj = _JOSA_BEFORE_RE.search(snippet)
        if mj:
            meta["pollster"] = mj.group(1).strip()

    # 4) "○○ 의뢰" → 의뢰기관 추출
    for m in _UIROE_RE.finditer(snippet):
        candidate = m.group(1).strip()
        if _POLLSTER_RE.search(candidate):
            meta.setdefault("pollster", candidate)
        elif _MEDIA_RE.search(candidate) and len(candidate) >= 2:
            meta.setdefault("sponsor", candidate)

    # 5) pollster가 미디어토마토 계열이면 정규화
    if meta.get("pollster"):
        meta["pollster"] = _canon_pollster(meta["pollster"])

    # 6) 의뢰기관/보도매체 fallback
    if not meta.get("sponsor"):
        mm = _MEDIA_RE.search(snippet)
        if mm:
            meta["sponsor"] = mm.group(1)

    # 7) 조사기간 — 범위 우선
    m_p2 = _PERIOD_RE2.search(snippet)
    if m_p2:
        start = f"{m_p2.group(1)}-{m_p2.group(2)}-{m_p2.group(3)}"
        end   = f"{m_p2.group(4)}-{m_p2.group(5)}-{m_p2.group(6)}"
        meta["pollStartDate"] = start
        meta["pollEndDate"]   = end
        meta["pollPeriod"]    = f"{start}~{end}"
    else:
        m_p = _PERIOD_RE.search(snippet)
        if m_p:
            y   = m_p.group(1)
            mon = m_p.group(2).zfill(2)
            d1  = m_p.group(3).zfill(2)
            d2  = m_p.group(4).zfill(2)
            meta["pollStartDate"] = f"{y}-{mon}-{d1}"
            meta["pollEndDate"]   = f"{y}-{mon}-{d2}"
            meta["pollPeriod"]    = f"{y}-{mon}-{d1}~{y}-{mon}-{d2}"
        else:
            m_sd = _SINGLE_DATE_RE.search(snippet)
            if m_sd:
                d = f"{m_sd.group(1)}-{m_sd.group(2)}-{m_sd.group(3)}"
                meta["pollStartDate"] = d
                meta["pollEndDate"]   = d
                meta["pollPeriod"]    = d

    # 8) 표본수
    m_s = _SAMPLE_RE.search(snippet) or _SAMPLE_RE2.search(snippet)
    if m_s:
        try:
            meta["sampleSize"] = int(m_s.group(1).replace(",", ""))
        except ValueError:
            pass

    # 9) 오차범위
    m_e = _MARGIN_RE.search(snippet)
    if m_e:
        meta["marginOfError"] = m_e.group(1).strip()

    # 10) 조사대상
    m_g = _GROUP_RE.search(snippet)
    if m_g:
        meta["sampleGroup"] = m_g.group(1).strip()[:40]

    # 11) 조사방법
    m_m = _METHOD_RE.search(snippet)
    if m_m:
        meta["surveyMethod"] = m_m.group(1).strip()

    return meta


def _parse_title_meta(title: str) -> dict:
    """제목에서 매체명·기간 직접 파싱."""
    meta: dict = {}
    brackets = re.findall(r'\[([^\]]+)\]', title)
    for b in brackets:
        date_m = re.match(r'(\d{4})(\d{2})(\d{2})-(\d{2})', b)
        if date_m:
            y, mo, d1, d2 = date_m.groups()
            meta["pollStartDate"] = f"{y}-{mo}-{d1}"
            meta["pollEndDate"]   = f"{y}-{mo}-{d2}"
            meta["pollPeriod"]    = f"{y}-{mo}-{d1}~{y}-{mo}-{d2}"
            continue
        clean = re.sub(r'여론조사|정기여론조사', '', b).strip()
        if clean and len(clean) >= 2:
            if _POLLSTER_RE.search(clean):
                meta.setdefault("pollster", _canon_pollster(clean))
            elif _MEDIA_RE.search(clean):
                meta.setdefault("sponsor", clean)
    return meta


def _make_dedupe_key(pollster: str, start: str, end: str, sample_size) -> str:
    """강화된 dedupeKey: pollster(정규화)+기간+표본수.

    기간과 표본수가 없으면 신뢰도 낮으므로 fallback url 사용.
    """
    ps = _canon_pollster(pollster).lower().strip() if pollster else ""
    s  = (start or "").strip()
    e  = (end or "").strip()
    sz = str(int(sample_size)) if sample_size else ""
    raw = f"{ps}|{s}|{e}|{sz}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _leading_candidate(candidates: list[dict]) -> str:
    if not candidates:
        return ""
    top = max(candidates, key=lambda c: c.get("pct", 0))
    return top.get("name", "")


# ── GPT 구조화 추출 ───────────────────────────────────────────
async def _gpt_parse_poll(title: str, text: str) -> dict:
    """GPT로 여론조사 전체 메타 + 후보 수치 추출."""
    try:
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            return {}
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=openai_key)

        snippet = (title + "\n\n" + text)[:3000]
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=700,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "다음 기사에서 더불어민주당 전당대회 당대표 여론조사 정보를 추출하라.\n"
                        f"후보: {', '.join(CANDIDATES)}\n"
                        "중요: 대통령 지지율/국정지지율 조사는 isPollArticle=false로 처리.\n"
                        "결과는 반드시 JSON만 출력. 형식:\n"
                        "{\n"
                        '  "isPollArticle": true,\n'
                        '  "isPartyLeaderPoll": true,\n'
                        '  "pollster": "조사기관명 (실제 조사 수행한 기관, 예: 미디어토마토)",\n'
                        '  "sponsor": "의뢰·보도 매체명 (예: 뉴스토마토)",\n'
                        '  "pollStartDate": "2026-06-22",\n'
                        '  "pollEndDate": "2026-06-23",\n'
                        '  "sampleSize": 1035,\n'
                        '  "sampleGroup": "전국 만18세 이상 성인",\n'
                        '  "marginOfError": "±3.1%p",\n'
                        '  "surveyMethod": "전화면접",\n'
                        '  "general": [{"name": "김민석", "pct": 27.4}],\n'
                        '  "party": [],\n'
                        '  "extractionConfidence": 0.9,\n'
                        '  "needsReview": false\n'
                        "}\n"
                        "- general: 전체/일반 응답자 기준 지지율\n"
                        "- party: 민주당 지지층 기준 (없으면 빈 배열)\n"
                        "- 없는 항목은 null\n"
                        "- 수치가 없으면 general/party는 빈 배열\n"
                        "- pollster와 sponsor를 혼동하지 말 것"
                    ),
                },
                {"role": "user", "content": snippet},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")

        # 당대표 여론조사가 아닌 경우 빈 결과
        if not parsed.get("isPollArticle") or not parsed.get("isPartyLeaderPoll"):
            return {"_not_poll": True}

        # 수치 검증
        for key in ("general", "party"):
            parsed[key] = [
                c for c in parsed.get(key, [])
                if c.get("name") in CANDIDATES and isinstance(c.get("pct"), (int, float))
            ]
        # pollster 정규화
        if parsed.get("pollster"):
            parsed["pollster"] = _canon_pollster(parsed["pollster"])
        # 빈값 정리
        for field in ["pollster", "sponsor", "sampleGroup", "marginOfError", "surveyMethod"]:
            if parsed.get(field) in ("-", "", "없음", "미상", "알 수 없음", None):
                parsed[field] = None

        return parsed
    except Exception as e:
        logger.warning("[poll_gpt] 파싱 실패: {}", e)
        return {}


# ── URL 수동 분석 (분석 큐 처리) ──────────────────────────────
async def analyze_url(url: str) -> dict:
    """단일 기사 URL을 즉시 분석해 poll 구조화 데이터 반환."""
    async with httpx.AsyncClient() as client:
        text, image = await _fetch_article(client, url)
    if not text:
        return {"error": "기사 본문을 가져올 수 없습니다"}

    body_meta = _parse_body_meta(text)
    general, party = extract_poll_sections(text)
    if not general:
        general = [{"name": m.group(1), "pct": float(m.group(2))}
                   for m in FULL_RE.finditer(text[:2000])]

    needs_gpt = not general or not body_meta.get("pollster")
    if needs_gpt:
        gpt = await _gpt_parse_poll("", text)
        if not gpt.get("_not_poll"):
            general = general or gpt.get("general", [])
            party   = party   or gpt.get("party", [])
            for k, v in gpt.items():
                if v and k not in ("general", "party", "_not_poll") and not body_meta.get(k):
                    body_meta[k] = v

    pollster   = body_meta.get("pollster") or ""
    start      = body_meta.get("pollStartDate") or ""
    end        = body_meta.get("pollEndDate") or ""
    sample_sz  = body_meta.get("sampleSize")

    dedup_key = _make_dedupe_key(pollster, start, end, sample_sz) if (pollster and start) else \
                hashlib.sha256(url.encode()).hexdigest()[:16]

    return {
        "dedupeKey":     dedup_key,
        "pollster":      pollster,
        "sponsor":       body_meta.get("sponsor") or "",
        "pollStartDate": start,
        "pollEndDate":   end,
        "pollPeriod":    body_meta.get("pollPeriod") or "",
        "sampleSize":    sample_sz,
        "sampleGroup":   body_meta.get("sampleGroup") or "",
        "marginOfError": body_meta.get("marginOfError") or "",
        "surveyMethod":  body_meta.get("surveyMethod") or "",
        "candidatesGeneral": general,
        "candidatesParty":   party,
        "leadingCandidate":  _leading_candidate(general),
        "hasData":       len(general) >= 1,
        "needsReview":   len(general) == 0 and bool(pollster),
        "sourceArticle": {"url": url, "title": "", "platform": "manual"},
    }


# ── 분석 큐 처리 ──────────────────────────────────────────────
async def process_analysis_queue(target_id: str, store) -> int:
    """Firestore pollAnalysisQueue에서 pending 항목을 처리."""
    try:
        db = store.connect()
        queue_ref = store._target_ref(target_id).collection("pollAnalysisQueue")
        pending = [d for d in queue_ref.where("status", "==", "pending").stream()]
        if not pending:
            return 0

        results = []
        for doc in pending:
            data = doc.to_dict()
            url = data.get("url", "")
            if not url:
                doc.reference.update({"status": "error", "error": "URL 없음"})
                continue
            try:
                doc.reference.update({"status": "processing"})
                result = await analyze_url(url)
                result["sourceArticle"]["title"] = data.get("title", "")
                result["source"] = "manual_queue"
                result["savedAt"] = datetime.now(timezone.utc)
                results.append(result)
                doc.reference.update({"status": "done"})
                logger.info("[poll_queue] 분석 완료: {}", url[:60])
            except Exception as e:
                doc.reference.update({"status": "error", "error": str(e)})

        if results:
            store.save_polls(target_id, results)
        return len(results)
    except Exception as e:
        logger.warning("[poll_queue] 큐 처리 실패: {}", e)
        return 0


# ── 메인 수집 함수 ─────────────────────────────────────────────
async def collect_poll_news(since: datetime | None = None) -> list[dict]:
    """네이버뉴스에서 전당대회 당대표 여론조사 기사 수집 → poll master 단위로 반환."""
    from ..collectors.naver import NaverCollector

    if since is None:
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=90)

    collector = NaverCollector()
    raw = await collector.collect(POLL_KEYWORDS, since=since, limit=600)

    # 제목 필터: 당대표/전당대회 AND 여론조사 키워드 포함, 대통령 관련 제외
    filtered = [
        it for it in raw
        if (any(k in it.title for k in TOPIC_KW) and any(k in it.title for k in POLL_KW))
        and not any(k in it.title for k in EXCLUDE_KW)
        and it.platform in {"naver_news", "google_news", "nate_news", "daum_news"}
    ]

    seen_urls: set[str] = set()
    unique = [it for it in filtered if not (it.url in seen_urls or seen_urls.add(it.url))]  # type: ignore
    logger.info("[poll_news] 수집 {}건 → 필터 {}건", len(raw), len(unique))

    # 기사 본문 수집 및 파싱
    async with httpx.AsyncClient() as client:
        for it in unique:
            text, image = await _fetch_article(client, it.url)
            if not text:
                continue

            general, party = extract_poll_sections(text)
            if not general:
                general = [{"name": m.group(1), "pct": float(m.group(2))}
                           for m in FULL_RE.finditer(f"{it.title} {it.content}")]

            # 1순위: 본문 정규식
            body_meta = _parse_body_meta(text)
            title_meta = _parse_title_meta(it.title)
            for k, v in title_meta.items():
                if v and not body_meta.get(k):
                    body_meta[k] = v
            it.__dict__["_body_meta"] = body_meta

            # 2순위: 정규식 실패 시 GPT
            needs_gpt = (not general) or (not body_meta.get("pollster") and not body_meta.get("pollPeriod"))
            if needs_gpt:
                gpt = await _gpt_parse_poll(it.title, text)
                if gpt.get("_not_poll"):
                    it.__dict__["_skip"] = True
                    continue
                general = general or gpt.get("general", [])
                party   = party   or gpt.get("party", [])
                for k, v in gpt.items():
                    if v and k not in ("general", "party", "_not_poll") and not body_meta.get(k):
                        body_meta[k] = v

            it.__dict__["_general"] = general
            it.__dict__["_party"]   = party
            if image:
                it.image_url = image

    # poll master 단위로 결과 생성
    raw_results = []
    for it in unique:
        if it.__dict__.get("_skip"):
            continue
        general = it.__dict__.get("_general") or []
        party   = it.__dict__.get("_party", [])
        meta    = it.__dict__.get("_body_meta") or {}

        pollster    = meta.get("pollster") or ""
        sponsor     = meta.get("sponsor") or ""
        start       = meta.get("pollStartDate") or ""
        end         = meta.get("pollEndDate") or ""
        poll_period = meta.get("pollPeriod") or ""
        sample_size = meta.get("sampleSize")
        sample_group = meta.get("sampleGroup") or ""

        # dedupeKey: pollster+기간+표본수 기준 (신뢰도 높음)
        if pollster and start:
            dedup_key = _make_dedupe_key(pollster, start, end, sample_size)
        else:
            dedup_key = hashlib.sha256(it.url.encode()).hexdigest()[:16]

        raw_results.append({
            "dedupeKey":         dedup_key,
            "surveyType":        "party_leader",
            "pollster":          pollster,
            "sponsor":           sponsor,
            "pollStartDate":     start,
            "pollEndDate":       end,
            "pollPeriod":        poll_period,
            "sampleSize":        sample_size,
            "sampleGroup":       sample_group,
            "marginOfError":     meta.get("marginOfError") or "",
            "surveyMethod":      meta.get("surveyMethod") or "",
            "candidatesGeneral": general,
            "candidatesParty":   party,
            "leadingCandidate":  _leading_candidate(general),
            "hasData":           len(general) >= 2,
            "needsReview":       len(general) == 0 and bool(pollster),
            "source":            "news",
            "imageUrl":          it.image_url or "",
            "sourceArticle": {
                "title":       it.title,
                "url":         it.url,
                "publishedAt": it.published_at,
                "platform":    it.platform,
            },
        })

    # 인-프로세스 1차 병합: 같은 dedupeKey끼리 sourceArticles 모으기
    merged: dict[str, dict] = {}
    for r in raw_results:
        k = r["dedupeKey"]
        if k not in merged:
            merged[k] = {**r, "sourceArticles": [r["sourceArticle"]]}
            del merged[k]["sourceArticle"]
        else:
            existing = merged[k]
            # sourceArticles 중복 없이 추가
            urls_seen = {a["url"] for a in existing["sourceArticles"]}
            if r["sourceArticle"]["url"] not in urls_seen:
                existing["sourceArticles"].append(r["sourceArticle"])
            # 누락 필드 보완 (수치는 덮어쓰지 않음)
            for field in ("pollster", "sponsor", "sampleSize", "sampleGroup", "marginOfError", "surveyMethod"):
                if not existing.get(field) and r.get(field):
                    existing[field] = r[field]
            # candidatesGeneral는 더 많은 쪽 유지
            if len(r.get("candidatesGeneral", [])) > len(existing.get("candidatesGeneral", [])):
                existing["candidatesGeneral"] = r["candidatesGeneral"]
                existing["leadingCandidate"]  = r["leadingCandidate"]
                existing["hasData"]           = r["hasData"]

    results = list(merged.values())
    logger.info("[poll_news] poll master {}개 (원본 {}건)", len(results), len(raw_results))
    return results
