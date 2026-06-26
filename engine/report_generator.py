"""전당대회 동향 브리핑 자동 생성기 — GPT-5.5 기반, 제진수 보좌관식 문체.

사용:
    python -m engine.report_generator --target minju-jeondaehoe --print
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from .config import get_settings
from .store import FirestoreStore

JEONDAE_DATE = datetime(2026, 8, 17, tzinfo=timezone.utc)
PROMPT_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "horizon_report_v2"

SAJASUNG = [
    (6, "구동존이(求同存異)·동주공제(同舟共濟)"),
    (7, "높은 곳에서 멀리 보라(登高望遠)"),
    (8, "한 번의 도약으로 천 리를 간다(一躍千里)"),
]


def _dday() -> int:
    return (JEONDAE_DATE - datetime.now(timezone.utc)).days


def _sajasung() -> str:
    m = datetime.now(timezone.utc).month
    for month, s in SAJASUNG:
        if month == m:
            return s
    return "구동존이(求同存異)·동주공제(同舟共濟)"


def _load_prompt(filename: str) -> str:
    path = PROMPT_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.warning("프롬프트 파일 없음: {}", path)
    return ""


def _fetch_data(store: FirestoreStore, target_id: str) -> dict:
    tref = store.connect().collection("targets").document(target_id)

    clusters = []
    try:
        for c in (
            tref.collection("clusters")
            .order_by("lastSeen", direction="DESCENDING")
            .limit(200)
            .stream()
        ):
            d = c.to_dict()
            clusters.append({
                "id": c.id,
                "title": d.get("title", ""),
                "summary": d.get("summary", ""),
                "grade": d.get("grade", "none"),
                "platforms": (d.get("stats") or {}).get("platforms", []),
                "posts": (d.get("stats") or {}).get("posts", d.get("itemCount", 0)),
                "likes": (d.get("stats") or {}).get("likes", 0),
                "comments": (d.get("stats") or {}).get("comments", 0),
                "keywords": d.get("keywords", []),
                "people": d.get("people", []),
                "publishedAt": str(d.get("publishedAt", "")),
                "source": d.get("source", ""),
            })
    except Exception as e:
        logger.warning("클러스터 조회 실패: {}", e)

    polls = []
    try:
        for p in (
            tref.collection("polls")
            .order_by("savedAt", direction="DESCENDING")
            .limit(5)
            .stream()
        ):
            d = p.to_dict()
            polls.append({
                "title": d.get("title", ""),
                "publishedAt": str(d.get("publishedAt", "")),
                "institution": d.get("institution", ""),
                "respondents": d.get("respondents", ""),
                "candidates": d.get("candidatesGeneral") or d.get("candidates") or [],
                "candidatesParty": d.get("candidatesParty") or [],
            })
    except Exception as e:
        logger.warning("여론조사 조회 실패: {}", e)

    alerts = []
    try:
        for a in (
            tref.collection("alerts")
            .order_by("createdAt", direction="DESCENDING")
            .limit(5)
            .stream()
        ):
            d = a.to_dict()
            alerts.append({
                "grade": d.get("grade", ""),
                "summary": d.get("summary", ""),
                "type": d.get("type", ""),
            })
    except Exception as e:
        logger.warning("알림 조회 실패: {}", e)

    return {"clusters": clusters, "polls": polls, "alerts": alerts}


def _build_data_prompt(data: dict, date_str: str, date_range: str, dday: int) -> str:
    top_clusters = [c for c in data["clusters"] if c["grade"] in ("red", "orange", "yellow")][:20]
    all_titles = [c["title"] for c in data["clusters"][:80]]

    return f"""오늘 날짜: {date_str}
대상 기간: {date_range}
전당대회까지: D-{dday}
사자성어: {_sajasung()}

=== 주요 이슈 클러스터 (red/orange/yellow 등급) ===
{json.dumps(top_clusters, ensure_ascii=False, indent=2)}

=== 전체 클러스터 제목 목록 ===
{json.dumps(all_titles, ensure_ascii=False)}

=== 최신 여론조사 ===
{json.dumps(data["polls"], ensure_ascii=False, indent=2)}

=== 위기 알림 ===
{json.dumps(data["alerts"], ensure_ascii=False, indent=2)}

