"""현안별 전략 메모 생성기 (온디맨드).

사용:
    python -m engine.strategy_analyzer --topic "정청래 공세" --target minju-jeondaehoe
    python -m engine.strategy_analyzer --cluster-ids "id1,id2" --topic "선거인단 구성"

대시보드에서 관리자가 '전략 분석 요청' 버튼 클릭 시 Firestore strategyRequests 에
요청 문서가 생성되며, 이 스크립트를 cron으로 돌려 처리한다.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone

from loguru import logger

from .config import get_settings
from .store import FirestoreStore

JEONDAE_DATE = datetime(2026, 8, 17, tzinfo=timezone.utc)


def _dday() -> int:
    return (JEONDAE_DATE - datetime.now(timezone.utc)).days


def _fetch_cluster_data(store: FirestoreStore, target_id: str, cluster_ids: list[str]) -> list[dict]:
    tref = store.connect().collection("targets").document(target_id)
    clusters = []
    if cluster_ids:
        for cid in cluster_ids:
            try:
                doc = tref.collection("clusters").document(cid).get()
                if doc.exists:
                    d = doc.to_dict()
                    clusters.append({
                        "id": doc.id,
                        "title": d.get("title", ""),
                        "summary": d.get("summary", ""),
                        "grade": d.get("grade", "none"),
                        "posts": (d.get("stats") or {}).get("posts", d.get("itemCount", 0)),
                        "likes": (d.get("stats") or {}).get("likes", 0),
                        "comments": (d.get("stats") or {}).get("comments", 0),
                        "platforms": (d.get("stats") or {}).get("platforms", []),
                        "lastSeen": str(d.get("lastSeen", "")),
                    })
            except Exception as e:
                logger.warning("클러스터 {} 조회 실패: {}", cid, e)
    else:
        # cluster_ids 없으면 최근 고등급 클러스터 자동 선택
        try:
            for c in (
                tref.collection("clusters")
                .order_by("lastSeen", direction="DESCENDING")
                .limit(50)
                .stream()
            ):
                d = c.to_dict()
                if d.get("grade") in ("red", "orange"):
                    clusters.append({
                        "id": c.id,
                        "title": d.get("title", ""),
                        "summary": d.get("summary", ""),
                        "grade": d.get("grade", "none"),
                        "posts": (d.get("stats") or {}).get("posts", d.get("itemCount", 0)),
                        "likes": (d.get("stats") or {}).get("likes", 0),
                        "comments": (d.get("stats") or {}).get("comments", 0),
                        "platforms": (d.get("stats") or {}).get("platforms", []),
                        "lastSeen": str(d.get("lastSeen", "")),
                    })
                if len(clusters) >= 10:
                    break
        except Exception as e:
            logger.warning("클러스터 조회 실패: {}", e)
    return clusters


def _fetch_recent_polls(store: FirestoreStore, target_id: str) -> list[dict]:
    tref = store.connect().collection("targets").document(target_id)
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
                "candidates": d.get("candidatesGeneral") or d.get("candidates") or [],
                "candidatesParty": d.get("candidatesParty") or [],
            })
    except Exception as e:
        logger.warning("여론조사 조회 실패: {}", e)
    return polls


_SYSTEM = """당신은 대한민국 최고 수준의 정치 전략 분석관입니다.
민주당 전당대회(2026년 8월 17일) 현안별 전략 메모를 작성합니다.
이 메모는 김민석 후보 캠프와 국회의원실에 즉시 보고되는 문서입니다.

대원칙: 핵심 목표는 김민석 당대표 만들기입니다.
모든 분석은 이 목표에 기여하는 방향으로 작성하되, 반드시 제공된 실제 데이터에 근거하십시오.

