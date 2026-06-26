"""전당대회 동향 브리핑 자동 생성기.

사용:
    python -m engine.report_generator --target minju-jeondaehoe
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

from loguru import logger

from .config import get_settings
from .store import FirestoreStore

CANDIDATES = ["김민석", "정청래", "송영길", "김용민"]
JEONDAE_DATE = datetime(2026, 8, 17, tzinfo=timezone.utc)

SAJASUNG = [
    ("6월", "지도자는 때를 아는 자(知時者)"),
    ("7월", "높은 곳에서 멀리 보라(登高望遠)"),
    ("8월", "한 번의 도약으로 천 리를 간다(一躍千里)"),
]


def _dday() -> int:
    return (JEONDAE_DATE - datetime.now(timezone.utc)).days


def _sajasung() -> str:
    m = datetime.now(timezone.utc).month
    for prefix, s in SAJASUNG:
        if prefix[0] == str(m):
            return s
    return "지도자는 때를 아는 자(知時者)"


def _fetch_data(store: FirestoreStore, target_id: str) -> dict:
    tref = store.connect().collection("targets").document(target_id)

    # 클러스터 (최근 48시간, 최대 300건)
    clusters = []
    try:
        for c in (
            tref.collection("clusters")
            .order_by("lastSeen", direction="DESCENDING")
            .limit(300)
            .stream()
        ):
            d = c.to_dict()
            clusters.append(
                {
                    "id": c.id,
                    "title": d.get("title", ""),
                    "summary": d.get("summary", ""),
                    "grade": d.get("grade", "none"),
                    "platforms": (d.get("stats") or {}).get("platforms", []),
                    "posts": (d.get("stats") or {}).get("posts", d.get("itemCount", 0)),
                    "likes": (d.get("stats") or {}).get("likes", 0),
                    "comments": (d.get("stats") or {}).get("comments", 0),
                }
            )
    except Exception as e:
        logger.warning("클러스터 조회 실패: {}", e)

    # 최신 여론조사 (최대 10건)
    polls = []
    try:
        for p in (
            tref.collection("polls")
            .order_by("savedAt", direction="DESCENDING")
            .limit(10)
            .stream()
        ):
            d = p.to_dict()
            cands = d.get("candidatesGeneral") or d.get("candidates") or []
            party = d.get("candidatesParty") or []
            polls.append(
                {
                    "title": d.get("title", ""),
                    "publishedAt": str(d.get("publishedAt", "")),
                    "candidates": cands,
                    "candidatesParty": party,
                }
            )
    except Exception as e:
        logger.warning("여론조사 조회 실패: {}", e)

    # 최신 알림
    alerts = []
    try:
        for a in (
            tref.collection("alerts")
            .order_by("createdAt", direction="DESCENDING")
            .limit(5)
            .stream()
        ):
            d = a.to_dict()
            alerts.append(
                {
                    "grade": d.get("grade", ""),
                    "summary": d.get("summary", ""),
                    "type": d.get("type", ""),
                }
            )
    except Exception as e:
        logger.warning("알림 조회 실패: {}", e)

    return {"clusters": clusters, "polls": polls, "alerts": alerts}


_SYSTEM = """당신은 대한민국 최고 수준의 정치 정보 분석관입니다.
민주당 전당대회(2026년 8월 17일) 동향 브리핑을 국회의원실 보좌관 수준으로 작성합니다.
이 보고서는 국회의원에게 직접 보고되며 단 하나의 실수도 허용되지 않습니다.

대원칙: 이 프로젝트의 핵심 목표는 김민석 당대표 만들기입니다.
모든 분석과 전략적 시사점은 이 목표에 기여하는 방향으로 작성하되,
반드시 제공된 실제 데이터에 근거하여 작성하십시오. 데이터에 없는 내용은 절대 작성하지 마십시오.

작성 원칙:
- 숫자·날짜·인명·기관명은 반드시 정확하게 기재 (불확실하면 "관측" "전언" 등으로 명시)
- 동향(사실) + 전략적 의미(해석) + 행동 지침(권고)을 반드시 함께 제시
- 전략적 시사점은 ▸ **[키워드]** 형식으로, 상황 → 의미 → 권고 행동 순으로 작성
- 체크포인트(관전포인트)는 굵은 빨간색 대신 "체크포인트" 태그 후 핵심만
- 향후 일정은 D-day 역산 표로 정확히 기재
"""


async def generate_report(target_id: str = "minju-jeondaehoe") -> str:
    s = get_settings()
    store = FirestoreStore(s)
    store.connect()

    logger.info("데이터 수집 중...")
    data = _fetch_data(store, target_id)

    today = datetime.now(timezone(timedelta(hours=9)))  # KST
    dday = _dday()
    date_str = today.strftime("%Y. %-m. %-d.(%a)").replace(
        "Mon", "월").replace("Tue", "화").replace("Wed", "수").replace(
        "Thu", "목").replace("Fri", "금").replace("Sat", "토").replace("Sun", "일")
    date_range = f"{(today - timedelta(days=1)).strftime('%-m/%-d')}~{today.strftime('%-m/%-d')}"

    logger.info("Claude 분석 중... (클러스터 {}건, 여론조사 {}건)", len(data["clusters"]), len(data["polls"]))

    from openai import AsyncOpenAI
    openai_key = os.environ.get("OPENAI_API_KEY") or getattr(s, "openai_api_key", None)
    if openai_key:
        _use_gpt = True
        client = AsyncOpenAI(api_key=openai_key)
    elif s.anthropic_api_key:
        _use_gpt = False
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=s.anthropic_api_key)
    else:
        raise RuntimeError("OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 없음")

    prompt = f"""다음 데이터를 바탕으로 전당대회 동향 브리핑을 작성하십시오.