---
위 데이터만 사용해 전당대회 동향 브리핑을 작성하라.
데이터에 없는 사실은 절대 작성하지 말 것.
"""


async def _call_gpt(client, system: str, messages: list) -> str:
    resp = await client.chat.completions.create(
        model="gpt-5.5",
        max_tokens=6000,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return resp.choices[0].message.content


async def generate_report(target_id: str = "minju-jeondaehoe") -> str:
    s = get_settings()
    store = FirestoreStore(s)
    store.connect()

    logger.info("[report_generator] 데이터 수집 중...")
    data = _fetch_data(store, target_id)

    today = datetime.now(timezone(timedelta(hours=9)))
    dday = _dday()
    date_str = (
        today.strftime("%Y. %-m. %-d.(%a)")
        .replace("Mon", "월").replace("Tue", "화").replace("Wed", "수")
        .replace("Thu", "목").replace("Fri", "금").replace("Sat", "토").replace("Sun", "일")
    )
    date_range = f"{(today - timedelta(days=1)).strftime('%-m/%-d')}~{today.strftime('%-m/%-d')}"

    openai_key = os.environ.get("OPENAI_API_KEY") or getattr(s, "openai_api_key", None)
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY 없음 — .env에 설정 필요")

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=openai_key)

    # 프롬프트 파일 로드
    system_prompt = _load_prompt("horizon_report_system_prompt.txt")
    style_rules = _load_prompt("horizon_report_style_rules.txt")
    style_sample = _load_prompt("horizon_report_style_sample.txt")
    telegram_prompt = _load_prompt("horizon_telegram_prompt.txt")

    data_prompt = _build_data_prompt(data, date_str, date_range, dday)

    # 브리핑 본문 생성
    logger.info("[report_generator] GPT-5.5 브리핑 생성 중... (클러스터 {}건)", len(data["clusters"]))
    messages = [
        {"role": "user", "content": style_rules},
        {"role": "user", "content": style_sample},
        {"role": "user", "content": data_prompt},
    ]
    body = await _call_gpt(client, system_prompt, messages)
    logger.info("[report_generator] 브리핑 본문 생성 완료 ({}자)", len(body))

    # 텔레그램 요약문 생성
    telegram_text = ""
    try:
        tg_messages = [
            {"role": "user", "content": telegram_prompt},
            {"role": "user", "content": f"아래 브리핑을 텔레그램용으로 요약하라:\n\n{body}"},
        ]
        resp2 = await client.chat.completions.create(
            model="gpt-5.5",
            max_tokens=800,
            messages=[{"role": "system", "content": system_prompt}] + tg_messages,
        )
        telegram_text = resp2.choices[0].message.content
        logger.info("[report_generator] 텔레그램 요약문 생성 완료")
    except Exception as e:
        logger.warning("[report_generator] 텔레그램 요약 실패: {}", e)
        telegram_text = body[:500] + "\n\n[전체 브리핑은 대시보드 확인]"

    # Firestore reports 저장
    report_doc = {
        "date": today.strftime("%Y-%m-%d"),
        "type": "morning",
        "createdAt": datetime.now(timezone.utc),
        "status": "draft",
        "sourceIssueCount": len(data["clusters"]),
        "title": f"HORIZON0817 전당대회 동향 브리핑 {date_str}",
        "summary": body[:200] if body else "",
        "reportText": body,
        "telegramText": telegram_text,
        "factCheckItems": [],
        "riskItems": [a["summary"] for a in data["alerts"]],
        "model": "gpt-5.5",
        "promptVersion": PROMPT_VERSION,
        "dday": dday,
    }

    try:
        db = store.connect()
        # 같은 날짜·타입 중복 방지
        existing = (
            db.collection("reports")
            .where("date", "==", report_doc["date"])
            .where("type", "==", "morning")
            .limit(1)
            .stream()
        )
        if any(True for _ in existing):
            logger.warning("[report_generator] 오늘 morning 브리핑 이미 존재 — 덮어쓰지 않음")
        else:
            db.collection("reports").add(report_doc)
            logger.info("[report_generator] Firestore reports 저장 완료")
    except Exception as e:
        logger.warning("[report_generator] Firestore 저장 실패: {}", e)

    # 텔레그램 발송
    try:
        from .telegram_bot import send_message as tg_send
        await asyncio.get_event_loop().run_in_executor(None, tg_send, telegram_text)
        logger.info("[report_generator] 텔레그램 발송 완료")
    except Exception as e:
        logger.warning("[report_generator] 텔레그램 발송 실패: {}", e)

    return body


def _cli():
    parser = argparse.ArgumentParser(description="전당대회 동향 브리핑 생성")
    parser.add_argument("--target", default="minju-jeondaehoe")
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()
    body = asyncio.run(generate_report(args.target))
    if args.print or True:
        print("\n" + "=" * 60)
        print(body)


if __name__ == "__main__":
    _cli()
