"""MacBook 로컬 SNS 1회 수집 실행기.

실행:
    python -m engine.local_collectors.sns_local_once
    python -m engine.local_collectors.sns_local_once --platforms x
    python -m engine.local_collectors.sns_local_once --platforms x facebook --dry-run

전제:
    1. serviceAccountKey.json 이 engine/ 또는 루트에 있어야 함
    2. .browser_profile_sns/ 에 X/Facebook 로그인 세션이 저장돼 있어야 함
       (없으면 python -m engine.local_collectors.sns_login 으로 먼저 로그인)
    3. DigitalOcean 파이프라인과 완전 독립 — 이 스크립트는 MacBook에서만 실행

저장 구조:
    - targets/{target_id}/items/{item_id}: 기존 items와 동일 스키마
    - sourceType="sns", platform="x"|"facebook", collector="local_sns"
    - 중복 URL은 저장하지 않음
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# 프로젝트 루트를 PYTHONPATH에 추가 (직접 실행 시 패키지 인식)
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.analysis.filters import RejectFilter
from engine.candidates import ALL_CANDIDATE_NAMES
from engine.config import get_settings
from engine.local_collectors.sns_collector import run_sns_collection
from engine.store.firestore import FirestoreStore, _item_doc

# 수집 대상 target_id — Firestore 실제 운영 경로 targets/minju-jeondaehoe
_DEFAULT_TARGET_ID = "minju-jeondaehoe"
_DEFAULT_KEYWORDS = ALL_CANDIDATE_NAMES + ["전당대회", "민주당 대표"]


async def _run(
    target_id: str,
    platforms: list[str],
    keywords: list[str],
    dry_run: bool,
    headless: bool,
) -> None:
    logger.info("=== SNS 로컬 수집 시작 (platforms={}, dry_run={}) ===", platforms, dry_run)

    # 1) 수집
    results = await run_sns_collection(
        target_id=target_id,
        keywords=keywords,
        platforms=platforms,
        headless=headless,
    )

    all_items = []
    for plat, items in results.items():
        for it in items:
            it.keyword = it.keyword or keywords[0]
        all_items.extend(items)

    if not all_items:
        logger.info("수집 결과 없음 — 종료")
        return

    logger.info("수집 원본 {}건", len(all_items))

    if dry_run:
        for it in all_items:
            entities = it.matched_entities or []
            logger.info(
                "[dry-run] {} | author={} | matched={} | {}",
                it.platform,
                it.author[:30] if it.author else "(없음)",
                entities,
                it.title[:50],
            )
        logger.info("[dry-run] 총 {}건 — Firestore 저장 안 함", len(all_items))
        return

    # 2) Firestore 연결 + 중복 체크
    store = FirestoreStore()
    db = store.connect()

    existing_ids = store.recent_item_ids(target_id, days=7)
    logger.info("기존 아이템 {}건 (최근 7일)", len(existing_ids))

    # 3) 필터 (노이즈·키워드 무관 제거) — SNS 날짜 없는 경우 많으므로 require_scraped_date=False
    flt = RejectFilter(
        keywords=keywords,
        entities=ALL_CANDIDATE_NAMES,
        require_scraped_date=False,
    )
    passed, rejected = flt.partition(all_items)
    logger.info("필터 통과 {}건 / 거부 {}건", len(passed), len(rejected))

    # 4) 중복 제거
    new_items = [it for it in passed if it.item_id not in existing_ids]
    logger.info("신규 저장 대상 {}건 (중복 {}건 제외)",
                len(new_items), len(passed) - len(new_items))

    if not new_items:
        logger.info("신규 아이템 없음 — 종료")
        return

    # 5) Firestore 저장
    # collector 식별자 추가 (raw 필드 활용)
    target_ref = db.collection("targets").document(target_id)
    items_ref = target_ref.collection("items")

    batch = db.batch()
    batch_count = 0
    saved = 0

    for it in new_items:
        doc = _item_doc(it)
        doc["collector"] = "local_sns"
        doc["needsReview"] = False
        doc["fetchStatus"] = "ok"

        doc_ref = items_ref.document(it.item_id)
        batch.set(doc_ref, doc)
        batch_count += 1
        saved += 1

        if batch_count >= 400:
            batch.commit()
            batch = db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()

    logger.info("=== SNS 로컬 수집 완료: {}건 저장 ===", saved)
    logger.info("대시보드 SNS 탭에서 확인: sourceType=sns, platform=x/facebook")


def main() -> None:
    ap = argparse.ArgumentParser(description="MacBook 로컬 SNS 1회 수집")
    ap.add_argument("--target", default=_DEFAULT_TARGET_ID, help="Firestore target_id")
    ap.add_argument(
        "--platforms", nargs="+", default=["x", "facebook"],
        choices=["x", "facebook", "instagram", "threads"],
        help="수집할 플랫폼 (기본: x facebook)",
    )
    ap.add_argument(
        "--keywords", nargs="+", default=None,
        help="검색 키워드 (기본: 후보명+전당대회)",
    )
    ap.add_argument("--dry-run", action="store_true", help="저장 없이 수집 결과만 출력")
    ap.add_argument("--headless", action="store_true", help="헤드리스 모드 (기본: GUI 표시)")
    args = ap.parse_args()

    keywords = args.keywords or _DEFAULT_KEYWORDS

    asyncio.run(_run(
        target_id=args.target,
        platforms=args.platforms,
        keywords=keywords,
        dry_run=args.dry_run,
        headless=args.headless,
    ))


if __name__ == "__main__":
    main()