작성 원칙:
- 동향(사실) + 전략적 의미(해석) + 권고 행동(지침)을 반드시 3단으로 제시
- 핵심동향|전략적의미 2열 구조로 핵심 내용 압축
- 전략은 번호(전략1, 전략2...)로 구분, 각각 과제·권고행동·타이밍 포함
- 불확실한 내용은 "관측" "전언" 명시, 추측 금지
- A4 1~2장 분량으로 간결하게
"""


async def generate_strategy_memo(
    topic: str,
    cluster_ids: list[str] | None = None,
    target_id: str = "minju-jeondaehoe",
    request_id: str | None = None,
) -> str:
    s = get_settings()
    store = FirestoreStore(s)
    store.connect()

    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 없음")

    clusters = _fetch_cluster_data(store, target_id, cluster_ids or [])
    polls = _fetch_recent_polls(store, target_id)

    today = datetime.now(timezone(timedelta(hours=9)))
    date_str = today.strftime("%Y. %-m. %-d.")
    dday = _dday()

    logger.info("전략 메모 생성 중... 주제: '{}', 클러스터 {}건", topic, len(clusters))

    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=s.anthropic_api_key)

    prompt = f"""다음 데이터를 바탕으로 현안 전략 메모를 작성하십시오.
반드시 제공된 실제 데이터에 있는 내용만 분석하십시오.

작성일: {date_str} (8·17 전당대회 D-{dday})
분석 주제: {topic}

=== 관련 클러스터 (이슈 데이터) ===
{json.dumps(clusters, ensure_ascii=False, indent=2)}

=== 최신 여론조사 ===
{json.dumps(polls, ensure_ascii=False, indent=2)}

---

아래 형식으로 작성하십시오.

===MEMO_HEADER===
# 현안 전략 메모: {topic}
**{date_str} | 8·17 전당대회 D-{dday}**

===MEMO_OVERVIEW===
## 총괄 판단

(3줄 이내로: 현 상황 핵심, 김민석에게 미치는 영향, 즉각 대응 필요 여부)

===MEMO_TABLE===
## 핵심 동향 | 전략적 의미

| 핵심 동향 | 전략적 의미 |
|----------|------------|
(데이터 기반 3~5개 행 — 왼쪽: 사실, 오른쪽: 김민석 캠프 관점의 의미)

===MEMO_ISSUES===
## 쟁점별 팩트체크 & 대응

(쟁점 2~3개, 각각:)
**[쟁점명]**
- 사실관계: (확인된 사실만)
- 리스크/기회: (캠프 관점)
- 대응 방향: (구체적 행동)

===MEMO_STRATEGY===
## 전략 시사점

**전략1. [전략 이름]**
- 과제: ...
- 권고 행동: ...
- 타이밍: ...

**전략2. [전략 이름]**
- 과제: ...
- 권고 행동: ...
- 타이밍: ...

**전략3. [전략 이름]**
- 과제: ...
- 권고 행동: ...
- 타이밍: ...

