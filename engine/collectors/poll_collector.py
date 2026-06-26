"""전당대회 여론조사 전용 수집기.

네이버뉴스에서 당대표 적합도/지지율 기사를 수집하고,
일반 응답자 수치와 민주당 지지층 수치를 별도 추출한다.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger

CANDIDATES = ["정청래", "김민석", "송영길", "김용민", "김두관", "강훈식", "우원식"]

# 검색 키워드 — 제목에 (당대표|전당대회) AND (지지율|여론조사|적합도) 필터와 함께 사용
POLL_KEYWORDS = [
    "민주당 당대표 적합도",
    "전당대회 당대표 적합도",
    "민주당 당대표 지지율",
    "전당대회 당대표 지지율",
    "당대표 후보 적합도",
    "민주당 전대 지지율",
    "민주당 당대표 여론조사",
]

TOPIC_KW = ["당대표", "전당대회", "전대"]
POLL_KW = ["지지율", "여론조사", "적합도", "지지도"]

# 후보 풀네임 정규식
FULL_RE = re.compile(r"(" + "|".join(CANDIDATES) + r")[^0-9\n]{0,20}?(\d{1,3}(?:\.\d+)?)\s*%")

# 약칭+직함 → 풀네임 매핑
ABBREV: dict[tuple[str, str], str] = {
    ("김", "총리"): "김민석",
    ("정", "대표"): "정청래",
    ("정", "의원"): "정청래",
    ("송", "의원"): "송영길",
    ("송", "전대표"): "송영길",
    ("우", "의원"): "우원식",
    ("우", "의장"): "우원식",
    ("김", "의원"): "김용민",
    ("이", "전대표"): "이재명",
    ("이", "대통령"): "이재명",
    ("강", "의원"): "강훈식",
}
ABBREV_RE = re.compile(
    r"([가-힣]{1,3})\s*(총리|대표|의원|전대표|의장|대통령|후보)\s*(\d{1,3}(?:\.\d+)?)\s*%"
)
OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']', re.I
)
OG_RE2 = re.compile(
    r'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+property=["\']og:image["\']', re.I
)


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
    """기사 본문에서 일반(전체)·민주당지지층 후보 수치를 별도 추출.

    Returns:
        (general, party) — 각각 [{name, pct}, ...]
    """
    full_names = {m.group(1) for m in FULL_RE.finditer(text)} & set(CANDIDATES)

    # 일반: 첫 후보 등장부터 지역별/정당별 교차분석 이전까지
    fi = min((text.find(n) for n in full_names if text.find(n) > 0), default=0)
    cut_keys = ["지역별로", "정당 지지층별", "이념성향별", "성별로", "연령별"]
    cuts = [text.find(k, fi) for k in cut_keys if text.find(k, fi) > 0]
    cut = min(cuts) if cuts else fi + 2000
    general = _parse_candidates(text[fi:cut], full_names)

    # 민주당 지지층 단락
    idx = text.find("민주당 지지층")
    party: list[dict] = []
    if idx >= 0:
        snip = text[idx: idx + 500]
        ends = [snip.find(k) for k in ["조국혁신", "국민의힘", "이념성향", "\n\n"] if snip.find(k) > 0]
        end = min(ends) if ends else len(snip)
        party = _parse_candidates(snip[:end], full_names)

    return general, party


async def _fetch_article(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """기사 본문 텍스트와 og:image URL 반환."""
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


def _parse_title_meta(title: str) -> dict:
    """제목에서 매체명·기간 직접 파싱. 예: [천지일보 여론조사], [20260608-09]"""
    meta: dict = {}
    # 대괄호 안 내용 추출
    brackets = re.findall(r'\[([^\]]+)\]', title)
    for b in brackets:
        # 날짜 패턴: 20260608-09 또는 20260606-08
        date_m = re.match(r'(\d{4})(\d{2})(\d{2})-(\d{2})', b)
        if date_m:
            y, m, d1, d2 = date_m.groups()
            meta["pollPeriod"] = f"{y}-{m}-{d1}~{y}-{m}-{d2}"
            continue
        # 여론조사 제외하고 매체명 추출
        clean = re.sub(r'여론조사|정기여론조사', '', b).strip()
        if clean and len(clean) >= 2:
            meta["media"] = clean
    return meta


async def _gpt_parse_poll(title: str, text: str) -> dict:
    """GPT-4o-mini로 여론조사 전체 메타 + 후보 수치 추출."""
    try:
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            return {}
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=openai_key)

        snippet = (title + "\n\n" + text)[:3000]
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=600,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "다음 기사에서 더불어민주당 전당대회 당대표 여론조사 정보를 추출하라.\n"
                        "후보: 이재명, 정청래, 김민석, 송영길, 김용민, 김두관, 강훈식\n"
                        "결과는 반드시 JSON만 출력. 형식:\n"
                        "{\n"
                        '  "pollster": "조사기관명 (예: 한국갤럽)",\n'
                        '  "media": "의뢰 매체명 (예: KBS, 조선일보)",\n'
                        '  "pollPeriod": "조사기간 (예: 2026-06-20~2026-06-22)",\n'
                        '  "sampleSize": 1000,\n'
                        '  "sampleGroup": "조사대상 (예: 전국 만18세 이상)",\n'
                        '  "marginOfError": "오차범위 (예: ±3.1%p)",\n'
                        '  "surveyMethod": "조사방법 (예: 전화면접, ARS)",\n'
                        '  "general": [{"name": "김민석", "pct": 27.4}],\n'
                        '  "party": [{"name": "김민석", "pct": 35.2}]\n'
                        "}\n"
                        "- general: 전체/일반 응답자 기준 지지율\n"
                        "- party: 민주당 지지층 기준 (없으면 빈 배열)\n"
                        "- 없는 항목은 null 또는 빈값\n"
                        "- 수치가 아예 없는 기사면 general/party는 빈 배열"
                    ),
                },
                {"role": "user", "content": snippet},
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content or "{}")
        # 후보 수치 검증
        parsed["general"] = [
            c for c in parsed.get("general", [])
            if c.get("name") in CANDIDATES and isinstance(c.get("pct"), (int, float))
        ]
        parsed["party"] = [
            c for c in parsed.get("party", [])
            if c.get("name") in CANDIDATES and isinstance(c.get("pct"), (int, float))
        ]
        # "-" 또는 빈값은 None으로 정리
        for field in ["pollster", "media", "pollPeriod", "sampleGroup", "marginOfError", "surveyMethod"]:
            if parsed.get(field) in ("-", "", "없음", "미상", "알 수 없음", None):
                parsed[field] = None
        # 제목 직접 파싱으로 보완
        title_meta = _parse_title_meta(title)
        for k, v in title_meta.items():
            if v and not parsed.get(k):
                parsed[k] = v
        return parsed
    except Exception as e:
        logger.warning("[poll_gpt] 파싱 실패: {}", e)
        return {}


async def _gpt_parse_candidates(title: str, text: str) -> tuple[list[dict], list[dict]]:
    """하위 호환용 래퍼."""
    result = await _gpt_parse_poll(title, text)
    return result.get("general", []), result.get("party", [])


async def collect_poll_news(since: datetime | None = None) -> list[dict]:
    """네이버뉴스에서 전당대회 당대표 여론조사 기사 수집.

    필터: 제목에 (당대표|전당대회|전대) AND (지지율|여론조사|적합도) 모두 포함.
    각 기사에서 일반 수치(candidatesGeneral)와 민주당 지지층 수치(candidatesParty)를 추출.
    """
    from ..collectors.naver import NaverCollector

    if since is None:
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=90)

    collector = NaverCollector()
    raw = await collector.collect(POLL_KEYWORDS, since=since, limit=600)

    # 제목 필터
    EXCLUDE_KW = ["대통령 지지율", "대통령 지지도", "국정지지율", "국정수행", "긍정평가", "부정평가", "이재명 지지율"]
    filtered = [
        it for it in raw
        if (any(k in it.title for k in TOPIC_KW) and any(k in it.title for k in POLL_KW))
        and not any(k in it.title for k in EXCLUDE_KW)
        and it.platform in {"naver_news", "naver_blog", "google_news", "nate_news", "daum_news"}
    ]

    # 중복 제거
    seen_urls: set[str] = set()
    unique = [it for it in filtered if not (it.url in seen_urls or seen_urls.add(it.url))]  # type: ignore
    logger.info("[poll_news] 수집 {}건 → 필터 {}건", len(raw), len(unique))

    # 기사 본문 패치해서 수치 추출 (네이버 블로그 제외 — JS 렌더링 필요)
    news_only = [it for it in unique if "blog.naver.com" not in it.url]
    async with httpx.AsyncClient() as client:
        for it in news_only:
            text, image = await _fetch_article(client, it.url)
            if text:
                general, party = extract_poll_sections(text)
                # 정규식 실패 시 snippet 수치 시도
                if not general:
                    snippet_cands = [{"name": m.group(1), "pct": float(m.group(2))}
                                     for m in FULL_RE.finditer(f"{it.title} {it.content}")]
                    general = snippet_cands
                # 여전히 없으면 GPT-4o-mini 파싱 (메타 포함)
                if not general:
                    gpt_result = await _gpt_parse_poll(it.title, text)
                    general = gpt_result.get("general", [])
                    party = gpt_result.get("party", party)
                    if general:
                        logger.info("[poll_gpt] GPT 파싱 성공: {} → {}건", it.title[:30], len(general))
                    it.__dict__["_gpt_meta"] = gpt_result
                it.__dict__["_general"] = general
                it.__dict__["_party"] = party
            if image:
                it.image_url = image

    results = []
    for it in unique:
        general = it.__dict__.get("_general") or [
            {"name": m.group(1), "pct": float(m.group(2))}
            for m in FULL_RE.finditer(f"{it.title} {it.content}")
        ]
        party = it.__dict__.get("_party", [])
        meta = it.__dict__.get("_gpt_meta", {})
        results.append({
            "title": it.title,
            "url": it.url,
            "platform": it.platform,
            "publishedAt": it.published_at,
            "content": it.content[:300],
            "candidatesGeneral": general,
            "candidatesParty": party,
            "hasData": len(general) >= 2,
            # 조사 메타 정보
            "pollster":     meta.get("pollster") or "",      # 조사기관
            "media":        meta.get("media") or "",         # 의뢰 매체
            "pollPeriod":   meta.get("pollPeriod") or "",    # 조사기간
            "sampleSize":   meta.get("sampleSize") or None,  # 표본 수
            "sampleGroup":  meta.get("sampleGroup") or "",   # 조사대상
            "marginOfError":meta.get("marginOfError") or "", # 오차범위
            "surveyMethod": meta.get("surveyMethod") or "",  # 조사방법
            "source": "news",
            "imageUrl": it.image_url or "",
        })

    # 수치 없는 것도 저장하되 hasData=False 태그로 구분 (대시보드에서 필터 가능)
    logger.info("[poll_news] 수치 있는 조사: {}건 / 전체: {}건", sum(1 for r in results if r["hasData"]), len(results))
    return results
