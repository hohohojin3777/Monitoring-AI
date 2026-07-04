"""주간 보고서 생성기 — 매주 금요일 오후 6시 자동 발행.

사용:
    python -m engine.weekly_report --target minju-jeondaehoe
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
from .candidates import MAIN_CANDIDATE_NAMES

CANDIDATES = MAIN_CANDIDATE_NAMES
JEONDAE_DATE = datetime(2026, 8, 17, tzinfo=timezone.utc)


def _dday() -> int:
    return (JEONDAE_DATE - datetime.now(timezone.utc)).days


def _fetch_weekly_data(store: FirestoreStore, target_id: str) -> dict:
    tref = store.connect().collection("targets").document(target_id)
    since = datetime.now(timezone.utc) - timedelta(days=7)

    clusters, polls, alerts = [], [], []
    try:
        for c in tref.collection("clusters").order_by("lastSeen", direction="DESCENDING").limit(500).stream():
            d = c.to_dict()
            last = d.get("lastSeen")
            if last and last.replace(tzinfo=timezone.utc) >= since:
                clusters.append({
                    "id": c.id,
                    "title": d.get("title", ""),
                    "summary": d.get("summary", ""),
                    "grade": d.get("grade", "none"),
                    "platforms": (d.get("stats") or {}).get("platforms", []),
                    "posts": (d.get("stats") or {}).get("posts", d.get("itemCount", 0)),
                    "likes": (d.get("stats") or {}).get("likes", 0),
                })
    except Exception as e:
        logger.warning("클러스터 조회 실패: {}", e)

    try:
        for p in tref.collection("polls").order_by("savedAt", direction="DESCENDING").limit(10).stream():
            d = p.to_dict()
            polls.append({
                "title": d.get("title", ""),
                "publishedAt": str(d.get("publishedAt", "")),
                "candidates": d.get("candidatesGeneral") or d.get("candidates") or [],
            })
    except Exception as e:
        logger.warning("여론조사 조회 실패: {}", e)

    try:
        for a in tref.collection("alerts").order_by("createdAt", direction="DESCENDING").limit(20).stream():
            d = a.to_dict()
            created = d.get("createdAt")
            if created and created.replace(tzinfo=timezone.utc) >= since:
                alerts.append({"grade": d.get("grade", ""), "summary": d.get("summary", ""), "type": d.get("type", "")})
    except Exception as e:
        logger.warning("알림 조회 실패: {}", e)

    return {"clusters": clusters, "polls": polls, "alerts": alerts}


_SYSTEM = """당신은 대한민국 최고 수준의 정치 정보 분석관입니다.
민주당 전당대회(2026년 8월 17일) 주간 종합 보고서를 작성합니다.
이 보고서는 한 주 전체의 흐름을 종합하여, 다음 주 전략 방향을 제시합니다.

대원칙: 핵심 목표는 김민석 당대표 만들기입니다.
모든 분석은 제공된 실제 데이터에 근거하여 작성하십시오.
"""


async def generate_weekly_report(target_id: str = "minju-jeondaehoe") -> str:
    s = get_settings()
    store = FirestoreStore(s)
    store.connect()

    data = _fetch_weekly_data(store, target_id)
    today = datetime.now(timezone(timedelta(hours=9)))
    dday = _dday()
    week_start = (today - timedelta(days=6)).strftime("%-m/%-d")
    week_end = today.strftime("%-m/%-d")
    date_str = today.strftime("%Y. %-m. %-d.(%a)").replace(
        "Mon","월").replace("Tue","화").replace("Wed","수").replace(
        "Thu","목").replace("Fri","금").replace("Sat","토").replace("Sun","일")

    openai_key = os.environ.get("OPENAI_API_KEY") or getattr(s, "openai_api_key", None)
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY 없음")

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=openai_key)

    prompt = f"""다음 한 주간 데이터를 바탕으로 주간 종합 보고서를 작성하십시오.

작성일: {date_str}
대상 기간: {week_start} ~ {week_end} (7일)
전당대회까지: D-{dday}

=== 주간 주요 클러스터 (이슈) ===
{json.dumps([c for c in data['clusters'] if c['grade'] in ('red','orange','yellow')][:40], ensure_ascii=False, indent=2)}