반드시 아래 제공된 실제 데이터에 있는 내용만 분석하십시오. 데이터에 없는 사실은 절대 작성하지 마십시오.

오늘 날짜: {date_str}
대상 기간: {date_range}
전당대회까지: D-{dday}
사자성어: {_sajasung()}

=== 주요 클러스터 (이슈 — 등급별) ===
{json.dumps([c for c in data['clusters'] if c['grade'] in ('red','orange','yellow')][:30], ensure_ascii=False, indent=2)}

=== 전체 클러스터 제목 목록 (최근 100건) ===
{json.dumps([c['title'] for c in data['clusters'][:100]], ensure_ascii=False)}

=== 최신 여론조사 ===
{json.dumps(data['polls'][:5], ensure_ascii=False, indent=2)}

=== 위기 알림 ===
{json.dumps(data['alerts'], ensure_ascii=False, indent=2)}

---

아래 형식으로 정확히 작성하십시오. 각 섹션 구분자(===섹션명===)는 반드시 유지하십시오.

===HEADER===
# 전당대회 동향 브리핑
**{date_str} | 대상기간 {date_range} | 8·17 전당대회 D-{dday} | {_sajasung()}**

===SECTION1===
## 1. 핵심 이슈

데이터 기반 핵심 이슈 3개를 아래 구조로 작성:
▶ **[이슈 제목]**
- 현황: (사실관계 — 언제·누가·무엇을, 수치 포함)
- 의미: (이슈가 전대 구도에 미치는 영향)
- 체크포인트: ⚑ (향후 관전 포인트 1줄)

===SECTION2===
## 2. 후보별 동향

데이터에 등장하는 후보(김민석·정청래·송영길·김용민)별로:
**▸ [후보명] | [핵심 키워드 2~3개]**
- 동향: (클러스터 데이터 기반 실제 움직임)
- 체크포인트: ⚑ (다음 48시간 내 주목할 변수)

※ 데이터에 해당 후보 언급이 없으면 해당 후보는 생략

===SECTION3===
## 3. 주요 쟁점 동향

클러스터에서 반복 등장하는 쟁점 2~3개:
**[쟁점명]**
- 현황: (사실관계)
- 문제점/리스크: (김민석 캠프 관점)
- 대응 방향: (실질적 권고 — 구체적으로)

===SECTION4===
## 4. SNS·온라인 여론 동향

▸ **언급량**: (플랫폼별 특이 동향)
▸ **프레임 경쟁**: (어떤 프레임이 확산 중인지, 누가 유리한지)
▸ **주목 콘텐츠**: (조회수·공유수 높은 항목)
▸ **체크포인트**: ⚑ (온라인 리스크 또는 기회 요인)

===SECTION5===
## 5. 전략적 시사점

**[핵심]** 김민석 캠프 관점에서 오늘의 데이터가 말하는 전략적 행동 지침 — 5개 필수.
형식: ▸ **[키워드]**  [상황 1문장] — [전략적 의미 1문장] — **[권고 행동 1문장]**

▸ **구도 변수**  ...
▸ **호남 표심**  ...
▸ **미디어 대응**  ...
▸ **일정 관리**  ...
▸ **리스크 관리**  ...

===SECTION6===
## 6. 현안별 전략 분석

오늘 가장 중요한 red/orange 클러스터 2~3개에 대해 아래 구조로 심층 분석:

**[현안명]**

| 핵심 동향 | 전략적 의미 |
|----------|------------|
(사실 | 김민석 캠프 관점 의미 — 3~4행)

- **전략1. [전략명]** — 과제: ... / 권고 행동: ... / 타이밍: ...
- **전략2. [전략명]** — 과제: ... / 권고 행동: ... / 타이밍: ...

(2~3개 현안 반복)

===SECTION7===
## 7. 향후 일정

| 날짜 | D-day | 주요 일정 | 비고 |
|------|-------|----------|------|
(향후 7일 주요 전대 일정 5~7건 — 공식 확정 일정만, 불확실하면 "예정" 표기)

---
*출처: HOrizon0817 여론모니터링 시스템 (자동수집 {date_str})*
"""

    if _use_gpt:
        resp = await client.chat.completions.create(
            model="gpt-5.5",
            max_tokens=8000,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        body = resp.choices[0].message.content
        logger.info("[report_generator] GPT-4o로 브리핑 생성")
    else:
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        body = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        logger.info("[report_generator] Claude로 브리핑 생성")

    # Firestore에 저장
    report_doc = {
        "type": "daily",
        "generatedAt": datetime.now(timezone.utc),
        "bodyMarkdown": body,
        "dday": dday,
        "totals": {
            "mentions": len(data["clusters"]),
            "uniqueIssues": len([c for c in data["clusters"] if c["grade"] != "none"]),
            "alerts": len(data["alerts"]),
        },
    }
    try:
        store.connect().collection("targets").document(target_id).collection("reports").add(report_doc)
        logger.info("보고서 Firestore 저장 완료")
    except Exception as e:
        logger.warning("Firestore 저장 실패: {} — 콘솔에만 출력", e)

    # 텔레그램 PDF 전송
    try:
        from .telegram_bot import push_report_pdf
        await push_report_pdf(target_id)
    except Exception as e:
        logger.warning("텔레그램 전송 실패: {}", e)

    return body


def _cli():
    parser = argparse.ArgumentParser(description="전당대회 동향 브리핑 생성")
    parser.add_argument("--target", default="minju-jeondaehoe")
    parser.add_argument("--print", action="store_true", help="콘솔 출력")
    args = parser.parse_args()
    body = asyncio.run(generate_report(args.target))
    if args.print or True:
        print("\n" + "=" * 60)
        print(body)


if __name__ == "__main__":
    _cli()
