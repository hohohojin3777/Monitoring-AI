"""수치 없는 여론조사 기사에 GPT-4o-mini로 후보 지지율 백필.

실행:
    python -m engine.backfill_polls
"""
from __future__ import annotations

import asyncio
import os

import httpx
from loguru import logger

from .config import get_settings
from .store import FirestoreStore
from .collectors.poll_collector import _fetch_article, _gpt_parse_poll, extract_poll_sections, FULL_RE


async def backfill():
    s = get_settings()
    store = FirestoreStore(s)
    db = store.connect()
    tref = db.collection("targets").document("minju-jeondaehoe")

    polls = list(tref.collection("polls").stream())
    no_data = [p for p in polls if not p.to_dict().get("candidatesGeneral") and not p.to_dict().get("candidates")]
    logger.info("수치 없는 여론조사: {}건 백필 시작", len(no_data))

    updated = 0
    async with httpx.AsyncClient() as client:
        for doc in no_data:
            d = doc.to_dict()
            url = d.get("url") or d.get("detailUrl") or ""
            title = d.get("title") or d.get("name") or ""

            if not url:
                logger.warning("URL 없음: {}", title[:40])
                continue

            text, _ = await _fetch_article(client, url)

            general, party = [], []
            if text:
                general, party = extract_poll_sections(text)
                if not general:
                    general = [{"name": m.group(1), "pct": float(m.group(2))}
                                for m in FULL_RE.finditer(text)]

            # Firestore에 저장된 스니펫도 시도
            if not general:
                stored_content = d.get("content") or d.get("snippet") or ""
                snippet = f"{title} {stored_content}"
                general = [{"name": m.group(1), "pct": float(m.group(2))}
                            for m in FULL_RE.finditer(snippet)]

            # GPT 파싱 (본문 또는 스니펫 기반) — 메타 포함
            if not general:
                gpt_input = text or d.get("content") or d.get("snippet") or ""
                meta = await _gpt_parse_poll(title, gpt_input)
                general = meta.get("general", [])
                party = meta.get("party", party)
            else:
                meta = {}

            if general:
                update_data = {
                    "candidatesGeneral": general,
                    "candidatesParty": party,
                    "hasData": len(general) >= 2,
                }
                # 메타 정보가 있으면 함께 저장
                for field in ["pollster", "media", "pollPeriod", "sampleSize", "sampleGroup", "marginOfError", "surveyMethod"]:
                    val = meta.get(field)
                    if val:
                        update_data[field] = val
                tref.collection("polls").document(doc.id).update(update_data)
                logger.info("✓ 백필 완료: {} → {}건 수치 | 기관: {}", title[:35], len(general), meta.get("pollster","미상"))
                updated += 1
            else:
                logger.warning("✗ 수치 없는 기사: {}", title[:40])

    logger.info("백필 완료: {}건 / {}건 업데이트", updated, len(no_data))


if __name__ == "__main__":
    asyncio.run(backfill())