=== 전체 클러스터 제목 (최근 200건) ===
{json.dumps([c['title'] for c in data['clusters'][:200]], ensure_ascii=False)}

=== 최신 여론조사 ===
{json.dumps(data['polls'][:5], ensure_ascii=False, indent=2)}

=== 주간 위기 알림 ===
{json.dumps(data['alerts'], ensure_ascii=False, indent=2)}

---

아래 형식으로 작성하십시오.

===HEADER===
# 주간 종합 보고서
**{date_str} | 대상기간 {week_start}~{week_end} | 8·17 전당대회 D-{dday}**

===SECTION1===
## 1. 이번 주 핵심 요약 (3줄)
(이번 한 주의 가장 중요한 흐름 3가지를 짧고 명확하게)

===SECTION2===
## 2. 주간 여론 흐름

▸ **후보별 지지율 변화**: (여론조사 데이터 기반 흐름 분석)
▸ **당심 변화**: (권리당원 동향)
▸ **온라인 여론**: (플랫폼별 반응 흐름)

===SECTION3===
## 3. 주간 주요 이슈 총평

(이번 주 red/orange 이슈 중 전대에 영향을 미친 것 3~4개를 현황·영향·평가 순으로)

===SECTION4===
## 4. 후보별 주간 성적표

| 후보 | 주요 행보 | 득점 요인 | 실점 요인 | 종합 평가 |
|-----|---------|---------|---------|---------|
(김민석·정청래·송영길·고민정 — 데이터 있는 후보만)

===SECTION5===
## 5. 다음 주 전략 과제

▸ **최우선 과제**: (김민석 캠프가 다음 주 반드시 해야 할 일 1순위)
▸ **경계 리스크**: (다음 주 터질 수 있는 위험 요소)
▸ **기회 포인트**: (선점 가능한 의제 또는 타이밍)
▸ **일정 관리**: (D-{dday} 기준 향후 2주 내 중요 일정)

===SECTION6===
## 6. 여론조사 데이터 정리

| 조사명 | 날짜 | 김민석 | 정청래 | 송영길 | 고민정 | 비고 |
|-------|-----|-------|-------|-------|-----|
(데이터 기반 정리)

---
*출처: HOrizon0817 주간 종합 보고서 (자동수집 {date_str})*
"""

    resp = await client.chat.completions.create(
        model="gpt-5.5",
        max_completion_tokens=16000,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    body = resp.choices[0].message.content or ""

    report_doc = {
        "type": "weekly",
        "generatedAt": datetime.now(timezone.utc),
        "bodyMarkdown": body,
        "dday": dday,
        "weekRange": f"{week_start}~{week_end}",
        "totals": {
            "mentions": len(data["clusters"]),
            "uniqueIssues": len([c for c in data["clusters"] if c["grade"] != "none"]),
            "alerts": len(data["alerts"]),
        },
    }
    try:
        store.connect().collection("targets").document(target_id).collection("reports").add(report_doc)
        logger.info("주간 보고서 Firestore 저장 완료")
    except Exception as e:
        logger.warning("저장 실패: {}", e)

    # 텔레그램 전송
    try:
        from .telegram_bot import markdown_to_pdf, push_report_pdf
        import io
        from telegram import Bot
        s2 = get_settings()
        if s2.telegram_bot_token and s2.telegram_chat_id:
            pdf_bytes = markdown_to_pdf(body, "주간 종합 보고서")
            bot = Bot(token=s2.telegram_bot_token)
            async with bot:
                await bot.send_document(
                    chat_id=s2.telegram_chat_id,
                    document=io.BytesIO(pdf_bytes),
                    filename=f"주간보고서_{today.strftime('%Y%m%d')}.pdf",
                    caption=f"📋 주간 종합 보고서 | D-{dday} | {week_start}~{week_end}\n🔗 https://horizon-dc3c6.web.app",
                )
    except Exception as e:
        logger.warning("텔레그램 전송 실패: {}", e)

    return body


def _cli():
    parser = argparse.ArgumentParser(description="주간 보고서 생성")
    parser.add_argument("--target", default="minju-jeondaehoe")
    args = parser.parse_args()
    body = asyncio.run(generate_weekly_report(args.target))
    print("\n" + "=" * 60)
    print(body)


if __name__ == "__main__":
    _cli()