===MEMO_FOOTER===
---
*HOrizon0817 전략분석 시스템 | {date_str} 자동생성*
"""

    resp = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    body = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    # Firestore에 저장
    report_doc = {
        "type": "strategy",
        "topic": topic,
        "clusterIds": cluster_ids or [],
        "generatedAt": datetime.now(timezone.utc),
        "bodyMarkdown": body,
        "dday": dday,
        "requestId": request_id,
    }
    try:
        ref = store.connect().collection("targets").document(target_id).collection("reports").add(report_doc)
        logger.info("전략 메모 저장 완료: {}", ref[1].id)
    except Exception as e:
        logger.warning("Firestore 저장 실패: {}", e)

    return body


async def process_pending_requests(target_id: str = "minju-jeondaehoe") -> int:
    """Firestore strategyRequests 컬렉션에서 pending 요청을 처리."""
    s = get_settings()
    store = FirestoreStore(s)
    db = store.connect()

    tref = db.collection("targets").document(target_id)
    pending = []
    try:
        for doc in tref.collection("strategyRequests").where("status", "==", "pending").stream():
            pending.append((doc.id, doc.to_dict()))
    except Exception as e:
        logger.warning("strategyRequests 조회 실패: {}", e)
        return 0

    for req_id, req in pending:
        topic = req.get("topic", "현안 분석")
        cluster_ids = req.get("clusterIds", [])
        logger.info("전략 요청 처리 중: {} — {}", req_id, topic)
        try:
            # 처리 중으로 상태 변경
            tref.collection("strategyRequests").document(req_id).update({"status": "processing"})
            await generate_strategy_memo(topic, cluster_ids, target_id, req_id)
            tref.collection("strategyRequests").document(req_id).update({
                "status": "done",
                "completedAt": datetime.now(timezone.utc),
            })
            logger.info("완료: {}", req_id)
        except Exception as e:
            logger.error("처리 실패 {}: {}", req_id, e)
            tref.collection("strategyRequests").document(req_id).update({"status": "error", "error": str(e)})

    return len(pending)


async def auto_generate(target_id: str = "minju-jeondaehoe") -> int:
    """red/orange 클러스터 중 최근 24시간 내 전략 메모가 없는 것을 자동 생성."""
    s = get_settings()
    store = FirestoreStore(s)
    db = store.connect()
    tref = db.collection("targets").document(target_id)

    # 최근 24시간 내 생성된 전략 메모의 clusterIds 수집
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    covered: set[str] = set()
    try:
        for doc in (
            tref.collection("reports")
            .where("type", "==", "strategy")
            .where("generatedAt", ">=", cutoff)
            .stream()
        ):
            for cid in (doc.to_dict().get("clusterIds") or []):
                covered.add(cid)
    except Exception as e:
        logger.warning("기존 전략 메모 조회 실패: {}", e)

    # red/orange 클러스터 중 미커버된 것
    candidates = []
    try:
        for c in (
            tref.collection("clusters")
            .order_by("lastSeen", direction="DESCENDING")
            .limit(100)
            .stream()
        ):
            d = c.to_dict()
            if d.get("grade") in ("red", "orange") and c.id not in covered:
                candidates.append((c.id, d.get("title", "현안 분석")))
            if len(candidates) >= 3:  # 한 번에 최대 3개
                break
    except Exception as e:
        logger.warning("클러스터 조회 실패: {}", e)
        return 0

    if not candidates:
        logger.info("자동 생성 대상 없음 (모두 커버됨)")
        return 0

    count = 0
    for cid, title in candidates:
        logger.info("자동 전략 메모 생성: {}", title)
        try:
            await generate_strategy_memo(title, [cid], target_id)
            count += 1
        except Exception as e:
            logger.error("자동 생성 실패 {}: {}", cid, e)

    return count


def _cli():
    parser = argparse.ArgumentParser(description="현안 전략 메모 생성")
    parser.add_argument("--topic", default="전당대회 현안 분석")
    parser.add_argument("--cluster-ids", default="", help="쉼표 구분 클러스터 ID")
    parser.add_argument("--target", default="minju-jeondaehoe")
    parser.add_argument("--process-requests", action="store_true", help="pending 요청 일괄 처리")
    parser.add_argument("--auto", action="store_true", help="red/orange 클러스터 자동 전략 메모 생성")
    args = parser.parse_args()

    if args.process_requests:
        count = asyncio.run(process_pending_requests(args.target))
        if args.auto:
            count += asyncio.run(auto_generate(args.target))
        print(f"처리 완료: {count}건")
        return

    if args.auto:
        count = asyncio.run(auto_generate(args.target))
        print(f"자동 생성: {count}건")
        return

    ids = [x.strip() for x in args.cluster_ids.split(",") if x.strip()]
    body = asyncio.run(generate_strategy_memo(args.topic, ids, args.target))
    print("\n" + "=" * 60)
    print(body)


if __name__ == "__main__":
    _cli()
